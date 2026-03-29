from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi_users import schemas
from typing import List
from decimal import Decimal
import uuid

class PostCreate(BaseModel):
    title: str
    content: str

class PostResponse(BaseModel):
    title: str
    content: str

# 1. 继承 BaseUser[str]，因为你的 ID 现在是字符串格式 (M000201)
class UserRead(schemas.BaseUser[str]):
    # --- 必须显式添加这些字段，Pydantic 才会包含它们 ---
    loginname: Optional[str] = None
    realname: Optional[str] = None
    memberlevel: int
    
    # 可选字段：如果你想在前端显示时间戳
    registrationdate: datetime
    
    # --- 关键配置：允许从 SQLAlchemy 模型读取数据 ---
    class Config:
        from_attributes = True  # Pydantic v2 用这个

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass

class ProductStockLocation(BaseModel):
    warehouseid: str
    warehousename: str
    latitude: Decimal
    longitude: Decimal
    quantity: int
    fulladdress: str

    class Config:
        from_attributes = True

class ProductStockResponse(BaseModel):
    productid: str
    locations: List[ProductStockLocation]


class ProductSummary(BaseModel):
    productid: str
    productname: str
    standardprice: Decimal
    unit: str

    class Config:
        from_attributes = True


class StatusLogRead(BaseModel):
    logid: int
    from_state_name: str
    to_state_name: str
    fromstate: str 
    tostate: str
    changetime: datetime
    changer: str
    remark: str | None = None # 使用 Python 3.10+ 联合类型语法

    class Config:
        from_attributes = True


class OrderDetailItem(BaseModel):
    productid: str
    productname: str
    quantity: int
    snapshotprice: Decimal
    linediscount: Decimal

    class Config:
        from_attributes = True

class OrderWithDetailsResponse(BaseModel):
    orderid: str
    orderstate: str
    submitdate: datetime
    # 金额信息
    originalmoney: Decimal
    discountedmoney: Decimal
    approveddiscount: Decimal
    # 明细列表
    details: list[OrderDetailItem]

    class Config:
        from_attributes = True

from typing import Optional

class OrderMinimalResponse(BaseModel):
    orderid: str
    memberid: str
    submitdate: datetime
    updatetimestamp: datetime
    orderstate: str
    
    operatorid: Optional[str]
    approverid: Optional[str]
    isemergency: bool

    # 新增评分字段
    customerscore: Optional[int] = Field(5, ge=1, le=5, description="客户评分1-5")
    customerremark: Optional[str] = None

    class Config:
        from_attributes = True

# 订单费用信息模型
class OrderFeeInfo(BaseModel):
    originalmoney: float
    discountedmoney: float
    conditionfreightfree: float
    freight_fee: float
    approveddiscount: float

    class Config:
        from_attributes = True

class OrderBaseResponse(BaseModel):
    base_info: OrderMinimalResponse
    fee_info: OrderFeeInfo

class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int
    price: float

class OrderCreateRequest(BaseModel):
    member_id: str
    total_price: float
    selected_phone: str
    selected_address: int
    items: List[OrderItemCreate]

class OrderCreateResponse(BaseModel):
    order_id: str
    status: str = "success"

class SingleProductReview(BaseModel):
    """单个商品的评价提交"""
    product_id: str
    content: str = Field(..., max_length=500)
    rating: int = Field(..., ge=1, le=5)

class FullOrderReviewRequest(BaseModel):
    """整单评价提交：包含订单整体评价 + 多个商品评价"""
    order_id: str
    # 订单整体评价（存入状态日志）
    order_rating: int = Field(..., ge=1, le=5)
    order_remark: str = Field(..., max_length=200, description="对物流或整体服务的评价")
    # 商品明细评价
    product_reviews: List[SingleProductReview]
    changer: str = "Customer"

class ProductEvaluation(BaseModel):
    username: str          # 评价人昵称 (来自 User.loginname 或 realname)
    member_level: str      # 会员等级 (展示身份感)
    content: Optional[str] # 评价内容
    rating: Optional[int]  # 星级
    review_time: Optional[datetime] # 评价时间

class ProductEvaluationList(BaseModel):
    product_id: str
    average_rating: float  # 平均分（加分项：展示该产品的整体口碑）
    total_count: int
    reviews: List[ProductEvaluation]

# 定义请求体模型
class OrderStatusLogRequest(BaseModel):
    order_id: str
    from_state: str
    to_state: str
    changer: str
    remark: Optional[str] = None


