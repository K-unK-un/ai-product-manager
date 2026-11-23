"""按用户隔离的 LLM 配置测试。"""
import os
import uuid

os.environ["LLM_PROVIDER"] = "demo"
os.environ["DATA_DIR"] = "data_test_settings"

from app.db import SessionLocal, init_db  # noqa: E402
from app.llm_config import read_llm_config, update_llm_config  # noqa: E402
from app.models import User  # noqa: E402


def _mk_user() -> str:
    db = SessionLocal()
    try:
        u = User(id=uuid.uuid4().hex, username=f"u{uuid.uuid4().hex[:12]}",
                 password_hash="x", salt="y")
        db.add(u)
        db.commit()
        return u.id
    finally:
        db.close()


def setup_module(_=None):
    init_db()


def test_user_api_key_isolated():
    uid1, uid2 = _mk_user(), _mk_user()

    update_llm_config(uid1, {
        "llm_provider": "deepseek",
        "llm_api_key": "sk-only-user1",
        "llm_model": "deepseek-chat",
    })

    c1 = read_llm_config(uid1)
    c2 = read_llm_config(uid2)

    assert c1["api_key"] == "sk-only-user1"
    assert c1["demo_mode"] is False
    assert c2["api_key"] == ""
    assert c2["demo_mode"] is True
    # 不带 user_id 的读取不得暴露任何用户的 Key
    assert read_llm_config()["api_key"] == ""
