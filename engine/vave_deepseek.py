"""
汽车VAVE建议生成器 - DeepSeek AI 增强层
v1.0

当用户启用"AI增强"模式时：
1. 读取知识库中的匹配案例
2. 将案例上下文 + 用户零件信息 发送给 DeepSeek
3. DeepSeek 生成针对该零件的个性化、定制化VAVE建议

API Key: 从环境变量 DEEPSEEK_API_KEY 读取（不存在代码中）
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional

# DeepSeek API Key（从环境变量读取，不硬编码）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ========== DeepSeek 调用 ==========
def call_deepseek(system_prompt: str, user_prompt: str,
                  model: str = "deepseek-chat",
                  temperature: float = 0.3,
                  max_tokens: int = 2000,
                  api_key: str = "") -> str:
    """
    调用 DeepSeek API 生成内容
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请先安装 openai 包：pip install openai")

    key = api_key or DEEPSEEK_API_KEY
    if not key:
        raise ValueError("未设置 DeepSeek API Key")

    client = OpenAI(
        api_key=key,
        base_url=DEEPSEEK_BASE_URL,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content


# ========== DeepSeek VAVE 建议生成 ==========
def generate_ai_suggestions(
    part_name: str,
    material: str,
    category: str,
    cost_per_unit: Optional[float] = None,
    weight_kg: Optional[float] = None,
    additional_info: str = "",
    matched_cases: list = None,
    api_key: str = "",
    methodology_context: str = "",
) -> dict:
    """
    调用 DeepSeek，为用户的具体零件生成个性化 VAVE 建议
    
    Args:
        part_name: 零件名称
        material: 材料/工艺
        category: 零件类别
        cost_per_unit: 当前单件成本（元/件）
        weight_kg: 当前重量（kg）
        additional_info: 补充信息
        matched_cases: 从知识库匹配到的案例（用于上下文参考）
        api_key: 可选的 API Key（优先使用）
    
    Returns:
        dict: {
            "success": bool,
            "suggestions": list[dict],   # 解析后的建议
            "raw_response": str,          # 原始AI输出（调试用）
            "error": str,                 # 错误信息
            "tokens_used": int,           # 消耗tokens
            "cost_estimate": float,       # 预估费用
        }
    """

    _api_key = api_key or DEEPSEEK_API_KEY
    if not _api_key:
        return {
            "success": False,
            "error": "未提供 DeepSeek API Key",
            "suggestions": [],
            "raw_response": "",
            "tokens_used": 0,
            "cost_estimate": 0.0,
        }

    # 构建系统提示词
    methodology_section = (
        f"\n\n## 汽车行业VAVE方法论参考\n{methodology_context}"
        if methodology_context
        else ""
    )

    system_prompt = """你是一位资深汽车行业成本工程专家，精通VAVE（Value Analysis Value Engineering，价值分析与价值工程）。

你的职责：根据用户提供的零件信息，结合汽车行业最佳实践和VAVE方法论（V=F/C公式、八步法、FAST功能分析等），生成针对该零件的个性化、可落地降本建议。
""" + methodology_section + """

## 输出格式要求
请严格按以下JSON格式输出（不要输出其他内容）：

{
  "summary": "2-3句话总结这个零件的降本重点和最大机会",
  "suggestions": [
    {
      "rank": 1,
      "strategy_type": "策略类型（材料替换/工艺优化/结构优化/设计标准化/供应商优化/功能集成）",
      "direction": "具体降本方向，一句话说清楚改什么",
      "expected_savings_pct": "预期降幅，如'12%~18%'（数字要具体，不要模糊）",
      "mechanism": "降本原理，2-3句话解释为什么能降本",
      "implementation_priority": "实施优先级：P0(立即做)/P1(近期做)/P2(条件具备时做）",
      "quality_risk": "质量风险，1-2句话",
      "key_consideration": "实施关键注意事项，1-2句话",
      "estimated_effort": "实施难度：低/中/高"
    }
  ],
  "warnings": ["需要特别关注的1-2个风险点"],
  "quick_wins": ["可以快速验证的1-2个小动作"]
}

## 注意事项
- 建议必须具体、可操作，不能是空话套话
- 降幅要有数字范围，不能只写"可以降本"
- 结合汽车行业特点，考虑安全法规、碰撞安全、可靠性要求
- 如果某些策略不适合该零件，直接说"不建议"，不要硬凑
- 费用估算基于 DeepSeek-V3 模型，¥1/百万tokens，极低成本
"""

    # 构建用户提示词
    context_parts = []

    # 零件基本信息
    context_parts.append("【零件信息】")
    context_parts.append(f"零件名称：{part_name}")
    context_parts.append(f"材料/工艺：{material if material else '未提供'}")
    context_parts.append(f"零件类别：{category}")
    if cost_per_unit:
        context_parts.append(f"当前单件成本：{cost_per_unit}元/件")
    if weight_kg:
        context_parts.append(f"当前重量：{weight_kg}kg")
    if additional_info:
        context_parts.append(f"补充信息：{additional_info}")

    # 知识库匹配案例
    if matched_cases:
        context_parts.append("\n【知识库匹配案例参考】")
        context_parts.append("以下是该零件类型在行业中的典型VAVE案例，可作为参考（但不要照搬）：")
        for case in matched_cases[:3]:  # 最多3个案例
            context_parts.append(f"\n- 零件：{case.get('part_name','')}")
            context_parts.append(f"  材料：{case.get('material','')}")
            context_parts.append(f"  当前成本：{case.get('typical_cost_per_unit','未知')}元/件")
            strategies = case.get('vave_strategies', [])
            for st in strategies[:2]:  # 每案例最多2个策略
                context_parts.append(f"  策略：{st.get('strategy','')} → {st.get('direction','')}")
                context_parts.append(f"  降幅：{st.get('expected_savings_pct','')}%")
                if st.get('case_ref'):
                    context_parts.append(f"  案例：{st.get('case_ref','')}")
    else:
        context_parts.append("\n【知识库匹配案例】无直接匹配案例，请基于汽车行业通用经验给出建议。")

    # 附加行业背景
    context_parts.append("""
\n【汽车行业VAVE背景】
- 汽车零部件降本通常从：材料替换、工艺简化、结构优化、设计标准化、供应商竞争、功能集成六个方向切入
- 近年新能源车对轻量化要求高，但纯降本项目仍以材料替换和结构优化为主
- 商用车侧重耐久性，乘用车侧重成本和外观
- 国产化/二供开发是快速降本的重要手段
""")

    user_prompt = "\n".join(context_parts)

    # 调用 DeepSeek
    try:
        result_text = call_deepseek(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="deepseek-chat",
            temperature=0.3,
            max_tokens=2000,
            api_key=_api_key,
        )

        # 尝试解析 JSON
        suggestions = []
        raw_response = result_text

        # 提取JSON（处理markdown代码块）
        json_text = result_text.strip()
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            json_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        json_text = json_text.strip("`").strip()

        parsed = json.loads(json_text)
        suggestions = parsed.get("suggestions", [])

        return {
            "success": True,
            "suggestions": suggestions,
            "summary": parsed.get("summary", ""),
            "warnings": parsed.get("warnings", []),
            "quick_wins": parsed.get("quick_wins", []),
            "raw_response": raw_response,
            "tokens_used": 0,  # 需要从响应头获取，这里简化
            "cost_estimate": 0.0,
        }

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"AI输出格式解析失败：{str(e)}\n\n原始输出：\n{result_text[:500]}",
            "suggestions": [],
            "raw_response": result_text,
            "tokens_used": 0,
            "cost_estimate": 0.0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"DeepSeek API 调用失败：{str(e)}",
            "suggestions": [],
            "raw_response": "",
            "tokens_used": 0,
            "cost_estimate": 0.0,
        }


