"""LangGraph 各节点实现。

每个节点是一个纯函数：读 state → 返回 state 更新字典。
演示模式（demo_mode=True）走确定性分支，不调用 LLM。
"""
import copy
import json

import json_repair
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from . import demo
from .prd_schema import (
    DraftOutput,
    DraftPatchOutput,
    MemoryExtract,
    PRDDocument,
    PlannerOutput,
    ReplyOut,
    ResearchSummary,
    ReviewOutput,
)
from .prompts import (
    DRAFT_SYSTEM,
    DRAFT_USER,
    FINALIZE_SYSTEM,
    FINALIZE_USER,
    MEMORY_SYSTEM,
    MEMORY_USER,
    PLANNER_SYSTEM,
    PLANNER_USER,
    RESEARCH_SUMMARY_SYSTEM,
    RESEARCH_SUMMARY_USER,
    RESEARCH_SYSTEM,
    RESEARCH_USER,
    REVIEW_SYSTEM,
    REVIEW_USER,
)
from .tools import TOOLS

MAX_HISTORY = 8
# 现有 PRD 要完整传给模型，截断会导致模型看不到后半部分章节、修改结果缺字段
MAX_PRD_CHARS = 30_000


def _fmt_history(history: list[dict]) -> str:
    if not history:
        return "（暂无）"
    lines = []
    for m in history[-MAX_HISTORY * 2:]:
        role = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{role}：{str(m.get('content', ''))[:200]}")
    return "\n".join(lines)


def _fmt_memory(facts: list[dict]) -> str:
    if not facts:
        return "（暂无）"
    return "\n".join(f"- [{f.get('category', '其他')}] {f.get('key')}：{f.get('value')}" for f in facts)


# 模型偶尔把数组写成 {"items": [...]} 或带 __comment 的对象，这里统一还原
_LIST_SHAPE_FIELDS = {
    "target_users", "user_stories", "features", "competitor_analysis", "metrics",
    "milestones", "risks", "changelog", "open_questions", "plan", "issues",
    "suggestions", "changes", "updates", "competitors", "key_insights", "goals",
    "non_goals", "needs", "pain_points", "strengths", "weaknesses", "deliverables",
    "acceptance_criteria", "queries",
}


def _coerce_list_shapes(obj):
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if key in _LIST_SHAPE_FIELDS and isinstance(value, dict):
                items = value.get("items")
                if isinstance(items, list):
                    obj[key] = value = items
            _coerce_list_shapes(value)
    elif isinstance(obj, list):
        for item in obj:
            _coerce_list_shapes(item)
    return obj


def _raw_tool_args(raw) -> str | None:
    """从原始 AIMessage 中取出工具参数的原始 JSON 字符串。"""
    calls = (getattr(raw, "additional_kwargs", {}) or {}).get("tool_calls") or []
    for call in calls:
        args = (call.get("function") or {}).get("arguments")
        if args:
            return args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    for call in getattr(raw, "invalid_tool_calls", []) or []:
        args = call.get("args")
        if args:
            return args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    return None


def _repair_structured(schema, raw):
    """用 json-repair 修复非法 JSON（多余内容/引号未转义等），再交给 Pydantic 校验。"""
    args = _raw_tool_args(raw)
    if not args:
        return None
    try:
        data = json_repair.loads(args)
    except Exception:
        return None
    if isinstance(data, list):  # 模型输出多个 JSON 对象时取第一个
        data = next((x for x in data if isinstance(x, dict)), None)
    if not isinstance(data, dict):
        return None
    try:
        return schema.model_validate(_coerce_list_shapes(data))
    except ValidationError:
        return None


def _invoke_structured(structured, schema, messages: list, retries: int = 2):
    """调用结构化 LLM：先尝试修复非法 JSON，修不好再带纠正提示重试。"""
    msgs = list(messages)
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = structured.invoke(msgs)
        except (OutputParserException, ValidationError) as e:
            last_exc = e
        else:
            if not (isinstance(result, dict) and "raw" in result):
                return result
            if result.get("parsed") is not None:
                return result["parsed"]
            repaired = _repair_structured(schema, result.get("raw"))
            if repaired is not None:
                print(f"[上策] 已自动修复 {schema.__name__} 的 JSON 输出")
                return repaired
            last_exc = result.get("parsing_error") or RuntimeError("结构化输出解析失败")
        if attempt >= retries:
            break
        detail = str(last_exc)[-300:]
        msgs = msgs + [HumanMessage(
            f"上一次输出无法解析为合法 JSON：{detail}。请重新输出完整结果，要求："
            "1) 只输出一个合法 JSON 对象，不要输出 JSON 以外的任何内容；"
            "2) 字符串里的英文双引号必须转义为 \\\" 或改用中文引号「」；"
            "3) 所有必填字段都不能缺失，数组字段必须是 JSON 数组。"
        )]
    if last_exc is None:
        raise RuntimeError("结构化输出失败")
    raise last_exc


