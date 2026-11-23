"""用户注册 / 登录 / 当前用户。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import create_token, hash_password, verify_password
from ..db import SessionLocal
from ..deps import AuthUser, get_current_user
from ..models import User

router = APIRouter()


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)


@router.post("/api/auth/register")
def register(req: AuthRequest):
    username = req.username.strip()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(409, "用户名已存在")
        salt, digest = hash_password(req.password)
        user = User(id=uuid.uuid4().hex, username=username,
                    password_hash=digest, salt=salt)
        db.add(user)
        db.commit()
        return {"token": create_token(user.id, user.username), "username": user.username}
    finally:
        db.close()


@router.post("/api/auth/login")
def login(req: AuthRequest):
    username = req.username.strip()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(req.password, user.salt, user.password_hash):
            raise HTTPException(401, "用户名或密码错误")
        return {"token": create_token(user.id, user.username), "username": user.username}
    finally:
        db.close()


@router.get("/api/auth/me")
def me(user: AuthUser = Depends(get_current_user)):
    return {"username": user.username}
