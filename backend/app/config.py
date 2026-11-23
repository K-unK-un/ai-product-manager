"""全局配置。

非敏感配置可通过环境变量覆盖（DATA_DIR、SECRET_KEY 等）；
LLM API Key 按用户保存在数据库中，不从环境变量读取。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 各服务商的默认 API 地址（OpenAI 兼容协议）
PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
}

PROVIDER_DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "qwen": "qwen-plus",
    "zhipu": "glm-4-flash",
    "moonshot": "moonshot-v1-8k",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # 默认 LLM 配置（API Key 只按用户保存在数据库中）
    llm_provider: str = "deepseek"
    llm_base_url: str = ""  # 留空则按 provider 取默认地址
    llm_model: str = ""     # 留空则按 provider 取默认模型
    llm_temperature: float = 0.3

    # 数据目录（SQLite 数据库 + LangGraph 检查点）
    data_dir: str = "data"

    # 用户认证：令牌签名密钥与有效期（部署时建议通过环境变量覆盖）
    secret_key: str = "shangce-dev-secret-please-change-in-production"
    token_expire_days: int = 7

    @property
    def resolved_model(self) -> str:
        return self.llm_model or PROVIDER_DEFAULT_MODELS.get(self.llm_provider, "deepseek-chat")

    @property
    def resolved_base_url(self) -> str | None:
        if self.llm_base_url:
            return self.llm_base_url
        return PROVIDER_BASE_URLS.get(self.llm_provider)


settings = Settings()

# 数据目录锚定：相对路径固定解析到 backend/ 下（与启动时的工作目录无关），
# 绝对路径（如 Docker 中的 /app/data）原样使用
_data = Path(settings.data_dir)
DATA_DIR = _data if _data.is_absolute() else (Path(__file__).resolve().parent.parent / _data).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
