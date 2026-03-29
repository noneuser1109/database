import streamlit as st
import httpx
import asyncio
import uuid
import os 
from dotenv import load_dotenv
import utils
from auth_utils import fetch_user_from_backend
import extra_streamlit_components as stx
import time
from datetime import datetime, timedelta

# 初始化管理器
if "cookie_manager" not in st.session_state:
    st.session_state.cookie_manager = stx.CookieManager()

@st.cache_resource
def get_manager():
    return stx.CookieManager()

cookie_manager = st.session_state.cookie_manager

# --- 身份恢复逻辑 ---
def sync_session_with_cookie():
    # 如果内存里已经有用户了，直接跳过
    if st.session_state.get("user"):
        return

    # 尝试从 Cookie 获取 Token (加入微小延迟防止组件未加载)
    token = cookie_manager.get("auth_token")
    
    # 技巧：如果刷新瞬间拿不到，脚本会重跑，第二次通常就能拿到了
    if token:
        user_data = fetch_user_from_backend(token)
        if user_data:
            st.session_state.user = user_data
            st.session_state.token = token
            # 刷新页面状态，进入已登录模式
            st.rerun() 
        # else:
            # Token 坏了，清理 Cookie 防止循环请求
            # cookie_manager.delete("auth_token")

# 在 pg.run() 之前调用
sync_session_with_cookie()

# 1. 加载根目录下的 .env 文件
# 这里的 .. 表示向上找一级到项目根目录
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# 2. 获取 BASE_URL，如果没有配置则使用默认值
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# 初始化 Session State
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "login"


# --- 核心同步请求函数 ---

def get_headers():
    """获取带 Token 的请求头"""
    if st.session_state.get("token"):
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

def login_sync(email, password):
    """同步登录"""
    # 使用 httpx.Client 替代 AsyncClient
    with httpx.Client(timeout=10.0) as client:
        try:
            # FastAPI Users 默认登录接口
            res = client.post(
                f"{BASE_URL}/auth/jwt/login", 
                data={"username": email, "password": password}
            )
            if res.status_code == 200:
                token = res.json()["access_token"]
                # 增加一个重试标记，避免死循环
                if token is None:
                    if "auth_retry" not in st.session_state:
                        st.session_state.auth_retry = 0
                        
                    if st.session_state.auth_retry < 2:
                        st.session_state.auth_retry += 1
                        time.sleep(0.3)
                        st.rerun()
                st.session_state.token = token
                expire_date = datetime.now() + timedelta(days=7)
                st.session_state.cookie_manager.set(
                    "auth_token", 
                    token, 
                    key="login_cookie_set",
                    expires_at=expire_date
                )
                # 紧接着获取用户信息
                user_res = client.get(f"{BASE_URL}/users/me", headers={"Authorization": f"Bearer {token}"})
                if user_res.status_code == 200:
                    st.session_state.user = user_res.json()
                    return "SUCCESS"
            elif res.status_code == 400:
                return "INVALID_CREDENTIALS"
            return f"ERROR: {res.json()}"
        except Exception as e:
            return f"CONNECTION_FAILED: {e}"

def register_sync(email, password, loginname, realname):
    """同步注册"""
    with httpx.Client(timeout=10.0) as client:
        payload = {
            "id": str(uuid.uuid4()), 
            "email": email,
            "password": password,
            "loginname": loginname,
            "realname": realname,
            "memberlevel": 1,
            "is_active": True
        }
        try:
            res = client.post(f"{BASE_URL}/auth/register", json=payload)
            return res.status_code == 201
        except Exception:
            return False

def forgot_password_sync(email):
    """同步找回密码"""
    with httpx.Client(timeout=10.0) as client:
        try:
            res = client.post(f"{BASE_URL}/auth/forgot-password", json={"email": email})
            return res.status_code == 202
        except Exception:
            return False

