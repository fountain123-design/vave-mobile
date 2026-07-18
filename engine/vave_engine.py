"""
汽车VAVE建议生成器 - 核心引擎
v1.0 MVP
用法：
  python vave_engine.py              # 交互模式
  python vave_engine.py --part xxx  # 单次查询
"""

import json
import pathlib
import sys
import os
from typing import Optional

# ========== 配置 ==========
KB_PATH = pathlib.Path(__file__).parent / "vave_knowledge_base.json"

# ========== 加载知识库 ==========
def load_knowledge_base():
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# ========== 相似度匹配（纯规则） ==========
def score_case(case: dict, query_lower: str, category: str) -> float:
    """计算案例与查询的匹配分数（0-100）"""
    score = 0.0
    
    # 关键词命中
    all_keywords = case.get("keywords", []) + [case.get("part_name", ""), case.get("category", "")]
    for kw in all_keywords:
        kw_l = kw.lower()
        # 精确匹配
        if kw_l in query_lower:
            score += 25
        # 部分包含
        for word in query_lower.split():
            if len(word) >= 2 and word in kw_l:
                score += 8
                break
    
    # 分类匹配
    if category and category != "通用":
        if case.get("category", "") == category:
            score += 15
        elif any(case.get("category", "") == cat for cat in [category]):
            score += 8
    
    return score

def get_top_cases(query: str, category: str, top_n: int = 5) -> list:
    """从知识库中找到最相关的案例"""
    kb = load_knowledge_base()
    query_lower = query.lower().strip()
    
    scored = []
    for case in kb["cases"]:
        s = score_case(case, query_lower, category)
        if s > 0:
            scored.append((s, case))
    
    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]

# ========== VAVE建议生成（规则+案例） ==========
def generate_suggestions(part_name: str, material: str, category: str, 
                          weight_kg: Optional[float] = None,
                          cost_per_unit: Optional[float] = None,
                          additional_info: str = "") -> dict:
    """基于零件信息和知识库生成VAVE建议"""
    kb = load_knowledge_base()
    query = f"{part_name} {material} {additional_info}".strip()
    
    # 找相关案例
    top_cases = get_top_cases(query, category, top_n=3)
    
    # 构建策略库快速查询
    strategy_map = {s["type"]: s for s in kb["strategy_library"]["strategies"]}
    
    # 生成建议
    suggestions = []
    seen_strategies = set()
    
    # 优先从匹配案例中提取
    for score, case in top_cases:
        for vave in case.get("vave_strategies", []):
            strat_type = vave.get("strategy", "")
            if strat_type in seen_strategies:
                continue
            seen_strategies.add(strat_type)
            
            # 判断可行性
            feasibility_text = vave.get("feasibility", "中")
            feasible = "高" in feasibility_text or "中" in feasibility_text
            
            if not feasible:
                continue
                
            suggestion = {
                "id": f"SUG-{len(suggestions)+1:02d}",
                "strategy_type": strat_type,
                "direction": vave.get("direction", ""),
                "expected_savings_pct": vave.get("expected_savings_pct", 0),
                "mechanism": vave.get("mechanism", ""),
                "quality_risk": vave.get("quality_risk", ""),
                "feasibility": feasibility_text,
                "case_ref": vave.get("case_ref", ""),
                "case_id": case.get("id", ""),
                "case_name": case.get("part_name", ""),
                "match_score": score,
            }
            suggestions.append(suggestion)
    
    # 如果案例不足，用策略库补充
    for case_score, case in top_cases:
        if len(suggestions) >= 5:
            break
        case_strat_type = case.get("vave_strategies", [{}])[0].get("strategy", "")
        if case_strat_type and case_strat_type not in seen_strategies:
            # 补充一个策略库方向
            for st_name, st_info in strategy_map.items():
                if st_name not in seen_strategies and len(suggestions) < 4:
                    seen_strategies.add(st_name)
                    suggestions.append({
                        "id": f"SUG-{len(suggestions)+1:02d}",
                        "strategy_type": st_name,
                        "direction": f"针对 {case.get('part_name','')} 类零件的{st_name}方向",
                        "expected_savings_pct": st_info.get("typical_savings_range", "5%~15%"),
                        "mechanism": st_info.get("description", ""),
                        "quality_risk": "；".join(st_info.get("key_risks", [])),
                        "feasibility": "中",
                        "case_ref": "",
                        "case_id": case.get("id", ""),
                        "case_name": case.get("part_name", ""),
                        "match_score": case_score * 0.5,
                    })
                    break
    
    # 计算预期降本金额
    if cost_per_unit:
        for s in suggestions:
            try:
                pct_str = str(s["expected_savings_pct"]).replace("%", "")
                if "~" in pct_str:
                    pct = float(pct_str.split("~")[0].replace("%", "")) / 100
                else:
                    pct = float(pct_str) / 100
                s["estimated_savings_per_unit"] = round(cost_per_unit * pct, 2)
                s["estimated_savings_amount"] = f"{s['estimated_savings_per_unit']}元/件"
            except:
                s["estimated_savings_amount"] = "需进一步评估"
    else:
        for s in suggestions:
            s["estimated_savings_amount"] = "需提供当前单件成本"
    
    # 按降本幅度排序
    def sort_key(s):
        try:
            pct_str = str(s["expected_savings_pct"]).replace("%", "").replace("~", "")
            return -float(pct_str)
        except:
            return 0
    
    suggestions.sort(key=sort_key)
    for i, s in enumerate(suggestions):
        s["id"] = f"SUG-{i+1:02d}"
        s["priority"] = "⭐⭐⭐ 优先" if i < 2 else ("⭐⭐ 推荐" if i < 4 else "⭐ 备选")
    
    return {
        "input": {
            "part_name": part_name,
            "material": material,
            "category": category,
            "weight_kg": weight_kg,
            "cost_per_unit": cost_per_unit,
            "additional_info": additional_info,
        },
        "matched_cases_count": len(top_cases),
        "suggestions": suggestions[:6],
        "strategy_summary": list(strategy_map.keys()),
    }

