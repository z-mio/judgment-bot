import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pyrogram import Client
from pyrogram.types import (
    CallbackQuery,
    Message,
    ChatPermissions,
    InlineKeyboardMarkup as Ikm,
    InlineKeyboardButton as Ikb,
    Chat,
    ChatMember,
)

from log import logger
from utils.aps import aps
from validator.base import BaseValidator, CQData


@dataclass(init=False)
class EasyValidator(BaseValidator[CallbackQuery]):
    validator_name: str = "easy_validator"

    def __init__(self, chat_id: int, user_id: int):
        super().__init__(chat_id, user_id)

        self.cli: Client | None = None
        self.chat: Chat | None = None
        self.chat_member: ChatMember | None = None
        self.verify_msg_id: int | None = None
        self.verify_msg: Message | None = None

    async def init(self, cli: Client):
        self.cli = cli
        self.chat = await cli.get_chat(self.chat_id)
        self.chat_member = await cli.get_chat_member(self.chat_id, self.user_id)
        if self.verify_msg_id and not self.verify_msg:
            self.verify_msg = await cli.get_messages(self.chat_id, self.verify_msg_id)

    def dumps(self):
        return json.dumps(
            {
                "chat_id": self.chat_id,
                "user_id": self.user_id,
                "verify_msg_id": self.verify_msg_id,
            }
        )

    @classmethod
    def loads(cls, obj: str) -> "EasyValidator":
        obj = json.loads(obj)
        v = cls(obj["chat_id"], obj["user_id"])
        v.verify_msg_id = obj["verify_msg_id"]
        return v

    async def start(self):
        await self.chat.restrict_member(self.user_id, ChatPermissions())
        random_number = random.randint(5, 10)
        text = (
            f"**击点前提勿请**, 证验行进 😀 击点时 😀 成变 🥵 后秒 __**{random_number}**__ "
            f"在请 [{self.chat_member.user.full_name}](tg://user?id={self.user_id})"
        )
        verify_msg = await self.cli.send_message(
            chat_id=self.chat_id, text=text, reply_markup=self.btn("one")
        )
        self.verify_msg = verify_msg
        self.verify_msg_id = verify_msg.id
        aps.add_job(
            id=f"{self.validator_id}|refresh_verify_msg",
            func=self.refresh_verify_msg,
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=random_number),
        )

    async def progress(self, content: CallbackQuery):
        data = CQData.parse(content.data)
        if data.operate == "admin":
            if data.value == "pass":
                await self.verify_pass(content)
            elif data.value == "fail":
                await self.admin_verify_fail(content)
        elif data.operate == "verify":
            if data.value == "pass":
                await self.verify_pass(content)
            elif data.value == "fail":
                await self.verify_fail(content)

    async def verify_pass(self, content: CallbackQuery):
        aps.remove_job(f"{self.validator_id}|verify_timeout")
        await self.chat.restrict_member(
            self.user_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_invite_users=True,
                can_add_web_page_previews=True,
            ),
        )
        await content.answer("验证通过")
        await self.verify_msg.delete()
        logger.debug(
            f"验证通过: 已在 {self.chat.full_name} 中通过验证: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def admin_verify_fail(self, content: CallbackQuery):
        aps.remove_job(f"{self.validator_id}|verify_timeout")
        await self.chat.ban_member(self.user_id)
        await content.answer("已永久踢出")
        await self.verify_msg.delete()
        logger.debug(
            f"验证失败(管理手动踢出): 已在 {self.chat.full_name} 中踢出: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_fail(self, content: CallbackQuery):
        until_date = datetime.now() + timedelta(seconds=60)
        await self.chat.ban_member(self.user_id, until_date)
        await content.answer("验证失败")
        await self.verify_msg.delete()
        logger.debug(
            f"验证失败: 已在 {self.chat.full_name} 中踢出: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_timeout(self):
        until_date = datetime.now() + timedelta(seconds=60)
        await self.chat.ban_member(self.user_id, until_date)
        await self.verify_msg.delete()
        logger.debug(
            f"验证超时: 已在 {self.chat.full_name} 中临时踢出60秒: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def refresh_verify_msg(self):
        text = f"""证验行进 😀 击点内秒 __**30**__ 在请 [{self.chat_member.user.full_name}](tg://user?id={self.user_id})"""
        await self.verify_msg.edit(text=text, reply_markup=self.btn("two"))
        aps.add_job(
            id=f"{self.validator_id}|verify_timeout",
            func=self.verify_timeout,
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=30),
        )

    def btn(self, step: Literal["one", "two"]):
        button = [
            Ikb(
                "✅",
                callback_data=str(CQData(self.validator_id, self.rid, "admin", "pass")),
            )
        ]
        match step:
            case "one":
                button.append(
                    Ikb(
                        "🥵",
                        callback_data=str(
                            CQData(self.validator_id, self.rid, "verify", "fail")
                        ),
                    )
                )
            case "two":
                button.append(
                    Ikb(
                        "😀",
                        callback_data=str(
                            CQData(self.validator_id, self.rid, "verify", "pass")
                        ),
                    )
                )
        button.append(
            Ikb(
                "❎",
                callback_data=str(CQData(self.validator_id, self.rid, "admin", "fail")),
            )
        )
        return Ikm([button])
