import pandas as pd
import streamlit as st
from datetime import datetime
import pandas as pd
import utils
import extra_streamlit_components as stx
import time
from auth_utils import fetch_user_from_backend


cookie_manager = stx.CookieManager(key="create_order_manager")

def sync_session_with_cookie():
    # 1. 内存中已有用户，直接跳过
    if st.session_state.get("user"):
        return

    # 2. 初始化重试计数器（只在 Session 开始时运行一次）
    if "auth_retry_count" not in st.session_state:
        st.session_state.auth_retry_count = 0

    token = cookie_manager.get("auth_token")
    
    # 3. 如果没拿到 Token 的处理逻辑
    if not token:
        # 如果还没尝试够 3 次
        if st.session_state.auth_retry_count < 3:
            st.session_state.auth_retry_count += 1
            time.sleep(0.3)  # 短暂等待浏览器同步 Cookie
            st.rerun()       # 强制重跑脚本尝试重新获取
        return  # 3 次之后依然没有，说明确实没登录，静默退出

    # 4. 拿到 Token 后，尝试校验
    user_data = fetch_user_from_backend(token)
    
    if user_data:
        # 登录成功：记录状态并重置计数器
        st.session_state.user = user_data
        st.session_state.token = token
        st.session_state.auth_retry_count = 0
        st.rerun()
    else:
        # Token 校验失败（可能过期或篡改）
        # 同样给予 3 次机会，防止后端接口瞬时波动
        if st.session_state.auth_retry_count < 3:
            st.session_state.auth_retry_count += 1
            time.sleep(0.3)
            st.rerun()
        else:
            # 彻底失败，清理 Cookie 避免死循环
            cookie_manager.delete("auth_token")
            st.session_state.auth_retry_count = 0
            st.error("登录凭证已失效，请重新登录")

# 调用
sync_session_with_cookie()

if not "scheduled_shipping" in st.session_state:
    st.session_state.scheduled_shipping = None
if not "shipped" in st.session_state:
    st.session_state.shipped = False

def log_order_final_shipping(order_id: str, changer: str = "Warehouse_Admin"):
    """
    业务封装：记录订单从‘已安排物流’到‘已发货未签收’的状态变更
    通常在物理出库（扣减库存）成功后调用。
    """
    # 状态编码定义
    FROM_STATE = "SCHEDULED_SHIPPING"
    TO_STATE = "SHIPPED_NOT_RECEIVED"
    REMARK = "商品已完成打包并离开仓库，交由物流商配送中"

    # 调用通用的日志/状态更新 API
    success = utils.add_order_log_via_api(
        order_id=order_id,
        from_state=FROM_STATE,
        to_state=TO_STATE,
        changer=changer,
        remark=REMARK
    )
    
    if success:
        st.toast(f"🚀 订单 {order_id} 物理出库成功，已更新为：运输中", icon="📦")
    
    return success


def sure_shipping():
    st.session_state.shipped = True 
    st.rerun()

def clear_cache():
    st.cache_data.clear()
    st.rerun()

