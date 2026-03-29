import streamlit as st
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

if 'current_page' not in st.session_state:
    st.session_state.current_page = "query_page"  # 默认页面

def update_to_not_rated(order_id: str) -> bool:
    """
    业务逻辑：确认收货。
    将订单状态从 SHIPPED_NOT_RECEIVED 变更为 NOT_RATED。
    """
    # 这里的参数要严格对应你数据库和 API 预期的值
    success = utils.add_order_log_via_api(
        order_id=order_id,
        from_state="SHIPPED_NOT_RECEIVED",
        to_state="NOT_RATED",
        changer=st.session_state.get("username", "Customer"), # 默认为当前用户
        remark="用户点击确认收货，等待评价"
    )
    
    if success:
        st.toast(f"订单 {order_id} 已确认收货！", icon="📦")
    return success


# --- 定义全局跳转回调 ---
def handle_review_click(order_id):
    """
    仅负责修改状态，不负责渲染
    """
    st.session_state.current_page = "review_page"
    st.session_state.target_order_id = order_id
    # 注意：回调执行完后 Streamlit 会自动重新运行，不需要手动 rerun


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



def render_select_order_by_user():
    st.session_state.customer_id = st.session_state.user.get("id", "") if st.session_state.get("user") else None
    if st.session_state.customer_id is not None and st.session_state.customer_id != "":
        raw_data = utils.get_customer_orders_list(st.session_state.customer_id)
        if raw_data:
            # 展平嵌套数据以便 DataFrame 显示
            flat_list = []
            for item in raw_data:
                # 合并两个字典的内容
                combined = {**item['base_info'], **item['fee_info']}
                flat_list.append(combined)
            for order_info in flat_list:
                real_freight_fee = float(order_info['freight_fee'])
                import pandas as pd
                updatetimestamp = pd.to_datetime(order_info['updatetimestamp'])
                if order_info['isemergency'] == False and order_info['originalmoney'] >= order_info[
                    'conditionfreightfree']:
                    real_freight_fee = 0
                emoji = get_status_emoji(order_info['orderstate'])
                backend_status_name = get_backend_status_name(order_info['orderstate'])
                summary_label = (
                    f"{emoji} **{backend_status_name}** | "
                    f"单号: {order_info['orderid']} | "
                    f"客户: {order_info['memberid']} | "
                    f"📅 {updatetimestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"💰 ¥{order_info['discountedmoney'] + real_freight_fee:,.2f}"
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
                            st.markdown("**用户评分**")
                            st.write(order_info['customerscore'])

                    # --- Tab 2: 订单明细 (Dataframe) ---
                    with tab2:
                        # 1. 默认不勾选 (value=False)
                        show_details = st.checkbox("显示订单明细 (包含单价与折扣信息)", value=False, key=f"detail{order_info['orderid']}")

                        if show_details:
                            # 2. 只有在勾选后，才触发后端 API 请求
                            with st.spinner("正在从服务器获取明细数据..."):
                                order_full_info = utils.get_order_full_info_sync(order_info['orderid'], st.session_state.token)
                                details = order_full_info.get("details", [])

                            if details:
                                df_items = pd.DataFrame(details)
                                
                                # 3. 渲染 Dataframe
                                st.dataframe(
                                    df_items,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "快照单价": st.column_config.NumberColumn("单价", format="¥%.2f"),
                                        "小计": st.column_config.NumberColumn("小计金额", format="¥%.2f"),
                                        "线性折扣": st.column_config.NumberColumn(
                                            "折扣系数",
                                            format="%.2f", 
                                            help="1.0代表无折扣，0.9代表九折"
                                        ),
                                    }
                                )
                            else:
                                st.info("该订单暂无明细数据。")
                        else:
                            # 4. 未勾选时的友好提示
                            st.info("💡 请勾选上方复选框以加载并查看订单明细。")

                    # --- Tab 3: 金额明细 (Key-Value 列表) ---
                    with tab3:
                        # 使用两列布局，更加紧凑
                        fc1, fc2 = st.columns(2)

                        with fc1:
                            st.markdown("#### ➕ 收入项")
                            st.markdown(f"**商品原始总金额**: `¥{order_info['originalmoney']:,.2f}`")
                            st.markdown(f"**商品折后总金额**: `¥{order_info['discountedmoney']:,.2f}`")
                            st.markdown(f"**基础运费**: `¥{order_info['freight_fee']:,.2f}`")
                            st.divider()
                            st.caption(f"ℹ️ 免运费门槛: ¥{order_info['conditionfreightfree']:,.2f}")

                        with fc2:
                            st.markdown("#### ➖ 折扣与最终项")
                            st.markdown(f"**实际运费**: `¥{real_freight_fee:,.2f}`")
                            st.markdown(f"**订单审批折扣**: `¥{order_info['approveddiscount']:,.2f}`")
                            st.markdown("---")
                            st.markdown(
                                f"### 🏷️ 最终总价: <span style='color:#e05260'>¥{order_info['discountedmoney'] + real_freight_fee:,.2f}</span>",
                                unsafe_allow_html=True)

                    # --- Tab 4: 状态变更记录 ---
                    # --- Tab 4: 状态日志 (Timeline) ---
                    with tab4:
                        # 1. 默认不勾选，减少页面初始化时的 API 调用
                        show_history = st.checkbox("查看状态变更历史", value=False, key=f"cb_history{order_info['orderid']}")

                        if show_history:
                            with st.spinner("正在加载历史记录..."):
                                # 只有勾选后才调用 utils 接口
                                order_history = utils.get_order_status_history(order_info['orderid'])
                            
                            if not order_history:
                                st.caption("暂无状态变更记录")
                            else:
                                st.markdown("---")
                                for log in order_history:
                                    # 简单的时间轴模拟
                                    col_time, col_info = st.columns([1, 4])
                                    
                                    # 格式化时间显示（如果 changetime 是字符串，可以视情况进行格式化）
                                    col_time.caption(f"📅 {log['changetime']}")
                                    
                                    # 逻辑兼容：根据之前 API 的改动，如果接口直接返回了 name，可以直接用；
                                    # 如果还是返回 code，则保留你的 get_backend_status_name 转换函数
                                    from_name = log.get('from_state_name') or get_backend_status_name(log['fromstate'])
                                    to_name = log.get('to_state_name') or get_backend_status_name(log['tostate'])
                                    
                                    col_info.write(
                                        f"**{get_status_emoji(log.get('fromstate'))} {from_name}** ➡️ "
                                        f"**{get_status_emoji(log.get('tostate'))} {to_name}**"
                                    )
                                    
                                    # 备注信息显示
                                    if log.get('remark'):
                                        col_info.caption(f"💬 备注: {log['remark']}")
                                    col_info.info(f"操作人: {log['changer']}")
                                    st.markdown("---")
                        else:
                            st.info("💡 勾选上方复选框以加载订单生命周期轨迹。")

                        st.write("") # 留白
                        st.divider()
                        
                        # 2. 动态操作区：根据当前订单状态显示按钮
                        current_state = order_info['orderstate']
                        
                        if current_state == "SHIPPED_NOT_RECEIVED":
                            st.subheader("🏁 履约确认")
                            st.warning("如果您已收到商品，请点击下方确认收货。")
                            if st.button("📦 确认收货", key=f"conf_{order_info['orderid']}", type="primary"):
                                if update_to_not_rated(order_info['orderid']): # 后端改状态逻辑
                                    st.success("收货成功！")
                                    st.rerun()

                        elif current_state == "NOT_RATED":
                            st.subheader("✍️ 评价回馈")
                            st.info("交易已完成，您可以对订单进行评价。")
                            # 触发之前写的 handle_review_click 跳转到评价页
                            st.button("💬 立即评价", 
                                    key=f"eval_{order_info['orderid']}", 
                                    type="primary", 
                                    on_click=handle_review_click, 
                                    args=(order_info['orderid'],))


