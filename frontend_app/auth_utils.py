# auth_utils.py
import httpx
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# 2. 获取 BASE_URL，如果没有配置则使用默认值
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
def fetch_user_from_backend(token: str) -> Optional[Dict[str, Any]]:
    """
    使用 JWT Token 从后端获取当前登录的用户信息。
    """
    try:
        # 使用 httpx 发送同步请求（Streamlit 环境下通常同步更易维护）
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{BASE_URL}/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                # 成功获取用户，返回 JSON 数据
                # 这里包含你之前定义的 id, email, realname, loginname 等
                return response.json()
            
            elif response.status_code == 401:
                # Token 已过期或无效
                print("Token 已失效或过期")
                return None
            
            else:
                print(f"后端返回异常状态码: {response.status_code}")
                return None
                
    except httpx.RequestError as exc:
        print(f"连接后端服务器失败: {exc}")
        return None
    except Exception as e:
        print(f"发生未知错误: {e}")
        return None
    

