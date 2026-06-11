import asyncio
import base64
import hashlib
from html import escape

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Chat, User


def get_hash(text: object) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


def get_md_chat_link(user: User | Chat) -> str:
    name_value = getattr(user, "full_name", None) or getattr(user, "title", None)
    name = escape(name_value if isinstance(name_value, str) else str(user.id))
    username = getattr(user, "username", None)
    if isinstance(username, str) and username:
        return f'<a href="https://t.me/{escape(username)}">{name}</a>'

    if isinstance(user, User):
        return f'<a href="tg://user?id={user.id}">{name}</a>'

    chat_id = abs(user.id or 0)
    if str(chat_id).startswith("100"):
        chat_id = int(str(chat_id)[3:])
    return f'<a href="https://t.me/c/{chat_id}">{name}</a>'


def html_code(value: object) -> str:
    return f"<code>{escape(str(value))}</code>"


def get_chat_link(chat: Chat) -> str:
    if chat.username:
        return f"https://t.me/{chat.username}"
    if chat.invite_link:
        return chat.invite_link

    chat_id = abs(chat.id or 0)
    if str(chat_id).startswith("100"):
        chat_id = int(str(chat_id)[3:])
    return f"https://t.me/c/{chat_id}"


async def member_is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
    except Exception:
        return False

    return member.status in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }


async def delete_messages(
    client: Client, chat_id: int, message_ids: list[int], delay: int = 5
) -> None:
    try:
        if delay:
            await asyncio.sleep(delay)
        ids = list(dict.fromkeys(message_ids))
        for index in range(0, len(ids), 100):
            chunk = ids[index : index + 100]
            if not chunk:
                continue
            try:
                await client.delete_messages(chat_id, chunk)
            except Exception:
                for message_id in chunk:
                    try:
                        await client.delete_messages(chat_id, message_id)
                    except Exception:
                        pass
    except Exception:
        pass


def decode_start_payload(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode()


async def build_start_link(client: Client, value: object) -> str:
    username = client.me.username if client.me else ""
    payload = base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")
    return f"https://t.me/{username}?start={payload}"
