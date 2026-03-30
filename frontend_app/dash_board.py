import streamlit as st
import pandas as pd
import chart_utils

# ===================== 全局设置 =====================
st.set_page_config(
    page_title="运营数据可视化看板",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📊"
)

# 马卡龙色系 CSS 美化
st.markdown("""
    <style>
    .main {
        background-color: #FFF9FB;
        padding: 0rem 1rem;
    }
    h1 {
        color: #F29191;
        font-weight: 700;
    }
    h2 {
        color: #8A8AF2;
        font-weight: 600;
    }
    div[data-testid="stContainer"] {
        background-color: #FFFFFF;
        border-radius: 14px;
        box-shadow: 0 4px 10px rgba(242, 145, 145, 0.08);
        padding: 16px;
        border: 1px solid #FFE6E6;
    }
    </style>
    """, unsafe_allow_html=True)

# ===================== 页面头部 =====================
st.title("📊 运营数据可视化看板")
st.divider()

# ===================== 侧边栏 =====================
with st.sidebar:
    st.header("⚙️ 筛选条件")
    days = st.slider("选择统计天数", 7, 90, 30)
    if st.button("🔄 刷新数据", use_container_width=True):
        st.rerun()

# ===================== 两列布局 =====================
col1, col2 = st.columns(2, gap="large")

with col1:
    # 1. 订单趋势
    with st.container(border=True):
        st.subheader("📈 订单趋势（按日）")
        trend = chart_utils.get_order_trend(days)
        if not trend.empty:
            st.line_chart(trend, x="date", y=["cnt", "amount"], use_container_width=True, color=["#8A8AF2","#8A8AF2"])
            col_a, col_b = st.columns(2)
            col_a.metric("总订单数", f"{trend['cnt'].sum():,} 单")
            col_b.metric("总金额", f"¥{trend['amount'].sum():,.2f}")
        else:
            st.info("暂无订单数据")

    # 2. 订单金额 TOP10
    with st.container(border=True):
        st.subheader("💰 订单金额 TOP10")
        top10_amount = chart_utils.get_order_amount_top10()
        if not top10_amount.empty:
            st.bar_chart(top10_amount, x="orderid", y="amount", use_container_width=True, color="#A8E6CF")
        else:
            st.info("暂无订单")

with col2:
    # 3. 商品销量 TOP10
    with st.container(border=True):
        st.subheader("📦 商品销量 TOP10")
        top10_product = chart_utils.get_product_sales_top10()
        if not top10_product.empty:
            st.bar_chart(top10_product, x="productid", y="sales", use_container_width=True, color="#FFB5B5")
        else:
            st.info("暂无商品销量")

    # 4. 用户订单频次
    with st.container(border=True):
        st.subheader("👥 用户订单频次分布")
        freq = chart_utils.get_user_order_frequency()
        if not freq.empty:
            st.bar_chart(freq, use_container_width=True, color="#FFD9B7")
        else:
            st.info("暂无用户订单数据")

# ===================== 底部 =====================
st.divider()
st.success(f"✅ 数据看板加载成功 | 更新时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")