# ========== 方法论完整思考链（逐方法跑完） ==========
def generate_methodology_analysis(
    part_name: str,
    material: str,
    category: str,
    methods: list,
    cost_per_unit: Optional[float] = None,
    weight_kg: Optional[float] = None,
    additional_info: str = "",
    bom: list = None,
    matched_cases: list = None,
    api_key: str = "",
) -> dict:
    """
    让 DeepSeek 对知识库中的“全部方法论方法”逐条评估，产出完整思考过程：
    零件功能理解、BOM 解读、每个方法是否适用及原因、适用方法对应的具体建议。

    Returns:
        dict: {
            "success", "function_understanding", "bom_interpretation",
            "method_decisions": [{id,type,lever,applicable,reason,suggestion?}],
            "summary", "raw_response", "error"
        }
    """
    _api_key = api_key or DEEPSEEK_API_KEY
    if not _api_key:
        return {"success": False, "error": "未提供 DeepSeek API Key",
                "function_understanding": "", "bom_interpretation": "",
                "method_decisions": [], "summary": "", "raw_response": ""}

    # 方法清单（精简字段，避免超出上下文）
    methods_brief = "\n".join(
        f"{m.get('id','')} | {m.get('type','')} | 抓手:{m.get('lever','')} | "
        f"适用零件:{','.join(m.get('applicable_parts',[]))} | 说明:{m.get('description','')}"
        for m in methods
    )

    system_prompt = """你是一位资深汽车行业成本工程专家，精通 VAVE（价值分析与价值工程）。
你的任务：对“全部”VAVE方法论方法逐条评估，输出完整、可追溯的思考过程，而不是只给结论。
请严格按以下JSON格式输出（不要输出其他内容）：
{
  "function_understanding": "用2-3句话阐述该零件的功能定位、关键性能要求、成本驱动因素",
  "bom_interpretation": "若有BOM则解读材质/工艺/成本结构分布；若无BOM填空字符串",
  "method_decisions": [
    {
      "id": "方法ID（如M01）",
      "type": "方法名",
      "applicable": true或false,
      "reason": "判断依据：为什么适用/不适用（结合零件功能、材料、工艺、法规、BOM）；若适用请说明可怎么降本",
      "suggestion": {"direction":"具体降本方向","expected_savings_pct":"如'8%~15%'"} 或 null
    }
  ],
  "summary": "2-3句话总结：哪些方法被采用、哪些值得后续评估、整体降本机会判断"
}

注意：
- method_decisions 必须覆盖传入的“每一个”方法，不得遗漏
- applicable=true 时必须给出 suggestion（具体可落地方向+降幅区间）
- applicable=false 时 reason 必须说明不适用原因（法规/性能/触发条件/收益不足等）
- 结合汽车行业实际：安全件、法规件谨慎；新能源车重轻量；商务/产业链方法对采购件普遍适用
"""

    ctx = []
    ctx.append("【零件信息】")
    ctx.append(f"零件名称：{part_name}")
    ctx.append(f"材料/工艺：{material or '未提供'}")
    ctx.append(f"零件类别：{category}")
    if cost_per_unit: ctx.append(f"当前单件成本：{cost_per_unit}元/件")
    if weight_kg: ctx.append(f"当前重量：{weight_kg}kg")
    if additional_info: ctx.append(f"补充信息：{additional_info}")
    if bom:
        ctx.append(f"\n【BOM（共{len(bom)}项）】")
        for b in bom[:20]:
            ctx.append(f"  - {b.get('name','')} | {b.get('material','')} | {b.get('process','')} | {b.get('qty','')}件")
    else:
        ctx.append("\n【BOM】无（未导入图纸）")
    if matched_cases:
        ctx.append("\n【知识库匹配案例】")
        for c in matched_cases[:3]:
            ctx.append(f"  - {c.get('part_name','')}：{';'.join(s.get('direction','') for s in c.get('vave_strategies',[])[:2])}")
    ctx.append("\n【需要逐条评估的全部方法论方法】")
    ctx.append(methods_brief)
    user_prompt = "\n".join(ctx)

    try:
        result_text = call_deepseek(system_prompt=system_prompt, user_prompt=user_prompt,
                                    model="deepseek-chat", temperature=0.3, max_tokens=3000,
                                    api_key=_api_key)
        json_text = result_text.strip()
        if json_text.startswith("```"):
            ls = json_text.split("\n")
            json_text = "\n".join(ls[1:-1] if ls[-1].strip() == "```" else ls[1:])
        json_text = json_text.strip("`").strip()
        parsed = json.loads(json_text)
        decisions = parsed.get("method_decisions", [])
        return {
            "success": True,
            "function_understanding": parsed.get("function_understanding", ""),
            "bom_interpretation": parsed.get("bom_interpretation", ""),
            "method_decisions": decisions,
            "summary": parsed.get("summary", ""),
            "raw_response": result_text,
            "error": "",
        }
    except Exception as e:
        return {"success": False, "error": f"方法论分析失败：{str(e)}\n原始输出前500字：\n{result_text[:500]}",
                "function_understanding": "", "bom_interpretation": "",
                "method_decisions": [], "summary": "", "raw_response": result_text}


