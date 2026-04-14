import asyncio
import hashlib

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus

from pyrogram.types import User, Chat


def get_hash(text) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


def get_md_chat_link(user: User | Chat):
    """获取 Markdown 格式的用户/聊天链接。"""
    if hasattr(user, "username") and user.username:
        return f"[{user.full_name}](https://t.me/{user.username})"

    if isinstance(user, User):
        return f"[{user.full_name}](tg://user?id={user.id})"
    else:
        # Pyrogram 的 chat.id 对于频道/超级群包含 -100 前缀，需要移除
        chat_id = abs(user.id)
        if str(chat_id).startswith("100"):
            chat_id = int(str(chat_id)[3:])
        return f"[{user.full_name}](https://t.me/c/{chat_id})"


def get_chat_link(chat: Chat):
    """获取聊天链接。"""
    if chat.username:
        return f"https://t.me/{chat.username}"
    elif chat.invite_link:
        return chat.invite_link
    else:
        # Pyrogram 的 chat.id 对于频道/超级群包含 -100 前缀，需要移除
        chat_id = abs(chat.id)
        if str(chat_id).startswith("100"):
            chat_id = int(str(chat_id)[3:])
        return f"https://t.me/c/{chat_id}"


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
