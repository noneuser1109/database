import pandas as pd
import streamlit as st
import db_utils
import psycopg
from psycopg.rows import dict_row
from datetime import datetime

# 获取全局共享的连接池
pool = db_utils.get_db_pool()

def distribute_inventory(product_id, required_qty, target_lat, target_lon):
    """
    根据曼哈顿距离派发货物
    :param product_id: 商品ID
    :param required_qty: 需要的总数量
    :param target_lat: 收货地纬度
    :param target_lon: 收货地经度
    """
    # 1. 获取该商品的仓库分布数据 (调用你之前的函数)
    df_inventory = db_utils.get_product_location_data(product_id)

    if df_inventory.empty:
        return None, "库存不足或未找到商品"

    # 2. 计算曼哈顿距离
    # 距离 = |lat1 - lat2| + |lon1 - lon2|
    df_inventory['distance'] = (
            (df_inventory['lat'] - target_lat).abs() +
            (df_inventory['lon'] - target_lon).abs()
    )

    # 3. 按距离从小到大排序 (就近原则)
    df_sorted = df_inventory.sort_values(by='distance').reset_index(drop=True)

    # 4. 模拟派发逻辑
    dispatch_plan = []
    remaining_needed = required_qty

    for index, row in df_sorted.iterrows():
        if remaining_needed <= 0:
            break

        stock_available = row['total_quantity']
        # 确定从当前仓库拿取的数量
        take_qty = min(remaining_needed, stock_available)

        if take_qty > 0:
            dispatch_plan.append({
                "仓库地址": row['fulladdress'],
                "派发数量": take_qty,
                "剩余库存": stock_available - take_qty,
                "距离系数": round(row['distance'], 4)
            })
            remaining_needed -= take_qty

    # 5. 检查最终是否满足需求
    if remaining_needed > 0:
        return pd.DataFrame(dispatch_plan), f"库存不足，还缺 {remaining_needed} 件"

    return pd.DataFrame(dispatch_plan), "全部分配成功"

@st.cache_data(ttl=3600)
def get_order_items_with_location(order_id: str):
    """
    联合查询：获取订单内每种货物的名称、数量以及该订单收货地址的经纬度
    """
    query = """
        SELECT 
            p.productname, 
            p.productid,
            d.quantity, 
            ag.latitude, 
            ag.longitude
        FROM customerorder_detail d
        JOIN productinfo p ON d.productid = p.productid
        JOIN customerorder_shipment s ON d.orderid = s.orderid
        JOIN memberaddress ma ON s.memberaddressid = ma.addressrecid
        JOIN address_geocoding ag ON ma.addressgeocodeid = ag.addressid
        WHERE d.orderid = %s
    """
    try:
        # 使用你之前定义的全局 pool
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (order_id,))
                return cur.fetchall()
    except Exception as e:
        st.error(f"查询订单位置及明细失败: {e}")
        return []


def process_full_order_distribution(order_id):
    """
    获取订单明细及位置，并为每个商品计算派发方案
    """
    # 1. 获取订单明细与目标位置
    items_data = get_order_items_with_location(order_id)

    if not items_data:
        st.warning("未找到订单明细或地址信息。")
        return

    # 2. 提取公共目标位置 (所有商品共用一个收货地址)
    target_lat = items_data[0]['latitude']
    target_lon = items_data[0]['longitude']

    st.write(f"### 📍 配送目标坐标: ({target_lat}, {target_lon})")
    num_item = len(items_data)
    cnt = 0
    # 3. 循环处理每个商品
    for item in items_data:
        p_name = item['productname']
        p_id = item['productid']
        needed_qty = item['quantity']

        st.markdown(f"#### 📦 商品: {p_name} (需 {needed_qty} 件)")

        # 调用你的曼哈顿距离派发函数
        df_plan, status_msg = distribute_inventory(p_id, needed_qty, target_lat, target_lon)

        # 4. 展示结果
        if df_plan is not None:
            if "库存不足" in status_msg:
                st.error(f"⚠️ {status_msg}")
            else:
                cnt += 1
                if cnt == num_item:
                    insert_order_transition_logs(order_id)
                st.success(f"✅ {status_msg}")

            # 使用 dataframe 展示派发路径
            st.dataframe(df_plan, use_container_width=True)
        else:
            st.error(f"❌ 无法获取商品 {p_name} 的库存分布数据。")


def insert_order_transition_logs(order_id):
    """
    为指定 orderid 顺序插入两条状态变更日志
    1. PAID_NOT_SHIPPED -> SCHEDULED_SHIPPING
    2. SCHEDULED_SHIPPING -> SHIPPED_NOT_RECEIVED
    """
    # 数据库连接信息

    # 定义两条日志的状态转换和备注信息
    log_data = [
        ('PAID_NOT_SHIPPED', 'SCHEDULED_SHIPPING', '商家安排物流'),
        ('SCHEDULED_SHIPPING', 'SHIPPED_NOT_RECEIVED', '商品已发出，等待买家收货')
    ]

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for from_state, to_state, remark in log_data:
                    # SQL 逻辑：
                    # logid: 通过子查询获取当前最大值并加 1
                    # changetime: 使用数据库内置的 CURRENT_TIMESTAMP 获取当前时间
                    sql = """
                          INSERT INTO customerorder_statuslog (logid, orderid, fromstate, tostate, changetime, changer, \
                                                               remark) \
                          VALUES ((SELECT COALESCE(MAX(logid), 0) + 1 FROM customerorder_statuslog), \
                                  %s, %s, %s, CURRENT_TIMESTAMP, %s, %s) \
                          """
                    # 执行插入，changer 固定为 'Merchant'
                    cur.execute(sql, (order_id, from_state, to_state, 'Merchant', remark))

                # 提交事务
                conn.commit()
                print(f"订单 {order_id} 的两条状态日志已成功插入。")

    except Exception as e:
        print(f"数据库操作失败: {e}")

orderid = st.text_input("订单号：")
if st.button("规划发货"):
    process_full_order_distribution(orderid)