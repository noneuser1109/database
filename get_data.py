import requests
import time
import psycopg
from psycopg import sql

# ----------------- ⚠️ 配置信息 -----------------
# 高德地图 API 配置 (校验最宽松)
GAODE_MAP_KEY = '8603eb836143c2427c9e7a0393d3c9a3'  # 替换成您的高德 Key
GEOCODE_URL = 'https://restapi.amap.com/v3/geocode/geo'
CITY = "合肥"  # 高德的城市参数要求只填城市名，无需加"市"

# KingBaseES 数据库配置 (请替换为您的实际配置)
DB_HOST = 'localhost'  # 例如: 'localhost'
DB_NAME = 'CustomerOrder'
DB_USER = 'system'
DB_PASSWORD = '18Monkey'
DB_PORT = '54321'  # 默认端口，请根据您的配置修改
TABLE_NAME = 'address_geocoding'

# 要查询的合肥市地址列表
ADDRESS_LIST = [
    # 🌟 重点地标和商业区 (Central Landmarks & Business Districts)
    "合肥市政务区天鹅湖万达广场",
    "合肥市包河区万达广场",
    "合肥步行街",
    "合肥银泰中心",
    "合肥新地中心",
    "合肥大剧院",
    "安徽省博物馆新馆",
    "合肥之心城",
    "国购广场",
    "三孝口",
    "合肥淮河路步行街",
    "融创茂",
    "罍街",
    "天玥中心",
    "合肥金融港",

    # 🏫 高校和科研机构 (Universities & Research Institutes)
    "中国科学技术大学东校区",
    "合肥工业大学屯溪路校区",
    "安徽大学磬苑校区",
    "安徽医科大学",
    "安徽师范大学合肥校区",
    "安徽农业大学",
    "中科院合肥物质科学研究院",
    "合肥学院",
    "安徽建筑大学",
    "合肥职业技术学院",

    # 🏢 行政和交通枢纽 (Government & Transportation Hubs)
    "安徽省人民政府",
    "合肥市人民政府",
    "合肥南站",
    "合肥站",
    "合肥新桥国际机场",
    "合肥客运南站",
    "合肥市公安局",
    "合肥市中级人民法院",
    "安徽省图书馆",
    "合肥市规划局",

    # 🏙️ 主要行政区和街道 (Main Districts and Streets)
    "庐阳区政府",
    "蜀山区政府",
    "包河区政府",
    "瑶海区政府",
    "滨湖新区管委会",
    "新站高新区管委会",
    "合肥高新技术产业开发区管委会",
    "长江中路",
    "徽州大道",
    "马鞍山路",
    "合作化南路",
    "望江路",
    "金寨路",
    "长江西路",
    "习友路",

    # 🏞️ 公园和风景区 (Parks and Scenic Spots)
    "合肥植物园",
    "大蜀山国家森林公园",
    "天鹅湖公园",
    "逍遥津公园",
    "包公园",
    "三国遗址公园",
    "渡江战役纪念馆",
    "岸上草原",
    "翡翠湖公园",
    "杏花公园",

    # 🏘️ 知名住宅区和商业综合体 (Residential Areas & Malls)
    "合肥栢景湾小区",
    "华润橡树湾",
    "文一塘溪津门",
    "融创城",
    "万科金色名郡",
    "政务区蔚蓝商务港",
    "庐阳区财富广场",
    "琥珀山庄",
    "庐州公园",
    "金大地时代城",
    "合肥宝马4S店",
    "合肥北城世纪城",
    "合肥恒大中心",

    # 🏥 医院 (Hospitals)
    "安徽省立医院",
    "安徽医科大学第一附属医院",
    "合肥市第一人民医院",
    "中国科学技术大学附属第一医院(安徽省立医院南区)",
    "合肥市第二人民医院",
    "安徽省儿童医院",
    "合肥市中医院",

    # 🗺️ 其他重要地点 (Other Important Locations)
    "合肥奥体中心",
    "合肥骆岗机场公园",
    "中国邮政合肥分公司",
    "中国银行安徽省分行",
    "合肥海关",
    "合肥市烟草专卖局",
    "合肥市文化馆",
    "合肥电视台",
    "合肥报业大厦",
    "合肥东部新中心",
    "北城办",
    "大圩镇政府",
    "长丰县人民政府",
    "肥西县政府",
    "庐江县人民政府",
    "巢湖市人民政府",
    "肥东县人民政府",
    "合肥科技馆新馆",
    "合肥体育中心",
    "合肥市气象局"
]