# ========== 格式化输出 ==========
def format_output(result: dict) -> str:
    """格式化输出为可读文本"""
    inp = result["input"]
    suggestions = result["suggestions"]
    
    lines = []
    lines.append("=" * 60)
    lines.append("  🚗 汽车VAVE降本建议报告")
    lines.append("=" * 60)
    lines.append(f"\n📋 零件信息")
    lines.append(f"  零件名称: {inp['part_name']}")
    lines.append(f"  材料/工艺: {inp['material']}")
    lines.append(f"  零件类别: {inp['category']}")
    if inp.get('cost_per_unit'):
        lines.append(f"  当前单件成本: {inp['cost_per_unit']}元/件")
    if inp.get('weight_kg'):
        lines.append(f"  当前重量: {inp['weight_kg']}kg")
    
    lines.append(f"\n📊 匹配到 {result['matched_cases_count']} 个相关历史案例")
    
    if not suggestions:
        lines.append("\n⚠️  未找到匹配的VAVE建议，请尝试调整关键词或扩大描述范围。")
        lines.append("\n💡 提示：可尝试输入：零件功能名称 + 材料 + 工艺，如：")
        lines.append("    '仪表台 PP塑料 注塑件' 或 '发动机支架 铝合金 压铸'")
        return "\n".join(lines)
    
    lines.append(f"\n💡 生成 {len(suggestions)} 条VAVE建议（按降本潜力排序）")
    lines.append("-" * 60)
    
    for s in suggestions:
        pct = s["expected_savings_pct"]
        lines.append(f"\n{s['id']} {s['priority']}")
        lines.append(f"  策略类型: {s['strategy_type']}")
        lines.append(f"  降本方向: {s['direction']}")
        lines.append(f"  预期降幅: {pct}% ({s.get('estimated_savings_amount', '金额待评估')})")
        lines.append(f"  降本逻辑: {s['mechanism']}")
        if s.get("case_ref"):
            lines.append(f"  📌 参考案例: {s['case_ref']}")
        elif s.get("case_name"):
            lines.append(f"  📌 参考案例: 同类零件 {s['case_name']}（案例库ID: {s['case_id']}）")
        lines.append(f"  ⚠️  风险提示: {s['quality_risk']}")
        lines.append(f"  ✅ 可行性: {s['feasibility']}")
    
    lines.append("\n" + "=" * 60)
    lines.append("  局限性说明：")
    lines.append("  - 本工具基于20+汽车行业典型VAVE案例，仅供参考")
    lines.append("  - 实际降本效果需通过工程验证确认后方可实施")
    lines.append("  - 建议优先试点小批量验证，再推广至大批量")
    lines.append("  - 所有降本方案需通过质量/法规/性能三重验证")
    lines.append("=" * 60)
    
    return "\n".join(lines)

