# AI 智能体服务平台

> 基于 Dify + Flask 的插件化智能体服务平台。支持多智能体共用一套基础服务，通过插件化机制快速扩展新的 AI 功能。

## 项目结构

```
dify-project-template/
├── README.md                      # 本文件（项目总览）
├── AGENTS.md                      # 开发参考手册（Dify DSL 设计规范）
├── deploy.sh                      # 部署脚本
├── backend/                       # Flask 后端服务
│   ├── app.py                     # 主服务入口（注册所有 Blueprint）
│   ├── requirements.txt           # Python 依赖
│   ├── core/                      # 核心模块（所有智能体共用）
│   │   ├── dify_client.py        # Dify API 封装（上传文件、调用工作流）
│   │   ├── auth.py               # Token 认证中间件
│   │   └── response.py           # 统一响应格式
│   └── plugins/                   # 各智能体插件
│       ├── job_ai.py             # 岗位 AI 辅助生成
│       └── ...                   # 后续新增的智能体
├── frontend/                      # 前端页面
│   ├── index.html                # 智能体平台入口（卡片式导航）
│   ├── core/                     # 共用前端组件（预留）
│   └── plugins/                  # 各智能体前端页面
│       └── job_ai.html           # 岗位 AI 页面
├── dsl/                           # Dify DSL 工作流定义
│   └── workflow.yml              # 岗位 AI 工作流（示例）
└── docs/
    └── architecture.md           # 架构设计详细说明
```

## 核心架构

### 插件化设计

```
┌─────────────────────────────────────────────────────────────┐
│                        AI 智能体服务平台                      │
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│   │  岗位 AI  │    │  聊天助手 │    │  待新增   │             │
│   │ job_ai   │    │ chat_bot│    │ xxx_ai   │             │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘             │
│        │               │               │                    │
│        └───────────────┼───────────────┘                    │
│                        │                                    │
│   ┌────────────────────┴────────────────────┐              │
│   │              Flask 后端服务               │              │
│   │  ┌────────────────────────────────────┐  │              │
│   │  │  核心模块 (core/)                   │  │              │
│   │  │  • dify_client.py - Dify API 封装   │  │              │
│   │  │  • auth.py        - Token 认证      │  │              │
│   │  │  • response.py    - 响应标准化      │  │              │
│   │  └────────────────────────────────────┘  │              │
│   │  ┌────────────────────────────────────┐  │              │
│   │  │  插件模块 (plugins/)                │  │              │
│   │  │  • job_ai.py      - 岗位 AI 路由    │  │              │
│   │  │  • xxx_ai.py      - 其他智能体路由   │  │              │
│   │  └────────────────────────────────────┘  │              │
│   └──────────────────────────────────────────┘              │
│                        │                                    │
│                        │ Dify API                          │
│                        ↓                                    │
│   ┌──────────────────────────────────────────┐              │
│   │           Dify 智能体引擎                 │              │
│   │  • 岗位 AI 工作流                         │              │
│   │  • 聊天助手工作流                         │              │
│   │  • 其他工作流                             │              │
│   └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 路由设计

每个智能体拥有独立的路由前缀，互不影响：

```
# 岗位 AI
POST /api/job_ai/analyze
POST /api/job_ai/generate
POST /api/job_ai/confirm

# 聊天助手（示例）
POST /api/chat_assistant/chat
POST /api/chat_assistant/stream

# 共用
GET  /health
GET  /                      # 智能体平台入口
GET  /job_ai               # 岗位 AI 页面
```

## 快速启动

### 1. 部署 Dify 工作流

```bash
# 安装 Dify Workflow CLI
pip install dify-ai-workflow-tools

# 登录 Dify Console
dify-workflow remote login --server http://<dify-host>:<port> --email <admin> --password <pwd> --profile default

# 导入工作流
dify-workflow remote push --file dsl/workflow.yml --force
```

### 2. 启动后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 修改 plugins/job_ai.py 中的 DIFY_API_KEY
python app.py          # 开发模式
# 或
gunicorn -w 1 -b 0.0.0.0:5000 --timeout 300 app:app   # 生产模式
```

### 3. 访问前端

```
http://localhost:5000/          # 智能体平台入口
http://localhost:5000/job_ai    # 岗位 AI
```

## 新增一个智能体

### 后端（3 步）

1. **复制插件模板**
   ```bash
   cp backend/plugins/job_ai.py backend/plugins/xxx_ai.py
   ```

2. **修改插件代码**
   - 修改 `Blueprint` 名称和 `url_prefix`
   - 修改 Dify API Key（每个智能体独立的工作流）
   - 调整表单字段

3. **注册插件**（`app.py` 中加一行）
   ```python
   from plugins.xxx_ai import xxx_ai_bp
   app.register_blueprint(xxx_ai_bp)
   ```

### 前端（2 步）

1. **复制前端模板**
   ```bash
   cp frontend/plugins/job_ai.html frontend/plugins/xxx_ai.html
   ```

2. **修改 API 路径和页面内容**
   ```javascript
   // 将 API_BASE + '/api/job_ai/xxx' 改为 '/api/xxx_ai/xxx'
   ```

3. **添加入口卡片**（`frontend/index.html`）

### Dify DSL（1 步）

新建 `dsl/xxx_ai.yml`，设计工作流，通过 CLI 推送。

## 核心特性

| 特性 | 说明 |
|------|------|
| **插件化架构** | 新增智能体只需复制模板、改字段名，30 分钟完成开发 |
| **共用基础服务** | Dify API 调用、文件上传、Token 认证全部封装在 core/ 模块 |
| **独立路由** | 每个智能体拥有 `/api/<name>/` 前缀，互不干扰 |
| **认证预留** | `core/auth.py` 已预留外部 Token 验证接口，接入即可使用 |
| **统一响应** | 所有 API 返回 `{code, message, data}` 标准化格式 |
| **异常处理** | 全局捕获异常，确保任何错误都返回 JSON 而非 HTML |

## 关键配置

- 每个插件中的 `DIFY_API_KEY` 需替换为实际 API Key
- `frontend/index.html` 中的入口卡片需要手动添加新的智能体
- 认证系统需要接入外部 Token 验证服务（`core/auth.py` 中预留接口）

## 开发参考

详见 [AGENTS.md](./AGENTS.md)，包含：
- Dify 工作流设计规范
- 文件上传处理最佳实践
- 前后端对接方式
- DSL 更新与发布流程
- 常见问题速查