def _prd_brief(prd: dict | None) -> str:
    if not prd:
        return "（尚无 PRD）"
    ov = prd.get("overview", {})
    features = [f.get("name") for f in prd.get("features", [])][:8]
    return json.dumps(
        {
            "title": prd.get("title"),
            "定位": ov.get("elevator_pitch"),
            "目标": ov.get("goals"),
            "功能": features,
        },
        ensure_ascii=False,
    )


# ---------------- planner：意图识别 + 任务规划 + 需求分析 ----------------

def make_planner(llm, demo_mode: bool):
    structured = None if demo_mode else llm.with_structured_output(PlannerOutput, include_raw=True)

    def planner(state: dict) -> dict:
        if demo_mode:
            return demo.planner(state)
        user = PLANNER_USER.format(
            prd_brief=_prd_brief(state.get("prd")),
            memory_lines=_fmt_memory(state.get("memory_facts") or []),
            history=_fmt_history(state.get("history") or []),
            user_input=state["user_input"],
        )
        out: PlannerOutput = _invoke_structured(
            structured, PlannerOutput, [SystemMessage(PLANNER_SYSTEM), HumanMessage(user)]
        )
        return {
            "intent": out.intent,
            "plan": [{"title": p.title, "detail": p.detail, "status": "pending"} for p in out.plan],
            "analysis": out.analysis.model_dump(),
            "needs_research": out.needs_research,
            "messages": [],
            "retry_count": 0,
            # 每轮重置：检查点会保留上一轮状态，避免旧 PRD/反馈混入本轮
            "prd_new": None,
            "prd_changes": [],
            "review_feedback": "",
        }

    planner.__name__ = "planner"
    return planner


def route_after_planner(state: dict) -> str:
    if state.get("intent") == "question":
        return "finalize"
    return "research" if state.get("needs_research") else "draft_prd"


# ---------------- research：决定调用哪些工具 ----------------

def make_research(llm, demo_mode: bool):
    tool_llm = None if demo_mode else llm.bind_tools(TOOLS)

    def research(state: dict) -> dict:
        if demo_mode:
            # 演示模式：直接构造工具调用，ToolNode 会真实执行内置知识库工具
            ai = AIMessage(content="调用工具进行调研（演示模式）", tool_calls=demo.research_tool_calls(state))
            return {"messages": [ai]}
        msgs = [
            SystemMessage(RESEARCH_SYSTEM),
            HumanMessage(RESEARCH_USER.format(
                analysis=json.dumps(state.get("analysis"), ensure_ascii=False),
                user_input=state["user_input"],
            )),
        ]
        ai = tool_llm.invoke(msgs)
        return {"messages": [ai]}

    research.__name__ = "research"
    return research


# ---------------- research_summary：把工具结果提炼为调研结论 ----------------

def make_research_summary(llm, demo_mode: bool):
    structured = None if demo_mode else llm.with_structured_output(ResearchSummary, include_raw=True)

    def research_summary(state: dict) -> dict:
        if demo_mode:
            return {"research_result": demo.research_summary(state)}
        tool_outputs = "\n\n".join(
            f"【工具 {m.name}】\n{m.content}" for m in state.get("messages", []) if isinstance(m, ToolMessage)
        )
        out: ResearchSummary = _invoke_structured(structured, ResearchSummary, [
            SystemMessage(RESEARCH_SUMMARY_SYSTEM),
            HumanMessage(RESEARCH_SUMMARY_USER.format(tool_outputs=tool_outputs or "（无）")),
        ])
        return {"research_result": out.model_dump(), "research_raw": tool_outputs}

    research_summary.__name__ = "research_summary"
    return research_summary


# ---------------- draft_prd：生成或修订 PRD ----------------

def _merge_prd(base: dict | None, patch: dict) -> dict:
    """把修改片段合并回完整 PRD：缺省字段沿用原值，overview 逐字段合并。

    列表字段按"修改后的完整列表"覆盖；changelog 按 note 去重后拼接，
    兼容模型只返回新增条目、或返回整份日志两种情况。
    """
    merged = copy.deepcopy(base or {})
    for key, value in patch.items():
        if value is None:
            continue
        if key == "overview" and isinstance(value, dict):
            ov = dict(merged.get("overview") or {})
            ov.update({k: v for k, v in value.items() if v is not None})
            merged["overview"] = ov
        elif key == "changelog":
            items = list(merged.get("changelog") or [])
            seen = {c.get("note") for c in items}
            for c in value:
                if c.get("note") not in seen:
                    items.append(c)
                    seen.add(c.get("note"))
            merged["changelog"] = items
        else:
            merged[key] = value
    return merged


