import asyncio
import json
import random
import re
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Self, cast

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    CallbackQuery,
    Chat,
    ChatMember,
    ChatMemberUpdated,
    ChatPermissions,
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from log import logger
from plugins.filters import new_members, start_filter
from plugins.helpers import (
    build_start_link,
    decode_start_payload,
    get_chat_link,
    get_hash,
    get_md_chat_link,
    delete_member_messages,
)
from services.redis_client import rc

VERIFY_NAME = "easy_validator"
VERIFY_REFRESH_MIN_SECONDS = 5
VERIFY_REFRESH_MAX_SECONDS = 10
VERIFY_TIMEOUT_SECONDS = 30
VERIFY_RETRY_SECONDS = 60

FinalState = Literal["passed", "failed", "timeout"]
STATE_WAITING_CLICK = "waiting_click"
STATE_PASSED: FinalState = "passed"
STATE_FAILED: FinalState = "failed"
STATE_TIMEOUT: FinalState = "timeout"

TaskName = Literal["refresh", "timeout"]
VERIFY_TASKS: dict[str, asyncio.Task[None]] = {}
SESSION_LOCKS: dict[str, asyncio.Lock] = {}


@dataclass(slots=True)
class CQData:
    validator_id: str
    rid: str
    operate: str
    value: str

    prefix = "@"
    suffix = ":"

    @classmethod
    def parse(cls, data: str) -> Self:
        match = re.search(rf"{cls.prefix}(.*?){cls.suffix}", data)
        if not match:
            raise ValueError("invalid callback data")

        validator_id = match[1]
        parts = data.replace(f"{cls.prefix}{validator_id}{cls.suffix}", "").split(",")
        if len(parts) != 3:
            raise ValueError("invalid callback data")

        rid, operate, value = parts
        return cls(validator_id, rid, operate, value)

    def __str__(self) -> str:
        return f"{self.prefix}{self.validator_id}{self.suffix}{self.rid},{self.operate},{self.value}"


@dataclass(slots=True)
class StartData:
    validator_id: str
    rid: str
    operate: str
    value: str

    sep = "="

    @classmethod
    def parse(cls, data: str) -> Self:
        parts = data.split(cls.sep, 3)
        if len(parts) != 4:
            raise ValueError("invalid start data")

        validator_id, rid, operate, value = parts
        return cls(validator_id, rid, operate, value)

    def __str__(self) -> str:
        return self.sep.join((self.validator_id, self.rid, self.operate, self.value))


@dataclass(slots=True)
class VerifySession:
    chat_id: int
    user_id: int
    rid: str
    verify_msg_id: int | None = None
    state: str = STATE_WAITING_CLICK

    @classmethod
    def create(cls, chat_id: int, user_id: int) -> Self:
        return cls(chat_id=chat_id, user_id=user_id, rid=secrets.token_urlsafe(8))

    @classmethod
    def loads(cls, raw: str) -> Self:
        data = cast(dict[str, Any], json.loads(raw))
        chat_id = data["chat_id"]
        user_id = data["user_id"]
        verify_msg_id = data["verify_msg_id"]
        rid = data["rid"]
        state = data.get("state", STATE_WAITING_CLICK)

        if not isinstance(chat_id, int):
            raise ValueError("invalid chat_id")
        if not isinstance(user_id, int):
            raise ValueError("invalid user_id")
        if not isinstance(verify_msg_id, int):
            raise ValueError("invalid verify_msg_id")
        if not isinstance(rid, str):
            raise ValueError("invalid rid")
        if not isinstance(state, str):
            raise ValueError("invalid state")

        return cls(
            chat_id=chat_id,
            user_id=user_id,
            rid=rid,
            verify_msg_id=verify_msg_id,
            state=state,
        )

    @property
    def validator_id(self) -> str:
        return get_hash(f"{VERIFY_NAME}_{self.chat_id}_{self.user_id}")[:8]

    @property
    def current_verify_msg_id(self) -> int:
        if self.verify_msg_id is None:
            raise RuntimeError("verify message is not initialized")
        return self.verify_msg_id

    def dumps(self) -> str:
        return json.dumps(
            {
                "chat_id": self.chat_id,
                "user_id": self.user_id,
                "verify_msg_id": self.current_verify_msg_id,
                "rid": self.rid,
                "state": self.state,
            },
            separators=(",", ":"),
        )


@dataclass(slots=True)
class VerifyContext:
    session: VerifySession
    chat: Chat
    member: ChatMember


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
        can_add_web_page_previews=True,
        can_react_to_messages=True,
        can_edit_tag=True,
        can_invite_users=True,
    )


def chat_display_name(chat: Chat | None) -> str:
    if not chat:
        return "未知群组"
    return chat.full_name or str(chat.id)


