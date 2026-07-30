import re
from typing import Any

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatMemberUpdated, Message

from core.config import bs


async def _is_admin(_: Any, __: Any, message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in bs.admins)


is_admin = filters.create(_is_admin)


async def _new_members(_: Any, __: Any, event: ChatMemberUpdated) -> bool:
    try:
        if not event.from_user or not event.new_chat_member:
            return False

        old_member = event.old_chat_member
        new_member = event.new_chat_member
        new_user = new_member.user
        if not new_user:
            return False
        if new_member.status not in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }:
            return False
        if not new_member.is_member:
            return False
        if old_member and old_member.user and old_member.user.id == new_user.id:
            old_status = old_member.status
            old_is_member = old_member.is_member
            if old_status in {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            }:
                return False
            if old_status == ChatMemberStatus.RESTRICTED and old_is_member:
                return False
        return bool(event.from_user.id == new_user.id)
    except Exception:
        return False


new_members = filters.create(_new_members)


def start_filter(pattern: str = ".*") -> filters.Filter:
    compiled = re.compile(pattern)

    async def func(_: Any, __: Any, message: Message) -> bool:
        if not message.text:
            return False
        parts = message.text.split(maxsplit=1)
        if not parts or parts[0].split("@", 1)[0] != "/start":
            return False
        if len(parts) < 2 or not parts[1]:
            return False
        return bool(compiled.match(parts[1]))

    return filters.create(func)


async def _guest_bot_message(_: Any, __: Any, msg: Message) -> bool:
    return bool(msg.guest_bot_caller_chat or msg.guest_bot_caller_user)


guest_bot_message = filters.create(_guest_bot_message)
