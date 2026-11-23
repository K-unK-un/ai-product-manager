"""聊天接口：SSE 流式返回 Agent 执行过程与结果。

事件协议（text/event-stream，每条 `data: {json}\n\n`）：
- {"type":"project", "project":{...}}                      建立/复用项目
- {"type":"node","name":...,"status":"running"|"done",...} 节点生命周期（任务规划/撰写PRD/质量自查…）
- {"type":"tool","name":...,"status":"running"|"done",...} 工具调用（竞品搜索/知识查询）
- {"type":"error","message":...}                           执行出错
- {"type":"done","project":{...}}                          本轮结束（含版本号等）
"""
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..agent.graph import NODE_TITLES, get_agent
from ..db import SessionLocal
from ..deps import AuthUser, get_current_user
from ..models import MemoryFact, Message, Project, RunStep
from ..schemas import ChatRequest
from ..utils import prd_to_markdown

router = APIRouter()

MAX_STEP_DETAIL = 4000


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _truncate(s, n: int = 800) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n] + "…"


def _guess_name(message: str) -> str:
    name = re.split(r"[，。！？；、,.!?;:\n]", message.strip())[0].strip()
    return name[:24] or "未命名产品"


def _node_payload(node: str, data: dict) -> dict:
    """节点完成时，提取面向用户的关键信息（不包含思维链）。"""
    if node == "planner":
        analysis = data.get("analysis") or {}
        return {
            "intent": data.get("intent"),
            "plan": data.get("plan"),
            "analysis": {
                "summary": analysis.get("summary"),
                "goals": analysis.get("goals"),
                "target_users": analysis.get("target_users"),
                "scenarios": analysis.get("scenarios"),
            },
        }
    if node == "research_summary":
        research = data.get("research_result") or {}
        return {
            "summary": research.get("summary"),
            "competitor_count": len(research.get("competitors") or []),
            "key_insights": research.get("key_insights"),
        }
    if node == "draft_prd":
        return {"prd": data.get("prd_new"), "changes": data.get("prd_changes") or []}
    if node == "review":
        return {"review": data.get("review_result")}
    if node == "update_memory":
        return {"updates": data.get("memory_updates") or []}
    if node == "finalize":
        return {"text": data.get("final_reply", "")}
    return {}