# ---------------------------------------------

def get_gaode_geocode(address, key=GAODE_MAP_KEY, url=GEOCODE_URL):
    """调用高德地图地理编码 API 获取指定地址的信息 (最宽松校验)。"""

    # 构造请求参数
    params = {
        'address': address,
        'city': CITY,
        'key': key,  # 唯一的校验参数
        'output': 'json',
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # 检查 API 返回状态
        if data.get('status') == '1' and data.get('infocode') == '10000' and data.get('count') != '0':
            # 高德结果列表在 geocodes 键下
            result = data.get('geocodes', [{}])[0]

            # 解析经纬度: 高德返回 'lng,lat' 格式
            location_str = result.get('location', ',')
            lng, lat = location_str.split(',') if location_str else (None, None)

            # 提取所需的字段
            geocode_data = (
                address,  # FullAddress
                lat,  # Latitude
                lng,  # Longitude
                result.get('confidence'),  # ConfidenceScore (1-10)
                result.get('level'),  # GeocodeLevel
                'GaodeMap',  # SourceSystem
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())  # GeocodedDate
            )
            return geocode_data
        else:
            print(f"❌ API 调用失败：{address}，错误信息: {data.get('info', '未知错误')}")
            return None

    except requests.RequestException as e:
        print(f"❌ 请求异常：{address}，错误详情: {e}")
        return None


# --- insert_data_to_kingbase 函数 (保持与之前 psycopg3 版本一致) ---
def insert_data_to_kingbase(data_list):
    """连接 KingBaseES (使用 psycopg3) 并批量插入数据。"""
    if not data_list:
        print("没有有效数据需要插入数据库。")
        return

    conn = None
    try:
        conn_string = (
            f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} "
            f"password={DB_PASSWORD} port={DB_PORT}"
        )
        conn = psycopg.connect(conn_string)
        conn.autocommit = False

        with conn.cursor() as cursor:
            columns = (
                "fulladdress",  # 对应 VARCHAR(200)
                "latitude",  # 对应 DECIMAL(10,8)
                "longitude",  # 对应 DECIMAL(11,8)
                "confidencescore",  # 对应 DECIMAL(4,2)
                "geocodelevel",  # 对应 VARCHAR(20)
                "sourcesystem",  # 对应 VARCHAR(20)
                "geocodeddate"  # 对应 TIMESTAMP
            )
            insert_query = sql.SQL(
                "INSERT INTO {} ({}) VALUES ({})"
            ).format(
                sql.Identifier(TABLE_NAME),
                sql.SQL(', ').join(map(sql.Identifier, columns)),
                sql.SQL(', ').join(sql.Placeholder() * len(columns))
            )

            cursor.executemany(insert_query, data_list)
            conn.commit()
            print(f"\n✅ 成功将 {len(data_list)} 条数据批量插入到 KingBaseES 表 '{TABLE_NAME}' (使用高德地图数据)。")

    except psycopg.Error as e:
        print(f"\n❌ KingBaseES 数据库操作失败：{e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"\n❌ 发生其他错误：{e}")
    finally:
        if conn:
            conn.close()

        # --- 主执行逻辑 ---


if __name__ == "__main__":
    if GAODE_MAP_KEY == 'YOUR_GAODE_MAP_KEY' or DB_PASSWORD == 'your_db_password':
        print("请先将代码中的 GAODE_MAP_KEY 和 KingBaseES 数据库配置信息替换为您自己的值！")
    else:
        print(f"开始查询 {CITY} 的地址数据并准备写入 KingBaseES (使用高德地图，校验最宽松)...")

        geocode_data_to_insert = []
        for address in ADDRESS_LIST:
            data_tuple = get_gaode_geocode(address)
            if data_tuple:
                geocode_data_to_insert.append(data_tuple)

            time.sleep(0.5)

            # 写入数据库
        insert_data_to_kingbase(geocode_data_to_insert)