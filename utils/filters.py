import re
from typing import Any

from aiogram.enums import ChatMemberStatus
from aiogram.filters import BaseFilter
from aiogram.types import ChatMemberUpdated, Message

from core.config import bs


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in bs.admins)


class NewMemberFilter(BaseFilter):
    async def __call__(self, event: ChatMemberUpdated) -> bool:
        old_user = event.old_chat_member.user
        new_user = event.new_chat_member.user
        if not event.from_user:
            return False
        if event.new_chat_member.status not in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }:
            return False
        if getattr(event.new_chat_member, "is_member", True) is False:
            return False
        if old_user and old_user.id == new_user.id:
            old_status = event.old_chat_member.status
            old_is_member = getattr(event.old_chat_member, "is_member", None)
            if old_status in {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            }:
                return False
            if old_status == ChatMemberStatus.RESTRICTED and old_is_member:
                return False
        return bool(event.from_user.id == new_user.id)


class StartPayloadFilter(BaseFilter):
    def __init__(self, pattern: str = ".*") -> None:
        self.pattern = re.compile(pattern)

    async def __call__(self, message: Message, command: Any = None) -> bool:
        args = getattr(command, "args", None)
        if args is None and message.text:
            parts = message.text.split(maxsplit=1)
            args = (
                parts[1] if len(parts) > 1 and parts[0].startswith("/start") else None
            )
        return bool(args and self.pattern.match(args))


is_admin = AdminFilter()
new_members = NewMemberFilter()
