"""Agent 工具集。

1. search_competitors  竞品搜索：有 DeepSeek Key 时使用 DeepSeek 官方联网搜索
   （与 LLM 共用同一把 Key），否则回退内置竞品知识库（离线可用、零成本）。
2. query_knowledge_base 行业知识查询：内置知识库（用户特征/痛点/商业模式/指标等）。
"""
import json
from functools import lru_cache
from pathlib import Path

import httpx
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

KB_PATH = Path(__file__).resolve().parent.parent.parent / "knowledge" / "domains.json"


@lru_cache(maxsize=1)
def _load_kb() -> list[dict]:
    with open(KB_PATH, encoding="utf-8") as f:
        return json.load(f)["domains"]


def _score_domain(domain: dict, text: str) -> int:
    """按关键词与标签的重叠度给领域打分，用于内置知识库检索。"""
    score = 0
    text_l = text.lower()
    for tag in domain.get("tags", []):
        if tag.lower() in text_l:
            score += 3
    for kw in domain.get("keywords", []):
        if kw.lower() in text_l:
            score += 2
    if domain["name"] in text:
        score += 4
    return score


def find_domain(text: str) -> dict | None:
    domains = _load_kb()
    scored = sorted(domains, key=lambda d: _score_domain(d, text), reverse=True)
    return scored[0] if _score_domain(scored[0], text) > 0 else None


def _fmt_competitor(c: dict) -> str:
    lines = [f"· {c['name']}（{c['positioning']}）"]
    lines.append(f"  优势：{'；'.join(c['strengths'])}")
    lines.append(f"  劣势/机会：{'；'.join(c['weaknesses'])}")
    return "\n".join(lines)


def _kb_competitor_search(keyword: str, domain: str) -> str:
    """内置知识库竞品检索。"""
    domains = _load_kb()
    text = f"{keyword} {domain}"
    scored = sorted(domains, key=lambda d: _score_domain(d, text), reverse=True)
    hits = [d for d in scored[:2] if _score_domain(d, text) > 0]
    if not hits:
        return "【内置知识库】未找到与关键词匹配的竞品信息，建议补充行业或产品关键词。"
    parts = ["【来源：内置竞品知识库】"]
    for d in hits:
        parts.append(f"■ 领域：{d['name']}（{d['overview']}）")
        for c in d["competitors"]:
            parts.append(_fmt_competitor(c))
    return "\n".join(parts)


def _deepseek_search(query: str, cfg: dict) -> str:
    """调用 DeepSeek 官方网页搜索接口（与 LLM 共用同一把 API Key）。"""
    base = (cfg.get("base_url") or "https://api.deepseek.com/v1").rstrip("/")
    resp = httpx.post(
        f"{base}/tools/search",
        headers={"Authorization": f"Bearer {cfg['api_key']}"},
        json={"query": query[:128], "count": 5, "need_content": False},
        timeout=20,
    )
    if resp.status_code != 200:
        msg = f"HTTP {resp.status_code}"
        try:
            msg = resp.json().get("error", {}).get("message") or msg
        except Exception:
            pass
        raise RuntimeError(msg)
    results = resp.json().get("results") or []
    if not results:
        raise ValueError("搜索无结果")
    lines = ["【来源：DeepSeek 官方联网搜索】"]
    seen_urls = set()
    for r in results:
        url = r.get("url") or ""
        if url and url in seen_urls:  # 同一页面可能以多语言重复返回
            continue
        seen_urls.add(url)
        title = r.get("title") or ""
        site = r.get("site_name") or ""
        summary = (r.get("summary") or r.get("snippet") or "")[:400]
        lines.append(f"· {title}" + (f"（{site}）" if site else ""))
        if summary:
            lines.append(f"  {summary}")
    return "\n".join(lines)


@tool
def search_competitors(keyword: str, domain: str = "", config: RunnableConfig = None) -> str:
    """搜索与产品相关的竞品信息。

    Args:
        keyword: 搜索关键词，如产品名称、核心功能或目标用户
        domain: 行业领域（可选），如"在线教育"、"健康管理"

    Returns:
        竞品名称、定位、优势与劣势的文本描述
    """
    from ..llm_config import read_llm_config

    user_id = ((config or {}).get("configurable") or {}).get("user_id")
    cfg = read_llm_config(user_id)
    query = f"{keyword} {domain} 竞品 产品分析".strip()

    # 有 DeepSeek Key 时使用官方联网搜索（与 LLM 共用同一把 Key）
    if cfg.get("provider") == "deepseek" and cfg.get("api_key"):
        try:
            return _deepseek_search(query, cfg)
        except Exception as e:
            return f"（DeepSeek 搜索失败：{e}，已改用内置知识库）\n{_kb_competitor_search(keyword, domain)}"

    return _kb_competitor_search(keyword, domain)


@tool
def query_knowledge_base(topic: str) -> str:
    """查询内置产品知识库，获取行业洞察。

    覆盖：典型用户特征、行业痛点、商业模式、关键指标、行业趋势。

    Args:
        topic: 查询主题，如"在线教育的商业模式"、"健身行业的用户痛点"

    Returns:
        相关行业知识文本
    """
    domain = find_domain(topic)
    if not domain:
        return "【内置知识库】未找到相关行业知识，建议更换查询主题（如：在线教育、健康管理、企业协作、跨境电商、内容社区、本地生活、AI工具、游戏）。"
    lines = [
        f"【来源：内置行业知识库】领域：{domain['name']}",
        f"■ 领域概况：{domain['overview']}",
        f"■ 典型用户：{domain['typical_users']}",
        "■ 行业痛点：",
    ]
    lines += [f"  - {p}" for p in domain["pain_points"]]
    lines.append("■ 常见商业模式：")
    lines += [f"  - {b}" for b in domain["business_models"]]
    lines.append("■ 关键指标：")
    lines += [f"  - {m}" for m in domain["key_metrics"]]
    lines.append("■ 行业趋势：")
    lines += [f"  - {t}" for t in domain["trends"]]
    return "\n".join(lines)


TOOLS = [search_competitors, query_knowledge_base]
