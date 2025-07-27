import asyncio
import hashlib

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus

from pyrogram.types import User, Chat


def get_hash(text) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()[:8]


def get_md_user_url(user: User | Chat):
    """获取 Markdown 格式的用户链接。"""
    if user.username:
        return f"[{user.full_name}](https://t.me/{user.username})"
    else:
        return f"[{user.full_name}](tg://user?id={user.id})"


async def member_is_admin(cli: Client, cid: int, uid: int) -> bool:
    try:
        member = await cli.get_chat_member(cid, uid)
    except Exception:
        return False

    if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
        return True
    return False


async def delete_messages(cli: Client, chat_id: int, message_ids: list[int]):
    try:
        await asyncio.sleep(5)
        await cli.delete_messages(chat_id, message_ids)
    except Exception:
        ...