def process_full_order_distribution(order_id: str):
    """
    获取整单派发方案并展示 (基于 API 返回结果)
    """
    # 1. 调用同步 API 获取完整计划
    with st.spinner("正在计算全单库存匹配方案..."):
        data = utils.get_inventory_distribute_plan(order_id)

    if not data or "results" not in data:
        return # 错误已在 utils 中提示

    # 2. 展示收货目标信息
    st.write(f"### 📍 配送目标坐标: ({data.get('target_latitude')}, {data.get('target_longitude')})")

    items_list = data["results"]
    all_success = True  # 用于追踪是否所有商品都分配成功

    # 3. 循环展示每个商品的方案
    for item in items_list:
        p_name = item['product_name']
        p_id = item['product_id']
        needed_qty = item['required_qty']
        status_msg = bool(item['success'])
        plan_data = item['plan']

        st.markdown(f"#### 📦 商品: {p_name} (需 {needed_qty} 件)")

        if plan_data:
            df_plan = pd.DataFrame(plan_data)
            
            # 判断库存是否充足
            if not status_msg:
                st.error(f"⚠️ {status_msg}")
                all_success = False
            else:
                st.success(f"✅ {status_msg}")

            # 展示派发详情表格
            st.dataframe(
                df_plan, 
                use_container_width=True,
                column_config={
                    "distance_score": st.column_config.NumberColumn("距离系数", format="%.4f"),
                    "dispatch_qty": "派发数量",
                    "warehouse_address": "仓库地址"
                }
            )
        else:
            st.error(f"❌ 无法获取商品 {p_name} 的库存分布数据或库存为0。")
            all_success = False

    # 4. 如果全部成功，执行后续逻辑（如记录日志）
    # 注意：这里的日志记录建议也封装成 API，由前端调用或由后端在计算成功后自动触发
   # 4. 如果全部成功，执行批量后续逻辑
    # --- 步骤 1: 执行安排配送（仅生成计划，不扣库存） ---
    if all_success and items_list:
        # 构造计划数据并存入 session_state，以便下一步使用
        st.session_state.pending_dispatch_plan = items_list
        
        # 调用后端接口：仅更新订单状态到 ARRANGED (已安排配送)
        # 此时不进行物理扣减库存
        log_success = log_order_scheduled_shipping(order_id)

        if log_success:
            st.success("✅ 配送路径已最优匹配，订单已进入【待出库】状态。")
            st.info("💡 请核对下方配送方案，确认无误后点击“确认出库”执行物理扣减。")
        else:
            st.error("❌ 状态更新失败，请检查后端服务。")

    # --- 步骤 2: 设计确认出库按钮（真正的物理出库） ---
    if "pending_dispatch_plan" in st.session_state:
        st.markdown("### 🚚 配送方案确认")
        # 展示一下即将出库的清单（可选）
        # st.json(st.session_state.pending_dispatch_plan)
        
        st.button("🔥 确认出库 (更新至已发货)", type="primary", use_container_width=True, on_click=sure_shipping)
            

def do_ship(orderid: str):
    items_list = st.session_state.pending_dispatch_plan
            
    # --- 构造批量出库数据结构 ---
    bulk_items = []
    for item in items_list:
        for plan in item['plan']:
            bulk_items.append({
                "warehouse_id": plan['warehouse_id'],
                "product_id": item['product_id'],
                "qty": plan['dispatch_qty']
            })
    
    
    # --- 执行物理出库 ---
    with st.status("正在执行物理仓库扣减...", expanded=True) as status:
        if bulk_items:
            # 1. 执行扣减库存
            stock_out_ok = utils.execute_bulk_stock_out_sync(
                orderid, 
                bulk_items, 
                st.session_state.get("user", {}).get("realname", "Admin")
            )
            
            if stock_out_ok:
                # 2. 更新订单状态到 SHIPPED_NOT_RECEIVED
                final_log_ok = log_order_final_shipping(orderid)
                
                if final_log_ok:
                    status.update(label="🚀 出库成功！订单已更新为已发货状态", state="complete")
                    st.balloons()
                    # 清理缓存计划，防止重复提交
                    del st.session_state.pending_dispatch_plan
                    st.session_state.shipped = False
                    
                    st.button("查看更新后的订单", on_click=clear_cache)
                        
                else:
                    status.update(label="库存已扣减，但订单状态更新失败", state="error")
            else:
                status.update(label="物理出库执行失败，库存未变动", state="error")


def log_order_scheduled_shipping(order_id: str, changer: str = "Merchant"):
    """
    业务封装：记录订单从‘已支付未发货’到‘已安排物流’的状态变更
    """
    # 固定的状态编码（需与数据库 orderstatus_map 表一致）
    FROM_STATE = "PAID_NOT_SHIPPED"
    TO_STATE = "SCHEDULED_SHIPPING"
    REMARK = "系统自动分仓成功，已安排就近仓库发货"

    # 调用你之前定义的 API 访问函数
    success = utils.add_order_log_via_api(
        order_id=order_id,
        from_state=FROM_STATE,
        to_state=TO_STATE,
        changer=changer,
        remark=REMARK
    )
    
    if success:
        st.toast(f"🚚 订单 {order_id} 状态已更新为：待发货", icon="✅")
    
    return success


# 1. 身份拦截逻辑：外层包裹
if not st.session_state.get("user"):
    st.warning("🔒 请先登录以访问订单调度系统")
    
    # 放置一个显眼的登录按钮
    if st.button("立即前往登录", type="primary", use_container_width=True):
        # 注意：这里的路径需与 st.navigation 中定义的或文件系统路径一致
        st.switch_page("user_login.py") 
    
    # 核心：强制停止当前页面后续代码渲染
    st.stop()


st.session_state.orderid = st.text_input("订单号：")
if st.button("规划发货"):
    process_full_order_distribution(st.session_state.orderid)
st.write(st.session_state.shipped)
if st.session_state.shipped:
    do_ship(st.session_state.orderid)
