import streamlit as st
import utils
import pandas as pd
from datetime import datetime, date
import pydeck as pdk
import json
import base64

def render_cluster_map(df: pd.DataFrame):
    """
    使用天地图底图和 ColumnLayer 渲染带颜色的聚类结果
    """
    if df.empty:
        st.warning("暂无数据可供渲染")
        return

    # --- 1. 颜色映射逻辑 ---
    # 定义 7 种配色（RGBA），用于区分不同 cluster_id
    CLUSTER_COLORS = [
        [255, 99, 71, 200],   # Tomato
        [60, 179, 113, 200],  # Medium Sea Green
        [30, 144, 255, 200],  # Dodger Blue
        [255, 215, 0, 200],   # Gold
        [153, 50, 204, 200],  # Dark Orchid
        [255, 69, 0, 200],    # Orange Red
        [0, 206, 209, 200],   # Dark Turquoise
    ]

    def assign_color(row):
        # 如果没有执行聚类，统一给蓝色
        if "cluster_id" not in row or pd.isna(row["cluster_id"]):
            return [0, 128, 255, 200]
        idx = int(float(row["cluster_id"])) % len(CLUSTER_COLORS)
        return CLUSTER_COLORS[idx]

    # 生成颜色列
    df["fill_color"] = df.apply(assign_color, axis=1)

    # --- 2. 动态计算聚焦视口 ---
    avg_lat = df["latitude"].mean()
    avg_lon = df["longitude"].mean()
    initial_zoom = 12 if len(df) == 1 else 10

    view_state = pdk.ViewState(
        latitude=avg_lat,
        longitude=avg_lon,
        zoom=initial_zoom,
        pitch=45, 
    )

    # --- 3. 配置 ColumnLayer ---
    layer = pdk.Layer(
        "ColumnLayer",
        df,
        get_position=["longitude", "latitude"],
        get_elevation=500,  # 如果有订单重量/数量字段，可以换成具体列名
        elevation_scale=1,
        radius=100,         # 柱子物理半径
        get_fill_color="fill_color", # 使用我们动态分配的颜色
        pickable=True,
        auto_highlight=True,
    )

    # --- 4. 构造天地图 Style (符合 Mapbox 规范) ---
    TDT_TK = "61c25cc0c063564e816f20e0a920aa38" # 你的天地图 Token
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
    
    # 编码样式字符串
    string_style = json.dumps(tdt_style)
    encoded_style = base64.b64encode(string_style.encode("utf-8")).decode("utf-8")
    style_url = f"data:application/json;base64,{encoded_style}"

    # --- 5. 渲染地图 ---
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_provider="mapbox",
        map_style=style_url, 
        tooltip={
            "html": "<b>订单号:</b> {orderid}<br><b>区域 ID:</b> {cluster_id}",
            "style": {"color": "white"}
        }
    ))

    st.caption("底图来源：国家地理信息公共服务平台（天地图） | 审图号：GS(2025)1508号 | 甲测资字 11110974")

st.set_page_config(page_title="订单配送调度", layout="wide")


# --- 2. 页面标题 ---
st.title("🚛 配送任务调度中心")
st.caption("筛选订单、确认位置并执行自动聚类方案")

# --- 3. 顶部筛选区 (取代侧边栏) ---
# 使用 expander 默认展开，用户查询完可以收起以节省空间
with st.expander("🔍 筛选与同步选项", expanded=True):
    # 第一行：状态多选和时间范围
    c1, c2 = st.columns([2, 1])
    with c1:
        status_options = ["UNPAID", "CLOSED", "PAID_NOT_SHIPPED", "SCHECULED_SHIPPING", "SHIPPED_UNPAID", "SHIPPED_NOT_RECEIVED", "NOT_RATED", "SUCCESS", "APPLY_REFUND", "REFUND_SUCCESS"]
        selected_status = st.multiselect("订单状态 (符合任一即可)", status_options, default=["PAID_NOT_SHIPPED"])
    with c2:
        today = date.today()
        date_range = st.date_input("提交日期范围", [today, today])

    # 第二行：加急和提交按钮
    c3, c4, c5 = st.columns([1, 1, 1])
    with c3:
        is_emergency = st.checkbox("🔥 只看加急订单", value=False)
    with c5:
        # 将按钮靠右对齐
        search_btn = st.button("同步实时订单", type="primary", use_container_width=True)

