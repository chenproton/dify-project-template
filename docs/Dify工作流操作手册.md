# Dify 工作流操作手册（服务器运维版）

> 适用对象：SSH 远程到本服务器的开发/运维人员。
> 目标：学会新建、调整、编辑 Dify 工作流，并部署上线、建知识库、测试接口。
> 本文档汇总了本环境已验证的全部操作（含踩坑记录）。

---

## 0. 速查表（最常用命令）

```bash
# ① 查看 Dify 服务状态
cd /opt/dify-deploy/docker && docker compose ps

# ② 生成工作流（方法A：确定性生成）
cd /root/projects/dify-project-template
tools/venv/bin/python scripts/generate_dsl_cli.py specs/xxx.json -o generated/xxx_methodA.dify.yml

# ③ 校验工作流（双校验器）
tools/venv/bin/dify-workflow validate --strict generated/xxx.dify.yml
tools/venv/bin/python skills/dify-workflow-dsl-skill/scripts/validate_dsl.py --target-version 0.6.0 generated/xxx.dify.yml

# ④ 部署到 Dify（登录→推送→发布）
tools/venv/bin/dify-workflow remote login --server http://127.0.0.1:8081 --email <邮箱> --password <密码>
tools/venv/bin/dify-workflow remote push -f generated/xxx.dify.yml --force

# ⑤ 测试接口
curl -X POST http://127.0.0.1:8081/v1/workflows/run \
  -H 'Authorization: Bearer <API_KEY>' -H 'Content-Type: application/json' \
  -d '{"inputs":{...},"response_mode":"blocking","user":"u_001"}'
```

---

## 1. 环境地图

| 组件 | 位置 | 说明 |
|------|------|------|
| Dify 部署目录 | `/opt/dify-deploy` | Dify 1.17.0 源码 + docker compose |
| Compose 文件 | `/opt/dify-deploy/docker/docker-compose.yaml` | 服务编排（.env 同目录） |
| Dify 入口 | `http://127.0.0.1:8081` | nginx 暴露，Web UI + API 都在此 |
| 数据卷 | `/opt/dify-deploy/docker/volumes` | 数据库/存储持久化（勿删） |
| 数据库 | docker-db_postgres-1 容器 | 库：dify（主库）、dify_plugin（插件库） |
| 备份目录 | `/opt/dify-deploy/backup` | 数据库 dump / 旧配置备份 |
| 工作流工具链 | `/root/projects/dify-project-template` | 多方法生成器 + vendored skills + DSL |
| 工具 venv | `tools/venv` | dify-workflow CLI 运行环境（bash tools/install.sh 可重建） |
| 正式 DSL | `dsl/` | 已入库的工作流 DSL（含 dsl/fuxing/ 复星差旅三件套） |
| mock 数据 | `/opt/dify-deploy/mock_data` | 复星差旅政策 mock 文档等 |

**关键端口**：8081（Dify nginx）、5001（api 内部）、8084（zhiyu-nginx）、8012（kkfileview 已停）、58627/4096（kimi/opencode 已停）。

---

## 2. Dify 服务管理

```bash
cd /opt/dify-deploy/docker

docker compose ps            # 查看所有服务状态
docker compose up -d         # 启动/更新（修改 compose 后执行）
docker compose down          # 停止全部（⚠️ 会保留数据卷）
docker compose restart <svc> # 重启单个服务（如 api）
docker compose logs -f api   # 跟踪日志
docker compose logs --since 10m plugin_daemon | grep -i error

# 健康检查
curl -s http://127.0.0.1:8081/console/api/setup   # 返回 step=finished 即正常
```

**服务清单**：api（核心）、worker（异步任务）、worker_beat（定时）、web（前端）、nginx（网关）、db_postgres、redis、sandbox（代码沙箱）、plugin_daemon（插件）、weaviate（向量库）、ssrf_proxy（外联代理）、agent_backend/local_sandbox/agent_ssrf_proxy（Agent 平台，不用可关）。

> ⚠️ api_websocket（协作 websocket）已按需求停用：.env 的 COMPOSE_PROFILES 已移除 collaboration。如需恢复，加回并 docker compose up -d。

---

## 3. 新建 Dify 工作流（三种方法）

本环境集成了三种工作流生成方式，可并行产出多个变体后人工测试选定：