# ========== 交互模式 ==========
def interactive_mode():
    print("\n" + "🚗" * 20)
    print("  汽车VAVE降本建议生成器 MVP v1.0")
    print("  基于20+汽车行业真实VAVE案例")
    print("🚗" * 20 + "\n")
    
    print("零件类别选项：")
    cats = ["冲压件", "机加件", "压铸件", "塑料件", "电子件", "管路件", "钣金件", "橡胶件", "标准件", "传动件", "底盘件", "车身件", "通用"]
    for i, c in enumerate(cats, 1):
        print(f"  {i}. {c}")
    
    print("\n" + "-" * 40)
    
    while True:
        print("\n请输入零件信息（输入 q 退出）:\n")
        
        try:
            part_name = input("零件名称（如：仪表台骨架）: ").strip()
            if part_name.lower() in ["q", "quit", "exit"]:
                print("\n再见！如有需要随时回来。👋")
                break
            
            print("\n零件类别: ")
            for i, c in enumerate(cats, 1):
                print(f"  {i}. {c}")
            cat_idx = input("选择类别编号（直接回车默认通用）: ").strip()
            if cat_idx.isdigit() and 1 <= int(cat_idx) <= len(cats):
                category = cats[int(cat_idx)-1]
            else:
                category = "通用"
            
            material = input("材料/工艺（如：PP+EPDM 注塑件，输入-跳过）: ").strip()
            if material == "-" or not material:
                material = "未知"
            
            cost_input = input("当前单件成本（元/件，输入-跳过）: ").strip()
            cost_per_unit = None
            if cost_input and cost_input != "-":
                try:
                    cost_per_unit = float(cost_input)
                except:
                    pass
            
            additional = input("补充信息（如：年用量30万件，输入-跳过）: ").strip()
            if additional == "-":
                additional = ""
            
            print("\n" + "生成中..." + "\n")
            
            result = generate_suggestions(
                part_name=part_name,
                material=material,
                category=category,
                cost_per_unit=cost_per_unit,
                additional_info=additional,
            )
            
            print(format_output(result))
            
        except KeyboardInterrupt:
            print("\n\n再见！👋")
            break
        except Exception as e:
            print(f"\n⚠️  出错了: {e}\n请重试。")

