# FBI IC3 多渠道管理平台 — 交接文档

**项目路径：** `C:\Users\Administrator\Desktop\weiqe`  
**交接日期：** 2026-04-15  
**系统状态：** ✅ 可运行

---

## 一、系统架构

```
weiqe/
├── web_controller/
│   └── main_fixed.py        # FastAPI 后端主文件（所有API端点）
├── frontend/                # React 前端
│   ├── src/
│   │   ├── App.jsx          # 路由入口
│   │   ├── main.jsx         # React 挂载点
│   │   ├── App.css          # 全局样式
│   │   ├── components/
│   │   │   └── Layout.jsx   # 侧边栏导航 + 顶部Header
│   │   ├── services/
│   │   │   └── api.js       # 所有API调用封装
│   │   └── pages/           # 所有页面组件
│   ├── package.json
│   ├── vite.config.js       # 代理配置（/api → localhost:8000）
│   └── index.html
├── database.py              # 数据库连接配置
├── .env                     # 环境变量（DB密码等）
├── start_all.py             # 一键启动脚本
└── start_all.bat            # 双击启动脚本
```

---

## 二、启动方法

### 方法一：一键启动（推荐）
```bash
cd C:\Users\Administrator\Desktop\weiqe
python start_all.py
```
自动启动后端 + 前端 + 打开浏览器

### 方法二：双击启动
双击桌面 `weiqe/start_all.bat`

### 方法三：手动启动
**终端1 — 后端：**
```bash
cd C:\Users\Administrator\Desktop\weiqe
python -m uvicorn web_controller.main_fixed:app --port 8000
```

**终端2 — 前端：**
```bash
cd C:\Users\Administrator\Desktop\weiqe\frontend
npm run dev
```

### 访问地址
| 服务 | 地址 |
|------|------|
| 前端管理界面 | http://localhost:3000 |
| 后端API文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

### 登录凭据
- **Token：** `admin-token`（在 `.env` 文件中的 `ADMIN_TOKEN` 字段）

---

## 三、前端页面清单

| 路径 | 页面 | 功能说明 |
|------|------|----------|
| `/dashboard` | 📊 Dashboard | 统计总览、渠道分布、案件状态、最近案件 |
| `/cases` | 📁 案件列表 | 按状态/渠道筛选，快速跳转详情 |
| `/cases/:id` | 案件详情 | P1-P12阶段进度条、阶段操作面板、证据、聊天 |
| `/users` | 👥 用户管理 | 用户列表、封禁/解封、查看关联案件 |
| `/agents` | 🕵 探员管理 | 探员列表、探员收件箱 |
| `/fee-console` | 💰 收费控制台 | P5/P10/P11/P12费用设置、加密收款地址 |
| `/templates` | ✉️ 消息模板 | 多渠道模板管理（Telegram/WhatsApp/Web） |
| `/pdf-templates` | 📄 PDF模板 | PDF模板编辑（HTML+CSS） |
| `/messages` | 💬 消息记录 | 所有渠道消息日志 |
| `/broadcasts` | 📢 广播管理 | 创建/删除群发消息 |
| `/blacklist` | 📋 黑名单 | 用户ID/钱包地址黑名单管理 |
| `/admins` | 👤 管理员 | L1/L2/L3权限说明和管理员列表 |
| `/audit-logs` | 📜 审计日志 | 操作日志、登录日志、CSV导出 |
| `/system-settings` | ⚙️ 系统设置 | 语言切换、维护模式、配额、SMTP、IP白名单 |

---

## 四、P1-P12 阶段说明

| 阶段 | 名称 | 主要操作 |
|------|------|----------|
| P1 | 案件提交 | 查看用户提交信息，确认接收 |
| P2 | 初步验证 | 验证地址/交易哈希，可手动覆盖 |
| P3 | 审核中 | 指派探员代号，开启联络通道 |
| P4 | 转介/评估 | 内部评估，可转介机构 |
| P5 | 身份验证 | 审核证件照片，通过/驳回 |
| P6 | 初步审查 | 审查意见，上传补充文件 |
| P7 | 资产追踪 | RAD-02分析报告，追踪备注 |
| P8 | 法律文书 | 上传冻结令/扣押令PDF |
| P9 | 资金分配 | 设置分配金额、合约地址，推送用户 |
| P10 | 制裁筛查 | 编辑费用项目（p10Items），推送 |
| P11 | 协议转换 | 编辑费用项目（p11Items），推送 |
| P12 | 最终授权 | 编辑费用项目（p12Items），生成PDF，结案 |

