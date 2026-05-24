import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, cast

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatPermissions,
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from i18n import t_
from log import logger
from services.redis_client import rc
from utils.aps import aps
from utils.util import build_start_link, get_chat_link, get_md_chat_link
from validator.base import BaseValidator, CQData, StartData


def full_chat_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_invite_users=True,
        can_add_web_page_previews=True,
    )


def chat_display_name(chat: Chat | None) -> str:
    if not chat:
        return "未知群组"
    return getattr(chat, "full_name", None) or chat.title or str(chat.id)


@dataclass(init=False)
class EasyValidator(BaseValidator):
    validator_name: str = "easy_validator"

    def __init__(self, chat_id: int, user_id: int):
        super().__init__(chat_id, user_id)

        self.bot: Bot | None = None
        self.chat: Chat | None = None
        self.chat_member: Any | None = None
        self.verify_msg_id: int | None = None

    @property
    def current_chat(self) -> Chat:
        if not self.chat:
            raise RuntimeError("validator chat is not initialized")
        return self.chat

    @property
    def current_chat_member(self) -> Any:
        if not self.chat_member:
            raise RuntimeError("validator chat member is not initialized")
        return self.chat_member

    @property
    def current_verify_msg_id(self) -> int:
        if self.verify_msg_id is None:
            raise RuntimeError("validator message is not initialized")
        return self.verify_msg_id

    async def init(self, bot: Bot) -> bool:
        self.bot = bot
        self.chat = await bot.get_chat(self.chat_id)
        try:
            self.chat_member = await bot.get_chat_member(self.chat_id, self.user_id)
        except Exception as e:
            logger.error(f"获取群成员信息失败: {e}")
            return False
        return True

    def dumps(self) -> str:
        return json.dumps(
            {
                "chat_id": self.chat_id,
                "user_id": self.user_id,
                "verify_msg_id": self.current_verify_msg_id,
            }
        )

    @classmethod
    def loads(cls, obj: str) -> "EasyValidator":
        data = cast(dict[str, int | None], json.loads(obj))
        chat_id = data["chat_id"]
        user_id = data["user_id"]
        verify_msg_id = data["verify_msg_id"]
        if chat_id is None or user_id is None:
            raise ValueError("invalid validator data")
        v = cls(chat_id, user_id)
        v.verify_msg_id = verify_msg_id
        return v

    async def start(self, bot: Bot) -> None:
        await bot.restrict_chat_member(
            self.chat_id, self.user_id, permissions=ChatPermissions()
        )
        random_number = random.randint(5, 10)
        cn_text = (
            f"<b>击点前提勿请</b>, 证验行进 😀 击点时 😀 成变 🥵 ,后秒 <b>{random_number}</b> "
            f"在请 {get_md_chat_link(self.current_chat_member.user)}"
        )
        en_text = (
            f"{get_md_chat_link(self.current_chat_member.user)} Please wait <b>{random_number}</b> seconds, "
            f"then click 😀 to verify once 🥵 changes to 😀. "
            f"<b>Do not click early!</b>"
        )
        text = f"{cn_text}\n\n{en_text}"
        verify_msg = await bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=await self.btn(bot, "one"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        self.verify_msg_id = verify_msg.message_id
        aps.add_job(
            id=f"{self.validator_id}|refresh_verify_msg",
            func=self.refresh_verify_msg,
            args=(bot,),
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=random_number),
        )
        await rc.set(self.validator_id, self.dumps())

    async def progress(
        self, bot: Bot, content: CallbackQuery | Message, payload: str | None = None
    ) -> None:
        if isinstance(content, CallbackQuery):
            if not content.data:
                raise ValueError("callback data is empty")
            cq_data = CQData.parse(content.data)
            if cq_data.operate == "admin":
                if cq_data.value == "pass":
                    await self.admin_verify_pass(bot, content)
                elif cq_data.value == "fail":
                    await self.admin_verify_fail(bot, content)
        elif isinstance(content, Message):
            text = payload or content.text
            if not text:
                raise ValueError("start payload is empty")
            start_data = StartData.parse(text.replace("/start ", ""))
            if start_data.value == "pass":
                await self.verify_pass(bot, content)
            elif start_data.value == "fail":
                await self.verify_fail(bot, content)

        await self.verify_end()

    async def admin_verify_fail(self, bot: Bot, content: CallbackQuery) -> None:
        _t = t_[content.from_user]

        if aps.get_job(f"{self.validator_id}|verify_timeout"):
            aps.remove_job(f"{self.validator_id}|verify_timeout")

        await bot.ban_chat_member(self.chat_id, self.user_id)
        await content.answer(_t("已永久踢出"))
        await self.end_text(
            bot, _t(f"由管理 {get_md_chat_link(content.from_user)} 手动击落")
        )
        logger.debug(
            f"验证失败(管理手动踢出): 已在 {chat_display_name(self.chat)} 中踢出: {self.current_chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def admin_verify_pass(self, bot: Bot, content: CallbackQuery) -> None:
        _t = t_[content.from_user]

        if aps.get_job(f"{self.validator_id}|verify_timeout"):
            aps.remove_job(f"{self.validator_id}|verify_timeout")

        await bot.restrict_chat_member(
            self.chat_id,
            self.user_id,
            permissions=full_chat_permissions(),
        )
        await content.answer(_t("已通过"))
        await self.end_text(
            bot, _t(f"由管理 {get_md_chat_link(content.from_user)} 手动通过")
        )
        logger.debug(
            f"验证通过: 已在 {chat_display_name(self.chat)} 中通过验证: {self.current_chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_pass(self, bot: Bot, content: Message) -> None:
        _t = t_[content]

        if aps.get_job(f"{self.validator_id}|verify_timeout"):
            aps.remove_job(f"{self.validator_id}|verify_timeout")

        await bot.restrict_chat_member(
            self.chat_id,
            self.user_id,
            permissions=full_chat_permissions(),
        )
        await content.reply(
            _t(f"<b>{get_md_chat_link(self.current_chat)} 验证通过</b>"),
            reply_markup=Ikm(
                inline_keyboard=[
                    [Ikb(text=_t("返回群组"), url=get_chat_link(self.current_chat))]
                ]
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        await self.end_text(bot, _t("验证通过"))
        logger.debug(
            f"验证通过: 已在 {chat_display_name(self.chat)} 中通过验证: {self.current_chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_fail(self, bot: Bot, content: Message) -> None:
        _t = t_[content]

        if aps.get_job(f"{self.validator_id}|refresh_verify_msg"):
            aps.remove_job(f"{self.validator_id}|refresh_verify_msg")

        until_date = datetime.now() + timedelta(seconds=60)
        await bot.ban_chat_member(self.chat_id, self.user_id, until_date=until_date)
        await content.reply(
            _t(
                f"<b>{get_md_chat_link(self.current_chat)} 验证失败</b>\n请 1 分钟后重试"
            ),
        )
        await self.end_text(bot, "验证未通过, 已击落")
        logger.debug(
            f"验证失败: 已在 {chat_display_name(self.chat)} 中踢出: {self.current_chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def verify_timeout(self, bot: Bot) -> None:
        if not await rc.exists(self.validator_id):
            return

        until_date = datetime.now() + timedelta(seconds=60)
        await bot.ban_chat_member(self.chat_id, self.user_id, until_date=until_date)
        await self.end_text(bot, "验证超时, 已击落")
        await self.verify_end()
        logger.debug(
            f"验证超时: 已在 {chat_display_name(self.chat)} 中临时踢出60秒: {self.current_chat_member.user.full_name} | {self.user_id} | {self.chat_id}"
        )

    async def refresh_verify_msg(self, bot: Bot) -> None:
        if not await rc.exists(self.validator_id):
            return

        cn_text = f"""证验行进 😀 击点内秒 <b>30</b> 在请 {get_md_chat_link(self.current_chat_member.user)}"""
        en_text = f"""{get_md_chat_link(self.current_chat_member.user)} Please complete verification by clicking 😀 within <b>30</b> seconds"""
        text = f"{cn_text}\n\n{en_text}"
        try:
            await bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.current_verify_msg_id,
                text=text,
                reply_markup=await self.btn(bot, "two"),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except TelegramBadRequest:
            await self.verify_end()
            return
        aps.add_job(
            id=f"{self.validator_id}|verify_timeout",
            func=self.verify_timeout,
            args=(bot,),
            trigger="date",
            run_date=datetime.now() + timedelta(seconds=30),
        )

    async def btn(self, bot: Bot, step: Literal["one", "two"]) -> Ikm:
        button = [
            Ikb(
                text="✅",
                callback_data=str(CQData(self.validator_id, self.rid, "admin", "pass")),
            )
        ]
        match step:
            case "one":
                button.append(
                    Ikb(
                        text="🥵",
                        url=await build_start_link(
                            bot,
                            StartData(self.validator_id, self.rid, "verify", "fail"),
                        ),
                    )
                )
            case "two":
                button.append(
                    Ikb(
                        text="😀",
                        url=await build_start_link(
                            bot,
                            StartData(self.validator_id, self.rid, "verify", "pass"),
                        ),
                    )
                )
        button.append(
            Ikb(
                text="❎",
                callback_data=str(CQData(self.validator_id, self.rid, "admin", "fail")),
            )
        )
        return Ikm(inline_keyboard=[button])

    async def end_text(self, bot: Bot, text: str) -> None:
        try:
            await bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.current_verify_msg_id,
                text=f"{get_md_chat_link(self.current_chat_member.user)} {text}",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            await asyncio.sleep(3)
            await bot.delete_message(self.chat_id, self.current_verify_msg_id)
        except TelegramBadRequest:
            pass

    async def verify_end(self) -> None:
        for job_id in (
            f"{self.validator_id}|refresh_verify_msg",
            f"{self.validator_id}|verify_timeout",
        ):
            if aps.get_job(job_id):
                aps.remove_job(job_id)
        await rc.delete(self.validator_id)