# ========== 方法论上下文提取 ==========
def get_methodology_context(category: str = "") -> str:
    """
    提取知识库中的VAVE方法论上下文，用于注入到AI增强prompt中。
    
    Args:
        category: 零件类别，用于筛选特定品类的策略（如'塑料件'）
    
    Returns:
        str: 格式化后的方法论文本
    """
    kb = load_knowledge_base()
    m = kb.get("vave_methodology", {})
    if not m:
        return ""

    lines = []
    lines.append("## V=F/C 核心公式")
    eq = m.get("core_equation", {})
    lines.append(f"价值V = 功能F / 成本C")
    for p in eq.get("five_paths_to_increase_value", []):
        lines.append(f"  路径{p['path']}：{p['function_change']}，{p['cost_change']} → {p['description']}")

    lines.append("\n## VE与VA的区别")
    veva = m.get("ve_vs_va", {})
    lines.append(veva.get("difference", ""))

    lines.append("\n## 汽车行业VAVE三阶段介入时机")
    for phase_key, phase in m.get("automotive_implementation_phases", {}).items():
        lines.append(f"【{phase['name']}】")
        lines.append(f"  {phase.get('vave_role', phase.get('description',''))}")

    lines.append("\n## 八步法VE工作程序（麦尔斯体系）")
    for step in m.get("eight_step_ve_job_plan", {}).get("steps", []):
        lines.append(f"  步骤{step['step']} {step['name']}：{step.get('inputs','')} → 输出：{step.get('outputs','')}")

    lines.append("\n## 对象选择原则（4P模型）")
    for p_key, p_desc in m.get("object_selection_criteria", {}).get("four_p_model", {}).items():
        lines.append(f"  {p_key}：{p_desc}")
    lines.append(f"  10/80法则：{m.get('object_selection_criteria',{}).get('ten_eighty_rule','')}")

    lines.append("\n## 成本分解结构（汽车零部件）")
    for cost_type, desc in m.get("automotive_cost_breakdown", {}).items():
        lines.append(f"  {cost_type}：{desc}")

    # 品类专属策略（含映射）
    part_type_strategies = m.get("common_vave_strategies_by_part_type", {})
    cat_map = {
        "塑料件": "plastic_parts",
        "冲压件": "stamping_parts",
        "压铸件": "casting_parts",
        "机加件": "machined_parts",
        "电子件": "electronics",
    }
    if category and category in cat_map:
        key = cat_map[category]
        strat_data = part_type_strategies.get(key, {})
        if strat_data:
            lines.append(f"\n## {category}类零件常见VAVE策略")
            lines.append(f"  典型降幅：{strat_data.get('typical_savings_range','')}")
            lines.append("  常见策略：")
            for s in strat_data.get("typical_strategies", []):
                lines.append(f"    - {s}")
            lines.append("  关键风险：")
            for r in strat_data.get("key_risks", []):
                lines.append(f"    - {r}")
    else:
        # 列出所有品类
        lines.append("\n## 各品类典型VAVE策略（降幅范围）")
        for ptype, pdata in part_type_strategies.items():
            lines.append(f"  {ptype}：{pdata.get('typical_savings_range','')}")

    lines.append("\n## BCG降本四抓手")
    for lev in m.get("bcg_cost_reduction_four_levers", {}).get("levers", []):
        examples_str = "、".join(lev.get("examples", [])[:3])
        lines.append(f"  {lev['lever']}.{lev['name']}：{examples_str}")

    lines.append("\n## FAST功能分析方法")
    lines.append(m.get("fast_functional_analysis", {}).get("description", ""))
    for step in m.get("fast_functional_analysis", {}).get("application_steps", []):
        lines.append(f"  - {step}")

    lines.append("\n## 常见陷阱与避免方法")
    for pit in m.get("common_pitfalls", {}).values():
        lines.append(f"  ⚠️ {pit.get('name','')}: {pit.get('consequence','')} → 解决：{pit.get('solution','')}")

    lines.append("\n## 实用总结（金规）")
    for rule in m.get("practical_summary", {}).values():
        if rule:
            lines.append(f"  ✓ {rule}")

    return "\n".join(lines)


def get_strategy_by_category(category: str) -> list:
    """
    按零件类别返回专属的VAVE策略清单。
    返回格式：[{'strategy': str, 'direction': str, 'savings': str, 'risk': str}]
    """
    kb = load_knowledge_base()
    m = kb.get("vave_methodology", {})
    part_types = m.get("common_vave_strategies_by_part_type", {})

    # 类别映射
    category_map = {
        "塑料件": "plastic_parts",
        "冲压件": "stamping_parts",
        "压铸件": "casting_parts",
        "机加件": "machined_parts",
        "电子件": "electronics",
    }

    key = category_map.get(category, "")
    data = part_types.get(key, {}) if key else {}

    results = []
    for i, strat in enumerate(data.get("typical_strategies", []), 1):
        results.append({
            "rank": i,
            "strategy": strat,
            "expected_savings_range": data.get("typical_savings_range", "5-20%"),
            "key_risks": data.get("key_risks", []),
        })
    return results


# ========== 命令行单次查询 ==========
def main():
    if len(sys.argv) > 1:
        # 单次查询模式
        query = " ".join(sys.argv[1:])
        result = generate_suggestions(part_name=query, material="", category="通用")
        print(format_output(result))
    else:
        # 交互模式
        interactive_mode()

if __name__ == "__main__":
    main()
