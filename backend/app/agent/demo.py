"""演示模式（demo）的确定性响应。

未配置 LLM API Key 时自动启用：不调用任何大模型，但 Agent 的完整流程
（任务规划 → 工具调用 → PRD 撰写 → 质量自查 → 记忆更新）全部真实执行，
工具调用的也是真实的内置知识库。配置 API Key 后自动切换为真实 LLM。

演示内容刻意保持通用，避免让用户误以为是真实 AI 分析结果。
"""
import re

from .tools import find_domain

_MODIFY_HINTS = ("改成", "修改", "增加", "新增", "去掉", "删除", "调整", "换成",
                 "不要", "补充", "加上", "改为", "更新", "替换")


def _guess_product_name(user_input: str) -> str:
    raw = re.split(r"[，。！？；、,.!?;:：\n]", user_input.strip())[0].strip()
    raw = re.sub(r"^(我想|我要|帮我|做一个?|开发一个?|打造一个?|设计一个?|想做个?)\s*", "", raw)
    return raw[:20] or "未命名产品"


def _detect_intent(user_input: str, has_prd: bool) -> str:
    if not has_prd:
        return "create"
    if any(h in user_input for h in _MODIFY_HINTS) or user_input.startswith("把"):
        return "modify"
    return "question"


def planner(state: dict) -> dict:
    """演示模式规划器：意图识别 + 任务计划 + 需求分析。"""
    user_input = state["user_input"]
    has_prd = bool(state.get("prd"))
    intent = _detect_intent(user_input, has_prd)
    name = _guess_product_name(user_input)

    if intent == "create":
        plan = [
            {"title": "需求分析", "detail": "拆解产品定位、目标与用户场景"},
            {"title": "竞品调研", "detail": "调用工具搜索竞品与行业知识"},
            {"title": "撰写 PRD", "detail": "生成结构化 PRD 文档"},
            {"title": "质量自查", "detail": "按评审清单检查 PRD 完整性"},
        ]
    elif intent == "modify":
        plan = [
            {"title": "定位修改点", "detail": "对照现有 PRD 明确修改范围"},
            {"title": "更新 PRD", "detail": "应用修改并记录变更日志"},
            {"title": "一致性自查", "detail": "检查修改后 PRD 的一致性与完整性"},
        ]
    else:
        plan = [
            {"title": "理解问题", "detail": "结合 PRD 与产品记忆理解疑问"},
            {"title": "生成解答", "detail": "给出基于当前 PRD 的解答"},
        ]

    analysis = {
        "product_name": name if intent == "create" else None,
        "summary": user_input,
        "goals": ["明确产品核心价值与目标用户", "在 3 个月内验证核心假设并上线 MVP"],
        "target_users": ["待进一步明确（演示模式建议配置 API Key 获得真实分析）"],
        "scenarios": ["用户首次使用核心流程", "用户留存与复访"],
        "constraints": ["演示模式未调用真实 LLM，分析结论为模板内容"],
        "open_questions": ["目标用户的核心画像？", "商业模式与变现路径？"],
    }
    needs_research = (intent == "create") or ("竞品" in user_input)

    return {
        "intent": intent,
        "plan": [dict(s, status="pending") for s in plan],
        "analysis": analysis,
        "needs_research": needs_research,
        "messages": [],
        "retry_count": 0,
        # 每轮重置：检查点会保留上一轮状态，避免旧 PRD/反馈混入本轮
        "prd_new": None,
        "prd_changes": [],
        "review_feedback": "",
    }


def research_tool_calls(state: dict) -> list[dict]:
    """演示模式：直接构造对真实工具的调用（ToolNode 执行）。"""
    user_input = state["user_input"]
    calls = [{
        "name": "search_competitors",
        "args": {"keyword": user_input[:50], "domain": ""},
        "id": "demo_call_1",
        "type": "tool_call",
    }]
    domain = find_domain(user_input)
    if domain:
        calls.append({
            "name": "query_knowledge_base",
            "args": {"topic": f"{domain['name']} 行业知识"},
            "id": "demo_call_2",
            "type": "tool_call",
        })
    return calls


