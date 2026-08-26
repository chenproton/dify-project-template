# 多方法 AI 生成 Dify 工作流 DSL

> 目标：新业务到来时，用 **多种方式同时生成 Dify 工作流 DSL**，逐个测试后由人工决定保留哪个。

## 1. 集成的三种方法

| 方法 | 工具 | 生成方式 | 校验 | 部署 | 特点 |
|------|------|---------|------|------|------|
| **A 确定性 CLI** | [Akabane71/dify-workflow-cli](https://github.com/Akabane71/dify-workflow-cli)（已装入 tools/venv） | 脚本按 spec 程序化拼 DSL | dify-workflow validate --strict（对齐 Dify 前端三层校验 + 环检测） | remote push 直接发布 | 结构可靠、可复现，但 Prompt/Code 需在 spec 中提供 |
| **B AI Skill** | [yzmw123/dify-workflow-dsl-skill](https://github.com/yzmw123/dify-workflow-dsl-skill)（已 vender 到 skills/dify-workflow-dsl-skill/） | AI 读 skill 参考资料直接写 DSL（支持 0.6.0/0.7.0） | validate_dsl.py --strict --target-version 0.6.0 | 无（输出文件） | 最接近"全自动"，业务 Prompt 由 AI 生成，含 10 个业务示例 |
| **C AI Skill + 版本锚定** | [jspi-fu/Aeson-skills dify-workflow](https://github.com/jspi-fu/Aeson-skills/blob/master/Skills/dify-workflow/SKILL.md)（已 vender 到 skills/aeson-dify-workflow/） | AI 读 skill 按固定 ID/布局/校验规则写 DSL | 4 项规则关卡（无脚本） | 配套 dify-deploy skill（Admin API） | 版本锚定（config.yml），节点用 13 位时间戳 ID，产出风格与 A 明显不同，便于对照 |

> 注：原第 3 个候选（LingyiChen-AI/workflow-skill）与 C 同源（同一套节点路由表/模板），故只保留一套。

## 2. 目录结构

```
specs/                            # 业务 spec（一个业务一个 JSON）
├── job_ai.json                   # 岗位 AI 示例（含真实 Prompt/Code）
scripts/
├── generate_dsl_cli.py           # 方法A：确定性生成器
└── battle_dsl.py                 # 编排器：生成A + B/C简报 + 双校验 + COMPARE.md
generated/                        # 生成产物（已 gitignore，不入库）
└── <business>/
    ├── <id>_methodA_cli.dify.yml
    ├── <id>_methodB_skill2.dify.yml
    ├── <id>_methodC_aeson.dify.yml
    ├── methodB_brief.md / methodC_brief.md   # 给 AI 的生成简报
    └── COMPARE.md                           # 校验对比报告
skills/                           # vendored AI skills（入库）
├── dify-workflow-dsl-skill/      # 方法B
└── aeson-dify-workflow/          # 方法C
tools/
├── install.sh                    # 一键安装方法A CLI（bash tools/install.sh）
└── venv/                         # 方法A 运行环境（已 gitignore）
dsl/                              # 正式入库的工作流 DSL（人工选定后放这里）
```

## 3. 新业务全流程

### 第 1 步：写业务 spec

复制 specs/job_ai.json 为 specs/<business>.json，填写：

- app：应用名/图标
- input_fields：用户输入字段（analyze 阶段表单）
- has_file：是否需要文档上传提取
- analyze.system_prompt / generate.system_prompt：业务 Prompt（可留空，用通用模板兜底）
- generate.code / confirm.code：Code 节点 Python（可留空，用通用清洗模板）
- model：模型配置（默认 deepseek-v4-flash）

### 第 2 步：跑编排器生成方法A + B/C 简报

```bash
bash tools/install.sh   # 首次需要，安装方法A CLI
tools/venv/bin/python scripts/battle_dsl.py specs/<business>.json
```

产出：方法A 变体 + 方法B/C 的 AI 生成简报（含业务描述和生成要求）。

### 第 3 步：AI 用 vendored skill 生成方法B/C 变体

让 AI 分别读取简报与对应 skill（skills/dify-workflow-dsl-skill/SKILL.md、skills/aeson-dify-workflow/SKILL.md），
产出 generated/<business>/<id>_methodB_skill2.dify.yml 和 ..._methodC_aeson.dify.yml。

### 第 4 步：再跑一次编排器完成双校验与对比

```bash
tools/venv/bin/python scripts/battle_dsl.py specs/<business>.json --skip-methodA
```

三个变体都会过两个校验器，结果汇总到 generated/<business>/COMPARE.md。

### 第 5 步：人工测试并保留

1. 把三个 YAML 逐个导入 Dify（或 dify-workflow remote push --file <dsl.yml> --app-id <id> --force 发布），跑真实业务验证
2. 选定保留的变体，复制到 dsl/<business>_workflow.yml 正式入库
3. 后端插件（backend/plugins/）的 DIFY_API_KEY / inputs 字段与该工作流对齐

## 4. 两个校验器说明

| 校验器 | 命令 | 严格度 | 备注 |
|--------|------|--------|------|
| dify-workflow CLI | dify-workflow validate --strict <file> | 对齐 Dify 前端三层校验 + 环检测 | 本项目现有两份手工 DSL 均通过 |
| skill2 validate_dsl.py | python skills/dify-workflow-dsl-skill/scripts/validate_dsl.py --strict --target-version 0.6.0 <file> | 额外检查依赖声明、分支连通 | 现有手工 DSL 会有 1 error（dependencies 缺 deepseek 插件声明）+ 1 warning（if-else false 分支未连线），属已知差异 |

> 两个校验器结果不一致是正常的：CLI 对齐 Dify 前端，skill2 更关注 0.7.0 插件体系。
> 若你的 Dify 实例能导出真实 DSL，把其中的 dependencies 段拷进 spec 的 dependencies 字段，方法A 输出即可双通过。

## 5. 常见问题

**Q：方法A 和 B/C 生成的文件能直接用吗？**

A：方法A 结构可靠但 Prompt 是 spec 里的（或通用模板）；B/C 的 Prompt 是 AI 按业务写的。都需要人工测试确认业务正确性。

**Q：为什么要三个方法都生成？**

A：三种方法产出风格不同（固定结构 vs AI 自由设计 vs 时间戳ID+网格布局），业务 Prompt 质量也有差异。多生成几个再测试，避免单一方法的天花板。

**Q：generated/ 为什么不入库？**

A：它们是测试期候选产物。最终选定保留的会复制到 dsl/ 入库，避免仓库被候选文件污染。

**Q：CLI 没装怎么办？**

A：bash tools/install.sh 一条命令完成（下载源码 → venv → pip install -e）。
