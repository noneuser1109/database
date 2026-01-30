
from datetime import datetime
option_map = {
    0: '按订单号',
    1: '按客户',
    2: '按时间段'
}

import streamlit as st
import db_utils
import psycopg
from psycopg.rows import dict_row
from datetime import datetime

# 获取全局共享的连接池
pool = db_utils.get_db_pool()

def select_order_by_id(id: str):
    query = 'SELECT * FROM customerorder WHERE orderid = %s'
    try:
        with pool.connection() as conn:
            # 使用 dict_row 自动将每一行转换为字典
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (id,))
                return cur.fetchall()
    except Exception as e:
        raise Exception(f"查询执行失败：{str(e)}") from e


def select_order_by_customer(customer_id: str):
    query = 'SELECT orderid FROM customerorder WHERE memberid = %s ORDER BY updatetimestamp DESC'
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (customer_id,))
                # 这里只需要单列结果列表
                return cur.fetchall()
    except Exception as e:
        raise Exception(f"查询执行失败：{str(e)}") from e


def select_order_by_time(start: datetime, end: datetime):
    query = 'SELECT * FROM customerorder WHERE submitdate BETWEEN %s AND %s'
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (start, end))
                return cur.fetchall()
    except Exception as e:
        raise Exception(f"查询执行失败：{str(e)}") from e

def select_order_detail_by_id(id: str):
    query = """
            SELECT productinfo.productname AS "产品名称",
                   quantity                AS "数量",
                   snapshotprice           AS "快照单价",
                   linediscount            AS "线性折扣"
            FROM customerorder_detail, \
                 productinfo
            WHERE productinfo.productid = customerorder_detail.productid
              AND customerorder_detail.orderid = %s \
            """
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (id,))
                results = cur.fetchall()

                # 计算小计逻辑
                for item in results:
                    subtotal = (item["数量"] * item["快照单价"]) - item["线性折扣"]
                    item["小计"] = max(float(subtotal), 0.0)
                return results
    except Exception as e:
        raise Exception(f"查询执行失败：{str(e)}") from e


def get_order_status_history(order_id: str) -> list:
    sql_query = """
                SELECT logid, orderid, fromstate, tostate, changetime, changer, remark
                FROM customerorder_statuslog
                WHERE orderid = %s
                ORDER BY changetime ASC \
                """
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_query, (order_id,))
                return cur.fetchall()
    except Exception as e:
        raise Exception(f"状态日志查询失败: {str(e)}") from e


def select_order_fee_by_id(id: str):
    query = """
            SELECT originalmoney, discountedmoney, conditionfreightfree, freight_fee, approveddiscount
            FROM customerorder, \
                 customerorder_shipment
            WHERE customerorder.orderid = customerorder_shipment.orderid
              AND customerorder.orderid = %s \
            """
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (id,))
                return cur.fetchall()
    except Exception as e:
        raise Exception(f"费用查询失败：{str(e)}") from e


def get_status_emoji(status_code):
    """
    根据 statuscode 返回对应的 Emoji 图标
    """
    # 确保输入是字符串并转为大写，防止大小写不一致
    if not isinstance(status_code, str):
        return "❓"

    status = status_code.upper().strip()

    # 状态映射字典
    status_map = {
        "UNPAID": "🔴",  # 未付款：红色警示，需要行动
        "CLOSED": "⚫",  # 已关闭：黑色/灰色，代表结束
        "PAID_NOT_SHIPPED": "📦",  # 已付待发：包裹，准备中
        "SCHEDULED_SHIPPING": "⏳",  # 安排发货：沙漏，正在处理
        "SHIPPED_UNPAID": "⚠️",  # 发货未付：黄色警告，属于异常状态
        "SHIPPED_NOT_RECEIVED": "🚚",  # 发货未收：卡车，运输中
        "NOT_RATED": "⭐",  # 未评价：星星，期待反馈
        "SUCCESS": "✅",  # 成功：绿色对勾，完美完成
        "APPLY_REFUND": "🔄",  # 申请退款：循环箭头，流程逆转
        "REFUND_SUCCESS": "💸"  # 退款成功：飞走的钱/钱袋，资金退回
    }

    # 返回对应的 emoji，如果找不到则返回默认的问号
    return status_map.get(status, "⚪")


def get_backend_status_name(status_code: str, default: str = "未知状态") -> str:
    """
    根据statuscode获取对应的后端状态名称（映射关系）

    Args:
        status_code: 传入的状态码（如"UNPAID"、"PAID_NOT_SHIPPED"）
        default: 当状态码不存在时返回的默认值，默认是"未知状态"

    Returns:
        对应的后端状态名称
    """
    status = status_code.upper().strip()

    # statuscode 到后端名称的映射字典
    statuscode_to_backendname = {
        "UNPAID": "未付款",
        "CLOSED": "关闭交易",
        "PAID_NOT_SHIPPED": "未发货",
        "SCHEDULED_SHIPPING": "已安排配送",
        "SHIPPED_UNPAID": "已发货未付款",
        "SHIPPED_NOT_RECEIVED": "已发货",
        "NOT_RATED": "未评价",
        "SUCCESS": "交易成功",
        "APPLY_REFUND": "申请退款",
        "REFUND_SUCCESS": "退款成功"
    }
    # 用get方法获取值，不存在则返回默认值（忽略大小写，可选优化）
    # 若需要忽略大小写，可改为：status_code.upper()
    return statuscode_to_backendname.get(status, default)


