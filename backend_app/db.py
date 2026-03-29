from collections.abc import AsyncGenerator
import uuid
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, BigInteger, Numeric, UniqueConstraint, Boolean, Integer, Sequence, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID
from fastapi import Depends
from sqlalchemy.sql import func

DATABASE_URL = "postgresql+asyncpg://system:18Monkey@localhost:54321/CustomerOrder"


class Base(DeclarativeBase):
    pass


from sqlalchemy import Column, String, Boolean, DateTime, text, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from datetime import datetime

class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    直接指向旧表 memberinfo，整合了 FastAPI-Users 认证和原有业务逻辑
    """
    __tablename__ = 'memberinfo'

    # --- 1. 身份识别 (ID 映射) ---
    # 插件默认用 id，我们通过 Column 映射到旧表的 memberid 字段
    id: Mapped[str] = mapped_column(String(length=36), name="memberid", primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # --- 2. 原有 MemberInfo 业务字段 ---
    loginname = Column(String(30), unique=True, nullable=True)
    realname = Column(String(30), nullable=True)
    
    # 密码字段：FastAPI-Users 内部会自动处理这个字段的哈希
    hashed_password = Column(String(1024), nullable=False)
    
    # 会员等级：对应你截图中的 integer 类型
    memberlevel = Column(Integer, nullable=False, default=1)

    # --- 3. 时间戳 ---
    registrationdate = Column(
        DateTime, 
        nullable=False, 
        server_default=text('CURRENT_TIMESTAMP')
    )
    updatetimestamp = Column(
        DateTime, 
        nullable=False, 
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=datetime.now
    )

    # --- 4. 补回所有“依赖”关系 ---
    # 之前消失的 posts 依赖加到这里
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    
    # 订单、地址、电话关系
    orders = relationship("CustomerOrder", back_populates="user")
    addresses = relationship("MemberAddress", back_populates="user", cascade="all, delete-orphan")
    phones = relationship("MemberPhone", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id='{self.id}', loginname='{self.loginname}')>"


class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("memberinfo.memberid"), nullable=False)
    caption = Column(Text)
    url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="posts")

class AddressGeocoding(Base):
    __tablename__ = "address_geocoding"

    addr_geo_seq = Sequence('address_geocoding_addressid_seq', start=200)
    
    addressid = Column(BigInteger, addr_geo_seq, primary_key=True, server_default=addr_geo_seq.next_value())
    fulladdress = Column(String(200), nullable=False, unique=True, comment="完整地址")
    
    latitude = Column(Numeric(precision=10, scale=8), nullable=False, comment="纬度")
    
    longitude = Column(Numeric(precision=11, scale=8), nullable=False, comment="经度")
    sourcesystem = Column(String(20), nullable=True, comment="来源系统")
    confidencescore = Column(Numeric(precision=4, scale=2), nullable=True, comment="置信度评分")
    
    geocodelevel = Column(String(20), nullable=True, comment="地理编码级别")
    
    # 默认为当前时间
    geocodeddate = Column(DateTime, nullable=False, default=datetime.utcnow, comment="编码时间")

    __table_args__ = (
        UniqueConstraint('fulladdress', name='address_geocoding_fulladdress_key'),
    )

    def __repr__(self):
        return f"<AddressGeocoding(id={self.addressid}, address='{self.fulladdress}')>"



class CustomerOrder(Base):
    __tablename__ = "customerorder"

    # 主键
    orderid = Column(String(20), primary_key=True)

    # 外键关联
    memberid = Column(String(20), ForeignKey("memberinfo.memberid"), nullable=False)
    orderstate = Column(String(20), ForeignKey("orderstatus_map.statuscode"), nullable=False)
    operatorid = Column(String(12), ForeignKey("fxh_operatorinfo.operatorid"), nullable=True)

    # 基础字段
    submitdate = Column(DateTime, nullable=False)
    approverid = Column(String(12), nullable=True)
    
    # 金额字段 (精度10, 标度2)
    originalmoney = Column(Numeric(10, 2), nullable=False)
    discountedmoney = Column(Numeric(10, 2), nullable=False)
    approveddiscount = Column(Numeric(10, 2), nullable=False)
    conditionfreightfree = Column(Numeric(10, 2), nullable=True)
    isemergency = Column(Boolean, nullable=False)
    customerremark = Column(String(200), nullable=True)
    customerscore = Column(Integer, nullable=True)
    updatetimestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    dataversion = Column(Integer, nullable=False, default=1)

    details = relationship("CustomerOrderDetail", back_populates="main_order", cascade="all, delete-orphan")
    shipment = relationship("CustomerOrderShipment", back_populates="main_order", uselist=False)
    logs = relationship("CustomerOrderStatusLog", back_populates="order")
    user = relationship("User", back_populates="orders")


class CustomerOrderDetail(Base):
    __tablename__ = "customerorder_detail"

    orderdetail_id_seq = Sequence('customerorder_detail_orderdetailid_seq', start=15000)
    
    # 主键
    orderdetailid = Column(
        BigInteger, 
        orderdetail_id_seq, 
        server_default=orderdetail_id_seq.next_value(), 
        primary_key=True
    )

    # 外键关联
    orderid = Column(String(20), ForeignKey("customerorder.orderid"), nullable=False)
    productid = Column(String(20), ForeignKey("productinfo.productid"), nullable=False)

    # 明细字段
    quantity = Column(Integer, nullable=False)
    snapshotprice = Column(Numeric(10, 2), nullable=False)
    linediscount = Column(Numeric(10, 2), nullable=False)

    # --- 新增：产品评价相关字段 ---
    review_content = Column(String(500), nullable=True) # 评价内容
    star_rating = Column(Integer, nullable=True)       # 星级 (1-5)
    review_time = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    product = relationship("ProductInfo", back_populates="detail")

    # 联合唯一约束
    __table_args__ = (
        UniqueConstraint('orderid', 'productid', name='customerorder_detail_orderid_productid_key'),
    )

    # 关系映射
    main_order = relationship("CustomerOrder", back_populates="details")

    
class CustomerOrderShipment(Base):
    __tablename__ = "customerorder_shipment"

    # orderid 作为主键同时也是外键
    orderid = Column(String(20), ForeignKey("customerorder.orderid"), primary_key=True)
    receiver = Column(String(30), nullable=False)
    mobilephone = Column(String(20), nullable=False)
    memberaddressid = Column(BigInteger, ForeignKey("memberaddress.addressrecid"), nullable=False)
    shipmenttype = Column(String(20), nullable=False)
    trackingnumber = Column(String(50), nullable=True)
    freight_fee = Column(Numeric(10, 2), nullable=True)

    address = relationship("MemberAddress")
    main_order = relationship("CustomerOrder", back_populates="shipment")



class CustomerOrderStatusLog(Base):
    __tablename__ = "customerorder_statuslog"
    __table_args__ = {"comment": "订单状态变更历史记录"} #

    logid = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True,
        comment="主键ID"
    ) 

    orderid = Column(
        String(20), 
        ForeignKey("customerorder.orderid"), 
        nullable=False, 
        comment="订单编号"
    ) 

    # 状态字段均指向 orderstatus_map 的 statuscode
    fromstate = Column(
        String(20), 
        ForeignKey("orderstatus_map.statuscode"), 
        nullable=False, 
        comment="变更前状态"
    ) 
    
    tostate = Column(
        String(20), 
        ForeignKey("orderstatus_map.statuscode"), 
        nullable=False, 
        comment="变更后状态"
    ) #

    # 3. 其他字段
    changetime = Column(
        DateTime, 
        nullable=False, 
        default=func.now(), 
        comment="变更时间"
    ) #
    
    changer = Column(
        String(30), 
        nullable=False, 
        comment="变更人"
    ) #
    
    remark = Column(
        String(100), 
        nullable=True, 
        comment="备注"
    ) #

    # 4. 关系映射 (可选)
    order = relationship("CustomerOrder", back_populates="logs")


class FxhOperatorInfo(Base):
    __tablename__ = "fxh_operatorinfo"
    operatorid = Column(String(12), primary_key=True)
    fullname = Column(String(100))


class MemberAddress(Base):
    __tablename__ = "memberaddress"
    
    addressrecid = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True, 
        comment="自增主键ID"
    )
    
    memberid = Column(String(20), ForeignKey("memberinfo.memberid"), nullable=False)
    addressgeocodeid = Column(BigInteger, ForeignKey("address_geocoding.addressid"), nullable=False)
    isdefault = Column(Boolean, nullable=False, default=False)

    address_detail = relationship("AddressGeocoding")
    user = relationship("User", back_populates="addresses")


class MemberPhone(Base):
    """
    存储用户的所有电话信息
    """
    __tablename__ = 'memberphone'
    __table_args__ = {'comment': '存储用户的所有电话信息'}


    phoneid = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True
    )
    memberid = Column(
        String(20), 
        ForeignKey('memberinfo.memberid'), 
        nullable=False
    )
    phonenumber = Column(String(20), nullable=False)
    phonetype = Column(String(10), nullable=True)
    isprimary = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="phones")

    def __repr__(self):
        return f"<MemberPhone(phoneid={self.phoneid}, number='{self.phonenumber}')>"


class OrderStatusMap(Base):
    """
    订单状态码定义及前后台名称映射
    """
    __tablename__ = 'orderstatus_map'
    __table_args__ = {'comment': '订单状态码定义及前后台名称映射'}

    statuscode = Column(String(20), primary_key=True, nullable=False)
    backendname = Column(String(30), nullable=False)
    frontendname = Column(String(30), nullable=False)
    isactive = Column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<OrderStatusMap(code='{self.statuscode}', name='{self.backendname}')>"
    


class ProductInfo(Base):
    """
    产品信息表
    """
    __tablename__ = 'productinfo'
    __table_args__ = {'comment': '产品信息表'}

    productid = Column(String(20), primary_key=True, nullable=False)
    productname = Column(String(100), nullable=False)
    standardprice = Column(Numeric(precision=10, scale=2), nullable=False)
    unit = Column(String(10), nullable=False)
    isactive = Column(Boolean, nullable=False, default=True)

    detail = relationship("CustomerOrderDetail", back_populates="product")
    stocks = relationship("WarehouseStock")

    def __repr__(self):
        return f"<ProductInfo(id='{self.productid}', name='{self.productname}', price={self.standardprice})>"


class WarehouseStock(Base):
    """
    仓库商品实时库存表
    """
    __tablename__ = 'warehouse_stock'
    
    stockid_seq = Sequence('warehouse_stock_stockid_seq', start=15000)
    stockid = Column(
        BigInteger, 
        stockid_seq, 
        server_default=stockid_seq.next_value(), 
        primary_key=True
    )
    warehouseid = Column(String(10), ForeignKey('warehouseinfo.warehouseid'), nullable=False) 
    productid = Column(
        String(20), 
        ForeignKey('productinfo.productid'), 
        nullable=False
    )
    quantity = Column(Integer, nullable=False, default=0)
    reservedquantity = Column(Integer, nullable=False, default=0)
    minstock = Column(Integer, nullable=False, default=0)
    lastupdated = Column(
        DateTime, 
        nullable=False, 
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP')
    )

    __table_args__ = (
        UniqueConstraint('warehouseid', 'productid', name='warehouse_stock_warehouseid_productid_key'),
        {'comment': '仓库商品实时库存表'}
    )

    warehouse = relationship("WarehouseInfo", back_populates="stocks")

    def __repr__(self):
        return f"<WarehouseStock(stockid={self.stockid}, product='{self.productid}', qty={self.quantity})>"



class StockInRecord(Base):
    __tablename__ = "stock_in_record"

    in_id = Column(BigInteger, primary_key=True, autoincrement=True)
    warehouseid = Column(String(10), nullable=False)
    productid = Column(String(20), nullable=False)
    in_quantity = Column(Integer, nullable=False)
    operator = Column(String(30))
    in_date = Column(DateTime, server_default=func.now())


class StockOutRecord(Base):
    __tablename__ = "stock_out_record"

    out_id = Column(BigInteger, primary_key=True, autoincrement=True)
    warehouseid = Column(String(10), nullable=False)
    productid = Column(String(20), nullable=False)
    out_quantity = Column(Integer, nullable=False)
    operator = Column(String(30))
    out_date = Column(DateTime, server_default=func.now())


class WarehouseInfo(Base):
    """
    仓库信息表
    """
    __tablename__ = 'warehouseinfo'
    __table_args__ = {'comment': '仓库信息表，其地址依赖于 AddressGeocoding 表'}

    warehouseid = Column(String(10), primary_key=True, nullable=False)
    warehousename = Column(String(50), nullable=False)
    addressgeocodeid = Column(
        BigInteger, 
        ForeignKey('address_geocoding.addressid'), 
        nullable=False
    )
    isactive = Column(Boolean, nullable=False, default=True)
    address = relationship("AddressGeocoding")
    stocks = relationship("WarehouseStock", back_populates="warehouse")

    def __repr__(self):
        return f"<WarehouseInfo(id='{self.warehouseid}', name='{self.warehousename}')>"

# 定义一个伪造的版本获取函数
def mocked_get_server_version_info(self, connection):
    return (12, 0, 0)  # 告诉 SQLAlchemy 这是一个 PostgreSQL 12

# 将 PostgreSQL 的 asyncpg 方言类中的方法替换掉
PGDialect_asyncpg._get_server_version_info = mocked_get_server_version_info

engine = create_async_engine(
    DATABASE_URL,
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)