# ========== BOM 智能识别（图纸→AI） ==========
def enrich_bom_with_ai(
    bom: list,
    raw_text: str = "",
    metadata: dict = None,
    file_format: str = "",
    api_key: str = "",
) -> dict:
    """
    将解析出的BOM + 图纸线索 发送给 DeepSeek，
    由AI推断每个子零件的材质、工艺、降本方向

    Args:
        bom: parse_drawing() 返回的 bom 列表
        raw_text: 图纸提取的原始文字
        metadata: 格式特定元数据
        file_format: STEP/DXF/STL/PDF
        api_key: DeepSeek API Key

    Returns:
        dict: {
            "success": bool,
            "enriched_bom": list[dict],  #  enrich后的BOM
            "summary": str,              # 总成降本总结
            "vave_suggestions": list,   # 总成级VAVE建议
            "error": str,
        }
    """
    _api_key = api_key or DEEPSEEK_API_KEY
    if not _api_key:
        return {"success": False, "error": "未提供 DeepSeek API Key",
                "enriched_bom": [], "summary": "", "vave_suggestions": []}

    if not bom:
        return {"success": False, "error": "BOM为空，无法识别",
                "enriched_bom": [], "summary": "", "vave_suggestions": []}

    system_prompt = """你是一位资深汽车成本工程师，精通VAVE（价值分析与价值工程）和制造工艺。

用户上传了一份汽车零件/总成图纸，系统已从中提取出装配BOM（零件清单）和部分线索。
你的任务：基于BOM名称、数量、材质/工艺线索，推断每个子零件的真实材质、制造工艺，并给出降本方向。

## 输出格式（严格JSON，不要其他内容）
{
  "summary": "2-3句话总结这个总成/零件的降本重点和最大机会",
  "enriched_bom": [
    {
      "name": "零件名（与输入一致）",
      "inferred_material": "推断材质，如'Q235冷轧钢'/'PP+EPDM-TD20'/'A380铝合金'",
      "inferred_process": "推断工艺，如'冲压'/'注塑'/'压铸'/'机加'/'焊接'/'装配'",
      "cost_level": "成本等级：高/中/低",
      "vave_direction": "针对该零件的1条核心降本方向",
      "confidence": "推断置信度：高/中/低"
    }
  ],
  "vave_suggestions": [
    {
      "title": "总成级VAVE建议标题",
      "detail": "具体做法，2-3句话",
      "expected_savings_pct": "预期降幅如'8%~15%'",
      "priority": "P0/P1/P2",
      "scope": "适用范围说明"
    }
  ]
}

## 规则
- 材质/工艺推断要基于零件名称中的关键词（如'支架'→冲压钢，'壳体'→压铸铝，'饰板'→注塑塑料）
- 汽车行业标准：结构件多用钢/铝，外观件多用塑料，密封件用橡胶
- 降本方向从：材料替换、工艺优化、结构优化、设计标准化、供应商优化、功能集成 中选
- 如果信息不足，confidence标'低'，并给出合理推测
- 降幅必须有数字范围
"""

    # 构建用户提示词
    user_parts = []
    user_parts.append(f"【图纸格式】{file_format}")
    user_parts.append(f"【提取到的BOM（{len(bom)}项）】")
    for i, item in enumerate(bom[:40], 1):
        line = f"{i}. {item.get('name','未知')}"
        if item.get('qty') and item['qty'] != 1:
            line += f" ×{item['qty']}"
        hints = []
        if item.get('material_hint'):
            hints.append(f"材质线索:{item['material_hint']}")
        if item.get('process_hint'):
            hints.append(f"工艺线索:{item['process_hint']}")
        if item.get('volume_mm3'):
            hints.append(f"体积:{item['volume_mm3']}mm³")
        if hints:
            line += " (" + "; ".join(hints) + ")"
        user_parts.append(line)

    if raw_text:
        user_parts.append(f"\n【图纸文字线索（前1500字）】\n{raw_text[:1500]}")

    user_parts.append("\n请基于以上信息，识别每个子零件的材质、工艺，并给出总成级VAVE降本建议。")
    user_prompt = "\n".join(user_parts)

    try:
        result_text = call_deepseek(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="deepseek-chat",
            temperature=0.2,
            max_tokens=2500,
            api_key=_api_key,
        )

        # 解析JSON
        json_text = result_text.strip()
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            json_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        json_text = json_text.strip("`").strip()
        parsed = json.loads(json_text)

        return {
            "success": True,
            "enriched_bom": parsed.get("enriched_bom", []),
            "summary": parsed.get("summary", ""),
            "vave_suggestions": parsed.get("vave_suggestions", []),
            "error": "",
        }
    except json.JSONDecodeError as e:
        return {"success": False,
                "error": f"AI输出解析失败：{e}\n\n原始：{result_text[:400]}",
                "enriched_bom": [], "summary": "", "vave_suggestions": []}
    except Exception as e:
        return {"success": False, "error": f"调用失败：{e}",
                "enriched_bom": [], "summary": "", "vave_suggestions": []}


