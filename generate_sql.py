import random
from datetime import datetime, timedelta


def generate_random_date(start_year, end_year):
    """生成指定年份范围内的随机时间戳，并格式化为 SQL 字符串。"""
    # 定义时间范围：2024-01-01 00:00:00 到 2025-12-31 23:59:59
    start_date = datetime(start_year, 1, 1, 0, 0, 0)
    end_date = datetime(end_year, 12, 31, 23, 59, 59)

    # 计算总秒数差
    time_diff = (end_date - start_date).total_seconds()

    # 随机选择一个秒数
    random_seconds = random.randint(0, int(time_diff))

    # 加上随机秒数得到随机日期时间
    random_datetime = start_date + timedelta(seconds=random_seconds)

    # 格式化为 SQL 接受的字符串格式
    return f"'{random_datetime.strftime('%Y-%m-%d %H:%M:%S')}'"


def generate_sql_inserts(num_records):
    sql_statements = []

    for i in range(1, num_records + 1):
        # 1. 生成 ID (M000001 到 M001000, ORD000001 到 ORD001000)
        member_id = f"M{(i-1)%201+1:06d}"
        order_id = f"ORD{i:06d}"

        # 2. 生成随机日期 (2024-2025)
        submit_date_str = generate_random_date(2024, 2025)

        # 3. 随机生成 isemergency (TRUE 或 FALSE)
        is_emergency = random.choice(['TRUE', 'FALSE', 'FALSE'])

        # 4. 构造 SQL 语句
        sql = (
            f"INSERT INTO customerorder ("
            f"orderid, memberid, orderstate, submitdate, originalmoney, discountedmoney, "
            f"isemergency, conditionfeightfree, updatetimestamp, dataversion"
            f") VALUES ("
            f"'{order_id}', '{member_id}', 'UNPAID', {submit_date_str}, 0, 0, "
            f"{is_emergency}, 5000, {submit_date_str}, 1"
            f");"
        )
        sql_statements.append(sql)

    return "\n".join(sql_statements)


# 生成 1000 条 SQL 语句
generated_sql = generate_sql_inserts(1000)

# 打印生成的 SQL 语句
print(generated_sql)