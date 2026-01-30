import streamlit as st
import db_utils
import psycopg


def insert_completion_logs(order_id):
    """
    为订单插入完成收货及待评价状态日志
    """
    # 定义要插入的两条日志数据流转
    # 格式: (fromstate, tostate, changer, remark)
    log_steps = [
        ('SHIPPED_NOT_RECEIVED', 'NOT_RATED', 'User', '买家确认收货'),
    ]

    try:
        # 使用你现有的数据库连接逻辑
        conn = db_utils.init_db_connection()
        with conn.cursor() as cur:
            for from_state, to_state, changer, remark in log_steps:
                # SQL 逻辑：
                # 1. logid: 使用子查询获取当前 MAX(logid) + 1，确保属性不重复
                # 2. changetime: 使用 CURRENT_TIMESTAMP 获取当前数据库系统时间
                sql = """
                      INSERT INTO customerorder_statuslog (logid, orderid, fromstate, tostate, changetime, changer, \
                                                           remark) \
                      VALUES ((SELECT COALESCE(MAX(logid), 0) + 1 FROM customerorder_statuslog), \
                              %s, %s, %s, CURRENT_TIMESTAMP, %s, %s) \
                      """
                cur.execute(sql, (order_id, from_state, to_state, changer, remark))

            conn.commit()
            return True
    except Exception as e:
        print(f"插入完成日志失败: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def insert_success_logs(order_id):
    """
    为订单插入完成收货及待评价状态日志
    """
    # 定义要插入的两条日志数据流转
    # 格式: (fromstate, tostate, changer, remark)
    log_steps = [
        ('NOT_RATED', 'SUCCESS', 'System', '交易成功，已评价'),
    ]

    try:
        # 使用你现有的数据库连接逻辑
        conn = db_utils.init_db_connection()
        with conn.cursor() as cur:
            for from_state, to_state, changer, remark in log_steps:
                # SQL 逻辑：
                # 1. logid: 使用子查询获取当前 MAX(logid) + 1，确保属性不重复
                # 2. changetime: 使用 CURRENT_TIMESTAMP 获取当前数据库系统时间
                sql = """
                      INSERT INTO customerorder_statuslog (logid, orderid, fromstate, tostate, changetime, changer, \
                                                           remark) \
                      VALUES ((SELECT COALESCE(MAX(logid), 0) + 1 FROM customerorder_statuslog), \
                              %s, %s, %s, CURRENT_TIMESTAMP, %s, %s) \
                      """
                cur.execute(sql, (order_id, from_state, to_state, changer, remark))

            conn.commit()
            return True
    except Exception as e:
        print(f"插入完成日志失败: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def update_order_remark(order_id, remark_text):
    """
    根据 orderid 更新 customerorder 表中的 customerremark 字段
    """

    sql = """
          UPDATE customerorder
          SET customerremark  = %s,
              updatetimestamp = CURRENT_TIMESTAMP
          WHERE orderid = %s \
          """
    conn = db_utils.init_db_connection()
    try:
        with conn.cursor() as cur:
            # 执行更新
            cur.execute(sql, (remark_text, order_id))

            # 检查是否成功更新了行
            if cur.rowcount > 0:
                conn.commit()
                print(f"✅ 订单 {order_id} 的备注已成功更新。")
                return True
            else:
                print(f"⚠️ 未找到订单号为 {order_id} 的记录。")
                return False
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        return False

st.header("📝 订单确认收货与评价")

# 1. 输入订单号
order_id_input = st.text_input("请输入您的订单号", placeholder="例如: ORD20250222...")

if order_id_input:
    # 这里建议先查询一下订单当前状态是否为“已发货”
    # 假设我们只允许对已发货的订单进行确认收货

    with st.container(border=True):
        st.info(f"正在为订单 **{order_id_input}** 办理收货")

        # 2. 输入评价内容
        # max_chars=100 对应数据库 character varying(100 char) 限制
        review_comment = st.text_area(
            "撰写评价",
            placeholder="商品质量如何？物流快吗？",
            max_chars=100
        )

        # 3. 确认收货按钮
        if st.button("确认收货", type="primary", use_container_width=True):
            # 4. 执行数据库写入
            # 逻辑：logid 自动 MAX+1，时间为当前时间
            success = insert_completion_logs(order_id_input)

            if success:
                st.success("✅ 操作成功！订单已完结。")
                if review_comment.strip():
                    review_success = update_order_remark(order_id_input, review_comment)

                    if review_success:
                        insert_success_logs(order_id_input)
                st.balloons()
            else:
                st.error("提交失败，请检查订单号是否正确。")