def task_key(session: VerifySession, name: TaskName) -> str:
    return f"{session.validator_id}:{session.rid}:{name}"


def session_lock(validator_id: str) -> asyncio.Lock:
    lock = SESSION_LOCKS.get(validator_id)
    if lock is None:
        lock = asyncio.Lock()
        SESSION_LOCKS[validator_id] = lock
    return lock


def schedule_verify_task(
    session: VerifySession,
    name: TaskName,
    delay: int,
    task_factory: Callable[[], Awaitable[None]],
) -> None:
    key = task_key(session, name)
    if old_task := VERIFY_TASKS.get(key):
        old_task.cancel()

    async def runner() -> None:
        try:
            await asyncio.sleep(delay)
            await task_factory()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(e)
            logger.error(f"验证任务执行失败: {key}")

    task = asyncio.create_task(runner())
    VERIFY_TASKS[key] = task

    def cleanup(done_task: asyncio.Task[None]) -> None:
        if VERIFY_TASKS.get(key) is done_task:
            VERIFY_TASKS.pop(key, None)

    task.add_done_callback(cleanup)


def cancel_verify_tasks(session: VerifySession) -> None:
    for name in cast(tuple[TaskName, TaskName], ("refresh", "timeout")):
        if task := VERIFY_TASKS.pop(task_key(session, name), None):
            task.cancel()


async def cancel_all_verify_tasks() -> None:
    tasks = list(VERIFY_TASKS.values())
    VERIFY_TASKS.clear()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def save_session(session: VerifySession) -> None:
    await rc.set(session.validator_id, session.dumps())


async def load_session(validator_id: str) -> VerifySession | None:
    raw = await rc.get(validator_id)
    if not raw:
        return None
    if not isinstance(raw, str):
        raise ValueError("invalid session data")
    return VerifySession.loads(raw)


async def finish_session(session: VerifySession, final_state: FinalState) -> bool:
    async with session_lock(session.validator_id):
        current = await load_session(session.validator_id)
        if not current:
            return False
        if current.rid != session.rid or current.state != STATE_WAITING_CLICK:
            return False

        current.state = final_state
        await save_session(current)
        return True


async def delete_session_if_current(session: VerifySession) -> None:
    async with session_lock(session.validator_id):
        current = await load_session(session.validator_id)
        if current and current.rid == session.rid:
            await rc.delete(session.validator_id)


async def is_current_waiting(session: VerifySession) -> bool:
    current = await load_session(session.validator_id)
    return bool(
        current and current.rid == session.rid and current.state == STATE_WAITING_CLICK
    )


def final_state_from_value(value: str) -> FinalState | None:
    if value == "pass":
        return STATE_PASSED
    if value == "fail":
        return STATE_FAILED
    return None


async def decode_callback_data(callback: CallbackQuery) -> CQData | None:
    if not callback.data:
        return None
    data_text = (
        callback.data.decode() if isinstance(callback.data, bytes) else callback.data
    )
    try:
        return CQData.parse(data_text)
    except Exception:
        return None


async def decode_start_data(message: Message) -> StartData | None:
    text = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        text = parts[1] if len(parts) > 1 else ""

    try:
        try:
            text = decode_start_payload(text)
        except Exception:
            pass
        return StartData.parse(text)
    except Exception:
        return None


async def load_current_session(validator_id: str, rid: str) -> VerifySession | None:
    session = await load_session(validator_id)
    if not session or session.rid != rid:
        return None
    return session


