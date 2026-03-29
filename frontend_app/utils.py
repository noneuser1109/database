import os 
from dotenv import load_dotenv
import streamlit as st

# 1. 加载根目录下的 .env 文件
# 这里的 .. 表示向上找一级到项目根目录
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# 2. 获取 BASE_URL，如果没有配置则使用默认值
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

import httpx
import pandas as pd


def get_product_location_data(product_id: str):
    """
    通过调用 FastAPI 接口获取产品库存地理位置数据
    并转换为原始代码兼容的 Pandas DataFrame 格式
    """
    url = f"{BASE_URL}/products/{product_id}/stock-locations"
    
    try:
        # 使用 httpx.Client 发起同步请求 (Streamlit 环境下通常用同步 client 配合 st.cache_data)
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            
            # 检查 HTTP 状态码
            if response.status_code == 200:
                data = response.json()
                locations = data.get("locations", [])
                
                # 如果没有库存，返回空的 DataFrame (保证列名一致)
                if not locations:
                    return pd.DataFrame(columns=["lat", "lon", "total_quantity", "fulladdress"])
                
                # 将接口返回的列表转换为 DataFrame
                # 关键点：将接口字段名映射回你原来 SQL 习惯的字段名
                df = pd.DataFrame(locations)
                
                # 重命名列以匹配你原有的逻辑（lat, lon, total_quantity, fulladdress）
                df = df.rename(columns={
                    "latitude": "lat",
                    "longitude": "lon",
                    "quantity": "total_quantity"
                })
                
                # 只保留你原本需要的列
                return df[["lat", "lon", "total_quantity", "fulladdress"]]
            
            elif response.status_code == 404:
                return pd.DataFrame(columns=["lat", "lon", "total_quantity", "fulladdress"])
            else:
                st.error(f"接口调用失败: {response.status_code}")
                return pd.DataFrame()

    except httpx.RequestError as e:
        st.error(f"网络连接失败，请确保 FastAPI 后端已启动: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"处理数据时出错: {e}")
        return pd.DataFrame()
    

import httpx
import streamlit as st


@st.cache_data(ttl=3600)
def get_products():
    """
    通过 HTTPX 访问 FastAPI 接口获取所有激活状态的商品
    替代原有的直接数据库查询逻辑
    """
    url = f"{BASE_URL}/products/active"
    
    try:
        # 使用同步 Client，因为 Streamlit 的 cache 机制在同步模式下最稳定
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            
            # 如果接口报错，抛出异常让 st.error 捕获
            response.raise_for_status()
            
            # FastAPI 返回的是 List[ProductSummary] 的 JSON 数组
            # 直接返回给 Streamlit 使用即可，格式通常是 [{}, {}]
            return  response.json()
            
    except httpx.HTTPStatusError as e:
        st.error(f"接口响应错误: {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        st.error(f"无法连接到后端服务器，请检查 FastAPI 是否启动: {e}")
        return []
    except Exception as e:
        st.error(f"获取商品列表失败: {str(e)}")
        return []
    


@st.cache_data(ttl=3600)
def get_member_contact_data(user_id: str):
    """
    内部辅助函数：一次性从 API 获取用户的所有联系信息
    """
    url = f"{BASE_URL}/member/contact_info/{user_id}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        st.error(f"获取会员联系信息失败: {e}")
        return None

# --- 兼容原代码的调用接口 ---

@st.cache_data(ttl=3600)
def get_user_phone(user_id):
    """
    获取电话列表，保持原有返回格式：[phone1, phone2, ...]
    """
    data = get_member_contact_data(user_id)
    if not data or "phones" not in data:
        return []
    
    # 按照 is_primary 降序排列（接口可能已经排过，这里双重保险）
    sorted_phones = sorted(data["phones"], key=lambda x: x["is_primary"], reverse=True)
    return [p["number"] for p in sorted_phones]

@st.cache_data(ttl=3600)
def get_user_address(user_id):
    """
    获取地址字典，保持原有返回格式：{address_id: full_address}
    注意：为了兼容你原来的 key, value 逻辑，这里需要确认后端是否返回了 address_id
    """
    data = get_member_contact_data(user_id)
    if not data or "addresses" not in data:
        return {}
    
    # 转换为原有的字典格式 {id: address}
    # 注意：如果你的接口返回里没有 recid，你可能需要在后端返回里加上 addr.addressrecid
    address_dict = {}
    for addr in data["addresses"]:
        # 假设后端返回了 recid，如果没有，请参考下方【后端建议】修改接口
        recid = addr.get("recid", "N/A") 
        address_dict[recid] = addr["full_address"]
        
    return address_dict


def submit_order_to_api(member_id, final_items, total_price, selected_phone, selected_address):
    """
    通过 API 提交订单，替代原有的直接数据库操作
    """
    
    if not member_id:
        st.error("未检测到登录用户信息，请重新登录")
        return None

    # 2. 构造符合后端 OrderCreateRequest 结构的 Payload
    # 注意：字段名必须与后端 Pydantic 模型完全一致
    payload = {
        "member_id": member_id,
        "total_price": float(total_price),
        "selected_phone": str(selected_phone),
        "selected_address": str(selected_address),
        "items": [
            {
                "product_id": item['商品ID'],
                "quantity": int(item['数量']),
                "price": float(item['单价'])
            }
            for item in final_items
        ]
    }

    url = f"{BASE_URL}/orders"
    
    try:
        with httpx.Client(timeout=15.0) as client:
            # 发送 POST 请求
            response = client.post(url, json=payload)
            
            # 检查是否成功
            if response.status_code == 200:
                result = response.json()
                order_id = result.get("order_id")
                st.success(f"订单提交成功！订单号: {order_id}")
                return order_id
            else:
                error_detail = response.json().get("detail", "未知错误")
                st.error(f"订单提交失败: {error_detail}")
                return None

    except httpx.RequestError as e:
        st.error(f"网络连接异常，无法连接至服务器: {e}")
        return None
    except Exception as e:
        st.error(f"提交订单时发生非预期错误: {e}")
        return None
    


    


def add_order_log_via_api(order_id: str, from_state: str, to_state: str, changer: str, remark: str = None):
    """
    通过 API 记录订单状态变更日志
    """
    url = f"{BASE_URL}/orders/logs"
    
    # 构造 Payload，字段名必须与后端的 OrderStatusLogRequest 模型完全一致
    payload = {
        "order_id": order_id,
        "from_state": from_state,
        "to_state": to_state,
        "changer": changer,
        "remark": remark
    }
    
    try:
        # 使用同步 Client，设置 5 秒超时即可（日志写入通常很快）
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=payload)
            
            # 检查 HTTP 状态码
            if response.status_code == 200:
                result = response.json()
                # st.toast(f"日志记录成功: {result.get('log_id')}") # 比赛演示时可以用 toast 提示
                return True
            else:
                error_msg = response.json().get("detail", "未知错误")
                st.error(f"记录状态日志失败: {error_msg}")
                return False

    except httpx.RequestError as e:
        st.warning(f"日志同步异常（网络连接问题）: {e}")
        return False
    except Exception as e:
        st.error(f"处理日志请求时出错: {e}")
        return False
    

from typing import Optional, Dict, Any


def get_order_minimal_info_sync(order_id: str, token: str) -> Optional[Dict[str, Any]]:
    """
    同步访问后端接口获取订单简要信息
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    # 使用同步 Client
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        try:
            response = client.get(f"/orders/{order_id}/minimal", headers=headers)
            
            if response.status_code == 404:
                return None
            
            # 如果是 401 (Token 过期) 或 500，抛出异常
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"服务器返回错误: {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"无法连接到后端服务器: {e}")
        

def get_order_base_info(order_id: str, token: str) -> Optional[Dict[str, Any]]:
    """
    同步获取订单基本信息+费用信息
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        try:
            response = client.get(f"/orders/{order_id}/minimal", headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                response.raise_for_status()
        except httpx.RequestError as e:
            raise Exception(f"API 连接失败: {e}")
    return None


def get_order_full_info_sync(order_id: str, token: str) -> Optional[Dict[str, Any]]:
    """
    同步获取订单全量信息（包含基本信息和商品明细列表）
    """
    headers = {"Authorization": f"Bearer {token}"}
    
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        try:
            # 访问后端 @app.get("/orders/{order_id}/full-info")
            response = client.get(f"/orders/{order_id}/full-info", headers=headers)
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"后端响应错误: {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"网络连接失败: {str(e)}")
        


def get_order_status_history(order_id: str) -> list:
    """
    同步获取订单状态变更历史（适配 Streamlit）
    """
    url = f"{BASE_URL}/orders/{order_id}/logs"
    
    try:
        # 使用 with 语句自动管理连接关闭
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            
            # 如果接口返回 4xx 或 5xx，抛出异常
            response.raise_for_status()
            
            # 返回解析后的列表数据
            return response.json()
            
    except httpx.HTTPStatusError as e:
        st.error(f"接口调用失败: 状态码 {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        st.error(f"网络请求异常: {str(e)}")
        return []
    except Exception as e:
        st.error(f"发生未知错误: {str(e)}")
        return []
    

def get_customer_orders_list(customer_id: str) -> list:
    """
    同步获取指定客户的订单列表（包含基本信息与费用）
    """
    # 这里的 BASE_URL 需根据实际情况定义
    url = f"{BASE_URL}/orders/customer/{customer_id}"
    
    try:
        with httpx.Client(timeout=15.0) as client:
            # 发起请求
            response = client.get(url)
            
            # 检查 HTTP 状态码（4xx, 5xx 抛出异常）
            response.raise_for_status()
            
            # 返回解析后的 OrderBaseResponse 列表
            return response.json()
            
    except httpx.HTTPStatusError as e:
        # 处理接口业务错误（如 404, 500）
        st.error(f"查询客户订单失败: 接口返回状态码 {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        # 处理网络层错误（如连接超时、DNS 解析失败）
        st.error(f"查询客户订单失败: 网络请求异常 {str(e)}")
        return []
    except Exception as e:
        # 兜底处理其他未知异常
        st.error(f"查询客户订单失败: 发生未知错误 {str(e)}")
        return []
    

from datetime import datetime

def select_order_by_time_sync(start: datetime, end: datetime) -> list:
    """
    同步获取时间范围内的订单列表（适配 Streamlit）
    """
    url = f"{BASE_URL}/orders/by-time"
    # 使用 params 传递 Query Parameters
    params = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat()
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params)
            
            # 触发状态检查
            response.raise_for_status()
            
            return response.json()
            
    except httpx.HTTPStatusError as e:
        st.error(f"时间范围查询失败: 接口状态码 {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        st.error(f"时间范围查询失败: 网络请求异常 {str(e)}")
        return []
    except Exception as e:
        st.error(f"时间范围查询失败: 发生未知错误 {str(e)}")
        return []
    

def get_inventory_distribute_plan(order_id: str) -> dict:
    """
    同步获取分仓派发方案
    """
    url = f"{BASE_URL}/inventory/distribute"
    
    # 构造请求体
    payload = {
        "order_id": order_id,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            # 使用 POST 方法
            response = client.post(url, json=payload)
            
            # 检查状态码
            response.raise_for_status()
            
            # 返回 JSON 结果
            return response.json()
            
    except httpx.HTTPStatusError as e:
        st.error(f"分仓方案计算失败: 接口返回 {e.response.status_code}")
        return {"success": False, "message": "接口异常", "plan": []}
    except httpx.RequestError as e:
        st.error(f"分仓方案计算失败: 网络请求异常 {str(e)}")
        return {"success": False, "message": "网络异常", "plan": []}
    except Exception as e:
        st.error(f"分仓方案计算失败: 未知错误 {str(e)}")
        return {"success": False, "message": "系统错误", "plan": []}
    

def add_order_status_log_sync(order_id: str, from_state: str, to_state: str, changer: str, remark: str) -> dict:
    """
    同步调用 POST 接口写入单条订单状态日志
    """
    url = f"{BASE_URL}/orders/logs"
    
    # 构造请求体 (Payload)，需与后端的 OrderStatusLogRequest 匹配
    payload = {
        "order_id": order_id,
        "from_state": from_state,
        "to_state": to_state,
        "changer": changer,
        "remark": remark
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            # 发送 POST 请求，json 参数会自动将字典转为 JSON 并设置 Content-Type
            response = client.post(url, json=payload)
            
            # 检查 HTTP 状态码
            response.raise_for_status()
            
            # 返回后端的结果 {"status": "success", "log_id": ...}
            return response.json()
            
    except httpx.HTTPStatusError as e:
        st.error(f"日志写入失败: 接口返回状态码 {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        st.error(f"日志写入失败: 网络连接异常 {str(e)}")
    except Exception as e:
        st.error(f"日志写入失败: 未知错误 {str(e)}")
    
    return {}


def execute_bulk_stock_out_sync(order_id: str, dispatch_items: list, operator: str):
    """
    通过同步 httpx 一次性发送所有扣减指令
    dispatch_items 格式示例: [{'warehouse_id': 'W01', 'product_id': 'P01', 'qty': 5}, ...]
    """
    url = f"{BASE_URL}/inventory/bulk-stock-out"
    
    payload = {
        "order_id": order_id,
        "items": dispatch_items,
        "operator": operator
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            res_data = response.json()
            if res_data["success"]:
                st.success(f"📦 批量库存扣减成功！共处理 {res_data['processed_count']} 项。")
                return True
            else:
                st.error(f"失败: {res_data['message']}")
                return False
    except Exception as e:
        st.error(f"批量出库异常: {e}")
        return False

def submit_review_to_server(order_id, order_rating, order_remark, item_reviews_list):
    """
    item_reviews_list 格式: [{"product_id": "P1", "content": "好", "rating": 5}, ...]
    """
    url = f"{BASE_URL}/orders/full-review-submission"
    
    payload = {
        "order_id": order_id,
        "order_rating": order_rating,
        "order_remark": order_remark,
        "product_reviews": item_reviews_list,
        "changer": st.session_state.get("username", "Customer")
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return True
    except Exception as e:
        st.error(f"提交评价失败: {e}")
        return False
    

def direct_reset_sync(email: str, loginname: str, new_password: str):
    """
    使用邮箱 + 登录名进行重置，保护真实姓名隐私
    """
    url = f"{BASE_URL}/auth/direct-reset-password"
    payload = {
        "email": email,
        "loginname": loginname,
        "new_password": new_password
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            if response.status_code == 200:
                return True, "密码已成功重置！"
            elif response.status_code == 404:
                return False, "验证失败：邮箱或登录名信息不匹配。"
            else:
                return False, f"请求失败: {response.status_code}"
    except Exception as e:
        return False, f"连接异常: {e}"
    

import httpx
from httpx import HTTPStatusError, RequestError

def fetch_order_data(order_id: str):
    """
    使用 httpx 同步获取订单数据的示例函数
    """
    url = f"{BASE_URL}/orders/{order_id}/dispatch-info"
    
    # 使用 with 语句自动管理连接池的关闭
    with httpx.Client(timeout=5.0) as client:
        try:
            response = client.get(url)
            
            # 如果状态码不是 2xx，抛出异常
            response.raise_for_status()
            
            # 解析 JSON 结果
            data = response.json()
            return data
            
        except HTTPStatusError as exc:
            print(f"响应错误: {exc.response.status_code} - {exc.response.text}")
        except RequestError as exc:
            print(f"网络连接错误: {exc.request.url} 无法访问")
        except Exception as e:
            print(f"发生未知错误: {e}")
            
    return None

# --- 1. 同步访问函数 ---
def fetch_orders(status_list, start_date, end_date, only_emergency):
    params = [
        ("only_emergency", only_emergency),
        ("start_date", start_date.isoformat() if start_date else None),
        ("end_date", end_date.isoformat() if end_date else None),
    ]
    for s in status_list:
        params.append(("status", s))
        
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.get(f"{BASE_URL}/orders/dispatch-list", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"接口调用失败: {e}")
            return []
        

import httpx
import pandas as pd
from typing import List, Dict, Any, Optional

def send_cluster_request(
    df: pd.DataFrame, 
    num_clusters: int, 
) -> Optional[Dict[str, Any]]:
    """
    将 edited_df 中勾选的内容转换为 Payload 并发送至后端聚类接口
    """
    # 1. 筛选出勾选的行
    selected_rows = df[df["selected"] == True].copy()
    
    if selected_rows.empty:
        return None

    # 2. 数据清洗：确保经纬度是 float，处理 Pydantic 兼容性
    # 排除掉前端专用的 'selected' 列
    relevant_cols = ["orderid", "latitude", "longitude", "isemergency"]
    
    # 确保列存在（防止后端返回字段名不一致）
    existing_cols = [c for c in relevant_cols if c in selected_rows.columns]
    payload_df = selected_rows[existing_cols].copy()

    # 转换类型：JSON 不支持 Decimal 或特定的 Numpy 类型
    if "latitude" in payload_df.columns:
        payload_df["latitude"] = payload_df["latitude"].astype(float)
    if "longitude" in payload_df.columns:
        payload_df["longitude"] = payload_df["longitude"].astype(float)

    # 3. 构造最终 JSON 结构
    payload = {
        "num_clusters": num_clusters,
        "orders": payload_df.to_dict(orient="records")
    }

    # 4. 执行同步请求
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{BASE_URL}/orders/cluster", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"请求失败，状态码: {e.response.status_code}, 原因: {e.response.text}")
        return {"error": f"服务器错误: {e.response.status_code}"}
    except Exception as e:
        print(f"网络或其他错误: {e}")
        return {"error": str(e)}
    


# --- 1. 异步搜索逻辑：支持 ID 和名称模糊匹配 ---
def search_product_ids_and_names(search_term: str):
    """
    对接后端 suggest 接口，返回 (显示文本, productid) 列表
    """
    if not search_term:
        return []
    
    try:
        # 这里的 URL 需要指向你 FastAPI 的 suggest 接口
        # 该接口后端逻辑应为：WHERE productid LIKE %q% OR productname LIKE %q%
        with httpx.Client() as client:
            response = client.get(
                f"{BASE_URL}/products/suggest", 
                params={"q": search_term}
            )
            if response.status_code == 200:
                data = response.json()
                # 返回格式：[("名称 (ID)", "ID"), ...]
                return [(f"{p['productname']} [{p['productid']}]", p['productid']) for p in data]
    except Exception:
        return []
    return []


def add_member_address(memberid: str, geocode_id: int, is_default: bool):
    payload = {
        "memberid": memberid,
        "addressgeocodeid": geocode_id,
        "isdefault": is_default
    }
    # 使用 with 语句确保连接及时关闭
    with httpx.Client() as client:
        response = client.post(f"{BASE_URL}/members/address", json=payload)
        response.raise_for_status()  # 如果返回 4xx 或 5xx 错误则抛出异常
        return response.json()

def add_member_phone(memberid: str, number: str, p_type: str, is_primary: bool):
    payload = {
        "memberid": memberid,
        "phonenumber": number,
        "phonetype": p_type,
        "isprimary": is_primary
    }
    with httpx.Client() as client:
        response = client.post(f"{BASE_URL}/members/phone", json=payload)
        response.raise_for_status()
        return response.json()


# --- 查询接口 ---
def fetch_addresses(memberid: str):
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/members/{memberid}/addresses")
        return response.json()

def fetch_phones(memberid: str):
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/members/{memberid}/phones")
        return response.json()

# --- 删除接口 ---
def delete_address_api(address_id: int):
    with httpx.Client() as client:
        response = client.delete(f"{BASE_URL}/members/address/{address_id}")
        return response.json()

def delete_phone_api(phone_id: int):
    with httpx.Client() as client:
        response = client.delete(f"{BASE_URL}/members/phone/{phone_id}")
        return response.json()
    

def search_addresses_api(query: str):
    """
    通过模糊全称搜索地址库
    返回格式: [("完整地址内容", addressid), ...]
    """
    if not query.strip():
        return []
        
    try:
        # 使用 httpx 的同步 Client
        with httpx.Client() as client:
            response = client.get(
                f"{BASE_URL}/addresses/search", 
                params={"q": query},
                timeout=5.0
            )
            response.raise_for_status()
            # 假设后端返回 [[fulladdress, addressid], ...]
            return response.json() 
    except Exception as e:
        print(f"搜索地址出错: {e}")
        return []


def fetch_all_products():
    with httpx.Client() as client:
        res = client.get(f"{BASE_URL}/products")
        return res.json() if res.status_code == 200 else []

def save_product(data, is_update=False):
    with httpx.Client() as client:
        if is_update:
            res = client.put(f"{BASE_URL}/products/{data['productid']}", json=data)
        else:
            res = client.post(f"{BASE_URL}/products", json=data)
        return res.status_code == 200

def remove_product(prod_id):
    with httpx.Client() as client:
        res = client.delete(f"{BASE_URL}/products/{prod_id}")
        return res.status_code == 200
    
def get_product_detail_api(prod_id: str):
    with httpx.Client() as client:
        resp = client.get(f"{BASE_URL}/products/{prod_id}")
        return resp.json() if resp.status_code == 200 else None