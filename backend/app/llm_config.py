"""运行时 LLM 配置：按用户隔离（UserSetting 表），环境变量兜底。

前端「设置」页保存后调用 update_llm_config() + AgentRuntime.refresh(user_id)，
该用户的 LLM 与工具配置立即生效，无需重启服务。
"""
from .config import PROVIDER_BASE_URLS, PROVIDER_DEFAULT_MODELS, settings
from .db import SessionLocal
from .models import AppSetting, User, UserSetting

_FIELDS = ("llm_provider", "llm_api_key", "llm_model", "llm_base_url")


def read_llm_config(user_id: str | None = None) -> dict:
    """读取指定用户的 LLM 配置；user_id 为空时只看环境变量默认值。

    每个用户的 Key 只从自己的 UserSetting 行读取，互不可见；
    用户未配置时回退到环境变量（部署级默认值）。
    """
    rows = {}
    if user_id:
        db = SessionLocal()
        try:
            rows = {
                s.key: s.value
                for s in db.query(UserSetting).filter(UserSetting.user_id == user_id).all()
            }
        except Exception:
            # 表尚未初始化（如纯图测试环境），回退为仅环境变量配置
            rows = {}
        finally:
            db.close()

    def pick(key: str, env_val: str) -> str:
        v = rows.get(key)
        return v if v not in (None, "") else (env_val or "")

    provider = pick("llm_provider", settings.llm_provider)
    # Key 只按用户读取，不回退全局环境变量，保证用户之间完全隔离
    api_key = rows.get("llm_api_key") or ""
    model = pick("llm_model", settings.llm_model) or PROVIDER_DEFAULT_MODELS.get(provider, "deepseek-chat")
    base_url = pick("llm_base_url", settings.llm_base_url) or PROVIDER_BASE_URLS.get(provider, "")
    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "demo_mode": (provider == "demo") or not api_key,
    }


def update_llm_config(user_id: str, updates: dict) -> None:
    """upsert 指定用户的配置项；value 为空字符串表示清除。"""
    db = SessionLocal()
    try:
        for key, value in updates.items():
            if key not in _FIELDS or value is None:
                continue
            row = db.get(UserSetting, (user_id, key))
            if row:
                row.value = value
            else:
                db.add(UserSetting(user_id=user_id, key=key, value=value))
        db.commit()
    finally:
        db.close()


def migrate_global_llm_settings() -> None:
    """把旧版全局 LLM 配置迁移到用户 admin 名下（一次性）。

    迁移后删除全局行，避免任何用户通过全局配置读到别人的 Key。
    找不到 admin 用户时保留原数据并打印警告，不做有损操作。
    """
    db = SessionLocal()
    try:
        # 清理已下线的 Tavily 配置
        db.query(UserSetting).filter(UserSetting.key == "tavily_api_key").delete()
        db.query(AppSetting).filter(AppSetting.key == "tavily_api_key").delete()
        db.commit()

        rows = db.query(AppSetting).filter(AppSetting.key.in_(_FIELDS)).all()
        if not rows:
            return
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("[上策] 警告：存在全局 LLM 配置，但未找到 admin 用户，暂未迁移")
            return
        for row in rows:
            setting = db.get(UserSetting, (admin.id, row.key))
            if setting:
                setting.value = row.value
            else:
                db.add(UserSetting(user_id=admin.id, key=row.key, value=row.value))
            db.delete(row)
        db.commit()
        print(f"[上策] 已将 {len(rows)} 条全局 LLM 配置迁移到用户 admin")
    finally:
        db.close()
