from datetime import datetime
import streamlit as st
import time
import extra_streamlit_components as stx
from auth_utils import fetch_user_from_backend

if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None

import streamlit as st
import extra_streamlit_components as stx
import time

# 初始化管理器
if "cookie_manager" not in st.session_state:
    st.session_state.cookie_manager = stx.CookieManager()

cookie_manager = st.session_state.cookie_manager

# --- 身份恢复逻辑 ---
def sync_session_with_cookie():
    # 如果内存里已经有用户了，直接跳过
    if st.session_state.get("user"):
        return

    # 尝试从 Cookie 获取 Token (加入微小延迟防止组件未加载)
    token = cookie_manager.get("auth_token")
    
    # 技巧：如果刷新瞬间拿不到，脚本会重跑，第二次通常就能拿到了
    if token:
        user_data = fetch_user_from_backend(token)
        if user_data:
            st.session_state.user = user_data
            st.session_state.token = token
            # 刷新页面状态，进入已登录模式
            st.rerun() 
        else:
            # Token 坏了，清理 Cookie 防止循环请求
            cookie_manager.delete("auth_token")

# 在 pg.run() 之前调用
sync_session_with_cookie()

# ====================== 1. 全局侧边栏（放在导航定义之前，确保全局常驻） ======================
# 第一步：初始化全局session_state（存储身份类型和选择的身份）
if "user_identity_type" not in st.session_state:
    # 身份类型：商家/用户，默认先选择
    st.session_state.user_identity_type = ""

# 第二步：创建全局常驻sidebar
with st.sidebar:
    st.title("🔑 身份选择")
    st.divider()

    # 1. 选择身份类型（商家/用户）
    identity_type = st.selectbox(
        label="选择身份类型",
        options=["", "商家", "用户"],  # 空值作为默认占位
        index=0,
        help="选择后将展示对应身份列表"
    )

    # 2. 根据身份类型，展示对应身份选择框
    if identity_type == "商家":
        st.session_state.user_identity_type = "商家"

    elif identity_type == "用户":
        st.session_state.user_identity_type = "用户"

    else:
        # 未选择身份类型时，清空全局状态
        st.session_state.user_identity_type = ""
        st.session_state.selected_identity = ""

    st.divider()

    # 3. 展示当前全局选中的身份（方便确认）
    if st.session_state.user_identity_type:
        st.success(
            f"当前身份：\n{st.session_state.user_identity_type}"
        )
    else:
        st.warning("请先选择身份类型和具体身份")

# ====================== 2. 原有导航逻辑（无需修改） ======================
pages = {
    "概览": [
        st.Page("description.py", title="基本信息"),
    ],
    "登录/注册": [
        st.Page("user_login.py", title="登录/注册"),
    ],
    "订单": [
        st.Page("select_order.py", title="查询订单"),
        st.Page("create_order.py", title="新建订单"),
    ],
    "仓储":[
        st.Page("product_info.py", title="货物信息"),
        st.Page("product_main_info.py", title="商品主数据"),
        st.Page("warehouse_info.py", title="仓库信息"),
    ],
    "物流":[
        st.Page("logistics.py", title="安排配送"),
        st.Page("multi_order.py", title="多订单聚类"),
        st.Page("multi_order_cluster.py", title="真.多订单聚类"),
    ],
    "个人中心":[
        st.Page("user_order.py", title="我的订单"),
        st.Page("phone_address.py", title="联系方式"),
    ],
    "数据看板":[
        st.Page("dash_board.py", title="数据可视化"),
    ]
}

pg = st.navigation(pages)
pg.run()