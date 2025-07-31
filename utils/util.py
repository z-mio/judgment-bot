import asyncio
import hashlib

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus

from pyrogram.types import User, Chat


def get_hash(text) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


def get_md_chat_link(user: User | Chat):
    """获取 Markdown 格式的用户链接。"""
    if user.username:
        return f"[{user.full_name}](https://t.me/{user.username})"
    else:
        if isinstance(user, User):
            return f"[{user.full_name}](tg://user?id={user.id})"
        else:
            return f"[{user.full_name}](https://t.me/c/-100{user.id})"


def get_chat_link(chat: Chat):
    if chat.username:
        return f"https://t.me/{chat.username}"
    else:
        return f"https://t.me/c/-100{chat.id}"


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


def build_start_link(cli: Client, value):
    return f"https://t.me/{cli.me.username}?start={value}"
