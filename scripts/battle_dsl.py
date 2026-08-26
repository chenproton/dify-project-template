#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多方法 DSL 生成编排器（battle）
==================================
用法:
    tools/venv/bin/python scripts/battle_dsl.py specs/job_ai.json

流程:
  1. 方法A（dify-workflow CLI 确定性生成）→ generated/<id>/<id>_methodA_cli.dify.yml
  2. 方法B（dify-workflow-dsl-skill，AI 生成）→ 生成 AI 生成简报（由 agent 用 vendored skill 产出变体）
  3. 方法C（aeson dify-workflow skill，AI 生成）→ 生成 AI 生成简报（同上）
  4. 校验所有已存在变体：dify-workflow validate --strict + validate_dsl.py --strict
  5. 汇总输出 generated/<id>/COMPARE.md
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENV_PY = ROOT / "tools" / "venv" / "bin" / "python"
DIFY_WF = ROOT / "tools" / "venv" / "bin" / "dify-workflow"
GEN_SCRIPT = ROOT / "scripts" / "generate_dsl_cli.py"
SKILL2_VALIDATOR = ROOT / "skills" / "dify-workflow-dsl-skill" / "scripts" / "validate_dsl.py"

METHODS = [
    ("methodA", "dify-workflow CLI 确定性生成", "{id}_methodA_cli.dify.yml"),
    ("methodB", "dify-workflow-dsl-skill（AI 直接生成）", "{id}_methodB_skill2.dify.yml"),
    ("methodC", "aeson dify-workflow skill（AI 生成 + 版本锚定）", "{id}_methodC_aeson.dify.yml"),
]


