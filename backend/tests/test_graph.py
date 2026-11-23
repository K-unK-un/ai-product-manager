"""Agent 图测试（演示模式，不依赖外部 API）。"""
import os

os.environ["LLM_PROVIDER"] = "demo"
os.environ["DATA_DIR"] = "data_test_graph"

from app.agent.graph import build_graph  # noqa: E402


def _input(user_input: str, prd=None, memory_facts=None):
    return {
        "user_input": user_input,
        "project_id": "p1",
        "history": [],
        "prd": prd,
        "memory_facts": memory_facts or [],
        "demo_mode": True,
    }


def test_create_flow_produces_complete_prd():
    g = build_graph(demo_mode=True)
    out = g.invoke(_input("做一个面向健身新手的AI健身教练App，核心功能是生成个性化训练计划"))

    assert out["intent"] == "create"
    assert len(out["plan"]) >= 3, "任务规划至少 3 步"
    prd = out["prd_new"]
    assert prd["overview"]["goals"], "PRD 应有目标"
    assert prd["features"] and prd["user_stories"], "PRD 应有功能与用户故事"
    assert prd["metrics"] and prd["milestones"] and prd["risks"]
    assert prd["competitor_analysis"], "演示模式应通过知识库工具获得竞品数据"
    assert out["review_result"]["passed"]
    assert out["memory_updates"], "应有记忆沉淀"
    assert out["final_reply"]


def test_modify_flow_keeps_prd_and_appends_changelog():
    g = build_graph(demo_mode=True)
    out1 = g.invoke(_input("做一个记账App"))
    prd1 = out1["prd_new"]

    out2 = g.invoke(_input(
        "把目标用户改成大学生，并增加预算提醒功能",
        prd=prd1,
        memory_facts=[{"key": "产品定位", "value": "记账App", "category": "定位"}],
    ))
    assert out2["intent"] == "modify"
    prd2 = out2["prd_new"]
    assert len(prd2["changelog"]) > len(prd1["changelog"]), "修改应追加变更日志"
    assert out2["prd_changes"], "应输出修改点说明"
    assert prd2["title"] == prd1["title"], "未涉及的标题应保留"
    assert out2["final_reply"]


def test_question_intent_skips_draft_and_keeps_prd():
    g = build_graph(demo_mode=True)
    out1 = g.invoke(_input("做一个宠物寄养预约小程序"))
    prd1 = out1["prd_new"]

    out2 = g.invoke(_input("这个产品的核心指标应该看什么？", prd=prd1))
    assert out2["intent"] == "question"
    assert out2.get("prd_new") is None, "提问不应重写 PRD"
    assert out2["final_reply"]


def test_graph_topology():
    g = build_graph(demo_mode=True)
    nodes = set(g.get_graph().nodes)
    assert {"planner", "research", "tools", "research_summary", "draft_prd",
            "review", "update_memory", "finalize"} <= nodes


def test_knowledge_tools_work():
    from app.agent.tools import query_knowledge_base, search_competitors

    kb = query_knowledge_base.invoke({"topic": "在线教育"})
    assert "在线教育" in kb and "痛点" in kb
    comps = search_competitors.invoke({"keyword": "健身教练 健康管理", "domain": ""})
    assert "竞品知识库" in comps or "竞品" in comps
