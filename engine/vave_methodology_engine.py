# -*- coding: utf-8 -*-
"""
方法论引擎：在生成降本建议时，逐条跑完知识库中的所有 VAVE 方法，
并记录「采用 / 适用未采纳 / 不适用」及原因，形成完整思考过程（完整版报告的数据源）。

- 纯规则模式：基于触发词 + 适用零件类型判定每个方法的适用性，结合已生成建议标记「采用」。
- AI 模式：由 vave_deepseek.generate_methodology_analysis 产出更深度的逐方法判断（功能理解/BOM解读）。
"""
import os
import json
from pathlib import Path

_KB_PATH = Path(__file__).parent / "vave_knowledge_base.json"


def load_knowledge_base() -> dict:
    try:
        return json.load(open(_KB_PATH, encoding="utf-8"))
    except Exception:
        return {}


def get_methodology_methods() -> list:
    """返回知识库 strategy_library 中的全部方法（单一数据源）。"""
    kb = load_knowledge_base()
    return kb.get("strategy_library", {}).get("strategies", [])


def get_kb_stats() -> dict:
    """知识库实际统计（供侧边栏/描述自动刷新）。"""
    kb = load_knowledge_base()
    cases = kb.get("cases", [])
    methods = kb.get("strategy_library", {}).get("strategies", [])
    enh = kb.get("enhanced_cases", [])
    return {
        "cases": len(cases),
        "enhanced_cases": len(enh),
        "methods": len(methods),
        "version": kb.get("metadata", {}).get("version", "1.0"),
    }


# 应用类别 → 知识库零件类型词汇 的归一
_CAT_MAP = {
    "塑料件": "塑料件", "冲压件": "冲压件", "压铸件": "压铸件",
    "机加件": "机加件", "电子件": "电子件",
    "通用": "通用件", "外观件": "外观件", "功能件": "功能件", "结构件": "结构件",
}
_ALL_PARTS = ["塑料件", "冲压件", "压铸件", "机加件", "电子件", "通用件",
              "外观件", "功能件", "结构件"]


def _normalize_category(category: str) -> str:
    return _CAT_MAP.get(category, "通用件")


def _match_suggestion(method: dict, suggestions: list) -> dict:
    """在已生成建议中查找匹配该方法的具体建议（用于展示采用的建议内容）。"""
    # 1) 精确匹配（建议的 strategy_type == 该方法自身名）
    for s in suggestions:
        if s.get("strategy_type") == method.get("type"):
            return s
    # 2) 主代表匹配（type==canonical 时，整类建议都算采用）
    canon = method.get("canonical", "")
    if method.get("type") == canon:
        for s in suggestions:
            if s.get("strategy_type") == canon:
                return s
    # 3) 子类方法：需其自身触发词命中建议文本才算“采用”
    triggers = [t.lower() for t in method.get("triggers", [])]
    for s in suggestions:
        if s.get("strategy_type") == canon and \
           any(t in (s.get("direction", "") + s.get("mechanism", "")).lower() for t in triggers):
            return s
    return None


def _is_used(method: dict, suggestions: list) -> bool:
    """判断该方法是否被某条已生成建议“采用”。"""
    sug_types = {s.get("strategy_type") for s in suggestions}
    type_, canon = method.get("type"), method.get("canonical", "")
    if type_ in sug_types:
        return True
    if type_ == canon and canon in sug_types:
        return True
    # 子类：建议文本需命中其“动作级”触发词（sub_triggers，避免材料词误判）
    sub_triggers = method.get("sub_triggers") or method.get("triggers", [])
    triggers = [t.lower() for t in sub_triggers]
    for s in suggestions:
        if s.get("strategy_type") == canon and \
           any(t in (s.get("direction", "") + s.get("mechanism", "")).lower() for t in triggers):
            return True
    return False


