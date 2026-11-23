"""项目管理接口（按登录用户隔离）。"""
from fastapi import APIRouter, Depends, HTTPException

from ..agent.graph import get_agent
from ..db import SessionLocal
from ..deps import AuthUser, get_current_user
from ..models import MemoryFact, Message, Project, RunStep

router = APIRouter()


def _iso(dt) -> str:
    """数据库存的是 UTC（无时区标记），序列化时补 Z，避免前端误按本地时间解析。"""
    if dt is None:
        return ""
    return dt.isoformat() + ("Z" if dt.tzinfo is None else "")


def _project_brief(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "version": p.version,
        "prd_title": (p.prd or {}).get("title", "") if p.prd else "",
        "has_prd": p.prd is not None,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


@router.get("/api/projects")
def list_projects(user: AuthUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        projects = (
            db.query(Project)
            .filter(Project.owner_id == user.id)
            .order_by(Project.updated_at.desc())
            .all()
        )
        return {"projects": [_project_brief(p) for p in projects]}
    finally:
        db.close()


@router.get("/api/projects/{project_id}")
def get_project(project_id: str, user: AuthUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project or project.owner_id != user.id:
            raise HTTPException(404, "项目不存在")

        messages = (
            db.query(Message).filter(Message.project_id == project_id)
            .order_by(Message.created_at.asc()).all()
        )
        steps = (
            db.query(RunStep).filter(RunStep.project_id == project_id)
            .order_by(RunStep.created_at.asc(), RunStep.seq.asc()).all()
        )
        by_msg: dict[str, list] = {}
        for s in steps:
            by_msg.setdefault(s.message_id, []).append({
                "kind": s.kind, "name": s.name, "title": s.title,
                "status": s.status, "summary": s.summary, "detail": s.detail,
            })

        return {
            "project": _project_brief(project),
            "messages": [
                {
                    "id": m.id, "role": m.role, "content": m.content,
                    "created_at": _iso(m.created_at),
                    "steps": by_msg.get(m.id, []),
                }
                for m in messages
            ],
            "memory": [
                {"key": f.key, "value": f.value, "category": f.category,
                 "updated_at": _iso(f.updated_at)}
                for f in db.query(MemoryFact).filter(MemoryFact.project_id == project_id)
                .order_by(MemoryFact.updated_at.desc()).all()
            ],
            "prd": project.prd,
        }
    finally:
        db.close()


@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, user: AuthUser = Depends(get_current_user)):
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project or project.owner_id != user.id:
            raise HTTPException(404, "项目不存在")
        # 执行记录没有 ORM 级联关系，必须先删，否则会触发 SQLite 外键约束
        db.query(RunStep).filter(RunStep.project_id == project_id).delete(
            synchronize_session=False
        )
        db.delete(project)  # 消息、产品记忆由 ORM cascade 一并删除
        db.commit()
    finally:
        db.close()

    # 清理该项目的 LangGraph 检查点，避免残留孤儿线程数据
    try:
        await get_agent().delete_thread(project_id)
    except Exception:
        pass  # 检查点清理失败不影响项目删除结果
    return {"ok": True}