def render_order_review_page():
    st.title("✍️ 订单服务评价")
    
    order_id = st.session_state.get("target_order_id")
    token = st.session_state.get("token", "") # 假设你存储了 token
    
    if not order_id:
        st.warning("请先在订单列表选择要评价的订单。")
        if st.button("返回列表"):
            st.session_state.current_page = "query_page"
            st.rerun()
        return

    # 1. 获取订单全量信息（包含明细）
    with st.spinner("正在加载订单明细..."):
        try:
            order_info = utils.get_order_full_info_sync(order_id, token)
        except Exception as e:
            st.error(f"加载失败: {e}")
            return

    if not order_info:
        st.error("未找到订单信息")
        return

    # 2. 开始构建评价表单
    with st.form("full_review_form"):
        # --- 区域 A: 订单整体评价 ---
        st.subheader("🌟 整体评价")
        col1, col2 = st.columns([1, 2])
        with col1:
            order_rating = st.select_slider(
                "物流与服务评分", 
                options=[1, 2, 3, 4, 5], 
                value=5,
                key="order_overall_star"
            )
        with col2:
            order_remark = st.text_input("服务反馈", placeholder="物流快吗？服务好吗？")

        st.divider()

        # --- 区域 B: 商品明细评价 ---
        st.subheader("📦 商品评价")
        product_reviews_payload = [] # 用于存储每个商品的评价数据
        
        # 假设 order_info['details'] 是商品明细列表
        for idx, item in enumerate(order_info.get('details', [])):
            p_id = item['productid']
            p_name = item['productname']
            
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 3])
                with c1:
                    st.markdown(f"**{p_name}**")
                    st.caption(f"编号: {p_id}")
                with c2:
                    # 每个商品独立的评分
                    item_rating = st.selectbox(
                        "评分", [5, 4, 3, 2, 1], 
                        key=f"rating_{p_id}_{idx}"
                    )
                with c3:
                    # 每个商品独立的评语
                    item_content = st.text_area(
                        "使用心得", 
                        placeholder="质量如何？", 
                        key=f"content_{p_id}_{idx}",
                        height=80
                    )
                
                # 将数据存入临时列表
                product_reviews_payload.append({
                    "product_id": p_id,
                    "rating": item_rating,
                    "content": item_content if item_content else "默认好评"
                })
                st.write("---")

        # --- 3. 提交逻辑 ---
        submit_btn = st.form_submit_button("🚀 提交整单评价", use_container_width=True)
        
        if submit_btn:
            # 构造发送给后端方案 B 的 Payload
            success = utils.submit_review_to_server(
                order_id=order_id,
                order_rating=order_rating,
                order_remark=order_remark if order_remark else "好评",
                item_reviews_list=product_reviews_payload
            )
            
            if success:
                st.balloons()
                st.success("评价已提交成功！感谢您的反馈。")
                # 提交成功后延迟跳转回查询页
                st.session_state.current_page = "query_page"
                st.rerun()

    if st.button("⬅️ 返回不评价"):
        st.session_state.current_page = "query_page"
        st.rerun()


if st.session_state.current_page == "query_page":
    render_select_order_by_user()
elif st.session_state.current_page == "review_page":
    render_order_review_page()