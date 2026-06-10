# Dify + 前后端项目开发参考手册

## 1. 项目范式

本模板采用 **"Dify 智能体工作流 + Flask 代理后端 + 零依赖前端"** 的三层架构：

- **Dify**：负责 AI 逻辑编排（多阶段工作流、LLM 调用、文件提取、JSON 校验）
- **Flask**：负责 API 代理、文件上传中转、数据清洗、安全隔离
- **前端**：纯 HTML/CSS/JS，通过 FormData 与后端交互

## 2. Dify 工作流设计规范

### 2.1 多阶段分支模式

当一个业务流程需要用户多次确认时，使用 **单入口 + if-else 多分支** 模式：

```yaml
# start_node 变量定义
variables:
  - variable: stage        # 分支控制器：analyze / generate / confirm
    type: text-input
    required: true
  - variable: job_name     # 业务字段
    type: text-input
  - variable: file         # 文件字段（类型必须是 file，不是 text-input）
    type: file
    required: false
```

```yaml
# if-else 节点
expression: "{{#start_node.stage#}}"
cases:
  - case_id: analyze
    logical_operator: and
    conditions:
      - comparison_operator: equals
        value: analyze
        varType: string
        variable_selector: [start_node, stage]
  - case_id: generate
    ...
  - case_id: confirm
    ...
```

**设计要点**：
- `stage` 是唯一分支控制器，前端/后端通过传入不同的 `stage` 值触发不同分支
- 每个分支的终点使用不同的 output key（`analyze_result` / `generate_result` / `confirm_result`），后端通过 key 区分

### 2.2 文件处理规范

**文件上传链路**：

```
用户上传文件
    │
    ├──→ 前端 FormData.append('file', file)
    │
    ├──→ 后端 /api/analyze
    │        ├──→ POST /v1/files/upload（multipart）→ upload_file_id
    │        └──→ POST /v1/workflows/run
    │                 inputs:
    │                   file:
    │                     transfer_method: local_file
    │                     upload_file_id: <id>
    │                     type: document
    │
    └──→ Dify start_node.file 变量
             │
             └──→ document-extractor
                      variable_selector: [start_node, file]
                      is_array_file: false    # 单个文件必须 false
```

**关键规则**：

| 场景 | `is_array_file` | `variable_selector` | 说明 |
|------|----------------|---------------------|------|
| 从 `sys.files` 读取 | `true` | `[sys, files]` | Web UI 拖拽上传时使用 |
| 从 `start_node.file` 读取 | `false` | `[start_node, file]` | API 调用时使用 |

**常见错误**：
- `(type 'text-input') file in input form must be a string` → start_node 的 `file` 变量类型必须是 `file`，不是 `text-input`
- `Output file_text is missing` → document-extractor 无法提取内容，检查 `is_array_file` 是否与文件数量匹配

### 2.3 LLM Prompt 设计规范

**JSON 输出强制格式**：

```
你必须严格按以下 JSON 格式输出，不要包含 markdown 代码块，不要包含其他说明文字：

{"suggested_count":5,"reasoning":"分析理由...","suggested_jobs":[
  {"name":"岗位名称","reason":"推荐理由"}
]}
```

**字段默认值兜底**：在 LLM 节点后的 Code 节点中，为可能缺失的字段设置默认值：

```python
for job in jobs:
    job.setdefault("shortName", "")
    job.setdefault("coverImage", "")
    job.setdefault("careerPath", {"horizontal":[],"vertical":[]})
    job.setdefault("abilityBindings", [])
    job.setdefault("abilityDomains", [])
    job.setdefault("competencyConfig", [])
```

**`<think>` 标签过滤**：DeepSeek 等模型会在推理时输出 `<think>...</think>`，后端必须在返回前用正则清洗：

```python
import re
result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
```

### 2.4 Code 执行节点规范

**参数名必须完全匹配输入变量名**：

