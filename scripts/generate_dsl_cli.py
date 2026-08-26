#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方法 A：dify-workflow CLI 确定性生成器
=========================================
根据业务 spec JSON，用 dify_workflow 库（tools/venv 中的 dify-workflow-cli）
生成"标准三段式"（analyze → generate → confirm）Dify 工作流 DSL。

用法:
    tools/venv/bin/python scripts/generate_dsl_cli.py specs/job_ai.json \
        -o generated/job_ai/job_ai_methodA_cli.dify.yml

说明:
    - 工作流结构固定为: start_node → if-else(stage) → 三个分支
    - analyze  分支: document-extractor → LLM 分析 → end
    - generate 分支: document-extractor → LLM 生成 → Code 校验 → end
    - confirm  分支: Code 格式化 → end
    - 节点 ID、连线、布局与 dsl/ 下人工维护的 DSL 风格一致
    - spec 未提供 Prompt / Code 时，使用内置通用模板兜底
"""
import argparse
import json
import pathlib
import sys

FENCE = chr(96) * 3  # markdown code fence


def default_analyze_prompt(spec):
    """未提供 analyze prompt 时的通用兜底模板"""
    entity = spec.get("entity_label", "条目")
    fields = "\n".join(
        "{}：{{{{#start_node.{}#}}}}".format(f["label"], f["variable"])
        for f in spec.get("input_fields", [])
    )
    return (
        "你是一位资深的业务分析专家。根据以下信息，建议应该拆分为多少个细分" + entity + "。\n\n"
        + fields + "\n"
        + "文件内容：{{#doc_extractor.text#}}\n\n"
        + "要求：\n"
        + "1. 分析输入内容的广度和深度，建议合理的细分" + entity + "数量\n"
        + "2. 每个建议" + entity + "给出简短命名和理由\n"
        + "3. 必须按以下 JSON 格式输出，不要包含 markdown 代码块，不要包含其他说明文字：\n\n"
        + '{"suggested_count":N,"reasoning":"分析理由...","suggested_items":[{"name":"名称","reason":"理由..."}]}'
    )


def default_generate_prompt(spec):
    """未提供 generate prompt 时的通用兜底模板"""
    entity = spec.get("entity_label", "条目")
    return (
        "你是一位专业的业务建模专家。请根据以下需求，生成 {{#start_node.count#}} 个" + entity + "的 JSON 数据。\n\n"
        "输入信息：\n"
        "- 文件内容（缓存）：{{#start_node.file_text#}}\n"
        "- 新上传文件内容：{{#doc_extractor_generate.text#}}\n"
        "- 用户选中的" + entity + "：{{#start_node.suggest#}}\n\n"
        "输出要求：\n"
        "1. 只输出纯 JSON 数组，不要任何 markdown 代码块，不要任何解释文字\n"
        "2. 每个" + entity + "对象包含有意义的完整字段（name/description 等）\n"
        "3. 必须生成恰好 {{#start_node.count#}} 个" + entity + "\n"
        "4. 输出必须是可以直接解析的 JSON 数组，前后不要加任何文字\n\n"
        '注意：请严格按照用户选中的' + entity + '名称和方向来生成，不要偏离用户的选择。'
    )


def default_generate_code(json_key="items"):
    """未提供 generate code 时的通用 JSON 清洗/校验代码"""
    return """import json
import re

def main(raw_json: str) -> dict:
    text = raw_json.strip()
    # 1. 去掉 <think>...</think> 思考过程
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # 2. 清理 markdown 代码块标记
    text = re.sub(r"^" + FENCE + r"json\\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^" + FENCE + r"\\s*", "", text)
    text = re.sub(r"\\s*" + FENCE + r"$", "", text)
    text = text.strip()

    data = None
    # 3. 尝试直接解析
    try:
        data = json.loads(text)
    except Exception:
        pass
    # 4. 尝试提取 JSON 数组 / 对象
    if data is None:
        for pat in (r"\\[.*\\]", r"\\{.*\\}"):
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(0))
                    break
                except Exception:
                    pass

    if data is None:
        return {
            "success": False,
            """ + json_key + """: "[]",
            "preview": json.dumps([{"_error": True, "_message": "LLM输出无法解析为JSON", "_raw_preview": raw_json[:500]}], ensure_ascii=False)
        }

    if not isinstance(data, list):
        data = [data]

    return {
        "success": True,
        """ + json_key + """: json.dumps(data, ensure_ascii=False),
        "preview": json.dumps(data, ensure_ascii=False, indent=2)
    }
"""


def default_confirm_code():
    """未提供 confirm code 时的通用格式化代码"""
    return """import json

def main(arg1: str) -> dict:
    input_json = arg1.strip()
    try:
        data = json.loads(input_json)
    except Exception as e1:
        cleaned = input_json
        if cleaned.startswith(FENCE):
            lines = cleaned.split("\\n")
            cleaned = "\\n".join(lines[1:-1] if lines[-1].strip() == FENCE else lines[1:])
        try:
            data = json.loads(cleaned.strip())
        except Exception as e2:
            return {
                "status": "error",
                "data": "JSON解析失败: " + str(e2) + " | 原始输入前200字: " + input_json[:200]
            }

    if not isinstance(data, list):
        data = [data]

    cleaned = []
    for item in data:
        if isinstance(item, dict):
            cleaned.append({k: v for k, v in item.items()})
        else:
            cleaned.append(item)

    return {
        "status": "confirmed",
        "data": json.dumps(cleaned, ensure_ascii=False)
    }
