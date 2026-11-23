"""上策（ShangCe）— AI 产品经理 Agent 后端服务入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from .agent.graph import get_agent
from .auth import decode_token
from .db import init_db
from .llm_config import migrate_global_llm_settings, read_llm_config
from .routers import auth, chat, projects, settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    migrate_global_llm_settings()  # 旧全局 LLM 配置 → 用户 admin
    agent = get_agent()
    await agent.setup()  # 初始化 LangGraph 检查点数据库
    print("[上策] 启动完成 | LLM 配置按用户隔离（user_settings）")
    yield
    await agent.close()


app = FastAPI(title="上策 ShangCe - AI 产品经理", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(projects.router)
app.include_router(settings.router)


@app.get("/api/health")
def health(authorization: str = Header(default="")):
    # 已登录时返回该用户自己的 LLM 状态；未登录时用环境默认值
    user_id = None
    token = authorization.removeprefix("Bearer ").strip()
    if token:
        try:
            user_id = decode_token(token)["uid"]
        except ValueError:
            user_id = None
    cfg = read_llm_config(user_id)
    return {"status": "ok", "demo_mode": cfg["demo_mode"], "model": cfg["model"]}
