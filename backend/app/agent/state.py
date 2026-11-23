"""LangGraph 全局状态定义。

一个"轮次"（用户发一句话）对应一次图执行：
planner → (research → tools → research_summary)? → draft_prd ⇄ review → update_memory → finalize

注意：messages 使用普通 list（无 add_messages reducer），每轮由 planner 重置，
避免检查点恢复后历史消息无限累积。
"""
from typing import Any, TypedDict


class PlanStep(TypedDict):
    title: str      # 展示给用户的步骤名
    detail: str     # 步骤说明
    status: str     # pending / running / done / skipped


class AgentState(TypedDict, total=False):
    # 输入
    project_id: str
    user_input: str
    history: list[dict]        # 近期对话（role/content）
    prd: dict | None           # 当前 PRD（已存在时）
    memory_facts: list[dict]   # 产品记忆快照
    demo_mode: bool            # 演示模式标记

    # planner 输出
    intent: str                # create / modify / question
    plan: list[PlanStep]
    analysis: dict             # 结构化需求分析
    needs_research: bool

    # 调研（注意：状态字段名不能与节点名重复，故用 research_result 而非 research）
    messages: list[Any]        # 本轮消息（含工具调用与结果，每轮重置）
    research_raw: str          # 工具原始返回（拼合）
    research_result: dict      # 调研总结（结构化）

    # PRD 撰写与反思循环
    prd_new: dict | None       # 本轮生成/更新的 PRD
    prd_changes: list[str]     # 本轮变更说明
    review_feedback: str       # 自查不通过时的反馈
    review_result: dict        # 自查结论
    retry_count: int

    # 记忆与输出
    memory_updates: list[dict]  # 本轮新增/更新的记忆事实
    final_reply: str            # 展示给用户的最终回复
