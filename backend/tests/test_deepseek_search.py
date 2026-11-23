"""竞品搜索：优先使用 DeepSeek 官方联网搜索，失败回退内置知识库。"""
import app.agent.tools as tools
from app.agent.tools import search_competitors


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "results": [
                {"title": "竞品A", "summary": "摘要A", "site_name": "站点A", "url": "https://a"},
                {"title": "竞品A-重复", "summary": "重复摘要", "site_name": "站点A", "url": "https://a"},
                {"title": "竞品B", "summary": "摘要B", "site_name": None, "url": "https://b"},
            ]
        }


def test_uses_deepseek_search_with_llm_key(monkeypatch):
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.update(url=url, headers=headers, json=json, timeout=timeout)
        return _FakeResponse()

    monkeypatch.setattr(tools.httpx, "post", fake_post)
    monkeypatch.setattr(
        "app.llm_config.read_llm_config",
        lambda user_id=None: {
            "provider": "deepseek",
            "api_key": "sk-deepseek",
            "base_url": "https://api.deepseek.com/v1",
        },
    )

    out = search_competitors.invoke({"keyword": "健身 App", "domain": "健康管理"})

    assert "【来源：DeepSeek 官方联网搜索】" in out
    assert "竞品A" in out and "摘要A" in out
    assert "重复摘要" not in out  # 同一 URL 的结果去重
    assert calls["url"] == "https://api.deepseek.com/v1/tools/search"
    assert calls["headers"]["Authorization"] == "Bearer sk-deepseek"
    assert calls["json"]["count"] == 5


def test_falls_back_to_builtin_kb_when_deepseek_fails(monkeypatch):
    def fake_post(*_args, **_kwargs):
        raise RuntimeError("402 余额不足")

    monkeypatch.setattr(tools.httpx, "post", fake_post)
    monkeypatch.setattr(
        "app.llm_config.read_llm_config",
        lambda user_id=None: {
            "provider": "deepseek",
            "api_key": "sk-deepseek",
            "base_url": "https://api.deepseek.com/v1",
        },
    )

    out = search_competitors.invoke({"keyword": "健身", "domain": "健康管理"})

    assert "已改用内置知识库" in out
    assert "内置竞品知识库" in out


def test_without_key_uses_builtin_kb(monkeypatch):
    monkeypatch.setattr(
        "app.llm_config.read_llm_config",
        lambda user_id=None: {"provider": "demo", "api_key": "", "base_url": ""},
    )

    out = search_competitors.invoke({"keyword": "健身", "domain": "健康管理"})

    assert "【来源：内置竞品知识库】" in out
