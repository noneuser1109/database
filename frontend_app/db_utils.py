import streamlit as st
import psycopg
from psycopg import sql
import os
from dotenv import load_dotenv  # 需安装：pip install python-dotenv
import pandas as pd
from psycopg_pool import ConnectionPool
# 加载.env文件中的环境变量（可选，推荐使用）
load_dotenv()

# ----------------------
# 缓存数据库连接（cache_resource）
# ----------------------
def init_db_connection():
    """初始化并缓存PostgreSQL数据库连接"""
    try:
        # 从环境变量获取配置（避免硬编码敏感信息）
        conn = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "54321")
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        # 这里抛出异常，让主应用处理；也可直接用st.error，但模块化建议抛异常
        raise Exception(f"数据库连接失败：{str(e)}") from e


@st.cache_resource
def get_db_pool():
    """初始化并缓存连接池"""
    try:
        # 构造连接字符串 (DSN)
        conn_info = (
            f"host={os.getenv('DB_HOST', 'localhost')} "
            f"dbname={os.getenv('DB_NAME')} "
            f"user={os.getenv('DB_USER')} "
            f"password={os.getenv('DB_PASSWORD')} "
            f"port={os.getenv('DB_PORT', '54321')}"
        )

        # 初始化连接池
        # min_size: 池中保持的最小空闲连接数
        # max_size: 池中允许的最大连接数
        pool = ConnectionPool(
            conninfo=conn_info,
            min_size=1,
            max_size=10,
            open=True,
            name="streamlit_pool"
        )
        return pool
    except Exception as e:
        st.error(f"无法创建数据库连接池: {e}")
        raise e

def get_product_location_data(product_id):
    # SQL 部分保持不变
    sql = """
          SELECT ag.latitude      as lat, \
                 ag.longitude     as lon, \
                 SUM(ws.quantity) as total_quantity, \
                 ag.fulladdress
          FROM warehouse_stock ws
                   JOIN warehouseinfo wi ON ws.warehouseid = wi.warehouseid
                   JOIN address_geocoding ag ON wi.addressgeocodeid = ag.addressid
          WHERE ws.productid = %s
            AND wi.isactive = TRUE
          GROUP BY ag.addressid, ag.latitude, ag.longitude, ag.fulladdress \
          """
    conn = init_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (product_id,))
            columns = [desc[0] for desc in cur.description]
            results = cur.fetchall()
            return pd.DataFrame(results, columns=columns)
    except Exception as e:
        st.error(f"数据库查询失败: {e}")
        return pd.DataFrame()

# ----------------------
# 缓存查询结果（cache_data）
# ----------------------
@st.cache_data(ttl=60)  # 缓存60秒，可根据需求调整
def run_db_query(query, params=None):
    """执行SQL查询并缓存结果，返回字典列表"""
    # 获取缓存的数据库连接
    conn = init_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            # 无返回结果的SQL（如INSERT/UPDATE），直接提交并返回空
            if cur.description is None:
                conn.commit()
                return []
            # 有返回结果的SQL，转换为字典列表
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            return results
    except Exception as e:
        raise Exception(f"查询执行失败：{str(e)}") from e