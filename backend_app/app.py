from typing import List
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from backend_app.schemas import OrderBaseResponse, OrderWithDetailsResponse, PostCreate, PostResponse, ProductSummary, StatusLogRead, UserRead, UserCreate, UserUpdate, ProductStockLocation, ProductStockResponse
from backend_app.db import CustomerOrder, CustomerOrderStatusLog, OrderStatusMap, Post, ProductInfo, create_db_and_tables, get_async_session, User, WarehouseStock, WarehouseInfo, MemberAddress, User, MemberPhone
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import delete, or_, select
import shutil
import os
import uuid
import tempfile
from backend_app.users import auth_backend, current_active_user, fastapi_users
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import aliased
from sqlalchemy import desc



@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])


@app.get("/feed")
async def get_feed(
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user),
):
    result = await session.execute(select(Post).order_by(Post.created_at.desc()))
    posts = [row[0] for row in result.all()]

    result = await session.execute(select(User))
    users = [row[0] for row in result.all()]
    user_dict = {u.id: u.email for u in users}

    posts_data = []
    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "user_id": str(post.user_id),
                "caption": post.caption,
                "url": post.url,
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat(),
                "is_owner": post.user_id == user.id,
                "email": user_dict.get(post.user_id, "Unknown")
            }
        )

    return {"posts": posts_data}


