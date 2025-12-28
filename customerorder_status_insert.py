import random
from datetime import datetime, timedelta
import psycopg  # 导入 psycopg3
import sys

# from psycopg import extras # psycopg3 中通常不需要 extras 来实现字典游标，可以直接设置 row_factory

# --- 1. 数据库配置（请根据您的实际环境修改） ---
DB_CONFIG = {
    "host": "localhost",  # 例如: "localhost"
    "dbname": "CustomerOrder",
    "user": "system",
    "password": "18Monkey",
    "port": 54321  # KingbaseES 默认端口可能为 54321 或 54300, 请确认
}

# --- 2. 订单和流程配置（保持不变） ---
START_ORDER_ID = 1
END_ORDER_ID = 1000

# 定义订单状态流转 (tostate, changer, remark)
FLOWS = {
    "SUCCESS": [
        ('PAID_NOT_SHIPPED', 'User', '用户完成支付'),
        ('SCHEDULED_SHIPPING', 'Merchant', '商家安排物流'),
        ('SHIPPED_NOT_RECEIVED', 'Merchant', '商品已发出，等待买家收货'),
        ('SUCCESS', 'User', '买家确认收货'),
        ('NOT_RATED', 'System', '交易成功，未评价状态')
    ],
    "CLOSED": [
        ('CLOSED', 'System', '超时未付款，系统自动关闭交易')
    ],
    "REFUND_SUCCESS": [
        ('PAID_NOT_SHIPPED', 'User', '用户完成支付'),
        ('APPLY_REFUND', 'User', '用户申请退款：拍错商品'),
        ('REFUND_SUCCESS', 'Merchant', '商家同意退款，退款成功')
    ]
}

# 概率分配
FLOW_PROBABILITIES = {
    "SUCCESS": 0.75,
    "CLOSED": 0.20,
    "REFUND_SUCCESS": 0.05
}


# --- 3. 辅助函数 ---
def get_random_timedelta(min_minutes, max_minutes):
    """生成一个随机的时间间隔 (timedelta)"""
    minutes = random.randint(min_minutes, max_minutes)
    return timedelta(minutes=minutes)


def generate_sql_log(order_id_num, flow_key, submit_date):
    """为单个订单生成 SQL 记录，基于查询到的 submit_date"""
    order_id = f"ORD{order_id_num:06d}"
    logs = []
    current_time = submit_date  # 初始时间设为 submit_date
    from_state = 'UNPAID'

    steps = FLOWS[flow_key]

    for i, step in enumerate(steps):
        to_state, changer, remark = step

        if i == 0:
            # 流程第一步: submitdate + 5分钟到6小时
            time_delta = get_random_timedelta(5, 6 * 60)
            current_time = current_time + time_delta
        else:
            # 后续步骤: 前一条记录 + 5分钟到48小时
            time_delta = get_random_timedelta(5, 48 * 60)
            current_time = current_time + time_delta

        # 注意：psycopg3 推荐使用参数化查询来插入数据，这里为了生成可直接执行的 SQL 文本，仍然使用字符串格式化
        changetime_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

        log = f"('{order_id}', '{from_state}', '{to_state}', '{changetime_str}', '{changer}', '{remark}')"
        logs.append(log)

        from_state = to_state

    return ",\n".join(logs)


# --- 4. 主生成逻辑 ---
def main():
    conn = None
    try:
        # 连接数据库
        print("尝试连接 KingbaseES 数据库...")
        # psycopg3 使用 connect() 而不是 connect(**DB_CONFIG)
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("数据库连接成功。")

        # 准备订单列表和流程分配
        total_orders = END_ORDER_ID - START_ORDER_ID + 1
        num_success = int(total_orders * FLOW_PROBABILITIES['SUCCESS'])
        num_closed = int(total_orders * FLOW_PROBABILITIES['CLOSED'])
        num_refund = total_orders - num_success - num_closed

        flow_counts = {"SUCCESS": num_success, "CLOSED": num_closed, "REFUND_SUCCESS": num_refund}
        order_flow_list = []
        for flow, count in flow_counts.items():
            order_flow_list.extend([flow] * count)
        random.shuffle(order_flow_list)

        print("INSERT INTO customerorder_statuslog (orderid, fromstate, tostate, changetime, changer, remark) VALUES")

        for i, flow_key in enumerate(order_flow_list):
            order_num = START_ORDER_ID + i
            order_id = f"ORD{order_num:06d}"

            # --- 核心查询部分 ---
            # 这里的 order_id 我们按照 1-1000 编号查询，请确保 customerorder 表中有这些记录
            # 在实际应用中，强烈建议使用参数化查询来避免 SQL 注入
            fetch_query = f"SELECT submitdate FROM customerorder WHERE orderid = '{order_id}';"
            cur.execute(fetch_query)
            # psycopg3 的 fetchone() 返回单个记录
            result = cur.fetchone()

            if result and result[0]:
                submit_date = result[0]
                sql_log = generate_sql_log(order_num, flow_key, submit_date)
            else:
                # 如果查询失败或无数据，使用一个默认值作为 submit_date (例如: 订单提交失败)
                print(f"-- 警告：未找到订单 {order_id} 的 submitdate，跳过生成。", file=sys.stderr)
                continue

            # 打印 SQL
            if i < total_orders - 1 and (i + 1) < len(order_flow_list):
                print(sql_log + ",")
            else:
                # 确保最后一个 INSERT 语句以分号结束
                print(sql_log + ";")

    except Exception as error:
        print(f"数据库操作失败: {error}", file=sys.stderr)
    finally:
        if conn:
            # psycopg3 中 close() 仍然是关闭连接的方法
            conn.close()
            print("\n数据库连接已关闭。")


if __name__ == "__main__":
    main()