def run_methodology_trace(part_info: dict, suggestions: list = None) -> dict:
    """
    逐条评估所有方法论方法，产出思考过程。

    Args:
        part_info: {part_name, material, category, additional_info, weight_kg,
                    cost_per_unit, bom(可选)}
        suggestions: 已生成的建议列表（含 strategy_type 等）

    Returns:
        dict: {
            "methods": [ {id,type,lever,status,reason,matched_suggestion} ],
            "counts": {total, used, applicable, not_applicable},
            "summary": str
        }
    """
    suggestions = suggestions or []
    methods = get_methodology_methods()
    part_name = (part_info.get("part_name") or "").lower()
    material = (part_info.get("material") or "").lower()
    addinfo = (part_info.get("additional_info") or "").lower()
    cat = _normalize_category(part_info.get("category", "通用"))
    haystack = f"{part_name} {material} {addinfo}"

    trace = []
    n_used = n_applicable = n_not = 0

    for m in methods:
        triggers = [t.lower() for t in m.get("triggers", [])]
        hits = [t for t in triggers if t in haystack]
        part_match = (cat in m.get("applicable_parts", [])) or \
                     (cat == "通用件" and "通用件" in m.get("applicable_parts", []))
        # 商务/产业链/平台类方法对采购件普遍适用，触发词命中即视为适用
        lever = m.get("lever", "")
        broad = lever in ("商务降本", "产业链策略", "零部件策略")
        applicable = bool(hits) and (part_match or broad)

        matched = _match_suggestion(m, suggestions)
        used = _is_used(m, suggestions)

        if used and matched:
            status = "used"
            n_used += 1
            sug_pct = str(matched.get("expected_savings_pct", "")).rstrip("%").rstrip()
            reason = f"✅ 已采用：{matched.get('direction','')}（预期降幅 {sug_pct}%）"
        elif applicable:
            status = "applicable"
            n_applicable += 1
            reason = (f"⚠️ 适用但未生成具体建议：{m.get('description','')} "
                      f"可结合本零件评估（典型降幅 {m.get('savings','')}）。")
        else:
            status = "not_applicable"
            n_not += 1
            reason = f"❌ 不适用：{m.get('not_reason','该零件特征与方法触发条件不匹配。')}"

        trace.append({
            "id": m.get("id", ""),
            "type": m.get("type", ""),
            "lever": lever,
            "status": status,
            "reason": reason,
            "matched_suggestion": matched,
        })

    total = len(methods)
    summary = (f"本次对知识库全部 {total} 个 VAVE 方法逐一评估："
               f"已采用 {n_used} 个，适用待评估 {n_applicable} 个，不适用 {n_not} 个。")

    return {
        "methods": trace,
        "counts": {
            "total": total, "used": n_used,
            "applicable": n_applicable, "not_applicable": n_not,
        },
        "summary": summary,
        "function_understanding": part_info.get("function_understanding", ""),
        "bom_interpretation": part_info.get("bom_interpretation", ""),
        "source": "rule",
    }


def merge_ai_trace(rule_trace: dict, ai_res: dict, methods: list) -> dict:
    """用 AI 完整思考链覆盖/补充规则版 trace（按方法 id 对齐）。

    AI 的每个 method_decision 提供更深度的 reason 与 suggestion；
    未覆盖到的方法保留规则版判定。同时回填功能理解/BOM解读。
    """
    if not ai_res or not ai_res.get("success"):
        return rule_trace
    dec_by_id = {d.get("id"): d for d in ai_res.get("method_decisions", [])}
    new_methods = []
    for it in rule_trace.get("methods", []):
        dec = dec_by_id.get(it["id"])
        if dec:
            applicable = dec.get("applicable", True)
            sug = dec.get("suggestion")
            if applicable and sug:
                status = "used"
            elif applicable:
                status = "applicable"
            else:
                status = "not_applicable"
            new_methods.append({
                "id": it["id"], "type": it["type"], "lever": it["lever"],
                "status": status,
                "reason": dec.get("reason", it["reason"]),
                "matched_suggestion": sug,
            })
        else:
            new_methods.append(it)
    n_used = sum(1 for m in new_methods if m["status"] == "used")
    n_app = sum(1 for m in new_methods if m["status"] == "applicable")
    n_not = sum(1 for m in new_methods if m["status"] == "not_applicable")
    total = len(new_methods)
    summary = ai_res.get("summary") or rule_trace.get("summary", "")
    return {
        "methods": new_methods,
        "counts": {"total": total, "used": n_used,
                   "applicable": n_app, "not_applicable": n_not},
        "summary": summary,
        "function_understanding": ai_res.get("function_understanding", ""),
        "bom_interpretation": ai_res.get("bom_interpretation", ""),
        "source": "ai",
    }


def render_trace_markdown(trace: dict) -> str:
    """将思考过程渲染为 Markdown 文本（用于 PDF / 调试）。"""
    lines = [trace.get("summary", ""), ""]
    if trace.get("function_understanding"):
        lines.append(f"**零件功能理解**：{trace['function_understanding']}")
        lines.append("")
    if trace.get("bom_interpretation"):
        lines.append(f"**BOM 解读**：{trace['bom_interpretation']}")
        lines.append("")
    lines.append("**方法论逐方法评估**：")
    for it in trace.get("methods", []):
        icon = {"used": "✅", "applicable": "⚠️", "not_applicable": "❌"}.get(it["status"], "•")
        lines.append(f"- {icon} **[{it['lever']}] {it['type']}**：{it['reason']}")
    return "\n".join(lines)


if __name__ == "__main__":
    demo = run_methodology_trace(
        {"part_name": "仪表台本体", "material": "PP+EPDM-T20 注塑", "category": "塑料件",
         "additional_info": "大型外观件，含多个卡扣与嵌件"},
        suggestions=[{"strategy_type": "材料替换", "direction": "PP+T20 改 PP+T10 降本",
                      "expected_savings_pct": "8%~12%"}],
    )
    print(render_trace_markdown(demo))
