"""API 端到端测试（演示模式）：认证 → SSE 流式 → 落库 → 查询 → 导出 → 配置。"""
import json
import os

os.environ["LLM_PROVIDER"] = "demo"
os.environ["DATA_DIR"] = "data_test_api"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

USERNAME = "tester"
PASSWORD = "test123456"


def _register(client: TestClient) -> dict:
    client.post("/api/auth/register", json={"username": USERNAME, "password": PASSWORD})
    r = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _stream_chat(client: TestClient, headers: dict, message: str,
                 project_id: str | None = None) -> list[dict]:
    events = []
    with client.stream("POST", "/api/chat",
                       json={"message": message, "project_id": project_id},
                       headers=headers) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_auth_required_and_register():
    with TestClient(app) as client:
        assert client.get("/api/projects").status_code == 401, "未登录应 401"

        r = client.post("/api/auth/register", json={"username": "alice", "password": "abc123456"})
        assert r.status_code == 200
        dup = client.post("/api/auth/register", json={"username": "alice", "password": "abc123456"})
        assert dup.status_code == 409, "重复注册应 409"

        bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong-pwd"})
        assert bad.status_code == 401

        ok = client.post("/api/auth/login", json={"username": "alice", "password": "abc123456"})
        token = ok.json()["token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["username"] == "alice"


def test_chat_stream_persist_export():
    with TestClient(app) as client:
        headers = _register(client)
        events = _stream_chat(client, headers, "做一个面向健身新手的AI健身教练App")

        types = [e["type"] for e in events]
        assert types[0] == "project"
        assert "node" in types and "tool" in types, "应包含节点与工具调用事件"
        assert "done" in types, f"应正常结束，实际: {types}"

        pid = next(e["project"]["id"] for e in events if e["type"] == "project")

        detail = client.get(f"/api/projects/{pid}", headers=headers).json()
        assert detail["prd"], "PRD 应已落库"
        assert detail["prd"]["features"]
        assert len(detail["messages"]) == 2, "用户与助手消息都应落库"
        assert detail["messages"][1]["steps"], "执行记录应落库"
        assert detail["memory"], "产品记忆应落库"

        md = client.get(f"/api/projects/{pid}/prd.md", headers=headers)
        assert md.status_code == 200
        assert "PRD" in md.text and "产品概述" in md.text

        projects = client.get("/api/projects", headers=headers).json()["projects"]
        assert any(p["id"] == pid for p in projects)

        # 其他用户看不到该项目
        client.post("/api/auth/register", json={"username": "bob", "password": "bob123456"})
        r2 = client.post("/api/auth/login", json={"username": "bob", "password": "bob123456"})
        bob = {"Authorization": f"Bearer {r2.json()['token']}"}
        assert client.get(f"/api/projects/{pid}", headers=bob).status_code == 404
        assert client.get("/api/projects", headers=bob).json()["projects"] == []


def test_multi_turn_modify_via_api():
    with TestClient(app) as client:
        headers = _register(client)
        events = _stream_chat(client, headers, "做一个记账App")
        pid = next(e["project"]["id"] for e in events if e["type"] == "project")

        events2 = _stream_chat(client, headers, "把目标用户改成大学生", project_id=pid)
        done = next(e for e in events2 if e["type"] == "done")
        assert done["project"]["version"] >= 2, "多轮修改应递增版本号"

        detail = client.get(f"/api/projects/{pid}", headers=headers).json()
        assert len(detail["messages"]) == 4


def test_llm_settings_crud():
    with TestClient(app) as client:
        headers = _register(client)
        cfg = client.get("/api/settings/llm", headers=headers).json()
        assert cfg["demo_mode"] is True

        r = client.put("/api/settings/llm", headers=headers, json={
            "provider": "deepseek", "api_key": "sk-test-1234567890",
            "model": "deepseek-chat",
        })
        assert r.status_code == 200
        cfg = r.json()
        assert cfg["provider"] == "deepseek" and cfg["has_api_key"] is True
        assert cfg["api_key_masked"], "应返回脱敏后的 Key"
        assert cfg["demo_mode"] is False

        # 清除 Key 回到演示模式
        r = client.put("/api/settings/llm", headers=headers, json={"api_key": ""})
        assert r.json()["demo_mode"] is True


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health").json()
        assert r["status"] == "ok"


def test_delete_project_with_execution_steps():
    """回归：项目有执行记录（run_steps）时删除不应触发外键错误。"""
    with TestClient(app) as client:
        headers = _register(client)
        events = _stream_chat(client, headers, "做一个校园二手书交易小程序")
        pid = next(e["project"]["id"] for e in events if e["type"] == "project")

        detail = client.get(f"/api/projects/{pid}", headers=headers).json()
        assert detail["messages"][-1]["steps"], "应已产生执行记录"

        r = client.delete(f"/api/projects/{pid}", headers=headers)
        assert r.status_code == 200, r.text
        assert client.get(f"/api/projects/{pid}", headers=headers).status_code == 404

        # 检查点也应一并清理
        import sqlite3

        from app.config import DATA_DIR

        cp = sqlite3.connect(DATA_DIR / "checkpoints.sqlite")
        try:
            n = cp.execute(
                "select count(*) from checkpoints where thread_id = ?",
                (f"project-{pid}",),
            ).fetchone()[0]
        finally:
            cp.close()
        assert n == 0, "项目的 LangGraph 检查点应被清理"
