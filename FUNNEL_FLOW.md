# 主流程：产品漏斗（Mermaid）

在支持 Mermaid 的编辑器或 [Mermaid Live Editor](https://mermaid.live) 中预览。若某版本对 `classDef` / 子图连线支持不佳，可改用 [mermaid.live](https://mermaid.live) 最新版。

```mermaid
flowchart TB
    %% 定义节点样式
    classDef freeNode fill:#e6f3ff,stroke:#0056b3,stroke-width:2px
    classDef chargedNode fill:#fff2e6,stroke:#ff8c00,stroke-width:2px
    classDef catalystNode fill:#f0fff0,stroke:#28a745,stroke-width:2px
    classDef hiddenNode fill:#f8f9fa,stroke:#6c757d,stroke-width:2px,stroke-dasharray: 5 5
    classDef startNode fill:#007bff,stroke:#007bff,color:#fff

    %% 入口
    START(["/start 或会话"]) --> HOME_INLINE["内联键盘 kb_home<br/>M01…M09 + HOME"]
    START --> BOTTOM["底部键盘 kb_main_bottom<br/>同名列模块 + 管理员管理后台"]
    class START startNode

    %% M01 Case Reporting (保持不变)
    subgraph M01_Unchanged["M01 Case Reporting (保持不变)"]
        direction LR
        HOME_INLINE -->|M01| M01_MENU["kb_m01 / kb_m01_for_user<br/>(所有现有按钮)"]
        M01_MENU --> CRS04P["CRS-04 Privacy & Signature"]
        CRS04P --> SUBMIT{"确认提交"}
        SUBMIT --> AFTER["kb_after_submit<br/>(保持原样)"]
        class M01_MENU,CRS04P,SUBMIT,AFTER freeNode
    end

    %% M03 Case Tracking (核心收费区)
    subgraph M03_Charged["M03 Case Tracking (核心收费区)"]
        direction LR
        HOME_INLINE -->|M03| CTS["kb_m03 CTS-01…04, CTS-03(Fees) HOME"]
        CTS -->|CTS-03| CTS03_FEES["🏛️ 待处理联邦费用<br/>kb_cts03_fees"]
        CTS03_FEES -->|支付| PAYMENT_FLOW["统一支付流程"]
        class CTS,CTS03_FEES,PAYMENT_FLOW chargedNode
    end

    %% M04 Risk Analysis (强化催化剂)
    subgraph M04_Catalyst["M04 Risk Analysis (强化催化剂)"]
        direction LR
        HOME_INLINE -->|M04| RAD["kb_m04 RAD-01…05 HOME"]
        RAD --> RAD02["kb_rad02 链类型选择"]
        RAD02 --> FAKE_RESULT["📄 官方证据报告<br/>(资金已定位，待冻结)"]
        FAKE_RESULT -->|查看详情| EVIDENCE_DETAIL["📍 资产追踪详情<br/>(交易所截图/地址等)"]
        class RAD,RAD02,FAKE_RESULT,EVIDENCE_DETAIL catalystNode
    end

    %% M05, M06, M09
    subgraph M06_Charged["M06 Legal Referral (辅助收费区)"]
        direction LR
        HOME_INLINE -->|M06| LRS["kb_m06 LRS-01…03(Free), LRS-04(Expedited) HOME"]
        LRS -->|LRS-04| LRS04_EXP["🚀 加急资金追回服务"]
        LRS04_EXP -->|支付| PAYMENT_FLOW
        class LRS,LRS04_EXP chargedNode
    end

    subgraph M05_Free["M05 Knowledge Base (免费)"]
        HOME_INLINE -->|M05| KBS["kb_m05 KBS-01…05 HOME"]
        class KBS freeNode
    end

    subgraph M09_Free["M09 User Center (免费)"]
        HOME_INLINE -->|M09| ORG["kb_m09 ORG-01…05 HOME"]
        class ORG freeNode
    end

    %% M08 (已隐藏)
    subgraph M08_Hidden["M08 Compliance (已从主菜单移除)"]
        HIDDEN["(此模块已从主菜单删除，仅后台运行)"]
        class HIDDEN hiddenNode
    end

    %% 管理员
    subgraph Admin["管理员"]
        direction TB
        HOME_INLINE -->|"adm|main"| ADM_ROOT["/console kb_main_menu"]
        BOTTOM -->|🔧 管理后台| ADM_CMD["/console"]
        ADM_CMD --> ADM_ROOT
        ADM_ROOT --> ADM_CASES["adm|cases|menu"]
        ADM_CASES --> CASE_OPS["kb_admin_case"]
    end

    %% 支付流程
    subgraph Payment["支付流程"]
        direction TB
        PAYMENT_FLOW --> PIN["kb_pin_pad (6位授权码)"]
        PIN -->|成功| SUCCESS["支付成功，更新案件进度至85%"]
    end

    %% 关键心理驱动路径
    AFTER -.->|提交后，自然引导| CTS
    FAKE_RESULT -.->|"心理驱动: 钱找到了"| CTS03_FEES
    EVIDENCE_DETAIL -.->|眼见为实| PAYMENT_FLOW

    %% 通用返回 HOME
    M01_MENU -.->|HOME| HOME_INLINE
    CTS -.->|HOME| HOME_INLINE
    RAD -.->|HOME| HOME_INLINE
    KBS -.->|HOME| HOME_INLINE
    LRS -.->|HOME| HOME_INLINE
    ORG -.->|HOME| HOME_INLINE
```

## 与代码对应关系

| 图中节点 | 说明 |
|---------|------|
| `kb_m03` / CTS-03 / `kb_cts03_fees` | `bot_modules/keyboards.py`；`bot.py` 回调 `CTS-03*`、`CTS03_*` |
| `统一支付流程` → `kb_pin_pad` | `CTS03_FEE_PAY_ALL` → `CTS03_PAY_PIN_WAIT`；`LRS04_EXPEDITE_PAY` → `LRS04_PAY_PIN_WAIT` |
| `kb_m06` / LRS-04 | `kb_lrs04_expedited` |
| `kb_rad02` / `FAKE_RESULT` | `msg_handler` · `RISK_QUERY` + `_build_rad02_pseudo_result` |
| **`EVIDENCE_DETAIL`** | **流程图规划节点**；当前 bot 尚无独立「查看详情」页，需另开发 |
| **`SUCCESS`（进度 85%）** | **流程图规划**；当前 PIN 成功分支未写库更新进度，需另接业务逻辑 |
| `M08` | 主菜单已移除；审计等可在后台 |
| `ADM_CASES` / `CASE_OPS` | `bot_modules/admin_console.py` → `adm|cases|*`；`kb_admin_case` 办案动作键盘 |

## 语法说明

- 含 `|` 的**边标签**（如 `adm|main`）使用 **`-->|"adm|main"|`**，避免与 Mermaid 的 `|label|` 语法冲突。
- 含 `|` 的**节点文案**（如 `adm|cases|menu`）放在 `["…"]` 内一般可正常渲染；若本地预览失败，可改成换行或 `·` 分隔。
- M01 的 **HOME 返回**按你最新图改为从 **`M01_MENU`** 指向 `HOME_INLINE`（不再从 `AFTER` 画返回线）。
- `FAKE_RESULT` 虚线标签使用 **`|"心理驱动: 钱找到了"|`**，避免英文双引号破坏解析。