def research_summary(state: dict) -> dict:
    """演示模式：从内置知识库生成调研总结。"""
    domain = find_domain(state["user_input"])
    if not domain:
        return {
            "summary": "（演示模式）内置知识库未匹配到相关行业，建议配置 API Key 或使用更明确的行业关键词。",
            "competitors": [],
            "key_insights": ["内置知识库覆盖：在线教育、健康管理、企业协作、跨境电商、内容社区、本地生活、AI工具、游戏等领域"],
        }
    competitors = [
        {
            "name": c["name"],
            "positioning": c["positioning"],
            "strengths": c["strengths"],
            "weaknesses": c["weaknesses"],
            "takeaway": "研究竞品差异化定位，寻找尚未被满足的细分需求",
        }
        for c in domain["competitors"][:3]
    ]
    return {
        "summary": f"（演示模式）基于内置知识库完成「{domain['name']}」领域调研：该领域核心痛点为 {domain['pain_points'][0]}；主流变现方式为 {domain['business_models'][0]}。",
        "competitors": competitors,
        "key_insights": [f"行业痛点：{p}" for p in domain["pain_points"][:3]]
                       + [f"趋势：{t}" for t in domain["trends"][:2]],
    }


def _build_prd(state: dict, research: dict, name: str) -> dict:
    """构造演示 PRD（结构完整，内容为通用模板）。"""
    competitors = research.get("competitors", [])
    return {
        "title": name,
        "overview": {
            "product_name": name,
            "elevator_pitch": f"{name}：{state['user_input'][:60]}",
            "background": state["user_input"],
            "goals": ["上线 MVP 验证核心价值", "3 个月内实现 1 万注册用户", "核心流程转化率 > 20%"],
            "non_goals": ["不做硬件", "不做社交平台级功能", "一期不做多语言"],
        },
        "target_users": [
            {
                "segment": "核心用户",
                "description": "（演示模板）目标用户画像待调研明确，配置 API Key 后可获得真实分析",
                "needs": ["高效完成核心任务", "低成本上手"],
                "pain_points": ["现有方案繁琐", "缺乏个性化"],
            }
        ],
        "user_stories": [
            {"as_a": "新用户", "want": "在 3 分钟内完成首次核心流程", "so_that": "快速感知产品价值", "priority": "P0"},
            {"as_a": "用户", "want": "查看个人数据与进度", "so_that": "持续获得反馈与激励", "priority": "P1"},
            {"as_a": "运营", "want": "查看关键指标看板", "so_that": "及时调整运营策略", "priority": "P2"},
        ],
        "features": [
            {
                "name": "核心主流程",
                "description": "（演示模板）产品核心价值流程",
                "priority": "P0",
                "acceptance_criteria": ["用户可在 3 步内完成主流程", "流程失败有明确引导"],
            },
            {
                "name": "账号体系",
                "description": "注册登录与基础资料",
                "priority": "P0",
                "acceptance_criteria": ["支持手机号+验证码登录", "支持第三方快捷登录"],
            },
            {
                "name": "数据看板",
                "description": "个人数据与进度可视化",
                "priority": "P1",
                "acceptance_criteria": ["核心数据实时更新", "支持按周/月查看"],
            },
        ],
        "competitor_analysis": competitors,
        "metrics": [
            {"name": "激活率", "definition": "完成核心流程的用户 / 注册用户", "target": "> 40%"},
            {"name": "次周留存率", "definition": "注册后第 2 周仍活跃的用户占比", "target": "> 30%"},
            {"name": "NPS", "definition": "净推荐值", "target": "> 30"},
        ],
        "milestones": [
            {"phase": "MVP 开发", "duration": "4 周", "deliverables": ["核心主流程", "账号体系"]},
            {"phase": "内测", "duration": "2 周", "deliverables": ["种子用户反馈报告", "关键指标基线"]},
            {"phase": "正式上线", "duration": "4 周", "deliverables": ["公开版本", "数据看板", "运营后台"]},
        ],
        "risks": [
            {"risk": "需求假设未经验证", "level": "高", "mitigation": "MVP 阶段小流量验证，预留调整空间"},
            {"risk": "获客成本过高", "level": "中", "mitigation": "优先内容/口碑获客，控制付费投放"},
            {"risk": "技术实现复杂度超预期", "level": "中", "mitigation": "一期砍掉非核心功能，聚焦主流程"},
        ],
        "changelog": [{"note": "初始版本（演示模式生成）"}],
        "open_questions": ["目标用户画像需要进一步明确", "商业模式与定价策略待定"],
    }