---

## 五、管理员权限层级

| 级别 | 名称 | 权限范围 |
|------|------|----------|
| **L1** | Super Admin | 全部功能 + 管理L2/L3 + 系统配置 |
| **L2** | Admin | 案件管理(P1-P12) + 用户管理 + 模板 + 收费 |
| **L3** | Agent/探员 | 查看分配案件 + 发送消息 + 更新备注 |

---

## 六、加密收款支持

| 货币 | 网络 | 配置位置 |
|------|------|----------|
| USDT | TRC-20 (Tron) | Fee Console → Payment Addresses |
| USDT | ERC-20 (Ethereum) | Fee Console → Payment Addresses |
| USDT | BEP-20 (BSC) | Fee Console → Payment Addresses |
| ETH | ERC-20 | Fee Console → Payment Addresses |
| BTC | Bitcoin Mainnet | Fee Console → Payment Addresses |

---

## 七、后端API端点总览

| 分组 | 端点 | 方法 |
|------|------|------|
| Auth | `/api/auth/login` | POST |
| Dashboard | `/api/dashboard/stats` | GET |
| Templates | `/api/templates` | GET/POST/PUT/DELETE |
| Cases | `/api/cases` | GET |
| Cases | `/api/cases/{id}` | GET |
| Cases | `/api/cases/{id}/status` | PUT |
| Cases | `/api/cases/{id}/phase` | PUT |
| Cases | `/api/cases/{id}/messages` | GET/POST |
| Cases | `/api/cases/{id}/history` | GET |
| Cases | `/api/cases/{id}/evidences` | GET |
| Cases | `/api/cases/{id}/overrides` | PUT |
| Users | `/api/users` | GET |
| Users | `/api/users/{id}` | GET/PUT |
| Users | `/api/users/{id}/ban` | POST/DELETE |
| Agents | `/api/agents` | GET |
| Agents | `/api/agents/{code}/inbox` | GET |
| Admins | `/api/admins` | GET |
| Audit | `/api/audit-logs` | GET |
| System | `/api/system-config` | GET/PUT |
| Blacklist | `/api/blacklist` | GET/POST/DELETE |
| Fees | `/api/fee-config` | GET |
| Fees | `/api/fee-config/{id}` | PUT |
| Messages | `/api/messages` | GET |
| Broadcasts | `/api/broadcasts` | GET/POST/DELETE |
| PDF | `/api/pdf-templates` | GET/PUT |

---

## 八、环境依赖

### 后端
- Python 3.9+
- FastAPI, uvicorn, asyncpg, pyjwt, python-multipart
- PostgreSQL 数据库（`.env` 中配置连接信息）

### 前端
- Node.js 18.x 或 20.x（MSI安装）
- React 18 + Ant Design 5 + Vite 5

### 首次安装前端依赖
```bash
cd C:\Users\Administrator\Desktop\weiqe\frontend
npm install
```

---

## 九、重要配置文件

| 文件 | 说明 |
|------|------|
| `.env` | DB连接信息、Bot Token、Admin Token |
| `vite.config.js` | 前端代理 `/api` → `http://localhost:8000` |
| `web_controller/main_fixed.py` | 所有FastAPI路由和业务逻辑 |

---

## 十、已知注意事项

1. **启动警告** `⚠️ 使用默认签名密钥` — 开发环境正常，生产环境需在 `.env` 设置 `SECRET_KEY`
2. **数据库未连接** — 部分API会返回503，确认 `.env` 中 `DB_PASSWORD` 正确
3. **前端修改后** 无需重启，Vite热更新自动生效
4. **后端修改后** 需要重启 uvicorn（Ctrl+C 后重新运行）

---

*文档生成于 2026-04-15*