| 方法 | 工具 | 特点 |
|------|------|------|
| A 确定性 CLI | tools/venv 的 dify-workflow-cli | 脚本按 spec 程序化拼 DSL，结构可靠可复现 |
| B AI Skill | skills/dify-workflow-dsl-skill/ | AI 按参考资料直接写 DSL（0.6/0.7 双版本） |
| C AI Skill+版本锚定 | skills/aeson-dify-workflow/ | AI 按固定 ID/布局规则写（chatflow 骨架） |

### 3.1 方法A：spec + CLI 确定性生成（推荐起步）

**Step 1 写业务 spec**（复制 specs/job_ai.json 为模板）：

```json
{
  "id": "my_biz",
  "app": {"name": "业务名", "icon": "🤖", "icon_background": "#FFEAD5"},
  "model": {"provider": "langgenius/deepseek/deepseek", "name": "deepseek-v4-flash", "temperature": 0.7},
  "entity_label": "条目",
  "input_fields": [{"variable": "name", "label": "名称", "type": "text-input"}],
  "has_file": true,
  "analyze": {"system_prompt": ["分析提示词..."], "outputs": []},
  "generate": {"system_prompt": ["生成提示词..."], "code": "", "json_key": "items"},
  "confirm": {"code": "", "json_key": "items"}
}
```

**Step 2 生成**：

```bash
cd /root/projects/dify-project-template
tools/venv/bin/python scripts/generate_dsl_cli.py specs/my_biz.json -o generated/my_biz_methodA.dify.yml
```

该方法生成标准三段式工作流：start → if-else(stage) → analyze/generate/confirm 三分支（文档提取→LLM→Code 校验→end）。

### 3.2 方法B：AI Skill 生成（业务 Prompt 由 AI 编写）

```bash
# 1. 生成 AI 简报（含业务描述和生成要求）
tools/venv/bin/python scripts/battle_dsl.py specs/my_biz.json
#    → 产出 generated/my_biz/methodB_brief.md

# 2. 让 AI 读取 skills/dify-workflow-dsl-skill/SKILL.md + 简报，产出变体
#    输出文件: generated/my_biz/my_biz_methodB_skill2.dify.yml
```

### 3.3 方法C：chatflow / 对话流生成