# ========== 环境变量设置 & 验证 ==========
def set_api_key(api_key: str):
    """设置 DeepSeek API Key（写入环境变量，仅当前进程有效）"""
    os.environ["DEEPSEEK_API_KEY"] = api_key.strip()

def check_api_key(api_key: str = "") -> dict:
    """验证 API Key 是否有效"""
    import urllib.request
    import urllib.error

    key = api_key or DEEPSEEK_API_KEY
    if not key:
        return {"valid": False, "error": "未提供 API Key"}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "say 'OK' in one word"}],
            max_tokens=5,
        )
        content = response.choices[0].message.content
        return {"valid": True, "content": content, "model": "deepseek-chat"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


if __name__ == "__main__":
    # 简单测试
    import sys
    if len(sys.argv) < 2:
        print("用法: python vave_deepseek.py <API_KEY>")
        print("或设置环境变量 DEEPSEEK_API_KEY 后运行")
        sys.exit(1)

    api_key = sys.argv[1]
    set_api_key(api_key)

    # 验证 Key
    print("正在验证 API Key...")
    check = check_api_key(api_key)
    if check["valid"]:
        print(f"✅ API Key 有效！模型：{check['model']}")
    else:
        print(f"❌ API Key 无效：{check['error']}")
        sys.exit(1)

    # 测试生成
    print("\n正在生成 VAVE 建议（零件：仪表台本体）...")
    result = generate_ai_suggestions(
        part_name="仪表台本体",
        material="PP+EPDM-TD20 注塑件",
        category="塑料件",
        cost_per_unit=91.0,
    )

    if result["success"]:
        print(f"\n✅ 生成成功！")
        print(f"摘要：{result.get('summary','')}")
        print(f"\n共 {len(result['suggestions'])} 条建议：")
        for s in result["suggestions"]:
            print(f"\n  [{s['rank']}] {s['strategy_type']} | 降幅: {s['expected_savings_pct']} | 优先级: {s['implementation_priority']}")
            print(f"      方向: {s['direction']}")
            print(f"      逻辑: {s['mechanism']}")
    else:
        print(f"\n❌ 生成失败：{result['error']}")
