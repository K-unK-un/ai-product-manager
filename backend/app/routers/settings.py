"""LLM 配置接口：前端「设置」页显式配置服务商 / API Key / 模型，保存后立即生效。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..agent.graph import get_agent
from ..deps import AuthUser, get_current_user
from ..llm_config import read_llm_config, update_llm_config

router = APIRouter()

PROVIDERS = ["deepseek", "openai", "qwen", "zhipu", "moonshot", "demo"]


def _public_config(user_id: str) -> dict:
    cfg = read_llm_config(user_id)
    key = cfg["api_key"]
    masked = ""
    if key:
        masked = f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "已配置"
    return {
        "provider": cfg["provider"],
        "model": cfg["model"],
        "base_url": cfg["base_url"],
        "has_api_key": bool(key),
        "api_key_masked": masked,
        "demo_mode": cfg["demo_mode"],
    }


@router.get("/api/settings/llm")
def get_llm_settings(user: AuthUser = Depends(get_current_user)):
    return _public_config(user.id)


class LlmSettingsRequest(BaseModel):
    provider: str | None = None
    api_key: str | None = None          # 空字符串 = 清除已保存的 Key
    model: str | None = None
    base_url: str | None = None


@router.put("/api/settings/llm")
def put_llm_settings(req: LlmSettingsRequest, user: AuthUser = Depends(get_current_user)):
    updates = {}
    if req.provider is not None:
        provider = req.provider.strip()
        if provider not in PROVIDERS:
            from fastapi import HTTPException
            raise HTTPException(400, f"不支持的服务商：{provider}")
        updates["llm_provider"] = provider
    if req.api_key is not None:
        updates["llm_api_key"] = req.api_key.strip()
    if req.model is not None:
        updates["llm_model"] = req.model.strip()
    if req.base_url is not None:
        updates["llm_base_url"] = req.base_url.strip()

    update_llm_config(user.id, updates)
    get_agent().refresh(user.id)  # 只重建该用户的 LLM 与图，立即生效
    return _public_config(user.id)
