import streamlit as st
import pandas as pd
import db_utils
import psycopg
import datetime
import random

@st.fragment
def show_payment_container():
    # 支付容器
    st.session_state.payment_shown = True
    pay_container = st.container(border=True)
    with pay_container:
        st.subheader("💳 确认支付")
        st.write(f"订单待支付金额: **￥{st.session_state.total_order_price:,.2f}**")
        pay_method = st.radio("选择支付方式", ["微信支付", "支付宝", "余额支付"])

        # 关键修改：点击按钮后更新 session_state 并重新运行
        if st.button("确认支付", type="primary", ):
            msg = st.toast("正在支付")
            # 执行支付逻辑
            log_success = add_order_status_log(
                order_id=st.session_state.orderid,
                from_state="UNPAID",
                to_state="PAID_NOT_SHIPPED",
                changer="User",
                remark="用户完成支付"
            )

            if log_success:
                msg.toast("支付成功并已记录日志！", icon="✅")

                st.session_state.payment_done = True
                st.rerun()  # 解决表单消失问题：通过 rerun 刷新到支付成功界面
            else:
                msg.toast("支付失败", icon="❌")

def change_list(item):
    st.session_state[item] = st.session_state[f"qty_input_{item}"]

def set_new_orderid(new_orderid):
    st.session_state.orderid = new_orderid