def draft(state: dict) -> dict:
    """演示模式 PRD 撰写。create 生成模板；modify 在现有 PRD 上追加变更记录。"""
    intent = state["intent"]
    if intent == "create":
        research = state.get("research_result") or {}
        name = state.get("analysis", {}).get("product_name") or _guess_product_name(state["user_input"])
        return {"prd_new": _build_prd(state, research, name), "prd_changes": []}

    # modify：保留原 PRD，追加变更日志与待确认问题
    prd = dict(state.get("prd") or {})
    request = state["user_input"]
    changelog = list(prd.get("changelog") or [])
    changelog.append({"note": f"（演示模式）按用户要求：{request[:60]}"})
    prd["changelog"] = changelog
    open_questions = list(prd.get("open_questions") or [])
    open_questions.append(f"待落实修改：{request[:60]}")
    prd["open_questions"] = open_questions[-5:]
    return {"prd_new": prd, "prd_changes": [f"（演示模式）已记录修改需求：{request[:60]}"]}


def review(state: dict) -> dict:
    return {
        "passed": True,
        "score": 8,
        "issues": [],
        "suggestions": ["配置真实 LLM API Key（如 DeepSeek）可解锁完整 AI 分析能力（当前为演示模式）"],
    }


def memory(state: dict) -> dict:
    user_input = state["user_input"]
    updates = []
    if state["intent"] == "create":
        updates.append({
            "key": "产品定位",
            "value": _guess_product_name(user_input)[:30],
            "category": "定位",
            "note": "新项目核心定位（演示模式）",
        })
    else:
        updates.append({
            "key": "最近修改",
            "value": user_input[:40],
            "category": "其他",
            "note": "最近一次修改要求（演示模式）",
        })
    return {"memory_updates": updates}


def reply(state: dict) -> str:
    intent = state["intent"]
    prd = state.get("prd_new") or state.get("prd") or {}
    title = prd.get("title", "未命名产品")
    plan_titles = "、".join(s["title"] for s in state.get("plan", []))
    if intent == "create":
        return (
            f"✅ 已完成「{title}」的 PRD v1 初稿（演示模式）。\n"
            f"本轮执行：{plan_titles}。PRD 包含目标用户、用户故事、功能清单、"
            f"竞品分析、数据指标与里程碑，可在右侧面板查看完整文档。\n"
            f"下一步建议：配置 API Key 获得真实 AI 分析；或直接告诉我修改意见，"
            f'例如"把目标用户改成大学生"、"增加会员订阅模式"。'
        )
    if intent == "modify":
        changes = "；".join(state.get("prd_changes", []))
        return (
            f"✅ 已按你的要求更新「{title}」的 PRD（演示模式）。\n"
            f"本次变更：{changes}。变更已记入 PRD 变更日志，产品记忆已同步更新。\n"
            f"下一步建议：继续提出修改意见，或让我\"补充数据指标体系\"。"
        )
    return (
        f"（演示模式）关于你的问题：当前 PRD「{title}」已有相关章节，"
        f"建议配置 API Key 以获得基于 PRD 内容的智能解答。"
    )
