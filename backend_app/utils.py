import datetime
import random
import asyncio

async def generate_order_metadata_async():
    """
    异步生成订单号、快递单号和统一的时间戳
    返回: (order_id, tracking_no, current_time)
    """
    # 获取当前时间（非阻塞获取）
    now_dt = datetime.datetime.now()
    time_str = now_dt.strftime('%Y%m%d%H%M%S')
    
    # 使用 asyncio.to_thread 处理可能的计算压力（虽然此处极轻量，但在高并发下是好习惯）
    # 或者直接运行，因为 random 在这里阻塞时间极短
    order_id_suffix = random.randint(100, 999)
    tracking_no_val = random.randint(10**11, 10**12 - 1)
    
    order_id = f"ORD{time_str}{order_id_suffix}"
    tracking_no = f"SF{tracking_no_val}"
    
    # 模拟微小的异步切划（可选，确保出让控制权）
    await asyncio.sleep(0) 
    
    return order_id, tracking_no, now_dt

from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import WarehouseInventory, OrderProductStockInfo, MultiProductStockResponse
from .db import CustomerOrder, CustomerOrderShipment, MemberAddress, CustomerOrderDetail, ProductInfo, WarehouseStock, WarehouseInfo
from sqlalchemy.sql import select

async def get_multi_product_storage_locations(order_id: str, session: AsyncSession):
    """
    获取订单中所有商品及其在各个仓库的实时库存与位置
    """
    # 1. 查询订单基本信息及商品明细
    stmt = (
        select(CustomerOrder)
        .options(
            # 加载客户收货地址
            joinedload(CustomerOrder.shipment)
                .joinedload(CustomerOrderShipment.address)
                .joinedload(MemberAddress.address_detail),
            # 加载订单明细及其对应的所有仓库库存
            joinedload(CustomerOrder.details)
                .joinedload(CustomerOrderDetail.product)
                .joinedload(ProductInfo.stocks) # 关联到 warehouse_stock
                .joinedload(WarehouseStock.warehouse) # 关联到 warehouseinfo
                .joinedload(WarehouseInfo.address) # 关联到仓库的经纬度
        )
        .where(CustomerOrder.orderid == order_id)
    )

    result = await session.execute(stmt)
    order = result.unique().scalar_one_or_none()

    if not order:
        return None

    # 提取客户位置
    cust_geo = order.shipment.address.address_detail
    
    products_data = []
    
    # 2. 遍历订单明细，构建商品-仓库映射
    for detail in order.details:
        storage_list = []
        # 遍历该产品在所有仓库的库存记录
        for stock in detail.product.stocks:
            if stock.warehouse and stock.warehouse.address:
                storage_list.append(WarehouseInventory(
                    warehouse_id=stock.warehouseid,
                    warehouse_name=stock.warehouse.warehousename,
                    latitude=float(stock.warehouse.address.latitude),
                    longitude=float(stock.warehouse.address.longitude),
                    available_qty=stock.quantity
                ))
        
        products_data.append(OrderProductStockInfo(
            product_id=detail.productid,
            product_name=detail.product.productname,
            order_quantity=detail.quantity,
            storage_locations=storage_list
        ))

    return MultiProductStockResponse(
        order_id=order.orderid,
        customer_latitude=float(cust_geo.latitude),
        customer_longitude=float(cust_geo.longitude),
        products=products_data
    )

from passlib.context import CryptContext

# 初始化加密上下文，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class PasswordHelper:
    @staticmethod
    def hash(password: str) -> str:
        """将明文密码转换为哈希值"""
        return pwd_context.hash(password)

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """验证明文密码是否与哈希值匹配"""
        return pwd_context.verify(plain_password, hashed_password)

# 实例化一个单例供全局使用
password_helper = PasswordHelper()