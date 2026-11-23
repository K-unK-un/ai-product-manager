"""结构化输出模型：PRD 文档 + 各节点的中间产物。

全部为 Pydantic v2 模型，LLM 通过 function calling 严格按此结构输出，
保证 PRD 可解析、可渲染、可导出。
"""
from typing import Literal

from pydantic import BaseModel, Field


# ---------- PRD 文档 ----------

class Overview(BaseModel):
    product_name: str = Field(description="产品名称")
    elevator_pitch: str = Field(description="一句话价值主张（电梯演讲）")
    background: str = Field(description="产品背景与要解决的问题")
    goals: list[str] = Field(description="产品目标，尽量可衡量")
    non_goals: list[str] = Field(description="明确不做什么（防止范围蔓延）")


class TargetUser(BaseModel):
    segment: str = Field(description="用户分层名称，如：核心用户")
    description: str = Field(description="用户画像描述")
    needs: list[str] = Field(description="核心需求")
    pain_points: list[str] = Field(description="痛点")


class UserStory(BaseModel):
    as_a: str = Field(description="角色")
    want: str = Field(description="想要的能力")
    so_that: str = Field(description="带来的价值")
    priority: Literal["P0", "P1", "P2"] = Field(description="优先级")


class Feature(BaseModel):
    name: str = Field(description="功能名称")
    description: str = Field(description="功能描述")
    priority: Literal["P0", "P1", "P2"] = Field(description="优先级")
    acceptance_criteria: list[str] = Field(description="验收标准，每条可测试")


class Competitor(BaseModel):
    name: str = Field(description="竞品名称")
    positioning: str = Field(description="竞品定位")
    strengths: list[str] = Field(description="竞品优势")
    weaknesses: list[str] = Field(description="竞品劣势/机会点")
    takeaway: str = Field(description="对本产品的启发")


class Metric(BaseModel):
    name: str = Field(description="指标名称")
    definition: str = Field(description="指标定义与口径")
    target: str = Field(description="目标值或方向")


class Milestone(BaseModel):
    phase: str = Field(description="阶段名称")
    duration: str = Field(description="周期，如 4 周")
    deliverables: list[str] = Field(description="交付物")


class Risk(BaseModel):
    risk: str = Field(description="风险描述")
    level: Literal["高", "中", "低"] = Field(description="风险等级")
    mitigation: str = Field(description="应对措施")


class ChangelogItem(BaseModel):
    note: str = Field(description="变更说明")


class OverviewPatch(BaseModel):
    """修改时的概述片段：只需返回本轮改动到的字段。"""
    product_name: str | None = None
    elevator_pitch: str | None = None
    background: str | None = None
    goals: list[str] | None = None
    non_goals: list[str] | None = None


class PRDPatch(BaseModel):
    """修改 PRD 时的宽容输出：允许只返回本轮改动到的字段。

    合并规则见 nodes._merge_prd：缺省字段沿用原 PRD；
    列表字段视为"修改后的完整列表"（不是增量）。
    """
    title: str | None = None
    overview: OverviewPatch | None = None
    target_users: list[TargetUser] | None = None
    user_stories: list[UserStory] | None = None
    features: list[Feature] | None = None
    competitor_analysis: list[Competitor] | None = None
    metrics: list[Metric] | None = None
    milestones: list[Milestone] | None = None
    risks: list[Risk] | None = None
    changelog: list[ChangelogItem] | None = Field(
        default=None, description="变更日志：保留全部历史条目并追加本轮说明"
    )
    open_questions: list[str] | None = None


class PRDDocument(BaseModel):
    title: str = Field(description="PRD 标题（产品名称）")
    overview: Overview
    target_users: list[TargetUser]
    user_stories: list[UserStory]
    features: list[Feature]
    competitor_analysis: list[Competitor] = Field(
        description="竞品分析；没有调研数据时留空数组，不得编造"
    )
    metrics: list[Metric]
    milestones: list[Milestone]
    risks: list[Risk]
    changelog: list[ChangelogItem] = Field(description="变更日志（每次修改追加一条）")
    open_questions: list[str] = Field(description="待确认问题")


# ---------- 节点中间产物 ----------

class PlanItem(BaseModel):
    title: str
    detail: str


class RequirementAnalysis(BaseModel):
    product_name: str | None = Field(description="产品名称（create 时给出）")
    summary: str = Field(description="需求一句话总结")
    goals: list[str]
    target_users: list[str]
    scenarios: list[str] = Field(description="核心使用场景")
    constraints: list[str] = Field(description="约束条件（技术/资源/合规等）")
    open_questions: list[str] = Field(description="待澄清问题")


class PlannerOutput(BaseModel):
    intent: Literal["create", "modify", "question"] = Field(
        description="create=生成新PRD；modify=修改现有PRD；question=仅解答不修改"
    )
    plan: list[PlanItem] = Field(description="3~5 步任务计划，展示给用户")
    analysis: RequirementAnalysis
    needs_research: bool = Field(description="是否需要调用工具做调研")


class ResearchSummary(BaseModel):
    summary: str = Field(description="调研结论概述")
    competitors: list[Competitor] = Field(description="竞品列表，仅来自工具返回内容")
    key_insights: list[str] = Field(description="3~5 条关键洞察")


class DraftOutput(BaseModel):
    prd: PRDDocument
    changes: list[str] = Field(description="本轮修改点说明；create 时为空数组")


class DraftPatchOutput(BaseModel):
    prd: PRDPatch = Field(description="修改后的 PRD 片段；未改动的字段可以省略")
    changes: list[str] = Field(default_factory=list, description="本轮修改点说明")


class ReviewOutput(BaseModel):
    passed: bool = Field(description="是否通过质量自查")
    score: int = Field(description="PRD 质量评分 1~10")
    issues: list[str] = Field(description="发现的问题（不通过时必填）")
    suggestions: list[str] = Field(description="改进建议")


class MemoryFactOut(BaseModel):
    key: str = Field(description="事实名称，不超过 6 个字")
    value: str = Field(description="事实内容，不超过 40 字")
    category: str = Field(description="分类：目标用户/功能/商业模式/场景/约束/其他")
    note: str = Field(description="一句话说明为什么记住它")


class MemoryExtract(BaseModel):
    updates: list[MemoryFactOut] = Field(description="本轮需要新增或更新的记忆；没有则返回空数组")


class ReplyOut(BaseModel):
    reply: str = Field(description="2~4 句话向用户汇报本轮成果与下一步建议")