def show_auth_pages():
    st.title("🛡️ 顾凯允的 Simple Social 系统")
    
    # 侧边栏导航
    choice = st.sidebar.radio("前往", ["登录", "注册", "找回密码"])

    # --- 1. 登录页面 ---
    if choice == "登录":
        st.subheader("🔑 用户登录")
        email = st.text_input("邮箱地址", placeholder="example@domain.com")
        pwd = st.text_input("登录密码", type="password")
        
        if st.button("立即登录", type="primary", use_container_width=True):
            if not email or not pwd:
                st.warning("请输入邮箱和密码")
            else:
                with st.spinner("正在验证身份..."):
                    result = login_sync(email, pwd) 
                
                if result == "SUCCESS":
                    st.success("登录成功！欢迎回来。")

                    st.rerun()
                elif result == "INVALID_CREDENTIALS":
                    st.error("邮箱或密码不正确，请重试。")
                else:
                    st.error(f"登录异常: {result}")

    # --- 2. 注册页面 ---
    elif choice == "注册":
        st.subheader("📝 新会员注册")
        st.caption("加入我们，开启您的社交与购物之旅")
        
        reg_email = st.text_input("邮箱 (必填)*", placeholder="作为登录账号使用")
        reg_pwd = st.text_input("设置密码 (必填)*", type="password", help="请确保密码强度")
        
        col1, col2 = st.columns(2)
        with col1:
            ln = st.text_input("登录名称", placeholder="用于显示的昵称")
        with col2:
            rn = st.text_input("真实姓名", placeholder="实名认证参考")
            
        if st.button("立即提交注册", type="primary", use_container_width=True):
            if reg_email and reg_pwd and ln and rn:
                with st.spinner("正在创建账号..."):
                    is_ok = register_sync(reg_email, reg_pwd, ln, rn)
                
                if is_ok:
                    st.success("✅ 注册成功！请切换到“登录”界面进入系统。")
                    st.balloons()
                else:
                    st.error("注册失败。该邮箱可能已被占用，或服务器响应异常。")
            else:
                st.warning("所有必填项（邮箱、密码、登录名、姓名）均不能为空。")

    # --- 3. 找回密码页面 ---
    elif choice == "找回密码":
        st.subheader("🗝️ 账号身份验证")
        st.caption("请完整填写以下信息以重置密码。表单提交前页面不会刷新。")

        # 1. 创建表单容器
        with st.form("reset_password_form", clear_on_submit=False):
            # 2. 放置所有输入组件
            f_email = st.text_input("注册邮箱", placeholder="example@domain.com")
            f_loginname = st.text_input("登录名 (昵称)", placeholder="您的账号昵称")
            
            st.divider()
            
            new_pwd = st.text_input("设置新密码", type="password", help="长度建议不超过 72 位")
            confirm_pwd = st.text_input("确认新密码", type="password")
            
            # 3. 唯一的提交入口
            submit_button = st.form_submit_button("立即重置密码", use_container_width=True)

        # 4. 处理提交逻辑（必须在 with 块之外或紧跟其后）
        if submit_button:
            # 此时 f_email 等变量已被锁定，不会因为刷新而消失
            if f_email.strip() and f_loginname.strip() and new_pwd:
                if new_pwd != confirm_pwd:
                    st.error("❌ 两次输入的密码不一致！")
                elif len(new_pwd) < 6: # 增加一个简单的长度校验
                    st.warning("⚠️ 密码太短了，至少需要 6 位。")
                else:
                    with st.spinner("正在安全校验并更新密码..."):
                        success, msg = utils.direct_reset_sync(f_email.strip(), f_loginname.strip(), new_pwd)
                    
                    if success:
                        st.success(f"✅ {msg}")
                        st.balloons()
                        st.info("💡 现在您可以前往“登录”界面使用新密码进入系统。")
                    else:
                        st.error(f"❌ {msg}")
            else:
                st.warning("⚠️ 请完整填写表单中的所有项。")

def show_dashboard():
    st.success(f"当前登录：{st.session_state.user['realname']} ({st.session_state.user['loginname']})")
    st.json(st.session_state.user)
    if st.button("退出登录"):
        st.session_state.user = None
        st.session_state.token = None
        st.rerun()

if st.session_state.user:
    show_dashboard()
else:
    show_auth_pages()