"""


def build(spec):
    from dify_workflow.models import DifyDSL, AppMode, NodeType
    from dify_workflow.editor import (
        add_node, add_edge, add_start_variable, add_end_output,
    )

    dsl = DifyDSL()
    dsl.app.name = spec["app"].get("name", spec.get("id", "workflow"))
    dsl.app.mode = AppMode.WORKFLOW
    dsl.app.description = spec["app"].get("description", "")
    dsl.app.icon = spec["app"].get("icon", "🤖")
    dsl.app.icon_background = spec["app"].get("icon_background", "#FFEAD5")
    if spec.get("dependencies"):
        dsl.dependencies = spec["dependencies"]

    has_file = spec.get("has_file", True)
    model = spec.get("model", {
        "provider": "langgenius/deepseek/deepseek",
        "name": "deepseek-v4-flash",
        "mode": "chat",
        "temperature": 0.7,
    })
    model_config = {
        "provider": model["provider"],
        "name": model["name"],
        "mode": model.get("mode", "chat"),
        "completion_params": {"temperature": model.get("temperature", 0.7)},
    }
    llm_common = {
        "model": model_config,
        "vision": {"enabled": False},
        "memory": None,
        "context": {"enabled": False, "variable_selector": []},
    }

    # ---- start 节点 ----
    add_node(dsl, NodeType.START, title="用户输入", node_id="start_node",
             position=(79, 282))
    add_start_variable(dsl, "start_node", "stage", label="阶段",
                       var_type="text-input", required=True)
    for f in spec.get("input_fields", []):
        add_start_variable(dsl, "start_node", f["variable"],
                           label=f.get("label", f["variable"]),
                           var_type=f.get("type", "text-input"),
                           required=f.get("required", False))
    if has_file:
        add_start_variable(dsl, "start_node", "file", label="上传文件",
                           var_type="file", required=False)
    state = spec.get("state_fields", {})
    add_start_variable(dsl, "start_node", "file_text",
                       label=state.get("file_text", {}).get("label", "文件提取文本"),
                       var_type=state.get("file_text", {}).get("type", "paragraph"),
                       required=False)
    add_start_variable(dsl, "start_node", "count",
                       label=state.get("count", {}).get("label", "确认数量"),
                       var_type=state.get("count", {}).get("type", "text-input"),
                       required=False)
    add_start_variable(dsl, "start_node", "suggest",
                       label=state.get("suggest", {}).get("label", "选中的条目"),
                       var_type=state.get("suggest", {}).get("type", "paragraph"),
                       required=False)
    add_start_variable(dsl, "start_node", "choose_id",
                       label=state.get("choose_id", {}).get("label", "选中条目ID"),
                       var_type=state.get("choose_id", {}).get("type", "text-input"),
                       required=False)
    add_start_variable(dsl, "start_node", "result_json",
                       label=state.get("result_json", {}).get("label", "确认后的JSON"),
                       var_type=state.get("result_json", {}).get("type", "paragraph"),
                       required=False)

    # ---- if-else 节点 ----
    cases = []
    for idx, (cid, stage_val) in enumerate([
        ("true", "analyze"), ("branch_generate", "generate"), ("branch_confirm", "confirm")]):
        cases.append({
            "id": cid,
            "case_id": cid,
            "conditions": [{
                "id": "cond{}".format(idx + 1),
                "comparison_operator": "is",
                "value": stage_val,
                "varType": "string",
                "variable_selector": ["start_node", "stage"],
            }],
            "logical_operator": "and",
        })
    add_node(dsl, NodeType.IF_ELSE, title="条件分支", node_id="ifelse_node",
             position=(381, 282), data_overrides={"cases": cases})
    add_edge(dsl, "start_node", "ifelse_node")

    def join_lines(x):
        if isinstance(x, list):
            return "\n".join(x)
        return x or ""

    # ---- analyze 分支 ----
    analyze = spec.get("analyze", {})
    analyze_prompt = join_lines(analyze.get("system_prompt")) or default_analyze_prompt(spec)
    prev = "ifelse_node"
    prev_handle = "true"
    if has_file:
        add_node(dsl, NodeType.DOCUMENT_EXTRACTOR, title="文档提取器",
                 node_id="doc_extractor", position=(683, 151),
                 data_overrides={"variable_selector": ["start_node", "file"],
                                 "is_array_file": False})
        add_edge(dsl, "ifelse_node", "doc_extractor", source_handle="true")
        prev, prev_handle = "doc_extractor", "source"
    add_node(dsl, NodeType.LLM, title="LLM-分析建议", node_id="llm_analyze",
             position=(966 if has_file else 683, 151),
             data_overrides=dict(llm_common, prompt_template=[
                 {"id": "sys1", "role": "system", "text": analyze_prompt}]))
    add_edge(dsl, prev, "llm_analyze", source_handle=prev_handle)
    add_node(dsl, NodeType.END, title="输出-分析建议", node_id="end_analyze",
             position=(1239 if has_file else 966, 151))
    for out in (analyze.get("outputs") or [
        {"variable": "analyze_result", "from": ["llm_analyze", "text"]},
        {"variable": "file_text", "from": ["doc_extractor", "text"]} if has_file else None,
    ]):
        if out:
            add_end_output(dsl, "end_analyze", out["variable"], out["from"],
                           value_type=out.get("type", "string"))
    add_edge(dsl, "llm_analyze", "end_analyze")

    # ---- generate 分支 ----
    gen = spec.get("generate", {})
    gen_prompt = join_lines(gen.get("system_prompt")) or default_generate_prompt(spec)
    json_key = gen.get("json_key", "items")
    prev = "ifelse_node"
    prev_handle = "branch_generate"
    if has_file:
        add_node(dsl, NodeType.DOCUMENT_EXTRACTOR, title="文档提取器-generate",
                 node_id="doc_extractor_generate", position=(550, 282),
                 data_overrides={"variable_selector": ["start_node", "file"],
                                 "is_array_file": False})
        add_edge(dsl, "ifelse_node", "doc_extractor_generate",
                 source_handle="branch_generate")
        prev, prev_handle = "doc_extractor_generate", "source"
    add_node(dsl, NodeType.LLM, title="LLM-生成" + spec.get("entity_label", ""),
             node_id="llm_generate", position=(850 if has_file else 683, 282),
             data_overrides=dict(llm_common, prompt_template=[
                 {"id": "sys2", "role": "system", "text": gen_prompt}]))
    add_edge(dsl, prev, "llm_generate", source_handle=prev_handle)
    gen_code = join_lines(gen.get("code")) or default_generate_code(json_key)
    add_node(dsl, NodeType.CODE, title="代码执行-JSON校验", node_id="code_generate",
             position=(1100 if has_file else 900, 282),
             data_overrides={
                 "code_language": "python3",
                 "code": gen_code,
                 "variables": [{
                     "variable": gen.get("code_input", "raw_json"),
                     "value_selector": gen.get("code_input_from", ["llm_generate", "text"]),
                     "value_type": "string",
                 }],
             })
    code_node = next(n for n in dsl.workflow.graph.nodes if n.id == "code_generate")
    code_node.data.__pydantic_extra__["outputs"] = {
        "success": {"type": "boolean", "children": None},
        json_key: {"type": "string", "children": None},
        "preview": {"type": "string", "children": None},
    }
    add_edge(dsl, "llm_generate", "code_generate")
    add_node(dsl, NodeType.END, title="输出-生成预览", node_id="end_generate",
             position=(1400 if has_file else 1200, 282))
    for out in (gen.get("outputs") or [
        {"variable": "generate_result", "from": ["code_generate", "preview"]},
        {"variable": "success", "from": ["code_generate", "success"], "type": "boolean"},
    ]):
        add_end_output(dsl, "end_generate", out["variable"], out["from"],
                       value_type=out.get("type", "string"))
    add_edge(dsl, "code_generate", "end_generate")

    # ---- confirm 分支 ----
    conf = spec.get("confirm", {})
    conf_code = join_lines(conf.get("code")) or default_confirm_code()
    add_node(dsl, NodeType.CODE, title="代码执行-确认输出", node_id="code_confirm",
             position=(683, 382),
             data_overrides={
                 "code_language": "python3",
                 "code": conf_code,
                 "variables": [{
                     "variable": conf.get("code_input", "arg1"),
                     "value_selector": conf.get("code_input_from", ["start_node", "result_json"]),
                     "value_type": "string",
                 }],
             })
    conf_node = next(n for n in dsl.workflow.graph.nodes if n.id == "code_confirm")
    conf_node.data.__pydantic_extra__["outputs"] = {
        "status": {"type": "string", "children": None},
        "data": {"type": "string", "children": None},
    }
    add_edge(dsl, "ifelse_node", "code_confirm", source_handle="branch_confirm")
    add_node(dsl, NodeType.END, title="输出-标准JSON", node_id="end_confirm",
             position=(966, 382))
    for out in (conf.get("outputs") or [
        {"variable": "confirm_result", "from": ["code_confirm", "data"]},
        {"variable": "status", "from": ["code_confirm", "status"]},
    ]):
        add_end_output(dsl, "end_confirm", out["variable"], out["from"],
                       value_type=out.get("type", "string"))
    add_edge(dsl, "code_confirm", "end_confirm")

    return dsl


def main():
    ap = argparse.ArgumentParser(description="方法A：dify-workflow 确定性 DSL 生成器")
    ap.add_argument("spec", help="业务 spec JSON 路径")
    ap.add_argument("-o", "--output", required=True, help="输出 DSL YAML 路径")
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    dsl = build(spec)
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    from dify_workflow.io import save_workflow
    save_workflow(dsl, out)
    print("[methodA] 已生成: {}".format(out))


if __name__ == "__main__":
    main()
