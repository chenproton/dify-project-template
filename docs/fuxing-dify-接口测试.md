# 复星差旅 AI 管家 — Dify 接口测试文档

> 三个工作流已部署到 Dify（127.0.0.1:8081），以下为接口测试信息。
> 生成方式：D1=方法A（CLI 确定性）、D2=方法B（skill2 AI + 知识库）、D3=方法C（chatflow 骨架）

## 1. D1 意图识别 + 槽位抽取（workflow）

| 项 | 值 |
|----|----|
| App ID | `7afbf241-a119-421f-913a-b91c021cecdc` |
| API Key | `app-5YF52YTUJlQ7ei1jwmbTD3gl` |
| 接口 | `POST /v1/workflows/run`（blocking） |
| 输入 | query(必填)、role、level |
| 输出 | intent、priority、slots(date/origin/destination/city/queryTarget) |

测试命令：

```bash
curl -X POST http://127.0.0.1:8081/v1/workflows/run \
  -H 'Authorization: Bearer app-5YF52YTUJlQ7ei1jwmbTD3gl' \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{"query":"帮我订8月20号上海飞北京的机票","role":"leader","level":"M3/P9"},"response_mode":"blocking","user":"u_001"}'
```

已验证用例：
- `帮我订8月20号上海飞北京的机票` → flight_book(3)，date=2026-08-20，origin=上海，destination=北京
- `不用出差单，帮我订个酒店` → personal_booking(1)（优先级冲突正确）
- `查一下领导的行程` → trip_query(4)，queryTarget=leader
- `帮我订8.15到深圳的机票` → flight_book(3)，date=2026-08-15，destination=深圳（中文日期解析）
- `报销期限是多久` → policy_query(5)；`今天天气怎么样` → chitchat(6)

## 2. D2 政策 RAG 问答（workflow + 知识库）

| 项 | 值 |
|----|----|
| App ID | `542a5f0a-13b0-433a-b192-c66221fe73bb` |
| API Key | `app-z86wgFoS9sUw643xXouNOflo` |
| 接口 | `POST /v1/workflows/run`（blocking） |
| 知识库 | 复星差旅政策2026（ID `2550b827-c7a8-47c3-9a73-5ca755925a59`，economy 索引） |
| 输出 | answer、citations(document/page) |

```bash
curl -X POST http://127.0.0.1:8081/v1/workflows/run \
  -H 'Authorization: Bearer app-z86wgFoS9sUw643xXouNOflo' \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{"query":"报销期限是多久"},"response_mode":"blocking","user":"u_003"}'
```

已验证用例：报销期限(30天/60天延期)、一线城市住宿(800元)、机票舱位(经济舱/1500元审批)、超标审批(20%/50%/CFO)、出差津贴(100/200元)；无命中走兜底话术；住宿回答按金额表述、不含星级（FR-POL-001）

## 3. D3 多轮对话编排（advanced-chat）

| 项 | 值 |
|----|----|
| App ID | `21ef0a49-03b7-4512-96ab-391398c7c364` |
| API Key | `app-DCXLiTZYEgbfUtzTfIPjwkrT` |
| 接口 | `POST /v1/chat-messages`（blocking） |
| 输入 | query、conversation_id(第二轮起传) |
| 输出 | answer（含 mock 航班/酒店列表）、conversation_id |

```bash
# 第一轮
curl -X POST http://127.0.0.1:8081/v1/chat-messages \
  -H 'Authorization: Bearer app-DCXLiTZYEgbfUtzTfIPjwkrT' \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{},"query":"帮我订8月20号上海飞北京的机票","response_mode":"blocking","user":"u_008","conversation_id":""}'

# 第二轮（携带第一轮返回的 conversation_id）
curl -X POST http://127.0.0.1:8081/v1/chat-messages \
  -H 'Authorization: Bearer app-DCXLiTZYEgbfUtzTfIPjwkrT' \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{},"query":"选第二个航班，帮我确认","response_mode":"blocking","user":"u_008","conversation_id":"<上轮conversation_id>"}'
```

已验证：第一轮返回 mock 航班列表（航班号/时间/价格，均在差标内）+ 询问选择；第二轮带 conversation_id 记住上下文继续确认预订。

## 4. 后端接入配置（.env）

```
DIFY_BASE_URL=http://127.0.0.1:8081/v1
DIFY_INTENT_API_KEY=app-5YF52YTUJlQ7ei1jwmbTD3gl   # D1
DIFY_POLICY_API_KEY=app-z86wgFoS9sUw643xXouNOflo   # D2
DIFY_CHAT_API_KEY=app-DCXLiTZYEgbfUtzTfIPjwkrT     # D3
DIFY_INTENT_APP_ID=7afbf241-a119-421f-913a-b91c021cecdc
DIFY_POLICY_APP_ID=542a5f0a-13b0-433a-b192-c66221fe73bb
DIFY_CHAT_APP_ID=21ef0a49-03b7-4512-96ab-391398c7c364
```

## 5. 说明

- D2 知识库使用 mock 政策文档（`/opt/dify-deploy/mock_data/复星差旅政策2026.md`），正式《复星集团全球差旅费报销管理规定(2026)》文档到位后可替换（更新同一 document）
- D3 航班/酒店为模拟数据，后端 /travel 接口就绪后可将 LLM 输出替换为 HTTP 节点拉取真实数据
- Dify 未配置/调用失败时，后端应回退现有正则引擎/内置知识库（降级策略 DD-4）
