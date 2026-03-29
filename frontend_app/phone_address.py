import streamlit as st
from utils import (
    fetch_addresses, fetch_phones, 
    delete_address_api, delete_phone_api,
    add_member_address, add_member_phone  # 假设你已将之前的 add 函数放入 utils
)
import extra_streamlit_components as stx
import time
from auth_utils import fetch_user_from_backend
import utils


cookie_manager = stx.CookieManager(key="phone_address_manager")

# --- 身份恢复逻辑 ---
def sync_session_with_cookie():
    if st.session_state.get("user"):
        return

    token = cookie_manager.get("auth_token")

    if not token:
        return

    if "auth_retry_count" not in st.session_state:
        st.session_state.auth_retry_count = 0

    user_data = fetch_user_from_backend(token)

    if user_data:
        # 登录成功：记录状态并重置计数器
        st.session_state.user = user_data
        st.session_state.token = token
        st.session_state.auth_retry_count = 0
        st.rerun()
    else:
        # 登录失败：开始重试逻辑
        if st.session_state.auth_retry_count < 3:
            st.session_state.auth_retry_count += 1
            time.sleep(0.3) 
            st.warning(f"身份验证尝试中... 第 {st.session_state.auth_retry_count} 次")
            st.rerun()
        else:
            # 3 次均失败：判定 Token 失效，清理并重置
            cookie_manager.delete("auth_token")
            st.session_state.auth_retry_count = 0
            st.error("登录已失效，请重新登录")
            # 可选：st.rerun() 刷新到未登录状态

# 在页面逻辑开始处调用
sync_session_with_cookie()

st.set_page_config(page_title="会员资料一站式管理", layout="wide")
st.title("👤 会员扩展信息管理中心")


if st.session_state.get("user") and st.session_state.user.get("id"):
    member_id = st.session_state.user["id"]
    # 使用 Tabs 区分地址和电话，界面更整洁
    tab_addr, tab_phone = st.tabs(["📍 地址管理", "📞 电话管理"])

    # --- 地址管理标签页 ---
    with tab_addr:
        with st.expander("➕ 新增会员地址", expanded=False):
            # 1. 搜索框（非 Form 内部，因为搜索需要即时响应）
            addr_query = st.text_input("🔍 搜索并定位地址 (输入街道、城市或大厦名)", placeholder="例如：南京东路")
            
            selected_geo_id = None
            
            if addr_query:
                # 调用后端搜索接口（假设你封装了 utils.search_addresses_api）
                with st.spinner("正在匹配地址库..."):
                    addr_suggestions = utils.search_addresses_api(addr_query) 
                
                if addr_suggestions:
                    selected_addr_tuple = st.selectbox(
                        "请从匹配到的地址中选择：",
                        options=addr_suggestions,
                        index=None,
                        format_func=lambda x: x[0] # 显示 fulladdress
                    )
                    if selected_addr_tuple:
                        selected_geo_id = selected_addr_tuple[1] # 获取 addressid
                        st.success(f"📍 已选中: {selected_addr_tuple[0]}")
                else:
                    st.warning("❌ 未找到匹配地址，请尝试其他关键词")

            # 2. 提交表单
            with st.form("add_addr_confirm_form", clear_on_submit=True):
                is_def = st.checkbox("设为默认地址")
                
                submit_btn = st.form_submit_button("确认关联此地址")
                
                if submit_btn:
                    if selected_geo_id:
                        # 调用你之前的添加函数
                        res = add_member_address(member_id, selected_geo_id, is_def)
                        st.toast("✅ 地址添加成功！")
                        st.rerun()
                    else:
                        st.error("请先搜索并选择一个有效的地址后再提交")

        st.subheader("现有地址记录")
        addresses = fetch_addresses(member_id)

        if addresses:
            for addr in addresses:
                # 使用容器让 UI 更整洁
                with st.container():
                    c1, c2 = st.columns([4, 1])
                    
                    # 1. 仅显示图标、完整地址和默认标签
                    default_badge = " :blue[**[默认]**]" if addr.get('isdefault') else ""
                    display_text = f"🏠 {addr.get('fulladdress', '无地址信息')}{default_badge}"
                    
                    c1.markdown(display_text)
                    
                    # 2. 删除按钮
                    if c2.button("删除", key=f"del_addr_{addr['addressrecid']}", type="secondary", use_container_width=True):
                        if delete_address_api(addr['addressrecid']):
                            st.toast(f"✅ 地址已成功删除")
                            st.rerun()
                st.divider() # 添加分割线，视觉上更清晰
        else:
            st.info("暂无地址记录")

    # --- 电话管理标签页 ---
    with tab_phone:
        # 第一部分：新增电话表单
        with st.expander("➕ 新增会员电话", expanded=False):
            with st.form("add_phone_form", clear_on_submit=True):
                p_num = st.text_input("电话号码")
                p_type = st.selectbox("类型", ["手机", "固定电话", "办公", "其他"])
                is_pri = st.checkbox("设为主要联系方式")
                if st.form_submit_button("立即添加"):
                    if p_num:
                        add_member_phone(member_id, p_num, p_type, is_pri)
                        st.success("电话添加成功！")
                        st.rerun()
                    else:
                        st.warning("请输入电话号码")

        st.divider()

        # 第二部分：现有电话列表
        st.subheader("现有电话记录")
        phones = fetch_phones(member_id)
        if phones:
            for p in phones:
                c1, c2 = st.columns([4, 1])
                c1.write(f"📞 ID: **{p['phoneid']}** | {p['phonenumber']} ({p['phonetype']}) | {'🔴 主电话' if p['isprimary'] else '备用'}")
                if c2.button("删除", key=f"del_phone_{p['phoneid']}", type="secondary"):
                    delete_phone_api(p['phoneid'])
                    st.toast(f"已删除电话 {p['phoneid']}")
                    st.rerun()
        else:
            st.info("暂无电话数据")
else:
    st.warning("⚠️ 无法识别用户身份，请确保已登录并重试")