import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import psycopg2
import pandas as pd

DB_CONFIG = {
    "host": "47.103.209.249",
    "port": 54321,
    "user": "system",
    "password": "18Monkey",
    "database": "customerorder"
}

def get_sync_conn():
    return psycopg2.connect(**DB_CONFIG)

# ===================== 1. 订单趋势 =====================
def get_order_trend(days=30):
    conn = get_sync_conn()
    try:
        query = """
            SELECT DATE(submitdate) AS date,
                   COUNT(orderid) AS cnt,
                   SUM(discountedmoney) AS amount
            FROM customerorder
            GROUP BY DATE(submitdate)
            ORDER BY DATE(submitdate)
            LIMIT %s;
        """
        df = pd.read_sql(query, conn, params=(days,))
        return df
    finally:
        conn.close()

# ===================== 2. 订单金额 TOP10 =====================
def get_order_amount_top10():
    conn = get_sync_conn()
    try:
        query = """
            SELECT orderid, discountedmoney AS amount
            FROM customerorder
            ORDER BY discountedmoney DESC
            LIMIT 10;
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()

# ===================== 3. 商品销量 TOP10（真实表名） =====================
def get_product_sales_top10():
    conn = get_sync_conn()
    try:
        query = """
            SELECT productid, SUM(quantity) AS sales
            FROM customerorder_detail
            GROUP BY productid
            ORDER BY SUM(quantity) DESC
            LIMIT 10;
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()

# ===================== 5. 用户订单频次 =====================
def get_user_order_frequency():
    conn = get_sync_conn()
    try:
        query = """
            SELECT memberid, COUNT(orderid) AS order_cnt
            FROM customerorder
            GROUP BY memberid;
        """
        df = pd.read_sql(query, conn)
        if not df.empty:
            df["freq_label"] = pd.cut(
                df["order_cnt"],
                bins=[0, 1, 5, 9999],
                labels=["1次", "2-5次", "≥6次"]
            )
            return df["freq_label"].value_counts().sort_index()
        return pd.Series()
    finally:
        conn.close()