```python
# 错误
result = [j for j in jobs]   # jobs 是传入的参数名

# 正确
result = [j for j in jobs]
```

**所有声明的 Output 变量必须在每次 return 中存在**：

```python
# 如果声明了 success (string) 和 jobs (array[object])
return {
    "success": "true",   # 必须是字符串，不能是布尔值
    "jobs": result       # 不能缺失
}
```

**代码必须从第 0 列顶格开始**：Dify 对缩进敏感，不要有多余空格。

## 3. 前后端对接规范

### 3.1 API 设计

| 端点 | 方法 | 内容类型 | 说明 |
|------|------|---------|------|
| `/api/analyze` | POST | `multipart/form-data` | 接收文件 + 表单字段，返回 AI 分析结论 |
| `/api/generate` | POST | `multipart/form-data` | 接收选中的岗位列表，返回完整 JSON |
| `/api/confirm` | POST | `application/json` | 接收最终岗位数据，返回格式化 JSON |

**为什么 analyze/generate 用 multipart？**
- 因为可能包含文件上传，multipart 可以一次性传文件和表单字段
- confirm 阶段无文件，用 JSON 更简洁

### 3.2 前端状态管理

```javascript
let state = {
    job_name: '',
    industry: '',
    description: '',
    responsibilities: '',
    uploadedFile: null,      // File 对象
    suggested_jobs: [],      // analyze 返回
    selected_jobs: [],       // 用户勾选
    jobs: []                 // generate 返回
};
```

**状态流转**：

```
Step 1 (输入) → state.{job_name, industry, description, responsibilities, uploadedFile}
                    ↓
Step 2 (分析) ← /api/analyze → state.suggested_jobs
                    ↓ 用户勾选
Step 3 (生成) ← /api/generate → state.jobs
                    ↓
Step 4 (导出) ← /api/confirm → 最终 JSON
```

### 3.3 文件上传前端实现

**Tab 切换模式**：

```html
<div class="tabs">
    <div class="tab active" onclick="switchTab('manual')">手动编辑</div>
    <div class="tab" onclick="switchTab('upload')">上传文件</div>
</div>

<div id="tab-manual" class="tab-content active">
    <!-- 表单字段 -->
</div>

<div id="tab-upload" class="tab-content">
    <div class="upload-zone" onclick="document.getElementById('file').click()">
        <div class="upload-icon">📁</div>
        <div class="upload-text">点击上传文件</div>
    </div>
    <input type="file" id="file" style="display:none" onchange="onFileSelected(this)">
</div>
```

**关键 JS**：

```javascript
function onFileSelected(input) {
    const file = input.files[0];
    if (file) {
        document.getElementById('upload-zone').classList.add('has-file');
        document.getElementById('upload-text').textContent = '已选择：' + file.name;
        state.uploadedFile = file;
    }
}

function submitAnalyze() {
    const tab = getActiveTab();  // 'manual' 或 'upload'
    const fileInput = document.getElementById('file');
    const file = fileInput.files[0];  // 从 DOM 实时获取

    if (tab === 'manual') {
        // 校验必填字段
    } else {
        if (!file) { alert('请上传文件'); return; }
    }

    const formData = new FormData();
    formData.append('job_name', ...);
    if (file) formData.append('file', file);
    // fetch /api/analyze
}
```

## 4. DSL 更新与发布流程

### 4.1 完整流程

```bash
# 1. 激活环境
source venv/bin/activate

# 2. 登录 Dify Console
dify-workflow remote login \
  --server http://127.0.0.1:8081 \
  --email <admin> \
  --password <pwd> \
  --profile default

# 3. 列出应用获取 app-id
dify-workflow remote list

# 4. 推送更新
dify-workflow remote push \
  --file dsl/workflow.yml \
  --app-id <app-id> \
  --force

# 5. 发布（调用 Console API）
TOKEN=$(cat ~/.dify-workflow/credentials.json | jq -r '.profiles.default.access_token')
CSRF=$(cat ~/.dify-workflow/credentials.json | jq -r '.profiles.default.csrf_token')

curl -X POST "http://127.0.0.1:8081/console/api/apps/<app-id>/workflows/publish" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -b "csrf_token=$CSRF" \
  -d '{"marked_name":"v1.0","marked_comment":"初始版本"}'
```

