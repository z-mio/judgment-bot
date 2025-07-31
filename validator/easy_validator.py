import asyncio
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
    LinkPreviewOptions,
)

from log import logger
from services.redis_client import rc
from utils.aps import aps
from utils.util import build_start_link, get_chat_link, get_md_chat_link
from validator.base import BaseValidator, CQData, StartData


@dataclass(init=False)
class EasyValidator(BaseValidator):
    validator_name: str = "easy_validator"

    def __init__(self, chat_id: int, user_id: int):
        super().__init__(chat_id, user_id)

        self.cli: Client | None = None
        self.chat: Chat | None = None
        self.chat_member: ChatMember | None = None
        self.verify_msg_id: int | None = None
        self.verify_msg: Message | None = None

    async def init(self, cli: Client) -> bool:
        self.cli = cli
        self.chat = await cli.get_chat(self.chat_id)
        try:
            self.chat_member = await cli.get_chat_member(self.chat_id, self.user_id)
        except Exception as e:
            logger.error(f"获取群成员信息失败: {e}")
            return False
        if self.verify_msg_id and not self.verify_msg:
            self.verify_msg = await cli.get_messages(self.chat_id, self.verify_msg_id)
        return True

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

    async def start(self, cli: Client):
        await self.chat.restrict_member(self.user_id, ChatPermissions())
        random_number = random.randint(5, 10)
        text = (
            f"**击点前提勿请**, 证验行进 😀 击点时 😀 成变 🥵 后秒 __**{random_number}**__ "
            f"在请 {get_md_chat_link(self.chat_member.user)}"
        )
        verify_msg = await self.cli.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=self.btn(cli, "one"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        self.verify_msg = verify_msg
        self.verify_msg_id = verify_msg.id
        aps.add_job(
            id=f"{self.validator_id}|refresh_verify_msg",
            func=self.refresh_verify_msg,
            args=(cli,),
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=random_number),
        )
        await rc.set(self.validator_id, self.dumps())

    async def progress(self, _, content: CallbackQuery | Message):
        if isinstance(content, CallbackQuery):
            data = CQData.parse(content.data)
            if data.operate == "admin":
                if data.value == "pass":
                    await self.admin_verify_pass(content)
                elif data.value == "fail":
                    await self.admin_verify_fail(content)
        elif isinstance(content, Message):
            data = StartData.parse(content.text.replace("/start ", ""))
            if data.value == "pass":
                await self.verify_pass(content)
            elif data.value == "fail":
                await self.verify_fail(content)

        await self.verify_end()

    async def admin_verify_fail(self, content: CallbackQuery):
        if aps.get_job(f"{self.validator_id}|verify_timeout"):
            aps.remove_job(f"{self.validator_id}|verify_timeout")

        await self.chat.ban_member(self.user_id)
        await content.answer("已永久踢出")
        await self.end_text("管理手动击落")
        logger.debug(
            f"验证失败(管理手动踢出): 已在 {self.chat.full_name} 中踢出: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def admin_verify_pass(self, content: CallbackQuery):
        if aps.get_job(f"{self.validator_id}|verify_timeout"):
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
        await content.answer("已通过")
        await self.end_text("管理手动通过")
        logger.debug(
            f"验证通过: 已在 {self.chat.full_name} 中通过验证: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_pass(self, content: Message):
        if aps.get_job(f"{self.validator_id}|verify_timeout"):
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
        await content.reply(
            f"**{get_md_chat_link(self.verify_msg.chat)} 验证通过**",
            reply_markup=Ikm(
                [[Ikb("返回群组", url=get_chat_link(self.verify_msg.chat))]]
            ),
        )
        await self.end_text("验证通过")
        logger.debug(
            f"验证通过: 已在 {self.chat.full_name} 中通过验证: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_fail(self, content: Message):
        if aps.get_job(f"{self.validator_id}|refresh_verify_msg"):
            aps.remove_job(f"{self.validator_id}|refresh_verify_msg")

        until_date = datetime.now() + timedelta(seconds=60)
        await self.chat.ban_member(self.user_id, until_date)
        await content.reply(
            f"**{get_md_chat_link(self.verify_msg.chat)} 验证失败**\n请 1 分钟后重试",
        )
        await self.end_text("验证未通过, 已击落")
        logger.debug(
            f"验证失败: 已在 {self.chat.full_name} 中踢出: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_timeout(self):
        until_date = datetime.now() + timedelta(seconds=60)
        await self.chat.ban_member(self.user_id, until_date)
        await self.end_text("验证超时, 已击落")
        await self.verify_end()
        logger.debug(
            f"验证超时: 已在 {self.chat.full_name} 中临时踢出60秒: {self.chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def refresh_verify_msg(self, cli: Client):
        text = f"""证验行进 😀 击点内秒 __**30**__ 在请 {get_md_chat_link(self.chat_member.user)}"""
        await self.verify_msg.edit(
            text=text,
            reply_markup=self.btn(cli, "two"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        aps.add_job(
            id=f"{self.validator_id}|verify_timeout",
            func=self.verify_timeout,
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=30),
        )

    def btn(self, cli: Client, step: Literal["one", "two"]):
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
                        url=build_start_link(
                            cli,
                            StartData(self.validator_id, self.rid, "verify", "fail"),
                        ),
                    )
                )
            case "two":
                button.append(
                    Ikb(
                        "😀",
                        url=build_start_link(
                            cli,
                            StartData(self.validator_id, self.rid, "verify", "pass"),
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

    async def end_text(self, text: str):
        await self.verify_msg.edit(
            f"{get_md_chat_link(self.chat_member.user)} {text}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        await asyncio.sleep(3)
        await self.verify_msg.delete()

    async def verify_end(self):
        await rc.delete(self.validator_id)