def add_order_status_log(order_id, from_state, to_state, changer, remark):
    """
    向 customerorder_statuslog 插入状态变更记录
    """
    sql = """
        INSERT INTO customerorder_statuslog 
        (logid, orderid, fromstate, tostate, changetime, changer, remark)
        VALUES (
            (SELECT COALESCE(MAX(logid), 0) + 1 FROM customerorder_statuslog), -- 确保 logid 不重复
            %s, %s, %s, CURRENT_TIMESTAMP, %s, %s
        )
    """
    conn = db_utils.init_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (order_id, from_state, to_state, changer, remark))
        conn.commit()
        return True
    except Exception as e:
        print(f"日志写入失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def generate_order_id():
    """生成格式如: ORD202310271430051234 的订单号"""
    now = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    rand_suffix = random.randint(100, 999)
    # 生成快递单号: SF + 12位随机数字
    tracking_no = f"SF{random.randint(10 ** 11, 10 ** 12 - 1)}"
    return f"ORD{now}{rand_suffix}", tracking_no



def submit_order_to_db(final_items, total_price, selected_phone, selected_address):
    order_id, tracking_no = generate_order_id()
    current_time = datetime.datetime.now()

    # 从 session_state 获取当前会员 ID
    # 假设结构为 st.session_state.current_user = {'memberid': 'M001', ...}
    member_id = st.session_state.get('current_user')
    conn = db_utils.init_db_connection()
    try:
        with conn.cursor() as cur:
            # --- 步骤 1: 插入 customerorder (主表) ---
            header_sql = """
                         INSERT INTO customerorder (orderid, memberid, orderstate, submitdate, \
                                                    operatorid, approverid, originalmoney, discountedmoney, \
                                                    approveddiscount, conditionfreightfree, isemergency, \
                                                    customerremark, updatetimestamp, dataversion) \
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) \
                         """
            cur.execute(header_sql, (
                order_id, member_id, 'UNPAID', current_time,
                None, None, total_price, 0,
                0, 5000, False,
                None, current_time, 1
            ))

            # --- 步骤 2: 插入 customerorder_detail (详情表) ---
            detail_sql = """
                         INSERT INTO customerorder_detail (orderid, productid, quantity, snapshotprice, \
                                                           linediscount) \
                         VALUES (%s, %s, %s, %s, %s) \
                         """
            detail_data = [
                (order_id, item['商品ID'], item['数量'], item['单价'], 0)
                for item in final_items
            ]
            cur.executemany(detail_sql, detail_data)

            # --- 步骤 3: 插入收货/物流表 ---
            # 根据 image_55a806.png 结构插入
            delivery_sql = """
                           INSERT INTO customerorder_shipment (orderid, receiver, mobilephone, memberaddressid, \
                                                               shipmenttype, trackingnumber, freight_fee) \
                           VALUES (%s, %s, %s, %s, %s, %s, %s) \
                           """
            cur.execute(delivery_sql, (
                order_id,
                "收件人-000000",
                selected_phone,
                selected_address,
                "SF_EXPRESS",
                tracking_no,
                80
            ))

            # 提交事务
            conn.commit()
            return order_id

    except Exception as e:
        st.error(f"数据库写入异常: {e}")
        return None

# 初始化 Session State，用于记录登录状态
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'selected_product' not in st.session_state:
    st.session_state.selected_product = set()
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'payment_done' not in st.session_state:
    st.session_state.payment_done = False
if 'orderid' not in st.session_state:
    st.session_state.orderid = None
if 'total_order_price' not in st.session_state:
    st.session_state.total_order_price = 0
if 'payment_shown' not in st.session_state:
    st.session_state.payment_shown = False


@st.cache_data(ttl=3600)
def get_users():
    # 建议连接逻辑也放在 try 块内，捕获连接失败的情况
    conn = db_utils.init_db_connection()
    try:
        query = "select memberid from memberinfo;"
        with conn.cursor() as cur:
            cur.execute(query)
            # 对于 SELECT 语句，cur.description 理论上不会是 None
            results = [row[0] for row in cur.fetchall()]

        return results
    except Exception as e:
        # 3. 发生错误时回滚，防止干扰后续连接
        if conn and not conn.closed:
            conn.rollback()
        raise Exception(f"查询执行失败：{str(e)}")


@st.cache_data(ttl=3600)
def get_user_phone(user_id):
    conn = db_utils.init_db_connection()
    query = """select phonenumber
               from memberphone
                where memberid = %s
                order by isprimary desc;"""
    params = (user_id,)
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            # 无返回结果的SQL（如INSERT/UPDATE），直接提交并返回空
            if cur.description is None:
                conn.commit()
                return []
            results = [row[0] for row in cur.fetchall()]
            return results
    except Exception as e:
        # 3. 发生错误时回滚，防止干扰后续连接
        if conn and not conn.closed:
            conn.rollback()
        raise Exception(f"查询执行失败：{str(e)}")


@st.cache_data(ttl=3600)
def get_user_address(user_id):
    conn = db_utils.init_db_connection()
    data_dict = {}
    query = """SELECT addressrecid, fulladdress
               FROM memberaddress, \
                    address_geocoding
               WHERE memberid = %s \
                 and memberaddress.addressgeocodeid = address_geocoding.addressid
                order by isdefault desc;"""
    params = (user_id,)
    try:
        # 执行查询：替换为你的表名和字段名（key_column是键字段，value_column是值字段）
        # 示例：查询用户表的id（键）和用户名（值）

        # 用with块管理游标（自动关闭游标）
        with conn.cursor() as cur:
            # 执行查询（若无需参数，可写cur.execute(query)）
            cur.execute(query, params)

            # 获取所有查询结果，整理成字典（显示值: 实际键）
            results = cur.fetchall()
            for key, value in results:
                data_dict[key] = value  # value是显示内容，key是系统需要的键
            return data_dict

    except Exception as e:
        if conn and not conn.closed:
            conn.rollback()
        raise Exception(f"查询执行失败：{str(e)}")


def login():
    """
    处理用户登录界面逻辑。
    """
    st.title("📦 内部商品订购系统")
    st.header("🔐 用户登录")

    with st.container(border=True):
        user_id_input = st.text_input("请输入用户 ID ", placeholder="例如: 1001")
        users = get_users()
        if st.button("查询 / 登录", type="primary"):
            if user_id_input in users:
                st.session_state.logged_in = True
                st.session_state.current_user = user_id_input
                st.session_state.current_user_id = user_id_input
                st.rerun()  # 刷新页面进入下单页
            else:
                st.error("❌ 未找到该用户 ID，请检查输入。")


def logout():
    """
    注销用户并重置状态。
    """
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.rerun()


@st.cache_data(ttl=3600)
def get_products():
    conn = db_utils.init_db_connection()
    query = """select *
               from productinfo
               where isactive = true"""
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            # 无返回结果的SQL（如INSERT/UPDATE），直接提交并返回空
            if cur.description is None:
                conn.commit()
                return []
            # 有返回结果的SQL，转换为字典列表
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            return results
    except Exception as e:
        # 即使开启了 autocommit，报错时显式 rollback 也是好习惯
        if conn and not conn.closed:
            conn.rollback()
        raise Exception(f"查询执行失败：{str(e)}") from e



def order_page():
    """
    处理订单填写和提交逻辑。
    """
    user = st.session_state.current_user

    # 顶部栏：显示用户信息和退出按钮
    col_info, col_logout = st.columns([8, 2])
    with col_info:
        st.success(f"👋 欢迎回来，**{user}** (ID: {st.session_state.current_user_id})")
    with col_logout:
        # 使用 key 避免与 form 内的按钮冲突
        if st.button("注销 / 退出", key="logout_btn"):
            logout()

    products = get_products()
    if products:
        total_products = len(products)
        for i in range(total_products // 5):
            row = st.columns(5)
            for col, product in zip(row, products[i * 5 : (i + 1) * 5]):
                tile = col.container(height=240)
                tile.title(":balloon:")
                tile.write(f"{product['productname']}\n\n价格：{product['standardprice']}元")
                if product['productname'] not in st.session_state:
                    st.session_state[product['productname']] = 0  # 仅在这里设置初始值
                num = tile.number_input("购买数量", min_value=0,step=1,key=product['productid'])
                if num != 0: st.session_state.selected_product.add(product['productid'])
        row = st.columns(5)
        for col, product in zip(row[:total_products % 5], products[-(total_products % 5):]):
            tile = col.container(height=240)
            tile.title(":balloon:")
            tile.write(f"{product['productname']}\n\n价格：{product['standardprice']}元")
            if product['productname'] not in st.session_state:
                st.session_state[product['productname']] = 0  # 仅在这里设置初始值
            num = tile.number_input("购买数量", min_value=0, step=1,key=product['productid'])
            if num != 0: st.session_state.selected_product.add(product['productid'])

    # 将列表转换为字典，格式为 {productid: {整行数据}}
    # 这样可以通过 productid 直接索引到 productname, standardprice 等
    products_map = {p['productid']: p for p in products}

    # --- 4.2 商品选择 (多选 + 独立数量定义) ---
    st.subheader("2. 已选商品及数量")

    # --- 1. 定义表头 ---
    # 这里的比例 [3, 2, 1, 1] 可以根据内容长短调整宽度
    header_cols = st.columns([3, 2, 1, 1])
    header_cols[0].markdown("**产品名称**")
    header_cols[1].markdown("**标准价格**")
    header_cols[2].markdown("**单位**")
    header_cols[3].markdown("**数量**")

    st.divider()  # 表头下方的分割线

    # --- 2. 循环显示数据行 ---
    for item in st.session_state.selected_product:
        product_detail = products_map.get(item)
        if not product_detail:
            continue

        # 提取数据
        name = product_detail['productname']
        price = product_detail['standardprice']
        unit = product_detail['unit']
        quantity = st.session_state.get(item, 0)
        if int(quantity) == 0:
            continue

        # 为每一行创建一组相同比例的列
        row_cols = st.columns([3, 2, 1, 1])

        # 填充数据
        row_cols[0].markdown(name)
        row_cols[1].markdown(f"￥{price}")
        row_cols[2].markdown(unit)
        widget_key = f"qty_input_{item}"

        new_quantity = row_cols[3].number_input(
            label=f"数量_{name}",
            min_value=0,
            step=1,
            value=int(quantity),
            key=widget_key,  # 这里的 key 是唯一的
            label_visibility="collapsed",
            on_change=change_list,
            args=(item,)
        )

        # 可选：每一行数据之间加一个细微的分割线
        st.write("<div style='margin: -10px 0px 5px 0px; border-top: 1px solid #eee;'></div>",
                 unsafe_allow_html=True)

    st.markdown("---")
    st.header("📝 填写多商品订单")

    with st.form("multi_order_form"):
        st.subheader("1. 收货信息 (根据用户ID加载)")
        st.info(f"收货人默认为: **{user}**")
        # 获取电话和地址选项
        phone_ops = get_user_phone(st.session_state.current_user_id)
        selected_phone = st.selectbox("选择联系电话", options=phone_ops, key="phone_select")

        address_ops = get_user_address(st.session_state.current_user_id)
        selected_address = st.selectbox("选择收货地址", options=address_ops.keys(), key="address_select",
                                        format_func=lambda x: address_ops[x])

        st.markdown("---")
        submitted = st.form_submit_button("✅ 提交订单", type="primary")
        if submitted:
            st.session_state.submitted = True  # 锁定提交状态
            st.session_state.payment_done = False  # 重置支付状态

    if st.session_state.get("submitted") and not st.session_state.get("orderid"):
        # --- 步骤 A: 收集数据 ---
        # 确保每次点击提交时重置列表，防止数据重复叠加
        final_items = []
        total_order_price = 0

        for item_id in st.session_state.selected_product:
            qty_key = f"qty_input_{item_id}"
            current_qty = st.session_state.get(qty_key, 0)

            if current_qty > 0:
                product_detail = products_map.get(item_id)
                if product_detail:
                    price = product_detail['standardprice']
                    item_total = price * current_qty

                    final_items.append({
                        "商品ID": item_id,
                        "商品名称": product_detail['productname'],
                        "单价": price,
                        "数量": current_qty,
                        "单位": product_detail['unit'],
                        "小计": item_total
                    })
                    st.session_state.total_order_price += item_total
        # --- 步骤 B: 检查并更新数据库 ---
        if not final_items:
            st.error("订单中没有商品，无法提交。")
        else:
            with st.spinner("正在创建订单..."):
                st.session_state.orderid = submit_order_to_db(
                    final_items, total_order_price, selected_phone, selected_address
                )

            if st.session_state.orderid:
                st.success(f"🎉 订单提交成功！订单号: **{st.session_state.orderid}**")
            else:
                # 如果数据库写入返回 None (发生 Exception)，错误消息已在函数内 st.error 显示
                st.error("订单创建失败，请检查数据库连接或联系管理员。")

    if st.session_state.submitted and not st.session_state.payment_done:
        show_payment_container()


    # --- 支付成功后的展示内容 ---
    if st.session_state.get("payment_done"):
        st.success(f"✅ 支付成功！订单已进入分发流程。")
        # st.balloons()

        # 这里可以放置你之前的“曼哈顿距离派发结果”展示
        # display_dispatch_plan(new_order_id)

        if st.button("返回首页或继续购物"):
            st.session_state.submitted = False
            st.session_state.payment_done = False
            st.session_state.orderid = None
            st.session_state.total_order_price = 0
            st.rerun()


if not st.session_state.logged_in:
    login()
else:
    order_page()