# --- 请求模型 ---
class DistributeRequest(BaseModel):
    order_id: str  # 传入订单ID，后端自动查询该订单下的所有商品及客户坐标

# --- 响应模型项 ---
class DispatchPlanItem(BaseModel):
    warehouse_id: str
    warehouse_name: str
    dispatch_qty: int
    distance_score: float

class ProductDispatchResult(BaseModel):
    product_id: str
    product_name: str
    required_qty: int
    actual_dispatched: int
    success: bool
    plan: List[DispatchPlanItem]

# --- 总体响应模型 ---
class DistributeResponse(BaseModel):
    order_id: str
    overall_success: bool
    target_latitude: float
    target_longitude: float
    message: str
    results: List[ProductDispatchResult]


from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# --- 基础模型 ---
class StockRecordBase(BaseModel):
    warehouse_id: str = Field(..., example="WH001")
    product_id: str = Field(..., example="PROD_A")
    operator: Optional[str] = "System"

# --- 入库请求模型 ---
class StockInCreate(StockRecordBase):
    qty: int = Field(..., gt=0, description="入库数量必须大于0")

# --- 出库请求模型 ---
class StockOutCreate(StockRecordBase):
    qty: int = Field(..., gt=0, description="出库数量必须大于0")

# --- 库存查询响应模型 ---
class WarehouseStockResponse(BaseModel):
    stockid: int
    warehouseid: str
    productid: str
    quantity: int
    reservedquantity: int
    minstock: int
    lastupdated: datetime

    class Config:
        from_attributes = True # 允许从 ORM 对象直接转换


class ProductItem(BaseModel):
    product_id: str
    quantity: int

class OrderLocationResponse(BaseModel):
    order_id: str
    receiver: str
    longitude: float
    latitude: float
    # 修改为包含详情的对象列表
    products: List[ProductItem]

    class Config:
        from_attributes = True


class WarehouseInventory(BaseModel):
    warehouse_id: str
    warehouse_name: str
    latitude: float
    longitude: float
    available_qty: int

class OrderProductStockInfo(BaseModel):
    product_id: str
    product_name: str
    order_quantity: int  # 订单需要的数量
    storage_locations: List[WarehouseInventory] # 该商品在各仓库的分布

class MultiProductStockResponse(BaseModel):
    order_id: str
    customer_latitude: float
    customer_longitude: float
    products: List[OrderProductStockInfo]

from pydantic import BaseModel
from typing import List

class StockOutItem(BaseModel):
    warehouse_id: str
    product_id: str
    qty: int

class BulkStockOutRequest(BaseModel):
    order_id: str
    items: List[StockOutItem]
    operator: str = "Admin"

class BulkStockOutResponse(BaseModel):
    success: bool
    message: str
    processed_count: int


# 单个订单的地理位置信息
class OrderLocationRead(BaseModel):
    orderid: str
    submitdate: datetime
    orderstate: str
    isemergency: bool
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")

    class Config:
        from_attributes = True

# 聚类请求模型
class ClusterRequest(BaseModel):
    order_ids: List[str]
    num_clusters: int = Field(3, ge=1, description="拟划分的配送区域数量")


# 单个订单的地理坐标模型
class OrderClusterInput(BaseModel):
    orderid: str
    latitude: float
    longitude: float
    isemergency: bool = False

# 聚类请求体
class ClusterRequest(BaseModel):
    num_clusters: int = 3
    orders: List[OrderClusterInput]


class ProductSuggestion(BaseModel):
    productid: str
    productname: str
    standardprice: Decimal
    unit: str

    class Config:
        from_attributes = True

# Pydantic 模型用于接收数据
class AddressCreate(BaseModel):
    memberid: str
    addressgeocodeid: int
    isdefault: bool = False

class PhoneCreate(BaseModel):
    memberid: str
    phonenumber: str
    phonetype: Optional[str] = None
    isprimary: bool = False


class AddressDetailSchema(BaseModel):
    addressid: int
    fulladdress: str
    latitude: float
    longitude: float

    class Config:
        from_attributes = True

class MemberAddressResponse(BaseModel):
    addressrecid: int
    memberid: str
    isdefault: bool
    # 嵌套返回完整的地址详情
    address_detail: AddressDetailSchema 

    class Config:
        from_attributes = True

# --- Pydantic 模型 ---
class ProductSchema(BaseModel):
    productid: str
    productname: str
    standardprice: float
    unit: str
    isactive: bool = True

    class Config:
        from_attributes = True