async def init_context(client: Client, session: VerifySession) -> VerifyContext | None:
    try:
        chat = await client.get_chat(session.chat_id)
        member = await client.get_chat_member(session.chat_id, session.user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("初始化验证上下文失败")
        return None

    return VerifyContext(session=session, chat=chat, member=member)


async def send_start_verify_message(client: Client, context: VerifyContext) -> None:
    session = context.session
    await client.restrict_chat_member(
        session.chat_id, session.user_id, permissions=ChatPermissions()
    )

    wait_seconds = random.randint(
        VERIFY_REFRESH_MIN_SECONDS, VERIFY_REFRESH_MAX_SECONDS
    )
    user_link = get_md_chat_link(context.member.user)
    text = (
        f"**击点前提勿请**, 证验行进 😀 击点时 😀 成变 🥵 ,后秒 **{wait_seconds}** "
        f"在请 {user_link}\n\n"
        f"{user_link} Please wait **{wait_seconds}** seconds, "
        f"then click 😀 to verify once 🥵 changes to 😀. "
        f"**Do not click early!**"
    )
    verify_msg = await client.send_message(
        chat_id=session.chat_id,
        text=text,
        reply_markup=await verify_buttons(client, session, "one"),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    session.verify_msg_id = verify_msg.id
    session.state = STATE_WAITING_CLICK
    await save_session(session)
    try:
        await delete_member_messages(
            client, session.chat_id, session.user_id, verify_msg.id, delay=0
        )
    except Exception as e:
        logger.error(f"删除消息失败: {e}")

    schedule_verify_task(
        session,
        "refresh",
        wait_seconds,
        lambda: refresh_verify_message(client, session),
    )


async def refresh_verify_message(client: Client, session: VerifySession) -> None:
    if not await is_current_waiting(session):
        return

    context = await init_context(client, session)
    if not context:
        await verify_end(session)
        return

    user_link = get_md_chat_link(context.member.user)
    text = (
        f"证验行进 😀 击点内秒 **{VERIFY_TIMEOUT_SECONDS}** 在请 {user_link}\n\n"
        f"{user_link} Please complete verification by clicking 😀 within "
        f"**{VERIFY_TIMEOUT_SECONDS}** seconds"
    )

    try:
        await client.edit_message_text(
            chat_id=session.chat_id,
            message_id=session.current_verify_msg_id,
            text=text,
            reply_markup=await verify_buttons(client, session, "two"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.exception(e)
        await verify_end(session)
        return

    if not await is_current_waiting(session):
        return

    schedule_verify_task(
        session,
        "timeout",
        VERIFY_TIMEOUT_SECONDS,
        lambda: verify_timeout(client, session),
    )


async def verify_buttons(
    client: Client, session: VerifySession, step: Literal["one", "two"]
) -> Ikm:
    buttons = [
        Ikb(
            text="✅",
            callback_data=str(
                CQData(session.validator_id, session.rid, "admin", "pass")
            ),
        )
    ]

    value = "fail" if step == "one" else "pass"
    text = "🥵" if step == "one" else "😀"
    buttons.append(
        Ikb(
            text=text,
            url=await build_start_link(
                client, StartData(session.validator_id, session.rid, "verify", value)
            ),
        )
    )
    buttons.append(
        Ikb(
            text="❎",
            callback_data=str(
                CQData(session.validator_id, session.rid, "admin", "fail")
            ),
        )
    )
    return Ikm([buttons])


async def verify_pass(client: Client, context: VerifyContext, message: Message) -> None:
    session = context.session
    await client.restrict_chat_member(
        session.chat_id,
        session.user_id,
        permissions=full_chat_permissions(),
    )
    await message.reply(
        f"**{get_md_chat_link(context.chat)} 验证通过**",
        reply_markup=Ikm([[Ikb(text="返回群组", url=u)]])
        if (u := get_chat_link(context.chat))
        else None,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await end_text(client, context, "验证通过")
    logger.debug(
        f"验证通过: 已在 {chat_display_name(context.chat)} 中通过验证: "
        f"{context.member.user.full_name} | {session.user_id} | {session.chat_id}"
    )


async def verify_fail(client: Client, context: VerifyContext, message: Message) -> None:
    session = context.session
    until_date = datetime.now() + timedelta(seconds=VERIFY_RETRY_SECONDS)
    await client.ban_chat_member(
        session.chat_id, session.user_id, until_date=until_date
    )
    await message.reply(
        f"**{get_md_chat_link(context.chat)} 验证失败**\n请 1 分钟后重试",
    )
    await end_text(client, context, "验证未通过, 已击落")
    logger.debug(
        f"验证失败: 已在 {chat_display_name(context.chat)} 中踢出: "
        f"{context.member.user.full_name} | {session.user_id} | {session.chat_id}"
    )


async def verify_timeout(client: Client, session: VerifySession) -> None:
    if not await finish_session(session, STATE_TIMEOUT):
        return

    context = await init_context(client, session)
    if not context:
        await verify_end(session)
        return

    try:
        until_date = datetime.now() + timedelta(seconds=VERIFY_RETRY_SECONDS)
        await client.ban_chat_member(
            session.chat_id, session.user_id, until_date=until_date
        )
        await end_text(client, context, "验证超时, 已击落")
        logger.debug(
            f"验证超时: 已在 {chat_display_name(context.chat)} 中临时踢出60秒: "
            f"{context.member.user.full_name} | {session.user_id} | {session.chat_id}"
        )
    finally:
        await verify_end(session)


async def admin_verify_pass(
    client: Client, context: VerifyContext, callback: CallbackQuery
) -> None:
    session = context.session
    await client.restrict_chat_member(
        session.chat_id,
        session.user_id,
        permissions=full_chat_permissions(),
    )
    await callback.answer("已通过")
    await end_text(
        client,
        context,
        f"由管理 {get_md_chat_link(callback.from_user)} 手动通过",
    )
    logger.debug(
        f"验证通过: 已在 {chat_display_name(context.chat)} 中通过验证: "
        f"{context.member.user.full_name} | {session.user_id} | {session.chat_id}"
    )


async def admin_verify_fail(
    client: Client, context: VerifyContext, callback: CallbackQuery
) -> None:
    session = context.session
    await client.ban_chat_member(session.chat_id, session.user_id)
    await callback.answer("已永久踢出")
    await end_text(
        client,
        context,
        f"由管理 {get_md_chat_link(callback.from_user)} 手动击落",
    )
    logger.debug(
        f"验证失败(管理手动踢出): 已在 {chat_display_name(context.chat)} 中踢出: "
        f"{context.member.user.full_name} | {session.user_id} | {session.chat_id}"
    )


async def end_text(client: Client, context: VerifyContext, text: str) -> None:
    session = context.session
    try:
        await client.edit_message_text(
            chat_id=session.chat_id,
            message_id=session.current_verify_msg_id,
            text=f"{get_md_chat_link(context.member.user)} {text}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        await asyncio.sleep(3)
        await client.delete_messages(session.chat_id, session.current_verify_msg_id)
    except Exception as e:
        logger.exception(e)


async def verify_end(session: VerifySession) -> None:
    cancel_verify_tasks(session)
    await delete_session_if_current(session)


async def progress_callback(
    client: Client, callback: CallbackQuery, data: CQData
) -> None:
    session = await load_current_session(data.validator_id, data.rid)
    final_state = final_state_from_value(data.value)
    if not session or not final_state:
        await callback.answer("验证已过期", show_alert=True)
        return

    if not await finish_session(session, final_state):
        await callback.answer("验证已过期", show_alert=True)
        return

    context = await init_context(client, session)
    if not context:
        await verify_end(session)
        return

    try:
        if data.value == "pass":
            await admin_verify_pass(client, context, callback)
        elif data.value == "fail":
            await admin_verify_fail(client, context, callback)
    finally:
        await verify_end(session)


async def progress_start(client: Client, message: Message, data: StartData) -> None:
    session = await load_current_session(data.validator_id, data.rid)
    final_state = final_state_from_value(data.value)
    if not session or not final_state:
        await message.reply("验证已过期")
        return

    if not await finish_session(session, final_state):
        await message.reply("验证已过期")
        return

    context = await init_context(client, session)
    if not context:
        await verify_end(session)
        return

    try:
        if data.value == "pass":
            await verify_pass(client, context, message)
        elif data.value == "fail":
            await verify_fail(client, context, message)
    finally:
        await verify_end(session)


@Client.on_chat_member_updated(new_members & filters.admin)
async def verify(client: Client, event: ChatMemberUpdated) -> None:
    if not event.chat.id:
        return

    session = VerifySession.create(event.chat.id, event.from_user.id)
    context = await init_context(client, session)
    if not context:
        return

    await send_start_verify_message(client, context)


@Client.on_callback_query(filters.regex(r"^@"))
async def verify_callback(client: Client, callback: CallbackQuery) -> None:
    data = await decode_callback_data(callback)
    if not data:
        await callback.answer("验证已过期", show_alert=True)
        return

    if not isinstance(callback.message, Message) or not callback.message.chat:
        await callback.answer("验证已过期", show_alert=True)
        return
    if callback.message.chat.id is None:
        await callback.answer("验证已过期", show_alert=True)
        return

    try:
        click_user = await client.get_chat_member(
            callback.message.chat.id, callback.from_user.id
        )
    except Exception:
        await callback.answer("验证已过期", show_alert=True)
        return

    session = await load_current_session(data.validator_id, data.rid)
    if not session:
        await callback.answer("验证已过期", show_alert=True)
        return
    if data.operate == "verify" and click_user.user.id != session.user_id:
        await callback.answer("这不是你的验证", show_alert=True)
        return
    if data.operate == "admin" and click_user.status not in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }:
        await callback.answer("权限不足", show_alert=True)
        return
    if data.operate != "admin" or data.value not in {"pass", "fail"}:
        await callback.answer("验证已过期", show_alert=True)
        return

    await progress_callback(client, callback, data)


@Client.on_message(start_filter(".*"))
async def start_handler(client: Client, message: Message) -> None:
    data = await decode_start_data(message)
    if not data:
        await message.reply("验证已过期")
        message.stop_propagation()
        return

    if not message.from_user:
        message.stop_propagation()
        return

    session = await load_current_session(data.validator_id, data.rid)
    if not session:
        await message.reply("验证已过期")
        message.stop_propagation()
        return
    if data.operate == "verify" and message.from_user.id != session.user_id:
        await message.reply("这不是你的验证")
        message.stop_propagation()
        return
    if data.operate != "verify" or data.value not in {"pass", "fail"}:
        await message.reply("验证已过期")
        message.stop_propagation()
        return

    await progress_start(client, message, data)
    message.stop_propagation()
