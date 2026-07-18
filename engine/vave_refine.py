# -*- coding: utf-8 -*-
"""
汽车VAVE建议精修模块
v1.0

方向① 成本精算：初版建议 + 材料牌号/供应商报价/年用量 → DeepSeek 重算具体降本金额
方向② 风险过滤：初版建议 + 历史失败案例 → DeepSeek 过滤/精化建议

API Key: 从 vave_deepseek.py 的 API Key 机制继承，或直接从 vave_config.json 读
"""

import os
import json
import re
import sys
from pathlib import Path
from typing import Optional

# 继承 DeepSeek 调用能力
try:
    from vave_deepseek import call_deepseek, DEEPSEEK_API_KEY
except ImportError:
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    def call_deepseek(system_prompt, user_prompt, model="deepseek-chat",
                      temperature=0.3, max_tokens=2000, api_key=""):
        from openai import OpenAI
        key = api_key or DEEPSEEK_API_KEY
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        r = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
            temperature=temperature, max_tokens=max_tokens,
        )
        return r.choices[0].message.content

KB_PATH = Path(__file__).parent / "vave_knowledge_base.json"

# ============================================================
# 方向①：成本精算
# ============================================================

def refine_cost(
    initial_suggestions: list,
    part_name: str,
    current_cost: float,        # 当前单件成本（元/件）
    annual_qty: int,            # 年用量（件/年）
    current_material: str = "",
    cost_data: str = "",       # 用户补充的成本数据（多行文本）
    api_key: str = "",
) -> dict:
    """
    精修 VAVE 建议的成本测算

    Args:
        initial_suggestions: 初版 DeepSeek 建议列表
        part_name: 零件名称
        current_cost: 当前单件成本（元/件）
        annual_qty: 年用量（件/年）
        current_material: 当前材料
        cost_data: 用户补充的成本数据（多行，如材料牌号/供应商报价/重量等）
        api_key: DeepSeek API Key

    Returns:
        dict: {
            "success": bool,
            "suggestions": list,   # 含精修后成本的建议
            "raw_response": str,
            "error": str,
        }
    """
    _key = api_key or DEEPSEEK_API_KEY
    if not _key:
        return {"success": False, "error": "未提供 DeepSeek API Key",
                "suggestions": [], "raw_response": ""}

    total_annual = current_cost * annual_qty

    # 构建上下文
    ctx = []
    ctx.append(f"【零件基本信息】")
    ctx.append(f"零件名称：{part_name}")
    ctx.append(f"当前单件成本：{current_cost} 元/件")
    ctx.append(f"年用量：{annual_qty} 件/年")
    ctx.append(f"当前年度采购额：{total_annual:,.0f} 元（约 {total_annual/10000:.2f} 万元）")
    if current_material:
        ctx.append(f"当前材料：{current_material}")
    if cost_data:
        ctx.append(f"\n【用户提供的成本数据】")
        ctx.append(cost_data)

    ctx.append(f"\n【初版 VAVE 建议】")
    ctx.append(f"（以下每条建议需要补充具体的降本金额测算）")
    for i, s in enumerate(initial_suggestions, 1):
        ctx.append(f"\n建议{i}：{s.get('direction','')}")
        ctx.append(f"  类型：{s.get('strategy_type','')}")
        ctx.append(f"  初版预期降幅：{s.get('expected_savings_pct','')}")
        ctx.append(f"  实施优先级：{s.get('implementation_priority','')}")
        ctx.append(f"  质量风险：{s.get('quality_risk','')}")
        ctx.append(f"  关键注意事项：{s.get('key_consideration','')}")

    system_prompt = """你是一位资深汽车行业成本工程师，擅长将抽象的VAVE降本建议量化为具体金额。

你的任务：根据【用户提供的成本数据】和【初版建议】，为每条建议计算：
1. 精确的单件降本金额（元/件）
2. 精确的年度降本金额（元/年）和降本幅度百分比
3. 实施该建议的ROI评估（降本收益 vs 实施成本估算）

## 计算原则
- 单件降本 = 当前单件成本 × 降幅百分比（或按用户提供的数据推算）
- 年度降本 = 单件降本 × 年用量
- 降幅百分比 = 单件降本 / 当前单件成本 × 100%
- 若用户提供具体牌号和报价，按实际价差计算；若未提供，按降幅百分比估算
- ROI = 年度降本金额 / 预估实施成本（实施成本需根据策略类型估算）

## 实施成本估算参考（行业经验值）
- 材料替换（P0-P1）：实施成本 0.5~2 万元（主要是验证试验）
- 工艺优化（P0-P1）：实施成本 2~10 万元（模具/工装修改）
- 结构优化（P1-P2）：实施成本 3~15 万元（CAE+模具）
- 供应商优化（P0）：实施成本 0.1~0.5 万元（寻源商务工作）
- 设计标准化（P2）：实施成本 5~20 万元（设计变更+验证）

## 输出格式（严格JSON，不要输出其他内容）
{
  "summary": "一句话总结降本最大机会在哪里",
  "suggestions": [
    {
      "rank": 1,
      "direction": "降本方向",
      "strategy_type": "策略类型",
      "current_unit_cost": 123.5,
      "expected_unit_cost_after": 105.0,
      "unit_savings": 18.5,
      "savings_pct": 15.0,
      "annual_qty": 50000,
      "annual_savings": 925000,
      "annual_savings_wan": 92.5,
      "roi_months": 3,
      "implementation_cost_wan": 2.0,
      "implementation_priority": "P0",
      "quality_risk": "风险描述",
      "risk_level": "低/中/高",
      "implementation_note": "落地关键点"
    }
  ],
  "total_annual_savings_wan": 185.5,
  "total_implementation_cost_wan": 5.0,
  "payback_months": 3,
  "warnings": ["需关注的1-2个风险"]
}

## 注意事项
- 所有金额保留1位小数，单位万元
- ROI回收期以月计（实施成本 / 月度降本金额）
- 若某建议数据不足无法计算，注明"数据不足，待确认"，不要虚构
- 按年度降本金额从大到小排序
"""
    user_prompt = "\n".join(ctx)

    try:
        raw = call_deepseek(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="deepseek-chat",
            temperature=0.2,
            max_tokens=3000,
            api_key=_key,
        )
        suggestions = _parse_json(raw)

        # 如果 DeepSeek 返回了结构化数据，直接用
        if suggestions and "suggestions" in suggestions:
            return {
                "success": True,
                "suggestions": suggestions.get("suggestions", []),
                "raw_response": raw,
                "error": "",
                "summary": suggestions.get("summary", ""),
                "total_annual_savings_wan": suggestions.get("total_annual_savings_wan", 0),
                "payback_months": suggestions.get("payback_months", 0),
            }
        # 否则尝试从原始文本解析
        return {
            "success": True,
            "suggestions": _parse_suggestions_from_text(raw, current_cost, annual_qty),
            "raw_response": raw,
            "error": "",
            "summary": "",
            "total_annual_savings_wan": 0,
            "payback_months": 0,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "suggestions": [], "raw_response": ""}


