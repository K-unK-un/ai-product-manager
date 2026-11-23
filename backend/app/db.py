"""SQLite 数据库连接（SQLAlchemy）。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATA_DIR

DB_PATH = DATA_DIR / "shangce.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

# 开启 WAL 模式，允许异步流式接口与写入并发
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    from . import models  # noqa: F401  确保模型注册

    # 轻量迁移：老库（无 owner_id 列）升级
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "projects" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("projects")]
        if "owner_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE projects ADD COLUMN owner_id VARCHAR(32)"))

    Base.metadata.create_all(engine)