def brief_b(spec, out_path):
    lines = [
        "# 方法B 生成简报：{name}".format(name=spec["app"].get("name", spec.get("id"))),
        "",
        "请使用仓库内 vendored skill：`skills/dify-workflow-dsl-skill/SKILL.md`（及其 references/）",
        "根据下方业务描述，为 Dify 生成可直接导入的工作流 DSL，保存到：" + out_path.name,
        "",
        "## 业务描述",
        spec.get("description", ""),
        "",
        "## 业务 spec（JSON）",
        "```json",
        json.dumps(spec, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 生成要求",
        "1. 结构遵循标准三段式：start → if-else(stage=analyze/generate/confirm) → 三个分支",
        "2. analyze 分支：document-extractor → LLM 分析（输出建议 JSON + 建议列表）",
        "3. generate 分支：document-extractor → LLM 生成 → Code 节点校验 JSON → end",
        "4. confirm 分支：Code 节点格式化 → end",
        "5. LLM 节点必须带 context: {enabled:false, variable_selector:[]}，workflow 模式不要 memory 字段",
        "6. 生成后用 `scripts/validate_dsl.py --strict --target-version 0.6.0` 自检",
        "",
        "## 输出文件",
        out_path.name + "（同时更新 battle 结果）",
    ]
    return "\n".join(lines)


def brief_c(spec, out_path):
    lines = [
        "# 方法C 生成简报：{name}".format(name=spec["app"].get("name", spec.get("id"))),
        "",
        "请使用仓库内 vendored skill：`skills/aeson-dify-workflow/SKILL.md`（含 references/config.yml 版本锚定）",
        "根据下方业务描述，为 Dify 生成可直接导入的工作流 DSL，保存到：" + out_path.name,
        "",
        "## 业务描述",
        spec.get("description", ""),
        "",
        "## 业务 spec（JSON）",
        "```json",
        json.dumps(spec, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 生成要求",
        "1. 遵循 `references/config.yml` 中 dsl_version=0.6.0 的版本锚定",
        "2. 结构：start → if-else(stage) → analyze/generate/confirm 三分支",
        "3. 节点 ID 用 13 位时间戳字符串，连线 sourceHandle 用分支 case_id",
        "4. LLM model.provider 用 langgenius/<provider>/<provider> 格式",
        "5. 交付前过 4 项校验关卡（语法命名/拓扑/变量引用/provider 正确性）",
        "",
        "## 输出文件",
        out_path.name + "（同时更新 battle 结果）",
    ]
    return "\n".join(lines)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def validate_variant(path):
    """用两个校验器分别校验一个 DSL 文件，返回结果 dict"""
    res = {"file": path.name, "bytes": path.stat().st_size}
    # 校验器1：dify-workflow CLI
    if DIFY_WF.exists():
        rc, out = run([str(DIFY_WF), "validate", str(path), "--strict"])
        ok = "✓ Workflow is valid" in out
        res["cli_valid"] = ok
        res["cli_detail"] = (out.strip() or "")[:300]
    # 校验器2：skill2 validate_dsl.py（先看 errors 数量，再看 warnings）
    if SKILL2_VALIDATOR.exists():
        rc2, out2 = run([str(VENV_PY), str(SKILL2_VALIDATOR), "--target-version", "0.6.0", str(path)])
        n_err = out2.count("ERROR")
        n_warn = out2.count("WARN")
        res["skill2_valid"] = (rc2 == 0)  # 无 error 即通过
        res["skill2_errors"] = n_err
        res["skill2_warnings"] = n_warn
        res["skill2_detail"] = (out2.strip() or "")[:300]
    return res


def node_edge_count(path):
    import yaml
    try:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        g = d["workflow"]["graph"]
        return len(g.get("nodes", [])), len(g.get("edges", []))
    except Exception:
        return -1, -1


def main():
    ap = argparse.ArgumentParser(description="多方法 DSL 生成编排器")
    ap.add_argument("spec", help="业务 spec JSON 路径")
    ap.add_argument("--skip-methodA", action="store_true", help="跳过方法A生成（只校验已有变体）")
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    bid = spec["id"]
    outdir = ROOT / "generated" / bid
    outdir.mkdir(parents=True, exist_ok=True)

    # 1. 方法A：确定性生成
    if not args.skip_methodA:
        outA = outdir / METHODS[0][2].format(id=bid)
        rc, log = run([str(VENV_PY), str(GEN_SCRIPT), str(pathlib.Path(args.spec)), "-o", str(outA)])
        print("[methodA]", "OK" if rc == 0 else "FAIL", outA.name)
        if rc != 0:
            print(log[:500])

    # 2/3. 方法B/C：生成 AI 简报
    for name, _, fname in METHODS[1:]:
        out_path = outdir / fname.format(id=bid)
        brief = brief_b(spec, out_path) if name == "methodB" else brief_c(spec, out_path)
        (outdir / (name + "_brief.md")).write_text(brief, encoding="utf-8")
        if not out_path.exists():
            print("[{name}] 待生成（AI 使用 vendored skill 产出）: {f}".format(name=name, f=out_path.name))

    # 4. 校验所有已存在变体
    variants = sorted(outdir.glob(bid + "_method*.dify.yml"))
    results = [validate_variant(v) for v in variants]
    for r in results:
        print("[validate]", r["file"], "cli:", r.get("cli_valid"), "skill2:", r.get("skill2_valid"))

    # 5. COMPARE.md
    rows = []
    for r in results:
        nodes, edges = node_edge_count(outdir / r["file"])
        rows.append({
            "file": r["file"],
            "bytes": r["bytes"],
            "nodes": nodes,
            "edges": edges,
            "cli_valid": r.get("cli_valid"),
            "skill2_valid": r.get("skill2_valid"),
            "skill2_errors": r.get("skill2_errors", 0),
            "skill2_warnings": r.get("skill2_warnings", 0),
        })
    md = [
        "# DSL 多方法对比报告：{name}".format(name=spec["app"].get("name", bid)),
        "",
        "业务 spec：`{s}`".format(s=pathlib.Path(args.spec).name),
        "",
        "| 变体 | 生成方法 | 大小 | 节点 | 边 | dify-workflow 校验 | skill2 校验(error/warn) |",
        "|------|---------|-----|------|----|------------------|------------------------|",
    ]
    method_names = {m[0]: m[1] for m in METHODS}
    for row in rows:
        mkey = next((k for k in ("methodA", "methodB", "methodC") if k in row["file"]), "?")
        s2 = "✅" if row.get("skill2_valid") else ("❌" if "skill2_valid" in row else "—")
        s2 = "{s} ({e}err/{w}warn)".format(s=s2, e=row["skill2_errors"], w=row["skill2_warnings"]) if "skill2_valid" in row else s2
        md.append("| {f} | {m} | {b}B | {n} | {e} | {c} | {s} |".format(
            f=row["file"], m=method_names.get("method" + mkey, mkey),
            b=row["bytes"], n=row["nodes"], e=row["edges"],
            c="✅" if row.get("cli_valid") else ("❌" if "cli_valid" in row else "—"),
            s=s2,
        ))
    md.append("")
    md.append("## 测试结论（人工）")
    md.append("")
    md.append("- 在 Dify 中逐个导入测试，确认业务正确性、分支行为、LLM 输出质量")
    md.append("- 选定保留的变体后：复制到 dsl/ 目录正式入库，并用 dify-workflow remote push 发布")
    md.append("")
    (outdir / "COMPARE.md").write_text("\n".join(md), encoding="utf-8")
    print("[battle] COMPARE.md 已生成: {}".format(outdir / "COMPARE.md"))


if __name__ == "__main__":
    main()