@router.post("/api/chat")
async def chat(req: ChatRequest, user: AuthUser = Depends(get_current_user)):
    agent = get_agent()
    graph, demo_mode = agent.get(user.id)  # LLM 配置按用户隔离

    # ---- 流式开始前：解析/创建项目，加载上下文（历史、记忆、PRD）----
    db = SessionLocal()
    if req.project_id:
        project = db.get(Project, req.project_id)
        if not project or project.owner_id != user.id:
            db.close()
            raise HTTPException(404, "项目不存在")
        created_new = False
    else:
        project = Project(id=uuid.uuid4().hex, name=_guess_name(req.message),
                          owner_id=user.id)
        db.add(project)
        db.commit()
        created_new = True

    user_msg = Message(id=uuid.uuid4().hex, project_id=project.id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()

    history = [
        {"role": m.role, "content": m.content}
        for m in db.query(Message)
        .filter(Message.project_id == project.id)
        .order_by(Message.created_at.desc())
        .limit(8)
        .all()
    ][::-1]
    memory_facts = [
        {"key": f.key, "value": f.value, "category": f.category}
        for f in db.query(MemoryFact).filter(MemoryFact.project_id == project.id).all()
    ]

    inputs = {
        "user_input": req.message,
        "project_id": project.id,
        "history": history,
        "prd": project.prd,
        "memory_facts": memory_facts,
        "demo_mode": demo_mode,
    }
    config = {"configurable": {"thread_id": f"project-{project.id}", "user_id": user.id}}
    db.close()

    collected_steps: list[dict] = []  # 收集执行记录，流结束后持久化

    async def gen():
        yield _sse({"type": "project", "project": {
            "id": project.id, "name": project.name, "version": project.version,
            "created_new": created_new, "demo_mode": demo_mode,
        }})
        try:
            async for event in graph.astream_events(inputs, config=config, version="v2"):
                kind = event.get("event")
                node = (event.get("metadata") or {}).get("langgraph_node")
                name = event.get("name")

                # 节点开始/结束
                if kind in ("on_chain_start", "on_chain_end") and node in NODE_TITLES and name == node:
                    if kind == "on_chain_start":
                        yield _sse({"type": "node", "name": node, "title": NODE_TITLES[node], "status": "running"})
                    else:
                        data = (event.get("data") or {}).get("output") or {}
                        payload = _node_payload(node, data)
                        collected_steps.append({
                            "kind": "node", "name": node, "title": NODE_TITLES[node],
                            "status": "done", "summary": _node_summary(node, payload),
                            "detail": _clip(payload),
                        })
                        yield _sse({"type": "node", "name": node, "title": NODE_TITLES[node],
                                    "status": "done", **payload})

                # 工具调用
                elif kind == "on_tool_start":
                    yield _sse({"type": "tool", "name": name, "status": "running",
                                "input": (event.get("data") or {}).get("input") or {}})
                elif kind == "on_tool_end":
                    out = (event.get("data") or {}).get("output")
                    content = out.content if hasattr(out, "content") else str(out)
                    collected_steps.append({
                        "kind": "tool", "name": name, "title": name, "status": "done",
                        "summary": _truncate(content, 200), "detail": {"output": _truncate(content, MAX_STEP_DETAIL)},
                    })
                    yield _sse({"type": "tool", "name": name, "status": "done", "output": _truncate(content, 800)})

            final = await graph.aget_state(config)
            values = final.values

            # ---- 持久化：回复、执行记录、PRD、版本、记忆 ----
            # 注意：此处变量必须叫 proj（gen 内赋值会使 project 变为局部变量，
            # 导致函数开头引用外层 project 时 UnboundLocalError）
            session = SessionLocal()
            try:
                proj = session.get(Project, inputs["project_id"])
                reply = values.get("final_reply") or "（本轮未生成回复）"
                assistant_msg = Message(id=uuid.uuid4().hex, project_id=proj.id,
                                        role="assistant", content=reply)
                session.add(assistant_msg)

                for i, s in enumerate(collected_steps):
                    session.add(RunStep(id=uuid.uuid4().hex, message_id=assistant_msg.id,
                                        project_id=proj.id, seq=i, **s))

                prd_new = values.get("prd_new")
                if prd_new:
                    proj.prd = prd_new
                    proj.version = (proj.version or 0) + 1
                    title = (prd_new.get("title") or "").strip()
                    if title and (created_new or proj.name == "未命名产品"):
                        proj.name = title[:40]

                for u in values.get("memory_updates") or []:
                    fact = session.query(MemoryFact).filter(
                        MemoryFact.project_id == proj.id, MemoryFact.key == u["key"]
                    ).first()
                    if fact:
                        fact.value = u["value"]
                        fact.category = u.get("category", "其他")
                    else:
                        session.add(MemoryFact(id=uuid.uuid4().hex, project_id=proj.id,
                                               key=u["key"], value=u["value"],
                                               category=u.get("category", "其他")))
                session.commit()
                # commit 后实例属性过期，close 前先取值，避免脱离会话后访问
                assistant_msg_id = assistant_msg.id
                done_project = {
                    "id": proj.id, "name": proj.name, "version": proj.version,
                    "demo_mode": demo_mode,
                }
                session.close()
            except Exception:
                session.rollback()
                session.close()
                raise

            yield _sse({"type": "done", "project": done_project,
                        "changes": values.get("prd_changes") or [],
                        "message_id": assistant_msg_id})
        except Exception as e:  # noqa: BLE001 流式错误统一转为 error 事件
            yield _sse({"type": "error", "message": f"执行出错：{e}"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _node_summary(node: str, payload: dict) -> str:
    """落库用的一行摘要。"""
    if node == "planner":
        intent = {"create": "新需求分析", "modify": "修改 PRD", "question": "解答疑问"}.get(
            payload.get("intent"), "")
        plan = " → ".join(s.get("title", "") for s in payload.get("plan") or [])
        return f"{intent}｜{plan}"
    if node == "research_summary":
        return str(payload.get("summary") or "")[:200]
    if node == "draft_prd":
        changes = payload.get("changes") or []
        return f"生成/更新 PRD，修改点 {len(changes)} 项"
    if node == "review":
        r = payload.get("review") or {}
        return f"评分 {r.get('score')}，{'通过' if r.get('passed') else '不通过'}"
    if node == "update_memory":
        return f"更新记忆 {len(payload.get('updates') or [])} 条"
    if node == "finalize":
        return str(payload.get("text") or "")[:200]
    return ""


def _clip(obj, n: int = MAX_STEP_DETAIL) -> dict:
    s = json.dumps(obj, ensure_ascii=False)
    if len(s) > n:
        return {"truncated": True, "preview": s[:n]}
    return obj if isinstance(obj, dict) else {"value": obj}


@router.get("/api/projects/{project_id}/prd.md")
def export_prd(project_id: str, user: AuthUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project or project.owner_id != user.id or not project.prd:
            raise HTTPException(404, "项目或 PRD 不存在")
        md = prd_to_markdown(project.prd, project.version)
        filename = f"{project.name or 'PRD'}-v{project.version}.md"
        from urllib.parse import quote

        return StreamingResponse(
            iter([md]),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    finally:
        db.close()
