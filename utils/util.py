import hashlib

from pyrogram.types import User


def get_hash(text) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()[:8]


def get_md_user_url(user: User):
    """获取 Markdown 格式的用户链接。"""
    if user.username:
        return f"[{user.full_name}](https://t.me/{user.username})"
    else:
        return f"[{user.full_name}](tg://user?id={user.id})"
    