import asyncio
from datetime import datetime
from sqlalchemy import select
from backend_app.db import WarehouseStock, StockInRecord
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg    
DATABASE_URL = "postgresql+asyncpg://system:18Monkey@localhost:54321/CustomerOrder"

# 定义一个伪造的版本获取函数
def mocked_get_server_version_info(self, connection):
    return (12, 0, 0)  # 告诉 SQLAlchemy 这是一个 PostgreSQL 12

# 将 PostgreSQL 的 asyncpg 方言类中的方法替换掉
PGDialect_asyncpg._get_server_version_info = mocked_get_server_version_info

engine = create_async_engine(
    DATABASE_URL,
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def initialize_stock_from_current_async(async_session_factory):
    """
    异步版本的库存初始化函数
    """
    async with async_session_factory() as session:
        try:
            # 1. 异步获取当前所有库存数据
            # 注意：异步 ORM 推荐使用 select(...) 配合 session.execute()
            result = await session.execute(select(WarehouseStock))
            current_stocks = result.scalars().all()
            
            print(f"正在处理 {len(current_stocks)} 条库存记录...")

            for stock in current_stocks:
                # 记录原始数值
                original_qty = stock.quantity
                
                # 2. 将实时库存清零
                stock.quantity = 0
                
                # 3. 补充入库记录
                if original_qty > 0:
                    new_in = StockInRecord(
                        warehouseid=stock.warehouseid,
                        productid=stock.productid,
                        in_quantity=original_qty,
                        operator="INIT_SYSTEM_ASYNC_RECON",
                        in_date=datetime.now()
                    )
                    session.add(new_in)
            
            # 确保清零操作先生效（防止触发器逻辑冲突）
            await session.flush()

            # 4. 提交事务
            await session.commit()
            print("🎉 异步初始化完成：库存已成功重置并生成流水。")

        except Exception as e:
            await session.rollback()
            print(f"❌ 异步操作失败，已回滚: {e}")
            raise e
        

import random
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from backend_app.db import WarehouseStock, StockOutRecord

async def seed_historical_data_safe(async_session_factory, count=2000):
    async with async_session_factory() as session:
        try:
            # 1. 获取有效商品和仓库
            result = await session.execute(select(WarehouseStock.productid, WarehouseStock.warehouseid))
            targets = result.all()
            
            print(f"正在生成 {count} 条历史流水（入库+出库对冲）...")

            for _ in range(count):
                pid, wid = random.choice(targets)
                
                # 随机日期 (2023-2025)
                start_date = datetime(2023, 1, 1)
                end_date = datetime(2025, 12, 31)
                historical_date = start_date + timedelta(
                    days=random.randrange((end_date - start_date).days),
                    seconds=random.randrange(86400)
                )

                qty = random.randint(1, 20)

                # --- 关键：先入库，再出库，确保触发器不报错 ---
                # 生成一条比出库早 1 小时的入库记录
                new_in = StockInRecord(
                    warehouseid=wid,
                    productid=pid,
                    in_quantity=qty + random.randint(5, 10), # 入库量略大于出库量，保持余货
                    operator="HISTORIC_REFILL",
                    in_date=historical_date - timedelta(hours=1)
                )
                
                new_out = StockOutRecord(
                    warehouseid=wid,
                    productid=pid,
                    out_quantity=qty,
                    operator="HISTORIC_SYNC",
                    out_date=historical_date
                )
                
                session.add(new_in)
                session.add(new_out)
                
                # 每 200 条 flush 一次，减轻事务压力
                if _ % 200 == 0:
                    await session.flush()

            await session.commit()
            print(f"🎉 成功补充 {count} 对历史出入库流水，库存逻辑平衡。")

        except Exception as e:
            await session.rollback()
            print(f"❌ 模拟失败: {e}")

if __name__ == "__main__":
    # 假设你的 async_session_maker 已经按照你提供的补丁逻辑定义好了
    try:
        asyncio.run(seed_historical_data_safe(async_session_maker, count=2000))
    except KeyboardInterrupt:
        pass