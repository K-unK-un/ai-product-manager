"""用户认证：密码加盐哈希 + HMAC 签名令牌（纯标准库实现，无第三方依赖）。

令牌格式类似 JWT：base64url(header).base64url(payload).base64url(hmac-sha256 签名)
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import settings


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> tuple[str, str]:
    """返回 (salt, digest)。"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return salt, digest


def verify_password(password: str, salt: str, digest: str) -> bool:
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return hmac.compare_digest(calc, digest)


def create_token(user_id: str, username: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "uid": user_id,
        "name": username,
        "exp": int(time.time()) + settings.token_expire_days * 86400,
    }
    body = f"{_b64e(json.dumps(header).encode())}.{_b64e(json.dumps(payload, ensure_ascii=False).encode())}"
    sig = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def decode_token(token: str) -> dict:
    """校验并解析令牌，失败抛 ValueError。"""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("令牌格式错误")
    body = f"{parts[0]}.{parts[1]}"
    try:
        got = _b64d(parts[2])
    except Exception as e:
        raise ValueError("令牌签名错误") from e
    expect = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expect, got):
        raise ValueError("令牌签名错误")
    try:
        payload = json.loads(_b64d(parts[1]))
    except Exception as e:
        raise ValueError("令牌载荷错误") from e
    if payload.get("exp", 0) < time.time():
        raise ValueError("令牌已过期，请重新登录")
    return payload
