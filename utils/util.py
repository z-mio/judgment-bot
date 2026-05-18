import asyncio
import hashlib
from html import escape

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Chat, User
from aiogram.utils.deep_linking import create_start_link


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

    chat_id = abs(user.id)
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

    chat_id = abs(chat.id)
    if str(chat_id).startswith("100"):
        chat_id = int(str(chat_id)[3:])
    return f"https://t.me/c/{chat_id}"


async def member_is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception:
        return False

    return member.status in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
    }


async def delete_messages(
    bot: Bot, chat_id: int, message_ids: list[int], delay: int = 5
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
                await bot.delete_messages(chat_id, chunk)
            except TelegramBadRequest:
                for message_id in chunk:
                    try:
                        await bot.delete_message(chat_id, message_id)
                    except TelegramBadRequest:
                        pass
    except Exception:
        pass


async def build_start_link(bot: Bot, value: object) -> str:
    return await create_start_link(bot, str(value), encode=True)
