import streamlit as st

MARKDOWN_DESCRIPTION = """
    ## 🛍️ 客户订单父表 (CustomerOrder) 字段设计

下表详细列出了客户订单父表 `CustomerOrder` 的所有字段、数据类型、可空性以及额外说明。

| 编号 | 字段名称 | 中文简称 | 数据类型 | 可空 | 额外说明/备注 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. | **OrderID** | 订单编号 | `CHAR(20)` | No | **主键**。 |
| 2. | **MemberID** | 订货人 | `CHAR(20)` | No | 会员用户名，关联 `MemberInfo` 表。 |
| 3. | **Receiver** | 收货人 | `CHAR(30)` | No | 默认与订货人一致，支持修改。 |
| 4. | **ReceiveAddress**| 收货地址 | `CHAR(100)`| No | 从会员信息中带出，支持修改。 |
| 5. | **Telephone** | 联系电话 | `CHAR(20)` | Yes | - |
| 6. | **Mobilephone** | 联系手机 | `CHAR(20)` | No | - |
| 7. | **OrderState** | 订单状态 | `CHAR(10)` | No | **只存储后台状态**。前台状态（3个不同状态）需通过判断映射。 |
| 8. | **SubmitDate** | 下单时间 | `DATETIME` | No | 系统当前日期时间。 |
| 9. | **Operator** | 接单人 | `CHAR(30)` | No | 操作员名称，关联 `fxh_OperatorInfo` 表。 |
| 10. | **OriginalMoney**| 标准金额 | `DOUBLE(6, 2)`| Yes | 不含运费，按标准价计算的总金额。 |
| 11. | **DiscountedMoney**| 折后金额 | `DOUBLE(6, 2)`| Yes | 计入常规优惠后的总金额，不包括审批让利。 |
| 12. | **PayedMoney** | 成交金额 | `DOUBLE(6, 2)`| Yes | **最终交易金额**，包含审批让利，默认与折后金额一致。 |
| 13. | **Approver** | 审批人 | `CHAR(12)` | Yes | - |
| 14. | **IsEmergency** | 是否加急 | `BOOL` | Yes | 加急订单，不能享受免运费。 |
| 15. | **ConditionFeightFree**| 免运费条件 | `INT` | Yes | 达到该金额，自动免运费。 |
| 16. | **LogisticsCharge**| 配送费 | `DOUBLE(3, 2)`| Yes | 实际配送费用。 |
| 17. | **FinalTotalMoney**| 最后总金额 | `DOUBLE(6, 2)`| Yes | **实收配送费 + 成交金额** (`LogisticsCharge` + `PayedMoney`)。 |
| 18. | **Remark** | 顾客留言 | `CHAR(100)`| Yes | 顾客留言信息。 |

---

## 🚦 订单状态映射说明

订单父表 `CustomerOrder` 中的 `OrderState` 字段**只存储后台状态**。前台向客户展示的状态，需要根据 `OrderState` 字段的值进行判断和映射。

| 后台状态 (OrderState) | 对应的前台展示状态 | 备注 |
| :--- | :--- | :--- |
| 未付款 | **未付款** | - |
| 关闭交易 | **关闭交易** | - |
| 已付款 | **已付款** | - |
| 未发货 | **已付款** | 前台状态不同之一。 |
| 已安排配送 | **已付款** | 前台状态不同之二。 |
| 已发货未付款 | **已发货未付款** | - |
| 未确认收货 | **已发货** | 前台状态不同之三。 |
| 已发货 | **已发货** | - |
| 未评价 | **未评价** | - |
| 交易成功 | **交易成功** | - |
| 申请退款 | **申请退款** | - |
| 退款成功 | **退款成功** | - |"""

st.markdown(MARKDOWN_DESCRIPTION)