多轮对话场景用 advanced-chat 形态（start→LLM→code→answer），参考 dsl/fuxing/d3_chat_methodC.dify.yml 结构，注意：
- LLM 节点引用 {{#sys.query#}}（系统变量，勿引用不存在的 sys.conversation.conversation_id）
- 多轮记忆靠 LLM 节点的 memory: {enabled: true, window: {enabled: true, size: 12}}
- 对话输出用 answer 节点（answer: "{{#code_parse.reply#}}"）

### 3.4 一键编排 + 双校验（battle）

```bash
tools/venv/bin/python scripts/battle_dsl.py specs/my_biz.json            # 生成A + B/C简报 + 校验
tools/venv/bin/python scripts/battle_dsl.py specs/my_biz.json --skip-methodA  # 只校验已有变体
# 结果汇总: generated/my_biz/COMPARE.md（节点数/校验结果对比表）
```

**双校验器**：
- dify-workflow validate --strict：对齐 Dify 前端三层校验（节点/变量/连通性）+ 环检测
- validate_dsl.py --strict --target-version 0.6.0：更严格（依赖声明、分支连通）

---

## 4. 编辑/调整已有工作流

### 4.1 修改后重新推送（最常用）

```bash
cd /root/projects/dify-project-template
# 1. 修改 DSL YAML（改 Prompt/节点/连线）
# 2. 校验
tools/venv/bin/dify-workflow validate --strict dsl/fuxing/d1_intent_methodA.dify.yml
# 3. 推送更新（--app-id 填线上 App ID）
tools/venv/bin/dify-workflow remote push -f dsl/fuxing/d1_intent_methodA.dify.yml --app-id <线上AppID> --force
# 4. 发布（见 §5.3）
```

### 4.2 从线上导出当前版本（remote pull）

```bash
tools/venv/bin/dify-workflow remote pull --app-id <AppID> -o generated/current.dify.yml
```

### 4.3 用 CLI 编辑节点

```bash
# 添加/删除/更新节点、连线（示例）
tools/venv/bin/dify-workflow edit add-node -f generated/x.dify.yml --type llm --title "新节点"
tools/venv/bin/dify-workflow edit update-node -f generated/x.dify.yml --id llm_node -d '{"model":{"name":"deepseek-v4-flash"}}'
tools/venv/bin/dify-workflow layout -f generated/x.dify.yml -o generated/x_layered.yml   # 自动布局
```

---

## 5. 部署到 Dify

### 5.1 登录（一次即可，session 保存）

```bash
tools/venv/bin/dify-workflow remote login --server http://127.0.0.1:8081 --email <管理员邮箱> --password <密码>
```

> 密码即 Dify 控制台登录密码（管理员：chenproton@gmail.com）。

### 5.2 推送（新建或更新）

```bash
# 新建应用（不传 --app-id）
tools/venv/bin/dify-workflow remote push -f generated/xxx.dify.yml --force

# 更新已有应用（传线上 App ID）
tools/venv/bin/dify-workflow remote push -f generated/xxx.dify.yml --app-id <AppID> --force
```

### 5.3 发布 + 创建 API Key（console API）

```bash
# ① 登录拿 cookie + CSRF（密码需 base64 编码）
B64=$(echo -n '<密码>' | base64)
curl -s -c /tmp/dc.txt -X POST http://127.0.0.1:8081/console/api/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"chenproton@gmail.com\",\"password\":\"$B64\",\"language\":\"zh-Hans\"}"
CSRF=$(grep -i csrf /tmp/dc.txt | awk '{print $7}')

# ② 发布工作流（带 CSRF header + marked_name）
curl -s -b /tmp/dc.txt -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://127.0.0.1:8081/console/api/apps/<AppID>/workflows/publish \
  -d '{"marked_name":"v1","marked_comment":"desc"}'

# ③ 创建 API Key
curl -s -b /tmp/dc.txt -H "X-CSRF-Token: $CSRF" \
  -X POST http://127.0.0.1:8081/console/api/apps/<AppID>/api-keys
```

### 5.4 应用信息查询

```bash
tools/venv/bin/dify-workflow remote list                      # 工作区所有应用 + App ID
curl -s -b /tmp/dc.txt -H "X-CSRF-Token: $CSRF" http://127.0.0.1:8081/console/api/apps/<AppID>
```

---

## 6. 知识库管理（D2 政策 RAG 用）

### 6.1 建知识库

```bash
# 注意 1.17 索引枚举是 economy（不是 economical）
curl -s -b /tmp/dc.txt -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://127.0.0.1:8081/console/api/datasets \
  -d '{"name":"库名","description":"desc","indexing_technique":"economy","permission":"only_me","provider":"vendor"}'
```

> economy = 关键词索引（无需 embedding 模型）；high_quality = 向量检索（需 embedding 模型，当前未配置，勿用）。

### 6.2 上传文档（两步：传文件 → 建文档）

```bash
# ① 上传文件拿 file_id
curl -s -b /tmp/dc.txt -H "X-CSRF-Token: $CSRF" -X POST http://127.0.0.1:8081/console/api/files/upload \
  -F 'file=@/opt/dify-deploy/mock_data/复星差旅政策2026.md' -F 'type=document' \
  > /tmp/upload_resp.json
FILE_ID=$(python3 -c "import json;print(json.load(open('/tmp/upload_resp.json'))['id'])")

# ② 建文档（data_source 结构是 1.17 关键）
cat > /tmp/doc.json <<EOF
{
  "name": "文档名",
  "indexing_technique": "economy",
  "data_source": {"info_list": {"data_source_type": "upload_file", "file_info_list": {"file_ids": ["$FILE_ID"]}}},
  "process_rule": {"mode": "automatic"},
  "doc_form": "text_model",
  "doc_language": "Chinese"
}
EOF
curl -s -b /tmp/dc.txt -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://127.0.0.1:8081/console/api/datasets/<DATASET_ID>/documents --data @/tmp/doc.json
```

### 6.3 更新文档（替换内容，原 document_id 不变）

```bash
# 重复 6.2① 上传新文件，然后在 doc.json 里加一行：
#   "original_document_id": "<旧document_id>",
# 再执行 6.2② 的建文档请求
```

### 6.4 工作流接入知识库

knowledge-retrieval 节点（1.17 格式）：

```yaml
type: knowledge-retrieval
dataset_ids: ["<DATASET_ID>"],
query_variable_selector: ["start_node", "query"],
retrieval_mode: "multiple",
multiple_retrieval_config: {top_k: 4, score_threshold: null, reranking_mode: "reranking_model", reranking_enable: false, reranking_model: null, weights: null},
metadata_filtering_mode: "disabled"
```

> ⚠️ retrieval_mode 是必填字段（缺失会导入失败）；无 rerank 模型时 reranking_enable: false。

---

## 7. 接口测试

### 7.1 workflow 接口（D1/D2）

```bash
curl -X POST http://127.0.0.1:8081/v1/workflows/run \
  -H 'Authorization: Bearer <API_KEY>' -H 'Content-Type: application/json' \
  -d '{"inputs":{"query":"测试内容"},"response_mode":"blocking","user":"u_001"}'
```

### 7.2 chat 接口（D3 多轮）

```bash
# 第一轮
curl -X POST http://127.0.0.1:8081/v1/chat-messages \
  -H 'Authorization: Bearer <API_KEY>' -H 'Content-Type: application/json' \
  -d '{"inputs":{},"query":"帮我订机票","response_mode":"blocking","user":"u_001","conversation_id":""}'
# 第二轮：带上轮返回的 conversation_id 保持上下文
```

### 7.3 现有测试样本

见 docs/fuxing-dify-接口测试.md：D1 意图/槽位 20+ 用例、D2 政策问答、D3 多轮对话的完整 curl 命令与预期输出。

---

## 8. 控制台 API 速查（带 CSRF）

```bash
# 通用请求格式：cookie + X-CSRF-Token header
# CSRF token 从登录后的 cookie 文件里取（名为 csrf_token 的那行第7列）

GET    /console/api/setup                              # 初始化状态
POST   /console/api/login                              # 登录（密码需 base64）
GET    /console/api/apps?page=1&limit=30               # 应用列表
GET    /console/api/apps/<id>                          # 应用详情
POST   /console/api/apps/<id>/workflows/publish        # 发布工作流
POST   /console/api/apps/<id>/api-keys                 # 创建 API Key
POST   /console/api/datasets                           # 建知识库
POST   /console/api/datasets/<id>/documents            # 建文档（data_source 格式见 §6.2）
POST   /console/api/files/upload                       # 上传文件
```

---

## 9. 常见问题与排障（踩坑记录）

### 9.1 DeepSeek 模型 Key 更换

- 登录 http://127.0.0.1:8081 → 设置 → 模型供应商 → DeepSeek → 更新 API Key
- 验证：跑一个真实工作流调用，不再报 401 Authentication Fails 即成功

### 9.2 管理员密码格式（重要！）

- Dify 1.17 密码 = base64(PBKDF2-SHA256(password, salt, 10000))，存 accounts.password + accounts.password_salt 两列
- 禁止直接 UPDATE 为 bcrypt 哈希（会破坏格式，登录报 base64 错误）
- 临时改密码的正确方法：

```bash
docker exec docker-api-1 python3 -c "import secrets,base64; from libs.password import hash_password; s=secrets.token_bytes(16); print(base64.b64encode(hash_password('新密码',s)).decode()); print(base64.b64encode(s).decode())" > /tmp/cred.txt
PWH=$(sed -n '1p' /tmp/cred.txt); PWS=$(sed -n '2p' /tmp/cred.txt)
docker exec docker-db_postgres-1 psql -U postgres -d dify -c "update accounts set password='$PWH', password_salt='$PWS' where email='chenproton@gmail.com';"
# 操作完成后务必恢复原值（先备份 password 和 password_salt 两列）
```

### 9.3 SSRF proxy（外联代理）故障

- 症状：插件市场下载报 Reached maximum retries / DNS 解析失败
- 原因：/opt/dify-deploy/docker/ssrf_proxy/ 下模板文件与 Dify 版本不匹配（squid.conf 渲染出 http_port accel 缺端口）
- 修复：按版本从官方仓库同步 docker/ssrf_proxy/ 全部文件后重建容器

```bash
cd /opt/dify-deploy/docker
docker compose rm -sf ssrf_proxy && docker compose up -d ssrf_proxy
docker exec docker-api-1 python3 -c "import requests; print(requests.get('https://marketplace.dify.ai/', timeout=10, proxies={'https':'http://ssrf_proxy:3128'}).status_code)"
```

### 9.4 插件任务卡死（install_tasks 暴涨）

- 症状：UI 插件操作一直转圈、系统负载高、plugin_daemon 日志刷 task timed out
- 处理：清空任务表 + 重启 daemon

```bash
docker exec docker-db_postgres-1 psql -U postgres -d dify_plugin -c "DELETE FROM install_tasks;"
docker exec docker-db_postgres-1 psql -U postgres -d dify_plugin -c "VACUUM FULL install_tasks;"
cd /opt/dify-deploy/docker && docker compose restart plugin_daemon
```

### 9.5 磁盘/内存管理

```bash
docker system df                                  # Docker 空间占用
docker builder prune -af                          # 清构建缓存（可释放 10G+）
journalctl --vacuum-size=50M                      # 压缩系统日志
docker stats --no-stream | sort -k4 -rn           # 容器内存排序
# 已停用服务：kimi-code / opencode（systemd disable）、kkfileview、api_websocket
# 如需再省内存：关 agent_backend/local_sandbox/agent_ssrf_proxy（Agent 平台）
```

### 9.6 版本升级注意事项

- 升级前：备份数据库（docker exec docker-db_postgres-1 pg_dump -U postgres -d dify -F c -f /tmp/x.dump）
- 升级时：整个 docker/ 目录（compose + ssrf_proxy + nginx 配置）按新版本 tag 全量同步，避免新旧文件混用
- .env 的 SECRET_KEY 保持不变（加密了租户密钥，改了凭证无法解密）
- 升级后：docker compose up -d → 等 api 健康 → 验证 8081

### 9.7 API 返回 400 "Workflow not published"

- 推送 DSL 后必须发布：§5.3 步骤②

### 9.8 知识库相关报错

- Invalid indexing technique：枚举是 economy（不是 economical）
- Invalid provider: langgenius/tongyi/tongyi：embedding 模型未配置，用 economy 索引
- retrieval_mode Field required：知识检索节点缺 retrieval_mode 字段（见 §6.4）

---

## 10. 备份与恢复

```bash
# 数据库备份
docker exec docker-db_postgres-1 pg_dump -U postgres -d dify -F c -f /tmp/dify.dump
docker exec docker-db_postgres-1 pg_dump -U postgres -d dify_plugin -F c -f /tmp/dify_plugin.dump
docker cp docker-db_postgres-1:/tmp/dify.dump /opt/dify-deploy/backup/dify_$(date +%Y%m%d).dump

# 恢复（示例）
docker cp /opt/dify-deploy/backup/dify_xxx.dump docker-db_postgres-1:/tmp/
docker exec docker-db_postgres-1 pg_restore -U postgres -d dify --clean /tmp/dify_xxx.dump
```

---

## 附录 A：复星差旅三件套部署信息

| 接口 | App ID | API Key | 说明 |
|------|--------|--------|------|
| D1 意图识别 | 7afbf241-a119-421f-913a-b91c021cecdc | app-5YF52YTUJlQ7ei1jwmbTD3gl | workflow，query→LLM→code→end |
| D2 政策问答 | 542a5f0a-13b0-433a-b192-c66221fe73bb | app-z86wgFoS9sUw643xXouNOflo | workflow+知识库(economy) |
| D3 对话管家 | 21ef0a49-03b7-4512-96ab-391398c7c364 | app-DCXLiTZYEgbfUtzTfIPjwkrT | advanced-chat+memory+mock |

知识库：复星差旅政策2026（2550b827-c7a8-47c3-9a73-5ca755925a59，economy 索引，文档 fba89b35）

## 附录 B：有用脚本/文件索引

| 文件 | 用途 |
|------|------|
| scripts/generate_dsl_cli.py | 方法A 生成器（三段式工作流） |
| scripts/battle_dsl.py | 多方法编排 + 双校验 + COMPARE 报告 |
| tools/install.sh | 重建 dify-workflow CLI 工具链 |
| docs/dsl-generation.md | 多方法生成体系设计文档 |
| docs/fuxing-dify-接口测试.md | 复星差旅接口测试命令 |
| dsl/fuxing/*.dify.yml | 已部署的三个工作流 DSL |