def make_draft(llm, demo_mode: bool):
    full_structured = None if demo_mode else llm.with_structured_output(DraftOutput, include_raw=True)
    patch_structured = None if demo_mode else llm.with_structured_output(DraftPatchOutput, include_raw=True)

    def draft(state: dict) -> dict:
        if demo_mode:
            return demo.draft(state)
        # 评审重写时以本轮上一稿为基础，避免丢掉已做的修改
        base_prd = state.get("prd_new") or state.get("prd")
        is_modify = state.get("intent") == "modify" and bool(base_prd)
        user = DRAFT_USER.format(
            analysis=json.dumps(state.get("analysis"), ensure_ascii=False),
            research=json.dumps(state.get("research_result"), ensure_ascii=False)[:4000],
            memory_lines=_fmt_memory(state.get("memory_facts") or []),
            existing_prd=(json.dumps(base_prd, ensure_ascii=False)[:MAX_PRD_CHARS]
                          if is_modify else "（无，首次生成）"),
            user_input=state["user_input"],
            review_feedback=state.get("review_feedback") or "（无）",
        )
        messages = [SystemMessage(DRAFT_SYSTEM), HumanMessage(user)]
        if is_modify:
            # 宽容解析：模型可以只返回改动字段，缺失章节由原 PRD 补齐
            out: DraftPatchOutput = _invoke_structured(patch_structured, DraftPatchOutput, messages)
            merged = _merge_prd(base_prd, out.prd.model_dump(exclude_none=True))
            prd = PRDDocument.model_validate(merged).model_dump()
        else:
            out: DraftOutput = _invoke_structured(full_structured, DraftOutput, messages)
            prd = out.prd.model_dump()
        return {"prd_new": prd, "prd_changes": out.changes}

    draft.__name__ = "draft_prd"
    return draft


# ---------------- review：PRD 质量自查（反思环节） ----------------

def make_review(llm, demo_mode: bool):
    structured = None if demo_mode else llm.with_structured_output(ReviewOutput, include_raw=True)

    def review(state: dict) -> dict:
        retry = state.get("retry_count", 0) + 1
        if demo_mode or retry >= 2:
            # 演示模式直接通过；真实模式第二次评审强制收口，避免无限循环
            result = demo.review(state) if demo_mode else {
                "passed": True, "score": state.get("review_result", {}).get("score", 7),
                "issues": [], "suggestions": ["第二轮自查：已确认上轮问题修订完成"],
            }
            return {"review_result": result, "retry_count": retry}
        out: ReviewOutput = _invoke_structured(structured, ReviewOutput, [
            SystemMessage(REVIEW_SYSTEM),
            HumanMessage(REVIEW_USER.format(
                prd_json=json.dumps(state.get("prd_new"), ensure_ascii=False)[:MAX_PRD_CHARS])),
        ])
        result = out.model_dump()
        feedback = ""
        if not result.get("passed"):
            feedback = "发现问题：\n" + "\n".join(f"- {i}" for i in result.get("issues", []))
        return {"review_result": result, "retry_count": retry, "review_feedback": feedback}

    review.__name__ = "review"
    return review


def route_after_review(state: dict) -> str:
    result = state.get("review_result") or {}
    if result.get("passed") or state.get("retry_count", 0) >= 2:
        return "update_memory"
    return "draft_prd"


# ---------------- update_memory：沉淀产品记忆 ----------------

def make_memory(llm, demo_mode: bool):
    structured = None if demo_mode else llm.with_structured_output(MemoryExtract, include_raw=True)

    def update_memory(state: dict) -> dict:
        if demo_mode:
            return demo.memory(state)
        out: MemoryExtract = _invoke_structured(structured, MemoryExtract, [
            SystemMessage(MEMORY_SYSTEM),
            HumanMessage(MEMORY_USER.format(
                user_input=state["user_input"],
                analysis=json.dumps(state.get("analysis"), ensure_ascii=False),
                memory_lines=_fmt_memory(state.get("memory_facts") or []),
            )),
        ])
        return {"memory_updates": [u.model_dump() for u in out.updates]}

    update_memory.__name__ = "update_memory"
    return update_memory


# ---------------- finalize：生成面向用户的回复 ----------------

def make_finalize(llm, demo_mode: bool):
    structured = None if demo_mode else llm.with_structured_output(ReplyOut, include_raw=True)

    def finalize(state: dict) -> dict:
        if demo_mode:
            return {"final_reply": demo.reply(state)}
        prd = state.get("prd_new") or state.get("prd")
        user = FINALIZE_USER.format(
            intent=state.get("intent"),
            plan_titles="、".join(s["title"] for s in state.get("plan", [])),
            user_input=state["user_input"],
            prd_title=(prd or {}).get("title", "未命名"),
            changes="；".join(state.get("prd_changes", [])) or "（无）",
            prd_brief=_prd_brief(prd),
        )
        out: ReplyOut = _invoke_structured(
            structured, ReplyOut, [SystemMessage(FINALIZE_SYSTEM), HumanMessage(user)]
        )
        return {"final_reply": out.reply}

    finalize.__name__ = "finalize"
    return finalize
