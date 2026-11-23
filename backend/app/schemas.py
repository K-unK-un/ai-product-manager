"""API 请求模型。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000, description="用户本轮输入")
    project_id: str | None = Field(default=None, description="为空则自动创建新项目")
