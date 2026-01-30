import streamlit as st
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import pydeck as pdk

st.title("🚚 智能物流：订单聚类配送系统")
st.sidebar.header("配置参数")

# --- 1. 参数设置 ---
num_orders = st.sidebar.slider("随机订单数量", 50, 500, 200)
num_clusters = st.sidebar.slider("配送小组数量 (聚类数)", 2, 20, 5)
city_lat = 31.2304  # 以上海为例
city_lon = 121.4737


# --- 2. 生成随机订单数据 ---
@st.cache_data
def generate_data(n, lat, lon):
    # 在城市坐标附近随机生成点
    data = pd.DataFrame({
        'lat': lat + (np.random.randn(n) * 0.05),
        'lon': lon + (np.random.randn(n) * 0.05)
    })
    return data


df = generate_data(num_orders, city_lat, city_lon)

# --- 3. 执行聚类算法 (K-Means) ---
kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
df['cluster'] = kmeans.fit_predict(df[['lat', 'lon']])

# 计算每个聚类的中心点（作为集合配送点）
centers = pd.DataFrame(kmeans.cluster_centers_, columns=['lat', 'lon'])
centers['is_center'] = True

# 为不同聚类生成颜色
colors = [
    [255, 0, 0, 150], [0, 255, 0, 150], [0, 0, 255, 150],
    [255, 255, 0, 150], [255, 0, 255, 150], [0, 255, 255, 150],
    [128, 0, 128, 150], [255, 165, 0, 150]
]
df['color'] = df['cluster'].apply(lambda x: colors[x % len(colors)])

# --- 4. 可视化渲染 ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("订单配送聚类地图")

    # 使用 Pydeck 绘制更丰富的地图
    layer_orders = pdk.Layer(
        "ScatterplotLayer",
        df,
        get_position='[lon, lat]',
        get_color='color',
        get_radius=100,
        pickable=True
    )

    layer_centers = pdk.Layer(
        "ScatterplotLayer",
        centers,
        get_position='[lon, lat]',
        get_color='[0, 0, 0, 255]',  # 黑色表示中心点
        get_radius=300,
        pickable=True
    )

    view_state = pdk.ViewState(latitude=city_lat, longitude=city_lon, zoom=11, pitch=0)

    st.pydeck_chart(pdk.Deck(
        layers=[layer_orders, layer_centers],
        initial_view_state=view_state,
        tooltip={"text": "配送小组: {cluster}"}
    ))

with col2:
    st.subheader("统计信息")
    cluster_counts = df['cluster'].value_counts().sort_index()
    st.write("各组订单分布：")
    st.bar_chart(cluster_counts)

    st.metric("平均每组配送量", f"{num_orders / num_clusters:.1f}")

    if st.checkbox("查看原始数据"):
        st.dataframe(df, height=300)

st.success(f"✅ 已将 {num_orders} 个送货点成功合并为 {num_clusters} 个配送波次。")