### 4.2 密码重置（备用）

如果不知道管理员密码，直接重置数据库：

```bash
# 查看管理员邮箱
cd /opt/dify-deploy/docker
docker compose exec -T db_postgres psql -U postgres -d dify -c "SELECT email FROM accounts;"

# Python 生成新 hash
python3 << 'PYEOF'
import hashlib, base64, binascii, os
password = "新密码"
salt_byte = os.urandom(16)
dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_byte, 10000)
password_hashed = binascii.hexlify(dk)
salt = base64.b64encode(salt_byte).decode()
hash_b64 = base64.b64encode(password_hashed).decode()
print(f"UPDATE accounts SET password = '{hash_b64}', password_salt = '{salt}' WHERE email = '管理员邮箱';")
PYEOF

# 执行 SQL
docker compose exec -T db_postgres psql -U postgres -d dify -c "<上面的SQL>"
```

## 5. 常见问题速查

| 现象 | 根因 | 解决 |
|------|------|------|
| `Access token is invalid` | API Key 对应应用被删 | 重建应用并更新后端 key |
| `CSRF token is missing or invalid` | 只传了 header 没传 cookie | curl 加 `-b "csrf_token=$CSRF"` |
| `(type 'text-input') file in input form must be a string` | start_node 的 file 变量类型错误 | 改为 `type: file` |
| `Output file_text is missing` | document-extractor 未提取到内容 | 检查 `is_array_file` 与文件数量是否匹配 |
| `Output success must be a string, got bool instead` | Code 节点返回了布尔值 | 改为字符串 `"true"` / `"false"` |
| `Output jobs is missing` | Code 节点 return 中缺少声明的变量 | 确保所有 output 变量都存在 |
| `Not all output parameters are validated` | Code 节点有语法错误 | 检查缩进和变量名 |
| `Arg user must be provided` | Dify 1.14+ 要求 user 字段 | payload 中加 `"user": "xxx"` |
| `<think>` 标签出现在输出 | DeepSeek 输出思考过程 | 后端正则过滤 |
| 文件上传后第二步内容为空 | doc_extractor 配置错误 | 检查 `variable_selector` 和 `is_array_file` |
| 固定生成 3 个岗位 | LLM prompt 示例固定写了 3 | 示例改为 `suggested_count:N` 并加明确指令 |

## 6. 快速复用指南

### 6.1 新建一个 Dify + 前后端项目

1. **复制本模板**
   ```bash
   cp -r dify-project-template my-new-project
   cd my-new-project
   ```

2. **修改业务字段**
   - `dsl/workflow.yml`：start_node 变量、LLM prompt、分支逻辑
   - `backend/app.py`：表单字段校验、Dify inputs 映射
   - `frontend/index.html`：表单字段、表格展示列

3. **导入 Dify 工作流**
   ```bash
   dify-workflow remote push --file dsl/workflow.yml --force
   ```

4. **创建 API Key 并配置后端**
   ```bash
   # 见 AGENTS.md 第 4.1 节
   ```

5. **启动服务**
   ```bash
   cd backend && gunicorn -w 1 -b 0.0.0.0:5000 app:app
   ```

### 6.2 新增一个工作流分支

1. 在 `start_node` 的 variables 中确保有分支控制器（如 `stage`）
2. 在 if-else 节点中新增 case
3. 绘制新分支的节点链（LLM → Code → end）
4. 在新分支的 end 节点声明新的 output key
5. 后端新增对应 API 端点
6. 前端新增对应步骤
