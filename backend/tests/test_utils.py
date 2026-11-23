"""PRD → Markdown 导出测试。"""
from app.utils import prd_to_markdown


def _prd(open_questions):
    return {"title": "测试产品", "open_questions": open_questions}


def test_open_questions_render_as_list_items():
    """回归：lines += _md_list(...) 会把字符串按字符拆成多行。"""
    md = prd_to_markdown(_prd(["第一个问题？", "第二个问题？"]), version=1)
    assert "## 九、待确认问题\n\n- 第一个问题？\n- 第二个问题？" in md


def test_open_questions_empty_shows_placeholder():
    md = prd_to_markdown(_prd([]), version=1)
    assert "## 九、待确认问题\n\n（无）" in md
