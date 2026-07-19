"""
crypto.py - API Key 静态加密模块（AES-256-GCM）

使用 AES-256-GCM 对数据库中的敏感字段进行可逆加密。
加密密钥通过 PBKDF2-SHA256 从 COOKIE_SECRET 安全派生，
确保即使数据库文件泄露，API Key 也不会直接暴露。

密文格式（base64 编码）：12 字节 nonce + 密文（含内联 16 字节 GCM tag）
"""

import os
import base64
import hashlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---------------------------------------------------------------------------
# Key derivation — 从 COOKIE_SECRET 派生 AES-256 密钥 (32 字节)
# ---------------------------------------------------------------------------

_KDF_SALT = b"dfaos_api_key_kdf_v1__"  # 固定盐值，仅用于 KDF
_ENCRYPTION_KEY: bytes | None = None


def _get_encryption_key() -> bytes:
    """惰性加载加密密钥（首次调用时从 config 读取 COOKIE_SECRET 派生）"""
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY

    try:
        from config.config import settings
        cookie_secret = settings.get("cookie_secret", "")
    except Exception:
        cookie_secret = ""

    if not cookie_secret:
        # 无 COOKIE_SECRET（首次启动前），使用默认值
        # 生产环境必须设置 COOKIE_SECRET 环境变量
        cookie_secret = "DataFinderAgentOS-default-key-change-in-production"

    _ENCRYPTION_KEY = hashlib.pbkdf2_hmac(
        "sha256",
        cookie_secret.encode("utf-8"),
        _KDF_SALT,
        100_000,        # 10 万次迭代，与项目中密码哈希一致
        dklen=32,       # AES-256 需要 32 字节
    )
    return _ENCRYPTION_KEY


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def encrypt(plaintext: str) -> str:
    """
    使用 AES-256-GCM 加密字符串。
    返回 base64 编码的密文（含 nonce + 密文 + GCM tag），可直接存入 TEXT 列。
    空字符串不加密，原样返回。
    """
    if not plaintext:
        return ""

    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)          # 96-bit nonce，GCM 标准
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # 存储格式: nonce(12) + ciphertext(含 GCM tag)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(encrypted: str) -> str:
    """
    使用 AES-256-GCM 解密密文，返回原始字符串。
    如果输入为空，返回空字符串。
    如果解密失败（损坏数据或遗留明文），返回原始输入以确保向后兼容。
    """
    if not encrypted:
        return ""

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    try:
        data = base64.b64decode(encrypted)
    except Exception:
        # 不是有效的 base64 — 可能是遗留明文，直接返回
        return encrypted

    if len(data) < 29:   # nonce(12) + GCM_tag(16) + 至少 1 字节密文
        return encrypted

    nonce = data[:12]
    ciphertext = data[12:]

    try:
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception:
        # 解密失败（遗留明文或损坏数据），返回原始值
        return encrypted


def is_encrypted(value: str) -> bool:
    """
    检测值是否已被加密（用于迁移时判断是否需要加密）。
    """
    if not value:
        return True
    try:
        data = base64.b64decode(value)
        return len(data) >= 29
    except Exception:
        return False
