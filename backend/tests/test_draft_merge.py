"""修改 PRD 的容错合并测试（不调用真实 LLM）。"""
from app.agent.nodes import _merge_prd, make_draft
from app.agent.prd_schema import DraftPatchOutput, PRDDocument

BASE_PRD = {
    "title": "校园寻物",
    "overview": {
        "product_name": "校园寻物",
        "elevator_pitch": "让失物快速回家",
        "background": "校园失物招领效率低",
        "goals": ["30 天内覆盖 3 所高校"],
        "non_goals": ["不做二手交易"],
    },
    "target_users": [
        {"segment": "学生", "description": "在校生",
         "needs": ["快速找回"], "pain_points": ["信息分散"]},
    ],
    "user_stories": [
        {"as_a": "学生", "want": "发布失物信息", "so_that": "尽快找回", "priority": "P0"},
    ],
    "features": [
        {"name": "失物发布", "description": "发布信息", "priority": "P0",
         "acceptance_criteria": ["可上传图片"]},
    ],
    "competitor_analysis": [],
    "metrics": [{"name": "找回率", "definition": "找回数/发布数", "target": "> 30%"}],
    "milestones": [{"phase": "MVP", "duration": "4 周", "deliverables": ["核心流程"]}],
    "risks": [{"risk": "冷启动", "level": "中", "mitigation": "校园地推"}],
    "changelog": [{"note": "初始版本"}],
    "open_questions": ["是否支持跨校？"],
}


def test_merge_partial_patch_keeps_untouched_sections():
    """模型只返回部分章节时，其余章节应沿用原 PRD。"""
    patch = {
        "title": "校园寻物 Pro",
        "overview": {"elevator_pitch": "新定位"},
        "target_users": [{"segment": "新生", "description": "大一新生",
                          "needs": ["找东西"], "pain_points": ["不熟悉校园"]}],
    }
    merged = _merge_prd(BASE_PRD, patch)
    doc = PRDDocument.model_validate(merged)  # 不应抛 ValidationError

    assert doc.title == "校园寻物 Pro"
    assert doc.overview.elevator_pitch == "新定位"
    assert doc.overview.background == BASE_PRD["overview"]["background"]
    assert doc.features[0].name == "失物发布"
    assert doc.target_users[0].segment == "新生"


def test_merge_changelog_deduplicates():
    """模型返回整份变更日志时不应重复追加历史条目。"""
    patch = {"changelog": [{"note": "初始版本"}, {"note": "本轮：调整目标用户"}]}
    merged = _merge_prd(BASE_PRD, patch)
    assert [c["note"] for c in merged["changelog"]] == ["初始版本", "本轮：调整目标用户"]


class _FakeStructured:
    def __init__(self, output):
        self.output = output

    def invoke(self, _messages):
        return self.output


class _FakeLLM:
    def __init__(self, output):
        self.output = output

    def with_structured_output(self, _schema, **_kwargs):
        return _FakeStructured(self.output)


def test_draft_modify_accepts_partial_output():
    """回归：修改时模型只返回部分字段，不应再报 8 个字段缺失。"""
    out = DraftPatchOutput.model_validate({
        "prd": {"title": "校园寻物 Pro", "overview": {"elevator_pitch": "新定位"}},
        "changes": ["调整定位"],
    })
    node = make_draft(_FakeLLM(out), demo_mode=False)
    result = node({
        "intent": "modify",
        "prd": BASE_PRD,
        "user_input": "把定位改成帮助新生找回失物",
        "analysis": {},
        "memory_facts": [],
        "research_result": {},
        "review_feedback": "",
    })

    PRDDocument.model_validate(result["prd_new"])
    assert result["prd_new"]["title"] == "校园寻物 Pro"
    assert result["prd_new"]["features"] == BASE_PRD["features"]
    assert result["prd_changes"] == ["调整定位"]
