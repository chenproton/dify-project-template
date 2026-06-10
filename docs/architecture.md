# 架构设计说明

## 版本

v2.0 - 插件化智能体服务平台

## 整体架构

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

## 插件化设计原则

### 1. 共用 vs 独立

| 对比项 | 共用 (core/) | 独立 (plugins/) |
|--------|-------------|----------------|
| **Dify API 调用** | ✅ 封装在 dify_client.py | ❌ 直接引用 |
| **Token 认证** | ✅ 全局中间件 | ❌ 无需处理 |
| **响应格式** | ✅ 统一函数 | ❌ 直接调用 |
| **路由前缀** | ✅ 框架自动处理 | ❌ 在 Blueprint 中定义 |
| **业务逻辑** | ❌ 不涉及 | ✅ 每个插件独立实现 |
| **Dify 工作流** | ❌ 不涉及 | ✅ 每个插件独立配置 |

### 2. 为什么这样设计？

- **维护成本低**：一个人维护多个智能体，共用代码只需改一处
- **开发速度快**：新增智能体只需复制模板、改字段名，30 分钟完成
- **灵活度高**：完全不同的交互（如聊天对话）可以独立实现，不受标准流程限制
- **故障隔离**：一个智能体挂了不影响其他（虽然当前不要求强隔离）

## 后端架构

### 目录结构

```
backend/
├── app.py                    # Flask 主入口
│   ├── 导入所有 Blueprint
│   ├── 注册全局中间件（认证）
│   └── 注册静态文件路由
├── core/                     # 核心模块（共用）
│   ├── dify_client.py       # Dify API 客户端
│   ├── auth.py              # Token 认证
│   └── response.py          # 响应标准化
└── plugins/                  # 插件模块（独立）
    ├── job_ai.py            # 岗位 AI 示例
    └── xxx_ai.py            # 其他智能体
```

### 核心模块说明

#### dify_client.py

封装了所有与 Dify 交互的操作：

```python
class DifyClient:
    def upload_file(self, file_stream, filename, content_type) -> str
    def build_file_input(self, file_stream, filename, content_type) -> dict
    def run_workflow(self, inputs, user="user-001", timeout=300) -> dict
    def clean_think_tags(self, text) -> str
```

#### auth.py

Flask `before_request` 中间件，全局拦截所有请求：

```python
def auth_middleware():
    # 1. 跳过白名单路径（/health, /, /index.html 等）
    # 2. 从 Header/Form/Query 获取 token
    # 3. 调用外部系统验证 token（预留接口）
    # 4. 将 token_info 挂载到 request
```

**预留接口**：`verify_token(token)` 函数需要接入外部系统的 Token 验证 API。

#### response.py

统一响应格式：

```python
{
    "code": 200,           # HTTP 状态码
    "message": "success",  # 提示信息
    "data": { ... }        # 实际数据
}
```

### 插件开发规范

#### 插件模板（job_ai.py）

```python
from flask import Blueprint, request, jsonify
from core.dify_client import DifyClient
from core.response import success_response, error_response, parse_dify_outputs

# 每个插件独立的 Dify 配置
DIFY_API_KEY = "your-api-key"
DIFY_API_URL = "http://127.0.0.1:8081/v1/workflows/run"
DIFY_UPLOAD_URL = "http://127.0.0.1:8081/v1/files/upload"

dify_client = DifyClient(DIFY_API_KEY, DIFY_API_URL, DIFY_UPLOAD_URL)

# 创建 Blueprint，定义路由前缀
bp = Blueprint('xxx_ai', __name__, url_prefix='/api/xxx_ai')

@bp.route("/analyze", methods=["POST"])
def analyze():
    try:
        # 1. 获取请求参数
        # 2. 如有文件，调用 dify_client.build_file_input()
        # 3. 组装 inputs
        # 4. 调用 dify_client.run_workflow(inputs)
        # 5. 清洗输出（如去掉 <think> 标签）
        # 6. 返回 success_response(data=outputs)
    except Exception as e:
        return jsonify(error_response(str(e))), 500
```

#### 注册插件（app.py）

```python
from plugins.job_ai import job_ai_bp
from plugins.xxx_ai import xxx_ai_bp  # 新增

app.register_blueprint(job_ai_bp)
app.register_blueprint(xxx_ai_bp)       # 新增
```

## 前端架构

### 目录结构

```
frontend/
├── index.html                # 智能体平台入口（卡片式导航）
├── core/                     # 共用前端组件（预留）
└── plugins/                  # 各智能体前端页面
    ├── job_ai.html          # 岗位 AI 示例
    └── xxx_ai.html          # 其他智能体
```

### 入口页面（index.html）

卡片式导航，展示所有可用的智能体：

```html
<div class="agent-grid">
    <a href="/job_ai" class="agent-card">
        <div class="agent-icon">💼</div>
        <div class="agent-name">岗位 AI 辅助生成</div>
        <div class="agent-desc">根据岗位描述智能拆解...</div>
    </a>
    <!-- 新增智能体卡片 -->
</div>
```

### 插件前端开发规范

1. **API 路径**：使用 `/api/xxx_ai/` 前缀
2. **状态管理**：每个页面独立的 `state` 对象
3. **错误处理**：`try/catch` + `console.error` + `alert`

## 数据流（以岗位 AI 为例）

### 第一步：输入需求（analyze）

```
用户输入 ──→ 前端 Tab 切换 ──→ FormData ──→ POST /api/job_ai/analyze
                                               │
                                               ├── 有文件 → DifyClient.upload_file()
                                               │           └──→ inputs["file"]
                                               └──→ DifyClient.run_workflow(inputs)
                                                        │
                                                        ├──→ document-extractor → file_text
                                                        └──→ LLM analyze → analyze_result (JSON)
```

