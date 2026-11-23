"""数据模型：项目 / 消息 / 执行记录 / 产品记忆。"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """注册用户。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    salt: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AppSetting(Base):
    """全局键值配置（历史遗留表：早期全局 LLM 配置，现已按用户迁移）。"""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), default="")


class UserSetting(Base):
    """按用户隔离的配置（LLM Provider / API Key / 模型等）。"""

    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), default="")


class Project(Base):
    """一个产品项目 = 一个 PRD + 一组会话。"""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="未命名产品")
    status: Mapped[str] = mapped_column(String(20), default="active")
    version: Mapped[int] = mapped_column(Integer, default=0)  # PRD 版本号，每次变更 +1
    prd: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 最新结构化 PRD
    owner_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    facts: Mapped[list["MemoryFact"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Message(Base):
    """一轮对话消息。"""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user / assistant
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped["Project"] = relationship(back_populates="messages")


class RunStep(Base):
    """Agent 执行过程记录（节点 / 工具调用），用于前端回放执行流程。"""

    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(32), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(10))  # node / tool
    name: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(10), default="done")  # running / done / error
    summary: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MemoryFact(Base):
    """产品记忆：跨轮次沉淀的产品关键事实（目标用户、商业模式等）。"""

    __tablename__ = "memory_facts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(20), default="其他")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="facts")