if 'time_range' not in st.session_state:
    start = datetime(2022, 1, 1, 9, 30)
    end = datetime(2026, 1, 1, 9, 30)
else:
    start, end = st.session_state.time_range
if 'customer_id' not in st.session_state:
    st.session_state.customer_id = None
if 'order_id' not in st.session_state:
    st.session_state.order_id = None

selection = st.pills(
    "查询方式",
    options=option_map.keys(),
    format_func=lambda option: option_map[option],
    selection_mode="single",
)
if selection == 0:
    st.session_state.order_id = st.text_input("输入需要查询的订单号")
    order_fee_list = select_order_fee_by_id(st.session_state.order_id)
    order_info_list = select_order_by_id(st.session_state.order_id)
    if (st.session_state.order_id is not None
            and order_fee_list is not None and len(order_fee_list) > 0)\
            and order_info_list is not None and len(order_info_list) > 0:
        order_fee = order_fee_list[0]
        order_info = order_info_list[0]
        real_freight_fee = order_fee['freight_fee']
        if order_info['isemergency'] == False and order_info['originalmoney'] >= order_info['conditionfreightfree']:
            real_freight_fee = 0
        emoji = get_status_emoji(order_info['orderstate'])
        backend_status_name = get_backend_status_name(order_info['orderstate'])
        summary_label = (
            f"{emoji} **{backend_status_name}** | "
            f"单号: {order_info['orderid']} | "
            f"客户: {order_info['memberid']} | "
            f"📅 {order_info['submitdate'].strftime('%Y-%m-%d %H:%M:%S')} | "
            f"💰 ¥{order_fee['discountedmoney'] + real_freight_fee:,.2f}"
        )
        with st.expander(summary_label):
            # 3. 内层：Tabs
            tab1, tab2, tab3, tab4 = st.tabs(["👤 总体信息", "🛒 订单明细", "💰 金额明细", "⏱️ 状态变更"])

            # --- Tab 1: 总体信息 ---
            with tab1:
                # 新增：顶部复制区
                st.info("💡 点击下方订单号右侧图标可直接复制")
                st.code(order_info['orderid'], language=None)

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown("**操作人**")
                    st.caption(order_info['operatorid'])
                with c2:
                    st.markdown("**审批人**")
                    st.caption(order_info['approverid'])
                with c3:
                    st.markdown("**是否加急**")
                    if order_info['isemergency']:
                        st.error("是 (Priority)")
                    else:
                        st.info("否 (Normal)")
                with c4:
                    st.markdown("**用户评价**")
                    st.write(order_info['customerremark'])

            # --- Tab 2: 订单明细 (Dataframe) ---
            with tab2:
                df_items = select_order_detail_by_id(st.session_state.order_id)
                st.dataframe(
                    df_items,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "快照单价": st.column_config.NumberColumn(format="¥%.2f"),
                        "小计": st.column_config.NumberColumn(format="¥%.2f"),
                        "线性折扣": st.column_config.NumberColumn(format="%.2f", help="1.0代表无折扣，0.9代表九折"),
                    }
                )

            # --- Tab 3: 金额明细 (Key-Value 列表) ---
            with tab3:
                # 使用两列布局，更加紧凑
                fc1, fc2 = st.columns(2)

                with fc1:
                    st.markdown("#### ➕ 收入项")
                    st.markdown(f"**商品原始总金额**: `¥{order_fee['originalmoney']:,.2f}`")
                    st.markdown(f"**商品折后总金额**: `¥{order_fee['discountedmoney']:,.2f}`")
                    st.markdown(f"**基础运费**: `¥{order_fee['freight_fee']:,.2f}`")
                    st.divider()
                    st.caption(f"ℹ️ 免运费门槛: ¥{order_fee['conditionfreightfree']:,.2f}")

                with fc2:
                    st.markdown("#### ➖ 折扣与最终项")
                    st.markdown(f"**实际运费**: `¥{real_freight_fee:,.2f}`")
                    st.markdown(f"**订单审批折扣**: `¥{order_fee['approveddiscount']:,.2f}`")
                    st.markdown("---")
                    st.markdown(f"### 🏷️ 最终总价: <span style='color:#e05260'>¥{order_fee['discountedmoney'] + real_freight_fee:,.2f}</span>",
                                unsafe_allow_html=True)

            # --- Tab 4: 状态变更记录 ---
            with tab4:
                order_history = get_order_status_history(st.session_state.order_id)
                if not order_history:
                    st.caption("暂无记录")
                else:
                    for log in order_history:
                        # 简单的时间轴模拟
                        col_time, col_info = st.columns([1, 4])
                        col_time.caption(log['changetime'])
                        col_info.write(f"**{get_status_emoji(log['fromstate'])} {get_backend_status_name(log['fromstate'])}**➡️**{get_status_emoji(log['tostate'])} {get_backend_status_name(log['tostate'])}** - {log['changer']}")