### 第二步：选择岗位（generate）

```
用户勾选岗位 ──→ POST /api/job_ai/generate
                     │
                     ├──→ suggest_job (JSON 数组)
                     ├──→ choose_id (逗号分隔)
                     ├──→ file_text (缓存)
                     └──→ DifyClient.run_workflow(inputs)
                              │
                              ├──→ if-else (stage == "generate")
                              ├──→ doc_extractor_generate（如有新文件）
                              ├──→ LLM generate
                              └──→ Code 节点校验 → generate_result (JSON 数组)
```

### 第三步：预览岗位（confirm）

```
用户点击下一步 ──→ POST /api/job_ai/confirm
                       │
                       ├──→ jobs (JSON 数组)
                       └──→ DifyClient.run_workflow(inputs)
                                │
                                ├──→ if-else (stage == "confirm")
                                └──→ Code 格式化 → confirm_result
```

## Dify DSL 架构

### 工作流分支设计

```
start_node (variables: stage, job_name, industry, description, file, file_text, count, suggest_job, choose_id, jobs_json)
    │
    └──→ if-else (stage)
            │
            ├──→ "analyze"  → doc_extractor → LLM analyze → end (analyze_result, file_text)
            │
            ├──→ "generate" → doc_extractor_generate → LLM generate → Code 校验 → end (generate_result, success)
            │
            └──→ "confirm"  → Code 格式化 → end (confirm_result, status)
```

### 关键设计决策

#### 1. 为什么 analyze 和 generate 都有 doc_extractor？

- **analyze**：用户第一步上传文件，需要提取文本用于分析
- **generate**：用户可能在第二步也上传文件（如补充材料），需要重新提取
- **file_text 缓存**：前端会将 analyze 提取的 file_text 传递给 generate，避免重复上传

#### 2. 为什么用 Code 节点做 JSON 校验？

- LLM 输出不稳定，可能包含 markdown 代码块、`<think>` 标签等
- Code 节点可以：去掉 think 标签、清理 markdown、提取 JSON 数组、设置默认值
- 确保下游节点拿到的是干净、格式正确的 JSON

#### 3. 能力点数量从 2-4 改为 10-20 的影响

- LLM 输出 token 增加，生成时间变长
- gunicorn timeout 需要从 30 秒调整为 300 秒
- 前端需要显示更长的加载时间提示

## 部署架构

### 生产环境

```
用户浏览器
    │
    │ HTTPS (443)
    ↓
┌─────────────┐
│  OpenResty  │  ← SSL 终止、反向代理
│  (1Panel)   │
└──────┬──────┘
       │ HTTP (5000)
       ↓
┌─────────────┐
│  Gunicorn   │  ← Flask 应用
│  (4 workers)│
└──────┬──────┘
       │ HTTP (8081)
       ↓
┌─────────────┐
│   Dify      │  ← AI 工作流引擎
│  (Docker)   │
└─────────────┘
```

### 部署步骤

1. **推送 DSL**：`dify-workflow remote push --file dsl/xxx.yml --app-id <id> --force`
2. **发布工作流**：调用 Dify publish API
3. **上传代码**：SCP 到服务器 `/opt/job-ai/`
4. **重启服务**：`bash start.sh`

## 认证设计

### 当前状态

- **开发阶段**：认证中间件放行所有请求（`verify_token` 返回 valid=True）
- **生产阶段**：需要接入外部系统的 Token 验证 API

### 接入方式

修改 `backend/core/auth.py` 中的 `verify_token` 函数：

```python
def verify_token(token):
    """接入外部系统的 Token 验证 API"""
    resp = requests.post("https://your-auth-system.com/verify", 
                        json={"token": token},
                        timeout=5)
    return resp.json()
```

### Token 传递方式

- **Header**：`X-API-Token: <token>`
- **FormData**：`token=<token>`
- **Query**：`?token=<token>`

## 扩展指南

### 新增一个标准流程智能体（analyze → generate → confirm）

1. **后端**：复制 `plugins/job_ai.py`，改 Blueprint 名称和路由
2. **前端**：复制 `plugins/job_ai.html`，改 API 路径
3. **DSL**：复制 `dsl/workflow.yml`，改变量名和 Prompt
4. **入口**：在 `frontend/index.html` 添加卡片
5. **注册**：在 `backend/app.py` 导入并注册 Blueprint

### 新增一个完全独立的智能体（如聊天对话）

1. **后端**：新建 `plugins/chat_bot.py`，自由设计路由
2. **前端**：新建 `plugins/chat_bot.html`，自由设计 UI
3. **DSL**：新建 DSL 文件，自由设计工作流
4. 其他步骤同上

## 常见问题

### Q: 新增智能体需要独立的 Dify 应用吗？

A: **推荐独立**。每个智能体应该有独立的 API Key 和工作流，方便独立迭代和管理。

### Q: 可以共用同一个 Dify 应用的不同工作流吗？

A: **技术上可以**（通过 stage 分支区分），但不推荐。会导致工作流过于复杂，且无法独立发布。

### Q: 前端可以共用一个页面吗？

A: **不推荐**。虽然都是表单，但字段不同、交互不同，独立页面更灵活。

### Q: 认证中间件会影响开发调试吗？

A: **不会**。白名单中已包含 `/health`、`/`、`/index.html` 等路径，开发时不会拦截。

### Q: 如何测试新的插件？

A: 
1. 本地启动 Flask：`python backend/app.py`
2. 访问 `http://localhost:5000/xxx_ai`
3. 直接调用 API：`curl -X POST http://localhost:5000/api/xxx_ai/analyze ...`

## 版本历史

- **v1.0**：单体架构，单一岗位 AI 功能
- **v2.0**：插件化架构，支持多智能体共用基础服务
