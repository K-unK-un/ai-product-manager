"""FastAPI 依赖：当前登录用户。"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from .auth import decode_token
from .db import SessionLocal
from .models import User


@dataclass
class AuthUser:
    id: str
    username: str


def get_current_user(authorization: str = Header(default="")) -> AuthUser:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "未登录")
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(401, str(e)) from e
    db = SessionLocal()
    try:
        user = db.get(User, payload["uid"])
        if not user:
            raise HTTPException(401, "用户不存在")
        return AuthUser(id=user.id, username=user.username)
    finally:
        db.close()


# 供路由使用：user: AuthUser = Depends(get_current_user)
user_dep = Depends(get_current_user)