@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, session: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user),):
    try:
        post_uuid = uuid.UUID(post_id)

        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this post")

        await session.delete(post)
        await session.commit()

        return {"success": True, "message": "Post deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# 假设你的 Pydantic 模型和 get_async_session 已经定义好

@app.get("/products/{product_id}/stock-locations", response_model=ProductStockResponse)
async def get_product_stock_locations(
    product_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    try:
        # 使用 select 语法配合 joinedload 预加载所有层级的关系
        # WarehouseStock -> WarehouseInfo (warehouse) -> AddressGeocoding (address)
        stmt = (
            select(WarehouseStock)
            .options(
                joinedload(WarehouseStock.warehouse)  # 预加载仓库信息
                .joinedload(WarehouseInfo.address)    # 顺着仓库信息进一步加载地址信息
            )
            .filter(WarehouseStock.productid == product_id)
            .filter(WarehouseStock.quantity > 0)
        )
        
        result = await session.execute(stmt)
        # scalars() 将结果转为 WarehouseStock 对象列表
        stocks = result.scalars().all()

        if not stocks:
            # 这里可以根据业务逻辑决定是返回空列表还是 404
            return {"productid": product_id, "locations": []}

        # 构建响应数据
        # 因为使用了 joinedload，这里的 .warehouse 和 .address 访问都不会触发额外的数据库 IO
        locations = [
            ProductStockLocation(
                warehouseid=s.warehouseid,
                warehousename=s.warehouse.warehousename,
                latitude=s.warehouse.address.latitude,
                longitude=s.warehouse.address.longitude,
                fulladdress=s.warehouse.address.fulladdress,
                quantity=s.quantity
            ) for s in stocks
        ]

        return ProductStockResponse(productid=product_id, locations=locations)

    except Exception as e:
        # 模仿你提供的上传接口的错误处理
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    


@app.get("/member/contact_info/{member_id}")
async def get_member_contact_info(
    member_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    # 使用 joinedload 预加载 phones 和 addresses 以及地址对应的详细地理信息
    query = (
        select(User)
        .where(User.id == member_id)
        .options(
            joinedload(User.phones),
            joinedload(User.addresses).joinedload(MemberAddress.address_detail)
        )
    )
    
    result = await session.execute(query)
    # unique() 用于处理 1 对多关联查询产生的重复行
    member = result.unique().scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # 格式化输出数据
    return {
        "member_id": member.id,
        "real_name": member.realname,
        "phones": [
            {
                "number": p.phonenumber,
                "type": p.phonetype,
                "is_primary": p.isprimary
            } for p in member.phones
        ],
        "addresses": [
            {
                "recid": addr.addressrecid,
                "is_default": addr.isdefault,
                "full_address": addr.address_detail.fulladdress if addr.address_detail else "Unknown"
            } for addr in member.addresses
        ]
    }


@app.get("/products/active", response_model=List[ProductSummary])
async def get_active_products(session: AsyncSession = Depends(get_async_session)):
    # 构造查询：选择所有 isactive 为 True 的商品
    stmt = select(ProductInfo).where(ProductInfo.isactive == True)
    
    result = await session.execute(stmt)
    # 获取对象列表
    products = result.scalars().all()
    
    return products


# 定义状态表的别名，分别用于映射“从状态”和“到状态”
FromStatus = aliased(OrderStatusMap)
ToStatus = aliased(OrderStatusMap)

@app.get("/orders/{order_id}/logs", response_model=list[StatusLogRead])
async def get_order_status_logs(
    order_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    # 构造查询：一次性关联两次状态表
    stmt = (
        select(
            CustomerOrderStatusLog,
            FromStatus.backendname.label("from_name"),
            ToStatus.backendname.label("to_name")
        )
        .join(FromStatus, CustomerOrderStatusLog.fromstate == FromStatus.statuscode)
        .join(ToStatus, CustomerOrderStatusLog.tostate == ToStatus.statuscode)
        .filter(CustomerOrderStatusLog.orderid == order_id)
        .order_by(desc(CustomerOrderStatusLog.changetime))
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    # 转换为响应结构
    return [
        StatusLogRead(
            logid=row.CustomerOrderStatusLog.logid,
            from_state_name=row.from_name,
            to_state_name=row.to_name,
            fromstate=row.CustomerOrderStatusLog.fromstate,
            tostate=row.CustomerOrderStatusLog.tostate,
            changetime=row.CustomerOrderStatusLog.changetime,
            changer=row.CustomerOrderStatusLog.changer,
            remark=row.CustomerOrderStatusLog.remark
        ) for row in rows
    ]


@app.get("/orders/{order_id}/full-info", response_model=OrderWithDetailsResponse)
async def get_order_full_info(
    order_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    # 构造查询：选择订单并预加载其明细 (details)
    stmt = (
        select(CustomerOrder)
        .options(
            joinedload(CustomerOrder.details)
            .joinedload(CustomerOrderDetail.product))
        .filter(CustomerOrder.orderid == order_id)
    )
    
    result = await session.execute(stmt)
    # unique() 是必须的，因为 joinedload 在左连接多个明细时会产生重复的主表行
    order = result.scalars().unique().first()

    if not order:
        raise HTTPException(status_code=404, detail="订单未找到")

    # 2. 手动构建 details 列表，解决字段映射问题
    # 这里将关联对象中的 productname 提取出来，转为 Pydantic 期望的 str
    manual_details = []
    for d in order.details:
        manual_details.append({
            "productid": d.productid,
            "quantity": d.quantity,
            "snapshotprice": d.snapshotprice,
            "linediscount": d.linediscount,
            # 关键点：跨表取值
            "productname": d.product.productname if d.product else "未知商品"
        })

    # 3. 返回符合 OrderWithDetailsResponse 结构的字典
    # FastAPI 会自动处理 Decimal 和 datetime 的序列化
    return {
        "orderid": order.orderid,
        "orderstate": order.orderstate,
        "submitdate": order.submitdate,
        "originalmoney": order.originalmoney,
        "discountedmoney": order.discountedmoney,
        "approveddiscount": order.approveddiscount, # 假设该字段在 CustomerOrder 中
        "details": manual_details
    }


from fastapi import HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

@app.get("/orders/{order_id}/minimal", response_model=OrderBaseResponse)
async def get_order_minimal_info(
    order_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    # 1. 构造联查语句：同时查出订单表和物流货运表
    stmt = (
        select(CustomerOrder, CustomerOrderShipment)
        .join(
            CustomerOrderShipment, 
            CustomerOrder.orderid == CustomerOrderShipment.orderid
        )
        .filter(CustomerOrder.orderid == order_id)
    )
    
    result = await session.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="未找到该订单或关联的费用信息")

    # 2. 解包元组 (对应 select 中的顺序)
    order_obj, shipment_obj = row

    # 3. 按照 OrderBaseResponse 的结构返回
    # FastAPI 会自动根据 response_model 进行校验和序列化
    return {
        "base_info": order_obj, 
        "fee_info": shipment_obj
    }


from fastapi import Query


@app.get("/orders/customer/{customer_id}", response_model=List[OrderBaseResponse])
async def get_customer_orders(
    customer_id: str, 
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session)
):
    """
    根据客户 ID (memberid) 筛选订单列表，包含基础信息与费用
    """
    # 1. 构造联查与筛选语句
    # 注意：根据你的模型，客户 ID 在数据库中对应的字段通常是 memberid
    stmt = (
        select(CustomerOrder, CustomerOrderShipment)
        .join(
            CustomerOrderShipment, 
            CustomerOrder.orderid == CustomerOrderShipment.orderid
        )
        .where(CustomerOrder.memberid == customer_id) # 执行筛选
        .order_by(CustomerOrder.submitdate.desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    rows = result.all() 

    # 2. 转换为模型结构
    # rows 的每个元素是一个元组 (CustomerOrder对象, CustomerOrderShipment对象)
    return [
        {
            "base_info": order_obj, 
            "fee_info": {
                # 从 CustomerOrder (order_obj) 取值
                "originalmoney": order_obj.originalmoney,
                "discountedmoney": order_obj.discountedmoney,
                
                # 从 CustomerOrderShipment (shipment_obj) 取值
                "conditionfreightfree": order_obj.conditionfreightfree,
                "approveddiscount": order_obj.approveddiscount,
                
                # 如果还有其他 shipment 里的字段也要带上
                "freight_fee": shipment_obj.freight_fee if hasattr(shipment_obj, 'freight_fee') else 0
            }
        } 
        for order_obj, shipment_obj in rows
    ]

@app.get("/orders/{order_id}/evaluation")
async def get_order_evaluation(
    order_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    # 只查询评价相关的少量字段
    stmt = select(CustomerOrder.customerremark).filter(CustomerOrder.orderid == order_id)
    result = await session.execute(stmt)
    remark = result.scalar_one_or_none()
    
    return {"orderid": order_id, "evaluation": remark or "None"}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
import datetime
import uuid

from .db import CustomerOrder, CustomerOrderDetail, CustomerOrderShipment
from .db import get_async_session
from .schemas import MemberAddressResponse, OrderCreateRequest, OrderCreateResponse, ProductSchema, ProductSuggestion
from . import utils



@app.post("/orders", response_model=OrderCreateResponse)
async def submit_order(
    payload: OrderCreateRequest, 
    session: AsyncSession = Depends(get_async_session)
):
    order_id, tracking_no, current_time = await utils.generate_order_metadata_async()

    try:
        # --- 步骤 1: 插入主表 ---
        new_order = CustomerOrder(
            orderid=order_id,
            memberid=payload.member_id,
            orderstate='UNPAID',
            submitdate=current_time,
            originalmoney=payload.total_price,
            discountedmoney=0,
            approveddiscount=0,
            conditionfreightfree=5000,
            isemergency=False,
            updatetimestamp=current_time,
            dataversion=1
        )
        session.add(new_order)

        # --- 步骤 2: 插入详情表 ---
        for item in payload.items:
            detail = CustomerOrderDetail(
                orderid=order_id,
                productid=item.product_id,
                quantity=item.quantity,
                snapshotprice=item.price,
                linediscount=0
            )
            session.add(detail)

        # --- 步骤 3: 插入物流表 ---
        shipment = CustomerOrderShipment(
            orderid=order_id,
            receiver="收件人-000000",
            mobilephone=payload.selected_phone,
            memberaddressid=payload.selected_address,
            shipmenttype="SF_EXPRESS",
            trackingnumber=tracking_no,
            freight_fee=80
        )
        session.add(shipment)

        # --- 提交事务 ---
        await session.commit()
        
        return {"order_id": order_id}

    except Exception as e:
        # 发生异常时回滚
        await session.rollback()
        # 记录日志，你可以根据需要细化错误类型
        raise HTTPException(status_code=500, detail=f"订单提交失败: {str(e)}")
    

from datetime import datetime


from sqlalchemy import update, select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from .schemas import FullOrderReviewRequest

@app.post("/orders/full-review-submission")
async def submit_full_order_review(
    payload: FullOrderReviewRequest,
    session: AsyncSession = Depends(get_async_session)
):
    submit_time = datetime.now()
    
    try:
        # --- 1. 批量更新商品明细评价 (子表) ---
        for p_review in payload.product_reviews:
            update_detail_stmt = (
                update(CustomerOrderDetail)
                .where(CustomerOrderDetail.orderid == payload.order_id)
                .where(CustomerOrderDetail.productid == p_review.product_id)
                .values(
                    review_content=p_review.content,
                    star_rating=p_review.rating,
                    review_time=submit_time
                )
            )
            await session.execute(update_detail_stmt)

        # --- 2. 新增：更新订单本身评价字段 (主表) ---
        # 假设你的 CustomerOrder 表有对应的列名
        update_order_stmt = (
            update(CustomerOrder)
            .where(CustomerOrder.orderid == payload.order_id)
            .values(
                # 请根据你 CustomerOrder 模型的实际字段名修改
                customerscore=payload.order_rating,
                customerremark=payload.order_remark,
                orderstate="SUCCESS"  # 评价完通常将状态置为最终态
            )
        )
        await session.execute(update_order_stmt)

        # --- 3. 插入订单状态日志 (日志表) ---
        new_log = CustomerOrderStatusLog(
            orderid=payload.order_id,
            fromstate="NOT_RATED",  # 或是从当前实际状态动态获取
            tostate="SUCCESS",
            changer=payload.changer,
            remark=f"【整单评分:{payload.order_rating}】{payload.order_remark}",
            changetime=submit_time
        )
        session.add(new_log)

        # --- 4. 统一提交事务 ---
        await session.commit()
        
        return {
            "status": "success",
            "message": "订单及商品明细评价已更新，订单状态已转为 SUCCESS",
            "order_id": payload.order_id
        }

    except Exception as e:
        await session.rollback()
        import traceback
        traceback.print_exc() 
        raise HTTPException(
            status_code=500, 
            detail=f"[{type(e).__name__}] 提交失败: {str(e)}"
        )


from .schemas import ProductEvaluation, ProductEvaluationList

@app.get("/products/{product_id}/evaluations", response_model=ProductEvaluationList)
async def get_product_reviews(
    product_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    # 1. 查询所有已评价的记录
    # 联表查询：详情表 + 用户表
    stmt = (
        select(
            User.loginname,
            User.memberlevel,
            CustomerOrderDetail.review_content,
            CustomerOrderDetail.star_rating,
            CustomerOrderDetail.review_time
        )
        .join(User, CustomerOrderDetail.orderid != None) # 逻辑关联
        .where(
            CustomerOrderDetail.productid == product_id,
            CustomerOrderDetail.star_rating != None  # 只看已评价的
        )
        .order_by(CustomerOrderDetail.review_time.desc()) # 按时间倒序
    )

    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return {
            "product_id": product_id,
            "average_rating": 0,
            "total_count": 0,
            "reviews": []
        }

    # 2. 计算平均分
    total_rating = sum(r.star_rating for r in rows if r.star_rating)
    avg_rating = round(total_rating / len(rows), 1)

    # 3. 构造返回列表
    reviews_list = [
        ProductEvaluation(
            username=r.loginname,
            member_level=r.memberlevel,
            content=r.review_content,
            rating=r.star_rating,
            review_time=r.review_time
        )
        for r in rows
    ]

    return {
        "product_id": product_id,
        "average_rating": avg_rating,
        "total_count": len(rows),
        "reviews": reviews_list
    }


from sqlalchemy import select
from .schemas import OrderStatusLogRequest


@app.post("/orders/logs")
async def add_order_status_log(
    payload: OrderStatusLogRequest, 
    session: AsyncSession = Depends(get_async_session)
):
    try:
        

        # 2. 创建新日志对象
        new_log = CustomerOrderStatusLog(
            orderid=payload.order_id,
            fromstate=payload.from_state,
            tostate=payload.to_state,
            changetime=datetime.now(), # 使用 Python 生成时间更易控
            changer=payload.changer,
            remark=payload.remark
        )

        session.add(new_log)
        
        # 3. 提交事务
        await session.commit()
        return {"status": "success"}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"日志写入失败: {str(e)}")
    

@app.get("/orders/by-time", response_model=List[OrderBaseResponse])
async def get_orders_by_time_range(
    start_date: datetime = Query(..., description="开始时间 (ISO格式)"),
    end_date: datetime = Query(..., description="结束时间 (ISO格式)"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    根据提交时间范围查询订单及其费用信息
    """
    # 构造联查语句
    stmt = (
        select(CustomerOrder, CustomerOrderShipment)
        .join(
            CustomerOrderShipment, 
            CustomerOrder.orderid == CustomerOrderShipment.orderid
        )
        .where(CustomerOrder.submitdate.between(start_date, end_date))
        .order_by(CustomerOrder.submitdate.desc())
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    # 将查询到的元组转换为 OrderBaseResponse 结构
    return [
        {
            "base_info": order_obj, 
            "fee_info": {
                # 从 CustomerOrder (order_obj) 取值
                "originalmoney": order_obj.originalmoney,
                "discountedmoney": order_obj.discountedmoney,
                
                # 从 CustomerOrderShipment (shipment_obj) 取值
                "conditionfreightfree": order_obj.conditionfreightfree,
                "approveddiscount": order_obj.approveddiscount,
                
                # 如果还有其他 shipment 里的字段也要带上
                "freight_fee": shipment_obj.freight_fee if hasattr(shipment_obj, 'freight_fee') else 0
            }
        } 
        for order_obj, shipment_obj in rows
    ]

from .schemas import DistributeRequest, DistributeResponse, DispatchPlanItem, ProductDispatchResult

@app.post("/inventory/distribute", response_model=DistributeResponse)
async def api_distribute_inventory(
    req: DistributeRequest, 
    session: AsyncSession = Depends(get_async_session)
):
    # 1. 获取该订单所有商品及其地理分布数据 (调用之前定义的 ORM 逻辑)
    # 假设该函数返回了包含客户坐标和 products 列表的对象
    order_data = await utils.get_multi_product_storage_locations(req.order_id, session)

    if not order_data:
        raise HTTPException(status_code=404, detail="未找到订单信息")

    all_results = []
    total_success = True
    
    target_lat = order_data.customer_latitude
    target_lon = order_data.customer_longitude

    # 2. 遍历订单中的每一个产品
    for p in order_data.products:
        product_plan = []
        remaining_needed = p.order_quantity
        
        # 3. 计算该产品在各个仓库到客户的曼哈顿距离并排序
        # storage_locations 是 List[WarehouseInventory]
        sorted_warehouses = sorted(
            p.storage_locations,
            key=lambda w: abs(w.latitude - target_lat) + abs(w.longitude - target_lon)
        )

        # 4. 执行派发逻辑
        for wh in sorted_warehouses:
            if remaining_needed <= 0:
                break
            
            take_qty = min(remaining_needed, wh.available_qty)
            if take_qty > 0:
                dist = abs(wh.latitude - target_lat) + abs(wh.longitude - target_lon)
                product_plan.append(DispatchPlanItem(
                    warehouse_id=wh.warehouse_id,
                    warehouse_name=wh.warehouse_name,
                    dispatch_qty=take_qty,
                    distance_score=round(float(dist), 4)
                ))
                remaining_needed -= take_qty

        # 5. 记录该产品的派发结果
        product_success = (remaining_needed <= 0)
        if not product_success:
            total_success = False

        all_results.append(ProductDispatchResult(
            product_id=p.product_id,
            product_name=p.product_name,
            required_qty=p.order_quantity,
            actual_dispatched=p.order_quantity - remaining_needed,
            success=product_success,
            plan=product_plan
        ))

    # 6. 构建总体响应
    message = "所有商品配货成功" if total_success else "部分商品库存不足"
    
    return DistributeResponse(
        order_id=req.order_id,
        overall_success=total_success,
        target_latitude=target_lat,
        target_longitude=target_lon,
        message=message,
        results=all_results
    )

from .schemas import StockOutCreate
from .db import StockOutRecord

@app.post("/inventory/stock-out", response_model=dict)
async def api_stock_out(payload: StockOutCreate, session: AsyncSession = Depends(get_async_session)):
    # 插入出库记录，触发器会自动更新 warehouse_stock 表
    new_record = StockOutRecord(
        warehouseid=payload.warehouse_id,
        productid=payload.product_id,
        out_quantity=payload.qty,
        operator=payload.operator
    )
    session.add(new_record)
    try:
        await session.commit()
        return {"status": "success", "msg": "出库记录已登记，库存已同步更新"}
    except Exception as e:
        await session.rollback()
        # 如果触发器抛出“库存不足”异常，这里会捕获到
        raise HTTPException(status_code=400, detail=f"出库失败: {str(e)}")
    

@app.post("/auth/direct-reset-password")
async def direct_reset_password(
    payload: dict, 
    session: AsyncSession = Depends(get_async_session)
):
    email = payload.get("email")
    loginname = payload.get("loginname")  # 改用登录名/昵称
    new_pwd = payload.get("new_password")

    # 1. 验证邮箱与登录名是否匹配
    stmt = select(User).where(User.email == email, User.loginname == loginname)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # 保持提示模糊，防止撞库攻击
        raise HTTPException(status_code=404, detail="账号验证失败")

    from .utils import password_helper
    # 2. 调用加密工具重置
    user.hashed_password = password_helper.hash(new_pwd)
    
    try:
        await session.commit()
        return {"status": "success"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail="服务器写入失败")
    

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from .schemas import OrderLocationResponse, ProductItem

@app.get("/orders/{order_id}/dispatch-info", response_model=OrderLocationResponse)
async def get_order_dispatch_info(
    order_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    stmt = (
        select(CustomerOrder)
        .options(
            joinedload(CustomerOrder.shipment)
                .joinedload(CustomerOrderShipment.address)
                .joinedload(MemberAddress.address_detail),
            joinedload(CustomerOrder.details) # 必须加载详情表以获取 quantity
        )
        .where(CustomerOrder.orderid == order_id)
    )
    
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if not order or not order.shipment:
        raise HTTPException(status_code=404, detail="订单或物流信息不存在")

    geo = order.shipment.address.address_detail
    
    # 构造包含 ID 和 数量 的列表
    product_list = [
        ProductItem(product_id=d.productid, quantity=d.quantity) 
        for d in order.details
    ]

    return OrderLocationResponse(
        order_id=order.orderid,
        receiver=order.shipment.receiver,
        longitude=float(geo.longitude),
        latitude=float(geo.latitude),
        products=product_list
    )


from .schemas import BulkStockOutRequest, BulkStockOutResponse

from sqlalchemy import insert

@app.post("/inventory/bulk-stock-out", response_model=BulkStockOutResponse)
async def api_bulk_stock_out(req: BulkStockOutRequest, session: AsyncSession = Depends(get_async_session)):
    try:
        # 1. 构造待插入的对象列表
        new_records = [
            StockOutRecord(
                warehouseid=item.warehouse_id,
                productid=item.product_id,
                out_quantity=item.qty,
                operator=req.operator
            )
            for item in req.items
        ]
        
        # 2. 批量添加到 Session
        session.add_all(new_records)
        
        # 3. 统一提交
        # 此时数据库触发器会被激活，自动去扣减 warehouse_stock 的数量
        await session.commit()
        
        return {
            "success": True, 
            "message": "出库记录已登记，库存已通过触发器自动扣减", 
            "processed_count": len(new_records)
        }
        
    except Exception as e:
        await session.rollback()
        # 如果触发器因为库存不足抛出异常（SIGNAL），这里也会捕获到
        return {"success": False, "message": f"入库登记失败: {str(e)}", "processed_count": 0}
    

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from typing import Optional
from .schemas import OrderLocationRead
from .db import AddressGeocoding

# 导入你的模型
# from models import CustomerOrder, CustomerOrderShipment, MemberAddress, AddressGeocoding
# 导入你的 get_async_session
@app.get("/orders/dispatch-list", response_model=List[OrderLocationRead])
async def get_dispatch_orders(
    status: Optional[List[str]] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    only_emergency: bool = Query(False),
    db: AsyncSession = Depends(get_async_session) # 使用你的异步依赖
):
    # 1. 构建异步查询语句
    stmt = (
        select(
            CustomerOrder.orderid,
            CustomerOrder.submitdate,
            CustomerOrder.orderstate,
            CustomerOrder.isemergency,
            AddressGeocoding.latitude,
            AddressGeocoding.longitude
        )
        .join(CustomerOrderShipment, CustomerOrder.orderid == CustomerOrderShipment.orderid)
        .join(MemberAddress, CustomerOrderShipment.memberaddressid == MemberAddress.addressrecid)
        .join(AddressGeocoding, MemberAddress.addressgeocodeid == AddressGeocoding.addressid)
    )

    # 2. 动态添加过滤条件
    filters = []
    if status:
        filters.append(CustomerOrder.orderstate.in_(status))
    if start_date:
        filters.append(CustomerOrder.submitdate >= start_date)
    if end_date:
        filters.append(CustomerOrder.submitdate <= end_date)
    if only_emergency:
        filters.append(CustomerOrder.isemergency == True)

    if filters:
        stmt = stmt.where(and_(*filters))

    # 3. 执行异步查询
    result = await db.execute(stmt.order_by(CustomerOrder.submitdate.desc()))
    
    # 4. 映射结果
    # result.all() 返回的是 Row 对象，Pydantic 会自动处理映射
    orders = result.all()
    
    return orders

import numpy as np
from sklearn.cluster import KMeans
from .schemas import ClusterRequest

@app.post("/orders/cluster")
async def perform_clustering(payload: ClusterRequest):
    """
    接收订单列表，根据经纬度进行聚类，并返回分组后的 OrderID 列表
    """
    orders = payload.orders
    n_clusters = payload.num_clusters

    if not orders:
        raise HTTPException(status_code=400, detail="订单列表不能为空")
    
    # 如果订单数少于预设的聚类数，强制调整聚类数
    actual_n_clusters = min(n_clusters, len(orders))

    # 1. 提取坐标特征矩阵 [ [lat1, lon1], [lat2, lon2], ... ]
    coords = np.array([[o.latitude, o.longitude] for o in orders])

    # 2. 执行 KMeans 聚类
    # n_init="auto" 是为了兼容较新版本的 sklearn
    model = KMeans(n_clusters=actual_n_clusters, n_init="auto", random_state=42)
    model.fit(coords)
    
    # 3. 获取聚类标签（每个订单属于哪个 Cluster ID）
    labels = model.labels_

    # 4. 组织返回数据结构： { "0": ["ORD1", "ORD2"], "1": ["ORD3"] }
    clusters = {}
    for i, order in enumerate(orders):
        cluster_id = str(labels[i])
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(order.orderid)

    return {
        "total_clusters": actual_n_clusters,
        "clusters": clusters,
        "centroids": model.cluster_centers_.tolist() # 可选：返回各组中心点坐标
    }


@app.get("/products/suggest", response_model=List[ProductSuggestion])
async def suggest_products(
    q: Optional[str] = Query(None, min_length=1),
    db: AsyncSession = Depends(get_async_session)
):
    """
    根据输入字符模糊匹配产品名称，仅返回激活状态的产品
    """
    if not q:
        return []

    # 使用 ilike 实现模糊匹配: %关键词%
    # 构造查询语句
    stmt = (
        select(ProductInfo)
        .where(
            # 使用 or_ 组合多个模糊匹配条件
            or_(
                ProductInfo.productid.ilike(f"%{q}%"),   # 匹配 ID
                ProductInfo.productname.ilike(f"%{q}%")  # 匹配 名称
            )
        )
        .where(ProductInfo.isactive == True)
        .limit(10)
    )
    
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    return products

from .schemas import AddressCreate, PhoneCreate

@app.post("/members/address")
async def create_address(address: AddressCreate, db: AsyncSession = Depends(get_async_session)):
    db_address = MemberAddress(**address.dict())
    db.add(db_address)
    await db.commit()
    await db.refresh(db_address)
    return {"status": "success", "id": db_address.addressrecid}

@app.post("/members/phone")
async def create_phone(phone: PhoneCreate, db: AsyncSession = Depends(get_async_session)):
    db_phone = MemberPhone(**phone.dict())
    db.add(db_phone)
    await db.commit()
    await db.refresh(db_phone)
    return {"status": "success", "id": db_phone.phoneid}


from sqlalchemy.orm import joinedload

@app.get("/members/{member_id}/addresses")
async def get_addresses(member_id: str, db: AsyncSession = Depends(get_async_session)):
    # 关键：使用 joinedload 预加载关联的 address_detail (即 AddressGeocoding)
    result = await db.execute(
        select(MemberAddress)
        .options(joinedload(MemberAddress.address_detail))
        .where(MemberAddress.memberid == member_id)
    )
    addresses = result.scalars().all()
    
    # 构造返回列表，将嵌套的 fulladdress 提取到外层
    return [
        {
            "addressrecid": addr.addressrecid,
            "isdefault": addr.isdefault,
            "fulladdress": addr.address_detail.fulladdress if addr.address_detail else "未知地址"
        }
        for addr in addresses
    ]

@app.get("/members/{memberid}/phones")
async def get_phones(memberid: str, db: AsyncSession = Depends(get_async_session)):
    phones = await db.execute(select(MemberPhone).where(MemberPhone.memberid == memberid))
    return phones.scalars().all()

@app.delete("/members/address/{address_id}")
async def delete_address(address_id: int, db: AsyncSession = Depends(get_async_session)):
    db_address = await db.execute(select(MemberAddress).where(MemberAddress.addressrecid == address_id))
    db_address = db_address.scalar()
    if not db_address:
        raise HTTPException(status_code=404, detail="Address not found")
    await db.delete(db_address)
    await db.commit()
    return {"status": "deleted"}

@app.delete("/members/phone/{phone_id}")
async def delete_phone(phone_id: int, db: AsyncSession = Depends(get_async_session)):
    db_phone = await db.execute(select(MemberPhone).where(MemberPhone.phoneid == phone_id))
    db_phone = db_phone.scalar()
    if not db_phone:
        raise HTTPException(status_code=404, detail="Phone not found")
    await db.delete(db_phone)
    await db.commit()
    return {"status": "deleted"}

@app.get("/addresses/search")
async def search_addresses(q: str, db: AsyncSession = Depends(get_async_session)):
    # 模糊匹配 fulladdress 字段
    result = await db.execute(
        select(AddressGeocoding)
        .where(AddressGeocoding.fulladdress.ilike(f"%{q}%"))
        .limit(10)
    )
    addresses = result.scalars().all()
    # 返回格式：[(全称, ID), ...] 方便 Streamlit 处理
    return [(addr.fulladdress, addr.addressid) for addr in addresses]


@app.get("/products", response_model=List[ProductSchema])
async def get_all_products(db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(ProductInfo))
    return result.scalars().all()

@app.post("/products")
async def create_product(prod: ProductSchema, db: AsyncSession = Depends(get_async_session)):
    db_prod = ProductInfo(**prod.dict())
    db.add(db_prod)
    await db.commit()
    return {"status": "success"}

@app.put("/products/{prod_id}")
async def update_product(prod_id: str, prod: ProductSchema, db: AsyncSession = Depends(get_async_session)):
    await db.execute(
        update(ProductInfo)
        .where(ProductInfo.productid == prod_id)
        .values(**prod.dict())
    )
    await db.commit()
    return {"status": "updated"}

@app.delete("/products/{prod_id}")
async def delete_product(prod_id: str, db: AsyncSession = Depends(get_async_session)):
    await db.execute(delete(ProductInfo).where(ProductInfo.productid == prod_id))
    await db.commit()
    return {"status": "deleted"}

@app.get("/products/{prod_id}")
async def get_product_detail(prod_id: str, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(ProductInfo).where(ProductInfo.productid == prod_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product