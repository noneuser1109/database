from datetime import datetime
import psycopg
import streamlit as st
from psycopg.rows import dict_row
import time
# import emoji

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
    "订单": [
        st.Page("select_order.py", title="查询订单"),
        st.Page("create_order.py", title="新建订单"),
    ],
    "仓储":[
        st.Page("product_info.py", title="货物信息"),
    ],
    "物流":[
        st.Page("logistics.py", title="安排配送"),
    ],
    "用户反馈":[
        st.Page("customer_review.py", title="客户评价"),
    ]
}

pg = st.navigation(pages)
pg.run()