elif selection == 1:
    st.session_state.customer_id = st.text_input("输入需要查询的客户")
    if st.session_state.customer_id is not None:
        ids = select_order_by_customer(st.session_state.customer_id)
        for id in ids:
            order_fee_list = select_order_fee_by_id(id[0])
            order_info_list = select_order_by_id(id[0])
            if (id is not None
                and order_fee_list is not None and len(order_fee_list) > 0) \
                    and order_info_list is not None and len(order_info_list) > 0:
                order_fee = order_fee_list[0]
                order_info = order_info_list[0]
                real_freight_fee = order_fee['freight_fee']
                if order_info['isemergency'] == False and order_info['originalmoney'] >= order_info[
                    'conditionfreightfree']:
                    real_freight_fee = 0
                emoji = get_status_emoji(order_info['orderstate'])
                backend_status_name = get_backend_status_name(order_info['orderstate'])
                summary_label = (
                    f"{emoji} **{backend_status_name}** | "
                    f"单号: {order_info['orderid']} | "
                    f"客户: {order_info['memberid']} | "
                    f"📅 {order_info['updatetimestamp'].strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"💰 ¥{order_fee['discountedmoney'] + real_freight_fee:,.2f}"
                )
                with st.expander(summary_label):
                    # 3. 内层：Tabs
                    tab1, tab2, tab3, tab4 = st.tabs(["👤 总体信息", "🛒 订单明细", "💰 金额明细", "⏱️ 状态变更"])

                    # --- Tab 1: 总体信息 ---
                    with tab1:
                        # 新增：顶部复制区
                        st.info("💡 点击下方订单号右侧图标可直接复制")
                        st.code(order_info['orderid'], language=None)

                        st.divider()
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            st.markdown("**操作人**")
                            st.caption(order_info['operatorid'])
                        with c2:
                            st.markdown("**审批人**")
                            st.caption(order_info['approverid'])
                        with c3:
                            st.markdown("**是否加急**")
                            if order_info['isemergency']:
                                st.error("是 (Priority)")
                            else:
                                st.info("否 (Normal)")
                        with c4:
                            st.markdown("**用户评价**")
                            st.write(order_info['customerremark'])

                    # --- Tab 2: 订单明细 (Dataframe) ---
                    with tab2:
                        df_items = select_order_detail_by_id(id[0])
                        st.dataframe(
                            df_items,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "快照单价": st.column_config.NumberColumn(format="¥%.2f"),
                                "小计": st.column_config.NumberColumn(format="¥%.2f"),
                                "线性折扣": st.column_config.NumberColumn(format="%.2f",
                                                                          help="1.0代表无折扣，0.9代表九折"),
                            }
                        )

                    # --- Tab 3: 金额明细 (Key-Value 列表) ---
                    with tab3:
                        # 使用两列布局，更加紧凑
                        fc1, fc2 = st.columns(2)

                        with fc1:
                            st.markdown("#### ➕ 收入项")
                            st.markdown(f"**商品原始总金额**: `¥{order_fee['originalmoney']:,.2f}`")
                            st.markdown(f"**商品折后总金额**: `¥{order_fee['discountedmoney']:,.2f}`")
                            st.markdown(f"**基础运费**: `¥{order_fee['freight_fee']:,.2f}`")
                            st.divider()
                            st.caption(f"ℹ️ 免运费门槛: ¥{order_fee['conditionfreightfree']:,.2f}")

                        with fc2:
                            st.markdown("#### ➖ 折扣与最终项")
                            st.markdown(f"**实际运费**: `¥{real_freight_fee:,.2f}`")
                            st.markdown(f"**订单审批折扣**: `¥{order_fee['approveddiscount']:,.2f}`")
                            st.markdown("---")
                            st.markdown(
                                f"### 🏷️ 最终总价: <span style='color:#e05260'>¥{order_fee['discountedmoney'] + real_freight_fee:,.2f}</span>",
                                unsafe_allow_html=True)

                    # --- Tab 4: 状态变更记录 ---
                    with tab4:
                        order_history = get_order_status_history(id[0])
                        if not order_history:
                            st.caption("暂无记录")
                        else:
                            for log in order_history:
                                # 简单的时间轴模拟
                                col_time, col_info = st.columns([1, 4])
                                col_time.caption(log['changetime'])
                                col_info.write(
                                    f"**{get_status_emoji(log['fromstate'])} {get_backend_status_name(log['fromstate'])}**➡️**{get_status_emoji(log['tostate'])} {get_backend_status_name(log['tostate'])}** - {log['changer']}")
elif selection == 2:
    st.slider(
        "选择一个时间范围",
        datetime(2022, 1, 1, 9, 30),
        datetime(2027, 1, 1, 9, 30),
        value=(start, end),
        format="MM/DD/YY - hh:mm",
        key='time_range'
    )
    if st.button('查询'):
        st.dataframe(select_order_by_time(start, end))