# ============================================================
# 方向②：风险过滤
# ============================================================

def _load_failure_cases() -> list:
    """从知识库提取历史失败/低可行性案例作为风险上下文"""
    try:
        with open(KB_PATH, encoding="utf-8") as f:
            kb = json.load(f)
        failures = []
        for case in kb.get("cases", []):
            for st in case.get("vave_strategies", []):
                # feasibility 字段记录可行性，低值视为"历史上不太成功的案例"
                feas = st.get("feasibility", "高")
                diff = st.get("implementation_difficulty", "低")
                if feas in ("低", "中") or diff == "高":
                    failures.append({
                        "part": case.get("part_name", ""),
                        "category": case.get("category", ""),
                        "material": case.get("material", ""),
                        "strategy": st.get("strategy", ""),
                        "direction": st.get("direction", ""),
                        "expected_savings_pct": st.get("expected_savings_pct", ""),
                        "feasibility": feas,
                        "failure_reason": st.get("quality_risk", "未记录"),
                        "case_ref": st.get("case_ref", ""),
                    })
        return failures
    except Exception:
        return []


def refine_risk_filter(
    initial_suggestions: list,
    part_name: str,
    material: str = "",
    category: str = "",
    additional_constraints: str = "",  # 用户补充的约束（制造能力/法规/客户要求等）
    api_key: str = "",
) -> dict:
    """
    风险过滤：初版建议 + 历史失败案例 → 过滤/精化建议

    Args:
        initial_suggestions: 初版建议列表
        part_name: 零件名称
        material: 当前材料
        category: 零件类别
        additional_constraints: 用户补充的约束条件
        api_key: DeepSeek API Key

    Returns:
        dict: {
            "success": bool,
            "filtered_suggestions": list,  # 过滤后剩余建议（带风险评分）
            "rejected_suggestions": list,   # 被过滤掉的建议（附原因）
            "risk_summary": str,           # 整体风险评估
            "raw_response": str,
            "error": str,
        }
    """
    _key = api_key or DEEPSEEK_API_KEY
    if not _key:
        return {"success": False, "error": "未提供 DeepSeek API Key",
                "filtered_suggestions": [], "rejected_suggestions": [],
                "risk_summary": "", "raw_response": ""}

    failures = _load_failure_cases()

    ctx = []
    ctx.append(f"【零件信息】零件：{part_name} | 材料：{material or '未提供'} | 类别：{category or '未提供'}")

    if additional_constraints:
        ctx.append(f"\n【用户补充约束条件】{additional_constraints}")

    ctx.append(f"\n【历史失败/风险案例库】（来自知识库，标注了低可行性策略，供你参考）")
    if failures:
        for f in failures[:8]:  # 最多8条
            ctx.append(f"\n- 零件：{f['part']} | 类别：{f['category']}")
            ctx.append(f"  策略：{f['strategy']} → {f['direction']}")
            ctx.append(f"  降幅：{f['expected_savings_pct']}% | 可行性：{f['feasibility']}")
            ctx.append(f"  失败/风险原因：{f['failure_reason']}")
    else:
        ctx.append("（知识库中暂无失败案例记录）")

    ctx.append(f"\n【初版 VAVE 建议】请逐条评估风险并过滤：")
    for i, s in enumerate(initial_suggestions, 1):
        ctx.append(f"\n建议{i}：{s.get('direction','')}")
        ctx.append(f"  类型：{s.get('strategy_type','')} | 优先级：{s.get('implementation_priority','')}")
        ctx.append(f"  预期降幅：{s.get('expected_savings_pct','')}")
        ctx.append(f"  质量风险：{s.get('quality_risk','')}")
        ctx.append(f"  注意事项：{s.get('key_consideration','')}")

    system_prompt = """你是一位资深汽车行业质量工程与制造工艺专家，负责对VAVE建议进行风险审查。

你的任务：
1. 将初版建议逐条与历史失败案例进行比对，识别高风险建议
2. 对被过滤的建议给出明确原因（为何在当前零件上不可行）
3. 对保留的建议补充风险缓解措施
4. 识别是否有"总成级"风险（该件改动影响相邻零件）

## 风险评分标准（1-5分）
- 1分：风险极低，直接可执行
- 2分：风险较低，按标准流程验证即可
- 3分：存在中等风险，需要专项验证
- 4分：风险较高，需较多试验/CAE，需管理层批准
- 5分：风险极高，不建议执行

## 过滤原则（直接淘汰）
- 风险评分 ≥ 4 的建议
- 与用户约束条件明显冲突的建议（如：客户指定材料不能换）
- 在同类零件历史上多次失败的策略
- 不符合安全法规/碰撞安全要求的建议

## 输出格式（严格JSON）
{
  "risk_summary": "整体风险评估，一句话",
  "filtered_suggestions": [
    {
      "rank": 1,
      "direction": "降本方向",
      "strategy_type": "策略类型",
      "implementation_priority": "P0",
      "risk_score": 2,
      "risk_level": "低",
      "risk_mitigation": "风险缓解措施，1-2句话",
      "implementation_note": "落地关键注意事项"
    }
  ],
  "rejected_suggestions": [
    {
      "direction": "被拒绝的方向",
      "reason": "拒绝原因，要具体，1-2句话",
      "original_risk_score": 4,
      "suggested_alternative": "替代方案建议（如果有）"
    }
  ],
  "assembly_risk": "总成级风险评估（该件改动是否影响相邻零件），无则填'无'"
}

## 注意事项
- 优先保留P0-P1建议，P2建议从严审查
- 风险评分要严格，不要为了讨好用户都打高分
- 如果过滤后只剩0条建议，说明项目本身风险高，这是有价值的信息
"""
    user_prompt = "\n".join(ctx)

    try:
        raw = call_deepseek(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="deepseek-chat",
            temperature=0.25,
            max_tokens=3000,
            api_key=_key,
        )
        result = _parse_json(raw)

        if result and "filtered_suggestions" in result:
            return {
                "success": True,
                "filtered_suggestions": result.get("filtered_suggestions", []),
                "rejected_suggestions": result.get("rejected_suggestions", []),
                "risk_summary": result.get("risk_summary", ""),
                "assembly_risk": result.get("assembly_risk", ""),
                "raw_response": raw,
                "error": "",
            }

        # 回退：无法解析JSON时返回原始建议并标注警告
        return {
            "success": True,
            "filtered_suggestions": _add_default_risk_scores(initial_suggestions),
            "rejected_suggestions": [],
            "risk_summary": "（风险评分未成功生成，原始建议已保留，请在实施前自行评估风险）",
            "raw_response": raw,
            "error": "",
        }
    except Exception as e:
        return {"success": False, "error": str(e),
                "filtered_suggestions": initial_suggestions,
                "rejected_suggestions": [], "risk_summary": "", "raw_response": ""}


