import streamlit as st
import pandas as pd
import numpy as np
import utils
import pydeck as pdk  # 引入 pydeck 处理高级地图
import json
import base64
st.title("📦 货物分布地理分析")

# --- 1. 模拟 Searchbox 的原生实现 ---
# 先放一个搜索框，让用户输入关键词
search_query = st.text_input("🔍 搜索货物：", placeholder="输入编号或名称关键词...")

product_id_input = None

if search_query:
    # 调用你之前写的 utils 匹配函数
    # 假设返回 [(显示名, ID), ...]
    with st.spinner("正在匹配货物..."):
        suggestions = utils.search_product_ids_and_names(search_query)
    
    if suggestions:
        # 用官方 selectbox 展示匹配结果
        # format_func 确保下拉列表显示的是“名称 [ID]”
        selected_tuple = st.selectbox(
            "找到以下匹配项，请选择：",
            options=suggestions,
            index=None,
            format_func=lambda x: x[0]
        )
        # 获取元组中的 ID 部分
        if selected_tuple:
            product_id_input = selected_tuple[1]
    else:
        st.warning("❌ 未找到匹配的货物，请尝试其他关键词")
else:
    st.info("💡 请在上方输入框输入货物名称或编号开始分析")

st.write(f"当前选中 ID: **{product_id_input}**")
if product_id_input:
    df = utils.get_product_location_data(product_id_input)

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


        TDT_TK = "61c25cc0c063564e816f20e0a920aa38"
        
        # 构造符合 Mapbox Style Spec 的配置
        tdt_style = {
            "version": 8,
            "sources": {
                "tdt-vec": {
                    "type": "raster",
                    "tiles": [
                        f"https://t0.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={{x}}&TILEROW={{y}}&TILEMATRIX={{z}}&tk={TDT_TK}"
                    ],
                    "tileSize": 256,
                },
                "tdt-cva": {
                    "type": "raster",
                    "tiles": [
                        f"https://t0.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={{x}}&TILEROW={{y}}&TILEMATRIX={{z}}&tk={TDT_TK}"
                    ],
                    "tileSize": 256,
                },
            },
            "layers": [
                {"id": "tdt-vec-layer", "type": "raster", "source": "tdt-vec", "minzoom": 0, "maxzoom": 18},
                {"id": "tdt-cva-layer", "type": "raster", "source": "tdt-cva", "minzoom": 0, "maxzoom": 18},
            ],
        }
        
        # 2. 核心修复：将字典转为 Base64 编码的字符串
        string_style = json.dumps(tdt_style)
        encoded_style = base64.b64encode(string_style.encode("utf-8")).decode("utf-8")
        style_url = f"data:application/json;base64,{encoded_style}"
        
        # 5. 渲染地图
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            # 关键点 1: 必须指定 map_provider 为 "mapbox"
            map_provider="mapbox",
            map_style=style_url, # 使用自定义的底图配置
            tooltip={"text": "地址: {fulladdress}\n库存量: {total_quantity}"}
        ))

        st.caption("底图来源：国家地理信息公共服务平台（天地图） | 审图号：GS(2025)1508号 | 甲测资字 11110974")

        
        # --- 辅助数据展示 ---
        st.dataframe(df[['fulladdress', 'total_quantity', 'lat', 'lon']], hide_index=True)
    else:
        st.info("未找到符合条件的库存记录。")