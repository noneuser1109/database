import streamlit as st
import psycopg
import pandas as pd
import numpy as np
import db_utils
import pydeck as pdk  # 引入 pydeck 处理高级地图


st.title("📦 货物分布地理分析")

product_id_input = st.text_input("请输入货物编号 (ProductID):", placeholder="例如: PROD001")

if product_id_input:
    df = db_utils.get_product_location_data(product_id_input)

    if not df.empty:
        # 1. 数据类型转换
        df['lat'] = df['lat'].astype(float)
        df['lon'] = df['lon'].astype(float)
        df['total_quantity'] = df['total_quantity'].astype(float)

        # 2. 优化半径显示：防止重叠过大
        # 使用平方根处理数量，使大小差异更平滑；同时设置较大的半径缩放以便在微观下观察
        df['radius'] = np.sqrt(df['total_quantity']) * 5

        st.subheader(f"货物 {product_id_input} 的分布热力分析")

        # 3. 定义图层 (ScatterplotLayer)
        layer = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position=["lon", "lat"],
            get_color="[255, 140, 0, 180]",  # 橙色半透明
            get_radius="radius",  # 使用处理后的半径
            radius_min_pixels=3,  # 最小不低于3像素
            radius_max_pixels=30,  # 限制最大像素，防止重叠覆盖整个屏幕
            pickable=True,
        )

        # 4. 动态计算聚焦视口
        # 自动计算中心点和合适的缩放等级
        # zoom 值越高越聚焦。如果有数据，我们把初始 zoom 设为 10-12 左右（城市级）
        avg_lat = df["lat"].mean()
        avg_lon = df["lon"].mean()

        # 如果只有1个点，聚焦更近；如果多个点，缩放稍远
        initial_zoom = 12 if len(df) == 1 else 10

        view_state = pdk.ViewState(
            latitude=avg_lat,
            longitude=avg_lon,
            zoom=initial_zoom,
            pitch=45,  # 增加一点倾斜度，更有空间感
        )

        # 5. 渲染地图
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/light-v9",  # 使用简洁的底图风格
            tooltip={"text": "地址: {fulladdress}\n库存量: {total_quantity}"}
        ))


        layer = pdk.Layer(
            "ColumnLayer",
            df,
            get_position=["lon", "lat"],
            get_elevation="total_quantity",  # 高度代表数量
            elevation_scale=5,  # 高度缩放
            radius=50,  # 柱子的物理半径（米）
            get_fill_color="[0, 128, 255, 200]",
            pickable=True,
            auto_highlight=True,
        )

        # --- 辅助数据展示 ---
        st.dataframe(df[['fulladdress', 'total_quantity', 'lat', 'lon']], hide_index=True)
    else:
        st.info("未找到符合条件的库存记录。")