# ============================================================
# 工具函数
# ============================================================

def _parse_json(raw: str) -> dict:
    """从 DeepSeek 输出中提取 JSON"""
    text = raw.strip()
    if text.startswith("```"):
        # 去掉 markdown 代码块标记
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    # 找第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return {}


def _parse_suggestions_from_text(raw: str, current_cost: float, annual_qty: int) -> list:
    """无法解析JSON时，从文本中提取建议并补估算降本金额"""
    suggestions = []
    # 简单按行解析 "建议X" 或 "direction" 模式
    lines = raw.split("\n")
    current = {}
    for line in lines:
        line = line.strip()
        if re.match(r"建议\s*\d+[:：]", line) or re.match(r"\d+[.、]", line):
            if current and "direction" in current:
                _estimate_savings(current, current_cost, annual_qty)
                suggestions.append(current)
            current = {"direction": re.sub(r"^[^：：]+[：:]\s*", "", line).strip()}
        elif "方向" in line and ":" in line:
            current["direction"] = line.split(":", 1)[-1].strip()
        elif "降幅" in line and ("%" in line or "降" in line):
            m = re.search(r"(\d+\.?\d*)\s*~?\s*(\d+\.?\d*)?\s*%", line)
            if m:
                low, high = float(m.group(1)), float(m.group(2)) if m.group(2) else float(m.group(1))
                current["savings_pct"] = f"{low:.0f}~{high:.0f}%"
                current["unit_savings"] = current_cost * (low / 100)
                current["annual_savings"] = current["unit_savings"] * annual_qty
    if current and "direction" in current:
        _estimate_savings(current, current_cost, annual_qty)
        suggestions.append(current)
    return suggestions


def _estimate_savings(s: dict, current_cost: float, annual_qty: int):
    """估算降本金额（供解析失败时回退用）"""
    pct_str = s.get("savings_pct", "").replace("%", "").replace("～", "~")
    try:
        if "~" in pct_str:
            parts = pct_str.split("~")
            avg_pct = (float(parts[0]) + float(parts[1])) / 2
        else:
            avg_pct = float(pct_str)
    except Exception:
        avg_pct = 0
    s["unit_savings"] = round(current_cost * avg_pct / 100, 2)
    s["annual_savings"] = round(s["unit_savings"] * annual_qty, 0)
    s["savings_pct_estimated"] = f"{avg_pct:.1f}%"


def _add_default_risk_scores(suggestions: list) -> list:
    """给建议加默认风险评分（回退用）"""
    priority_risk = {"P0": 1, "P1": 2, "P2": 3}
    for s in suggestions:
        p = s.get("implementation_priority", "P2")
        s["risk_score"] = priority_risk.get(p, 3)
        s["risk_level"] = ["低", "低", "中", "高", "极高"][min(s["risk_score"]-1, 4)]
        s["risk_mitigation"] = s.get("key_consideration", "请结合实际情况评估")
    return suggestions
