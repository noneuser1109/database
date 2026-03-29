import streamlit as st
import pandas as pd
import utils
import extra_streamlit_components as stx
import time
from auth_utils import fetch_user_from_backend


cookie_manager = stx.CookieManager(key="create_order_manager")

# --- 身份恢复逻辑 ---
def sync_session_with_cookie():
    if st.session_state.get("user"):
        return

    token = cookie_manager.get("auth_token")

    if not token:
        return

    if "auth_retry_count" not in st.session_state:
        st.session_state.auth_retry_count = 0

    user_data = fetch_user_from_backend(token)

    if user_data:
        # 登录成功：记录状态并重置计数器
        st.session_state.user = user_data
        st.session_state.token = token
        st.session_state.auth_retry_count = 0
        st.rerun()
    else:
        # 登录失败：开始重试逻辑
        if st.session_state.auth_retry_count < 3:
            st.session_state.auth_retry_count += 1
            # 这种短时间的 sleep 配合 rerun 可以给后端/网络一点缓冲时间
            time.sleep(0.3) 
            st.warning(f"身份验证尝试中... 第 {st.session_state.auth_retry_count} 次")
            st.rerun()
        else:
            # 3 次均失败：判定 Token 失效，清理并重置
            cookie_manager.delete("auth_token")
            st.session_state.auth_retry_count = 0
            st.error("登录已失效，请重新登录")
            # 可选：st.rerun() 刷新到未登录状态

# 在页面逻辑开始处调用
sync_session_with_cookie()


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
            log_success = utils.add_order_log_via_api(
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
    st.session_state[f"input_{item}"] = st.session_state[f"qty_input_{item}"]

def set_new_orderid(new_orderid):
    st.session_state.orderid = new_orderid


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


def order_page():
    """
    处理订单填写和提交逻辑。
    """

    user = st.session_state.user
    if not user:
        st.title("🛍️ 订单下单")
        # 使用警告框提示用户
        st.warning("⚠️ 您尚未登录，无法查看产品或提交订单。")
        
        # 提供一个美观的引导界面
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("前往登录", type="primary"):
                # 假设你的 navigation 中登录页的 key 是 "login"
                # 或者如果你使用 query_params 切换页面
                st.switch_page("user_login.py") # 请根据你实际的文件路径修改
        
        # 核心：停止后续逻辑执行，不渲染产品列表
        st.stop()


    products = utils.get_products()

    if products:
        # 设定每行显示 5 列
        cols_per_row = 5
        
        # 使用这种方式可以更简洁地处理余数，不需要写两遍逻辑
        for i in range(0, len(products), cols_per_row):
            row_products = products[i : i + cols_per_row]
            cols = st.columns(cols_per_row)
            
            for col, product in zip(cols, row_products):
                # 1. 使用不带 border 的 container 实现自适应
                with col.container(): 
                    # 这里可以换成 ImageKit 的图片 URL
                    st.markdown(f"### :balloon:") 
                    st.write(f"**ID:** {product['productid']}")
                    st.write(f"**价格:** {product['standardprice']}元")
                    
                    # 初始化 session_state
                    pid = product['productid']
                    if pid not in st.session_state:
                        st.session_state[pid] = 0
                    
                    # 2. 数字输入框：Streamlit 默认就带加减号，只要 step 是整数
                    # 注意：label 设置为 "label_visibility='collapsed'" 可以隐藏标题让界面更清爽
                    num = st.number_input(
                        "购买数量", 
                        min_value=0, 
                        step=1, 
                        key=f"input_{pid}", # 建议加上前缀避免冲突
                        label_visibility="visible" 
                    )
                    
                    # 更新选择状态
                    if num > 0:
                        st.session_state.selected_product.add(pid)
                    elif pid in st.session_state.selected_product:
                        st.session_state.selected_product.remove(pid)
                        
            # 每一行结束后画一条淡淡的分隔线（可选）
            st.divider()
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
        price = float(product_detail['standardprice'])
        unit = product_detail['unit']
        quantity = int(st.session_state.get(f"input_{item}", 0))
        st.write(quantity)
        if quantity == 0:
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
        st.info(f"收货人默认为: **{user["realname"]}**")
        # 获取电话和地址选项
        phone_ops = utils.get_user_phone(user["id"])
        selected_phone = st.selectbox("选择联系电话", options=phone_ops, key="phone_select")

        address_ops = utils.get_user_address(user["id"])
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
            current_qty = int(st.session_state.get(qty_key, 0))

            if current_qty > 0:
                product_detail = products_map.get(item_id)
                if product_detail:
                    price = float(product_detail['standardprice'])
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
                st.session_state.orderid = utils.submit_order_to_api(
                    user.get('id'), final_items, total_order_price, selected_phone, selected_address
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


order_page()