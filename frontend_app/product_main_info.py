import streamlit as st
import utils
import pandas as pd
import datetime
import random
import string

def generate_product_id(prefix="PRD"):
    """
    生成格式如: PRD-20240520-X8K2 的商品ID (共17位)
    """
    # 获取当前日期
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    
    # 生成4位随机大写字母和数字
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    return f"{prefix}-{date_str}-{random_str}"

st.title("🛡️ 商品主数据管理")

# --- A. 新增/编辑表单 ---
with st.expander("📝 新增商品信息"):
    with st.form("product_form", clear_on_submit=True):
        pid = generate_product_id()
        col1, col2 = st.columns(2)
        pname = col1.text_input("商品名称")
        price = col2.number_input("标准单价", min_value=0.0, step=0.01)

        col3, col4 = st.columns(2)
        unit = col3.text_input("单位", value="件")
        active = col4.checkbox("是否激活", value=True)
        
        submitted = st.form_submit_button("保存商品")
        if submitted:
            payload = {
                "productid": pid, "productname": pname,
                "standardprice": price, "unit": unit, "isactive": active
            }
            if utils.save_product(payload):
                st.success("数据已同步至数据库")
                st.rerun()

import streamlit as st
import utils

st.title("📦 商品信息管理")

# --- 阶段 1：搜索商品 ---
search_query = st.text_input("🔍 搜索并编辑货物：", placeholder="输入编号或名称关键词...")

selected_product_id = None

if search_query:
    with st.spinner("正在匹配货物..."):
        suggestions = utils.search_product_ids_and_names(search_query)
    
    if suggestions:
        selected_tuple = st.selectbox(
            "找到以下匹配项，请选择要编辑的商品：",
            options=suggestions,
            index=None,
            format_func=lambda x: x[0]
        )
        if selected_tuple:
            selected_product_id = selected_tuple[1]
    else:
        st.warning("❌ 未找到匹配的货物")

# --- 阶段 2：单独的 Expander 用于编辑 ---
if selected_product_id:
    # 获取该商品的最新详情用于填充表单
    current_data = utils.get_product_detail_api(selected_product_id)
    
    if current_data:
        with st.expander(f"📝 正在编辑：{current_data['productname']} ({selected_product_id})", expanded=True):
            with st.form("edit_product_form"):
                # ID 作为主键通常不允许修改，设为只读
                st.info(f"商品编号: {selected_product_id}")
                
                # 填充原始值
                new_name = st.text_input("商品名称", value=current_data['productname'])
                new_price = st.number_input("标准单价", value=float(current_data['standardprice']), step=0.01)
                new_unit = st.text_input("单位", value=current_data['unit'])
                new_active = st.checkbox("是否激活", value=current_data['isactive'])
                
                # 提交修改
                if st.form_submit_button("保存修改"):
                    update_payload = {
                        "productid": selected_product_id,
                        "productname": new_name,
                        "standardprice": new_price,
                        "unit": new_unit,
                        "isactive": new_active
                    }
                    if utils.save_product(update_payload, is_update=True):
                        st.success("✅ 商品信息更新成功！")
                        st.rerun()
                    else:
                        st.error("❌ 更新失败，请检查后端连接")
else:
    st.info("💡 请先在上方搜索并选择一个商品以开启编辑面板")

# --- B. 商品列表展示 ---
st.subheader("📋 现有商品目录")
products = utils.fetch_all_products()

if products:
    # 转换为 DataFrame 仅用于美化展示，不编辑
    df_display = pd.DataFrame(products)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.write("---")
    # 操作区：每行一个删除按钮
    for p in products:
        c1, c2, c3 = st.columns([2, 4, 1])
        c1.code(p['productid'])
        c2.write(f"**{p['productname']}** ({p['unit']}) - 💰{p['standardprice']}")
        
        # 删除按钮逻辑
        if c3.button("🗑️ 删除", key=f"del_{p['productid']}"):
            if utils.remove_product(p['productid']):
                st.toast(f"商品 {p['productid']} 已下架")
                st.rerun()
else:
    st.info("暂无商品信息，请先添加。")