# --- 4. 数据处理与展示 ---
if search_btn:
    start_dt = datetime.combine(date_range[0], datetime.min.time()) if len(date_range) >= 1 else None
    end_dt = datetime.combine(date_range[1], datetime.max.time()) if len(date_range) == 2 else None
    
    data = utils.fetch_orders(selected_status, start_dt, end_dt, is_emergency)
    if data:
        df = pd.DataFrame(data)
        df.insert(0, "selected", True) # 默认全选
        st.session_state.df_orders = df
    else:
        st.session_state.df_orders = pd.DataFrame()
        st.info("查无数据")

# --- 5. 核心展示区 ---
if "df_orders" in st.session_state and not st.session_state.df_orders.empty:
    # 左右布局：左边表格，右边地图预览（如果有经纬度）
    tab1, tab2 = st.tabs(["📋 订单清单", "🗺️ 空间分布预览"])
    
    with tab1:
        edited_df = st.data_editor(
            st.session_state.df_orders,
            column_config={
                "selected": st.column_config.CheckboxColumn("派送", default=True),
                "orderid": "订单号",
                "submitdate": st.column_config.DatetimeColumn("时间", format="MM-DD HH:mm"),
                "orderstate": "状态",
                "isemergency": "加急",
                "lat": None, "lon": None 
            },
            disabled=["orderid", "submitdate", "orderstate", "isemergency"],
            hide_index=True,
            use_container_width=True,
            key="dispatch_editor"
        )
    
    with tab2:
        # 1. 筛选并清洗数据
        # 确保列名正确，并包含 cluster_id
        mask = (edited_df["selected"] == True)
        map_df = edited_df[mask].copy()
        
        # 转换坐标为 float 确保 pydeck 能识别
        map_df["latitude"] = pd.to_numeric(map_df["latitude"], errors='coerce')
        map_df["longitude"] = pd.to_numeric(map_df["longitude"], errors='coerce')
        map_df = map_df.dropna(subset=["latitude", "longitude"])

        if not map_df.empty:
            render_cluster_map(map_df)
        else:
            st.warning("所选订单无有效坐标信息")

    # --- 6. 底部聚类操作 ---
    st.write("---")
    foot_c1, foot_c2, foot_c3 = st.columns([1, 1, 2])
    with foot_c1:
        num_drivers = st.number_input("拟出动配送员数量", 1, 10, 3)
    with foot_c2:
        st.markdown("<br>", unsafe_allow_html=True) 
        if st.button("🚀 生成聚类派单建议", type="primary", use_container_width=True):
            
            # 调用专门的同步函数
            with st.spinner("正在计算配送路径..."):
                result = utils.send_cluster_request(edited_df, num_drivers)
            
            # 处理返回结果
            if result:
                if "error" in result:
                    st.error(result["error"])
                else:
                    clusters = result.get("clusters", {})
                    # 反向映射：{ "ORD1": 0, "ORD2": 0, "ORD3": 1 }
                    id_to_cluster = {oid: cid for cid, oids in clusters.items() for oid in oids}
                    
                    # 将聚类 ID 合并到 session_state 的数据中
                    st.session_state.df_orders['cluster_id'] = st.session_state.df_orders['orderid'].map(id_to_cluster)
                    st.toast(f"✅ 成功：划分为 {result.get('total_clusters')} 个区域", icon="🎯")
                    # 强制刷新以展示下方结果
                    st.rerun()
            else:
                st.warning("⚠️ 未勾选任何订单，请在上方表格中选择。")

else:
    st.info("请先配置上方筛选条件并点击同步按钮")