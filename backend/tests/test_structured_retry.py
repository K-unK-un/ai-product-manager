"""结构化输出：非法 JSON 的修复与重试。"""
import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.agent.nodes import _invoke_structured


class _Out(BaseModel):
    title: str
    metrics: list[str]


class _Flaky:
    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise OutputParserException("are not valid JSON")
        return "ok"


class _Repairing:
    def __init__(self, args: str):
        self.args = args

    def invoke(self, _messages):
        raw = AIMessage(
            content="",
            additional_kwargs={"tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "Out", "arguments": self.args},
            }]},
        )
        return {"raw": raw, "parsed": None, "parsing_error": OutputParserException("bad")}


def test_retries_on_invalid_json():
    f = _Flaky(fail_times=1)
    assert _invoke_structured(f, _Out, [], retries=2) == "ok"
    assert f.calls == 2


def test_raises_after_retries_exhausted():
    f = _Flaky(fail_times=5)
    with pytest.raises(OutputParserException):
        _invoke_structured(f, _Out, [], retries=1)
    assert f.calls == 2


def test_repairs_extra_data_quotes_and_list_shape():
    """回归：JSON 后多余内容、字符串内未转义引号、数组被写成 {"items": [...]}。"""
    args = (
        '{"title": "他说"你好"", '
        '"metrics": {"__comment": "placeholder", "items": ["留存率"]}}'
        '{"extra": true}'
    )
    out = _invoke_structured(_Repairing(args), _Out, [], retries=0)
    assert out.title == '他说"你好"'
    assert out.metrics == ["留存率"]
