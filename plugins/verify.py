import asyncio
import json
import random
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
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
    full_chat_permissions,
    get_chat_link,
    get_hash,
    get_md_chat_link,
    delete_member_messages,
)
from services.redis_client import rc
from services.raid_guard_manager import raid_guard_manager
from services.verify_fail_manager import verify_fail_manager

logger = logger.bind(name="Verify")

VERIFY_NAME = "easy_validator"
VERIFY_REFRESH_MIN_SECONDS = 5
VERIFY_REFRESH_MAX_SECONDS = 10
VERIFY_TIMEOUT_SECONDS = 30
VERIFY_RETRY_SECONDS = 60
# 兜底超时, 避免丢失定时任务后会话一直残留
VERIFY_SESSION_TTL_SECONDS = 24 * 3600

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
    # 定时任务的 Unix 时间戳, 重启后可恢复
    refresh_at: int | None = None
    timeout_at: int | None = None

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
        refresh_at = data.get("refresh_at")
        timeout_at = data.get("timeout_at")

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
        if refresh_at is not None and not isinstance(refresh_at, int):
            raise ValueError("invalid refresh_at")
        if timeout_at is not None and not isinstance(timeout_at, int):
            raise ValueError("invalid timeout_at")

        return cls(
            chat_id=chat_id,
            user_id=user_id,
            rid=rid,
            verify_msg_id=verify_msg_id,
            state=state,
            refresh_at=refresh_at,
            timeout_at=timeout_at,
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
                "refresh_at": self.refresh_at,
                "timeout_at": self.timeout_at,
            },
            separators=(",", ":"),
        )


@dataclass(slots=True)
class VerifyContext:
    session: VerifySession
    chat: Chat
    member: ChatMember


def chat_display_name(chat: Chat | None) -> str:
    if not chat:
        return "未知群组"
    return chat.full_name or str(chat.id)


def member_display_name(member: ChatMember) -> str:
    if not member.user:
        return "未知用户"
    return member.user.full_name or str(member.user.id)


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
        except Exception:
            logger.exception(f"验证任务执行失败: task={key}")

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
    if tasks:
        logger.info(f"正在取消 {len(tasks)} 个进行中的验证任务")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def verify_chat_key(chat_id: int) -> str:
    return f"verify_chat:{chat_id}"


async def save_session(session: VerifySession) -> None:
    async with rc.pipeline() as pipe:
        pipe.set(
            session.validator_id, session.dumps(), ex=VERIFY_SESSION_TTL_SECONDS
        )
        pipe.sadd(verify_chat_key(session.chat_id), session.validator_id)
        await pipe.execute()


async def load_session(validator_id: str) -> VerifySession | None:
    raw = await rc.get(validator_id)
    if not raw:
        return None
    if not isinstance(raw, str):
        raise ValueError("invalid session data")
    return VerifySession.loads(raw)


async def update_waiting_session(
    session: VerifySession,
    apply: Callable[[VerifySession], None],
) -> bool:
    async with session_lock(session.validator_id):
        current = await load_session(session.validator_id)
        if not current:
            return False
        if current.rid != session.rid or current.state != STATE_WAITING_CLICK:
            return False

        apply(current)
        await save_session(current)
        return True


async def finish_session(session: VerifySession, final_state: FinalState) -> bool:
    def set_final_state(current: VerifySession) -> None:
        current.state = final_state

    return await update_waiting_session(session, set_final_state)


async def set_timeout_at(session: VerifySession, timeout_at: int) -> bool:
    def set_timeout(current: VerifySession) -> None:
        current.timeout_at = timeout_at

    return await update_waiting_session(session, set_timeout)


async def delete_session_if_current(session: VerifySession) -> None:
    async with session_lock(session.validator_id):
        current = await load_session(session.validator_id)
        if current and current.rid == session.rid:
            async with rc.pipeline() as pipe:
                pipe.delete(session.validator_id)
                pipe.srem(verify_chat_key(session.chat_id), session.validator_id)
                await pipe.execute()


async def is_current_waiting(session: VerifySession) -> bool:
    current = await load_session(session.validator_id)
    return bool(
        current and current.rid == session.rid and current.state == STATE_WAITING_CLICK
    )


async def mark_verify_failed(chat_id: int, user_id: int) -> None:
    """标记验证失败用户, 失败不影响主流程"""
    try:
        await verify_fail_manager.mark_failed(chat_id, user_id)
        logger.debug(f"已写入验证失败标记: user_id={user_id} | chat_id={chat_id}")
    except Exception:
        logger.exception(f"写入验证失败标记失败: user_id={user_id} | chat_id={chat_id}")


async def record_verify_result(chat_id: int, rid: str, passed: bool) -> None:
    try:
        await raid_guard_manager.record_result(chat_id, rid, passed)
    except Exception:
        logger.exception(
            f"记录验证结果失败: chat_id={chat_id} | rid={rid} | passed={passed}"
        )


async def temp_ban(client: Client, chat_id: int, user_id: int) -> None:
    await client.ban_chat_member(
        chat_id,
        user_id,
        until_date=datetime.now() + timedelta(seconds=VERIFY_RETRY_SECONDS),
    )


async def silent_kick(
    client: Client, chat_id: int, user_id: int, name: str
) -> None:
    await mark_verify_failed(chat_id, user_id)
    try:
        await temp_ban(client, chat_id, user_id)
    except Exception:
        logger.exception(
            f"防轰炸静默踢出失败: user_id={user_id} | chat_id={chat_id}"
        )
    logger.info(f"防轰炸静默踢出: {name} | user_id={user_id} | chat_id={chat_id}")


async def send_raid_notice(client: Client, chat_id: int) -> None:
    try:
        await client.send_message(
            chat_id,
            "**已开启防轰炸模式**\n"
            "检测到异常入群, 期间新成员将被自动移出, 请稍后再加入\n\n"
            "**Anti-raid mode enabled**\n"
            "Unusual join activity detected, new members will be removed "
            "automatically, please try joining again later",
        )
    except Exception:
        logger.exception(f"发送防轰炸模式通知失败: chat_id={chat_id}")


async def clear_pending_verifies(client: Client, chat_id: int) -> None:
    index_key = verify_chat_key(chat_id)
    validator_ids = cast(set[str], await rc.smembers(index_key))
    cleared = 0
    for validator_id in validator_ids:
        session = await load_session(validator_id)
        if not session:
            await rc.srem(index_key, validator_id)
            continue
        if not await finish_session(session, STATE_TIMEOUT):
            continue

        cancel_verify_tasks(session)
        await mark_verify_failed(session.chat_id, session.user_id)
        try:
            await temp_ban(client, session.chat_id, session.user_id)
        except Exception:
            logger.exception(
                f"防轰炸清理验证用户失败: user_id={session.user_id} | "
                f"chat_id={session.chat_id}"
            )
        if session.verify_msg_id:
            try:
                await client.delete_messages(
                    session.chat_id, session.verify_msg_id
                )
            except Exception:
                logger.exception(
                    f"删除防轰炸验证消息失败: user_id={session.user_id} | "
                    f"chat_id={session.chat_id}"
                )
        await verify_end(session)
        cleared += 1
    logger.info(
        f"防轰炸清场: 已静默处理 {cleared} 个进行中的验证 | chat_id={chat_id}"
    )


async def clear_verify_failed(chat_id: int, user_id: int) -> None:
    """清除验证失败标记, 失败不影响主流程"""
    try:
        await verify_fail_manager.clear_failed(chat_id, user_id)
        logger.debug(f"已清除验证失败标记: user_id={user_id} | chat_id={chat_id}")
    except Exception:
        logger.exception(f"清除验证失败标记失败: user_id={user_id} | chat_id={chat_id}")


def final_state_from_value(value: str) -> FinalState | None:
    if value == "pass":
        return STATE_PASSED
    if value == "fail":
        return STATE_FAILED
    return None


def decode_callback_data(callback: CallbackQuery) -> CQData | None:
    if not callback.data:
        return None
    data_text = (
        callback.data.decode() if isinstance(callback.data, bytes) else callback.data
    )
    try:
        return CQData.parse(data_text)
    except Exception:
        return None


def decode_start_data(message: Message) -> StartData | None:
    text = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        text = parts[1] if len(parts) > 1 else ""

    try:
        with suppress(Exception):
            text = decode_start_payload(text)
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
        if not chat:
            return None
        member = await client.get_chat_member(session.chat_id, session.user_id)
    except Exception:
        logger.exception(
            f"初始化验证上下文失败: user_id={session.user_id} | chat_id={session.chat_id}"
        )
        return None

    return VerifyContext(session=session, chat=chat, member=member)


async def send_start_verify_message(client: Client, context: VerifyContext) -> None:
    session = context.session
    if not context.member.user:
        return
    await client.restrict_chat_member(
        session.chat_id, session.user_id, permissions=ChatPermissions()
    )

    wait_seconds = random.randint(
        VERIFY_REFRESH_MIN_SECONDS, VERIFY_REFRESH_MAX_SECONDS
    )
    user_link = get_md_chat_link(context.member.user)
    text = (
        f"{user_link} 请在 **{wait_seconds}** 秒后, 待 🥵 变成 😀 时点击 😀 进行验证, "
        f"**请勿提前点击!**\n\n"
        f"{user_link} Please wait **{wait_seconds}** seconds, "
        f"then click 😀 to verify once 🥵 changes to 😀. "
        f"**Do not click early!**"
    )
    try:
        verify_msg = await client.send_message(
            chat_id=session.chat_id,
            text=text,
            reply_markup=verify_buttons(client, session, "one"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        logger.exception(
            f"发送验证提示失败: user_id={session.user_id} | "
            f"chat_id={session.chat_id} | 已临时踢出并标记"
        )
        await mark_verify_failed(session.chat_id, session.user_id)
        try:
            await temp_ban(client, session.chat_id, session.user_id)
        except Exception:
            logger.exception(
                f"临时踢出验证提示发送失败用户失败: user_id={session.user_id} | "
                f"chat_id={session.chat_id}"
            )
        return
    if not verify_msg:
        return
    session.verify_msg_id = verify_msg.id
    session.state = STATE_WAITING_CLICK
    session.refresh_at = int(time.time()) + wait_seconds
    await save_session(session)

    logger.info(
        f"开始验证: {member_display_name(context.member)} | user_id={session.user_id} | "
        f"chat_id={session.chat_id} | chat={chat_display_name(context.chat)} | "
        f"rid={session.rid} | 等待 {wait_seconds}s"
    )

    try:
        deleted = await delete_member_messages(
            client, session.chat_id, session.user_id, verify_msg.id
        )
        logger.debug(
            f"已清理验证用户历史消息: {deleted} 条 | user_id={session.user_id} | "
            f"chat_id={session.chat_id}"
        )
    except Exception:
        logger.exception(
            f"清理验证用户历史消息失败: user_id={session.user_id} | "
            f"chat_id={session.chat_id}"
        )

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
    if not context.member.user:
        return
    user_link = get_md_chat_link(context.member.user)
    text = (
        f"{user_link} 请在 **{VERIFY_TIMEOUT_SECONDS}** 秒内点击 😀 进行验证\n\n"
        f"{user_link} Please complete verification by clicking 😀 within "
        f"**{VERIFY_TIMEOUT_SECONDS}** seconds"
    )

    try:
        await client.edit_message_text(
            chat_id=session.chat_id,
            message_id=session.current_verify_msg_id,
            text=text,
            reply_markup=verify_buttons(client, session, "two"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        logger.exception(
            f"刷新验证提示失败: user_id={session.user_id} | chat_id={session.chat_id} | "
            f"rid={session.rid}"
        )
        await verify_timeout(client, session)
        return

    logger.debug(
        f"验证提示已刷新: user_id={session.user_id} | chat_id={session.chat_id} | "
        f"rid={session.rid}"
    )

    if not await set_timeout_at(session, int(time.time()) + VERIFY_TIMEOUT_SECONDS):
        return

    schedule_verify_task(
        session,
        "timeout",
        VERIFY_TIMEOUT_SECONDS,
        lambda: verify_timeout(client, session),
    )


def resume_verify_session(client: Client, session: VerifySession, now: int) -> bool:
    """恢复会话定时任务, 已过期时返回 False"""
    refresh_at = session.refresh_at
    if (
        session.timeout_at is None
        and refresh_at is not None
        and refresh_at + VERIFY_TIMEOUT_SECONDS > now
    ):
        # 验证提示尚未刷新
        schedule_verify_task(
            session,
            "refresh",
            max(0, refresh_at - now),
            lambda: refresh_verify_message(client, session),
        )
        return True

    # 无时间戳的旧会话按已过期处理
    delay = max(0, (session.timeout_at or now) - now)
    schedule_verify_task(
        session, "timeout", delay, lambda: verify_timeout(client, session)
    )
    return delay > 0


async def restore_verify_sessions(client: Client) -> None:
    """恢复重启后丢失定时任务的验证会话"""
    now = int(time.time())
    resumed = expired = 0
    async for key in rc.scan_iter(match="[0-9a-f]" * 8, count=100):
        try:
            session = await load_session(key)
        except Exception:
            logger.warning(f"跳过无法解析的验证会话: key={key}")
            continue
        if not session or session.validator_id != key:
            continue
        if session.state != STATE_WAITING_CLICK:
            continue

        if resume_verify_session(client, session, now):
            resumed += 1
        else:
            expired += 1

    if resumed or expired:
        logger.info(f"已恢复验证会话: 继续等待 {resumed} 个 | 按超时处理 {expired} 个")


def verify_buttons(
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
            url=build_start_link(
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
    await record_verify_result(session.chat_id, session.rid, passed=True)
    await clear_verify_failed(session.chat_id, session.user_id)
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
    logger.info(
        f"验证通过: {member_display_name(context.member)} | user_id={session.user_id} | "
        f"chat_id={session.chat_id} | chat={chat_display_name(context.chat)} | "
        f"rid={session.rid}"
    )


async def verify_fail(client: Client, context: VerifyContext, message: Message) -> None:
    session = context.session
    await record_verify_result(session.chat_id, session.rid, passed=False)
    await mark_verify_failed(session.chat_id, session.user_id)
    await temp_ban(client, session.chat_id, session.user_id)
    await message.reply(
        f"**{get_md_chat_link(context.chat)} 验证失败**\n请 1 分钟后重试",
    )
    await end_text(client, context, "验证未通过, 已击落")
    logger.info(
        f"验证失败: {member_display_name(context.member)} | user_id={session.user_id} | "
        f"chat_id={session.chat_id} | chat={chat_display_name(context.chat)} | "
        f"rid={session.rid} | 已临时踢出并标记"
    )


async def verify_timeout(client: Client, session: VerifySession) -> None:
    if not await finish_session(session, STATE_TIMEOUT):
        return

    await record_verify_result(session.chat_id, session.rid, passed=False)
    await mark_verify_failed(session.chat_id, session.user_id)

    context = await init_context(client, session)
    if not context:
        await verify_end(session)
        return

    try:
        await temp_ban(client, session.chat_id, session.user_id)
        await end_text(client, context, "验证超时, 已击落")
        logger.info(
            f"验证超时: {member_display_name(context.member)} | "
            f"user_id={session.user_id} | chat_id={session.chat_id} | "
            f"chat={chat_display_name(context.chat)} | rid={session.rid} | 已临时踢出并标记"
        )
    finally:
        await verify_end(session)


async def admin_verify_pass(
    client: Client, context: VerifyContext, callback: CallbackQuery
) -> None:
    session = context.session
    await record_verify_result(session.chat_id, session.rid, passed=True)
    await clear_verify_failed(session.chat_id, session.user_id)
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
    logger.info(
        f"管理员手动通过: {member_display_name(context.member)} | "
        f"user_id={session.user_id} | chat_id={session.chat_id} | "
        f"chat={chat_display_name(context.chat)} | admin_id={callback.from_user.id}"
    )


async def admin_verify_fail(
    client: Client, context: VerifyContext, callback: CallbackQuery
) -> None:
    session = context.session
    await record_verify_result(session.chat_id, session.rid, passed=False)
    await client.ban_chat_member(session.chat_id, session.user_id)
    await callback.answer("已永久踢出")
    await end_text(
        client,
        context,
        f"由管理 {get_md_chat_link(callback.from_user)} 手动击落",
    )
    logger.info(
        f"管理员手动击落: {member_display_name(context.member)} | "
        f"user_id={session.user_id} | chat_id={session.chat_id} | "
        f"chat={chat_display_name(context.chat)} | admin_id={callback.from_user.id}"
    )


async def end_text(client: Client, context: VerifyContext, text: str) -> None:
    session = context.session
    if not context.member.user:
        return
    edited = False
    try:
        await client.edit_message_text(
            chat_id=session.chat_id,
            message_id=session.current_verify_msg_id,
            text=f"{get_md_chat_link(context.member.user)} {text}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        edited = True
    except Exception:
        logger.exception(
            f"更新验证结果消息失败: user_id={session.user_id} | chat_id={session.chat_id}"
        )

    if edited:
        await asyncio.sleep(3)

    try:
        await client.delete_messages(session.chat_id, session.current_verify_msg_id)
    except Exception:
        logger.exception(
            f"删除验证消息失败: user_id={session.user_id} | chat_id={session.chat_id}"
        )


async def verify_end(session: VerifySession) -> None:
    cancel_verify_tasks(session)
    await delete_session_if_current(session)
    logger.debug(
        f"验证会话已结束: user_id={session.user_id} | chat_id={session.chat_id} | "
        f"rid={session.rid}"
    )


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

    chat_id = event.chat.id
    new_chat_member = event.new_chat_member
    if not new_chat_member:
        return
    user = new_chat_member.user
    if not user:
        return

    try:
        await raid_guard_manager.record_join(chat_id, user.id)
        mode, newly = await raid_guard_manager.evaluate(chat_id)
    except Exception:
        logger.exception(
            f"防轰炸状态检查失败: user_id={user.id} | chat_id={chat_id}"
        )
        mode, newly = None, False
    if mode:
        await silent_kick(client, chat_id, user.id, user.full_name or str(user.id))
        if newly:
            await send_raid_notice(client, chat_id)
            await clear_pending_verifies(client, chat_id)
        return

    session = VerifySession.create(chat_id, user.id)
    context = await init_context(client, session)
    if not context:
        return

    await send_start_verify_message(client, context)


@Client.on_callback_query(filters.regex(r"^@"))
async def verify_callback(client: Client, callback: CallbackQuery) -> None:
    data = decode_callback_data(callback)
    if not data:
        logger.debug(f"忽略验证回调: 数据无法解析 | user_id={callback.from_user.id}")
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
        logger.debug(
            f"忽略验证回调: 会话已过期 | user_id={callback.from_user.id} | "
            f"rid={data.rid} | operate={data.operate}"
        )
        await callback.answer("验证已过期", show_alert=True)
        return
    if (
        data.operate == "verify"
        and click_user.user
        and click_user.user.id != session.user_id
    ):
        logger.debug(
            f"忽略验证回调: 非本人操作 | user_id={callback.from_user.id} | "
            f"target_user_id={session.user_id} | chat_id={session.chat_id}"
        )
        await callback.answer("这不是你的验证", show_alert=True)
        return
    if data.operate == "admin" and click_user.status not in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }:
        logger.warning(
            f"忽略验证回调: 权限不足 | user_id={callback.from_user.id} | "
            f"chat_id={session.chat_id}"
        )
        await callback.answer("权限不足", show_alert=True)
        return
    if data.operate != "admin" or data.value not in {"pass", "fail"}:
        await callback.answer("验证已过期", show_alert=True)
        return

    await progress_callback(client, callback, data)


@Client.on_message(start_filter(".*"))
async def start_handler(client: Client, message: Message) -> None:
    data = decode_start_data(message)
    if not data:
        await message.reply("验证已过期")
        message.stop_propagation()
        return

    if not message.from_user:
        message.stop_propagation()
        return

    session = await load_current_session(data.validator_id, data.rid)
    if not session:
        logger.debug(
            f"忽略验证链接: 会话已过期 | user_id={message.from_user.id} | "
            f"rid={data.rid} | operate={data.operate}"
        )
        await message.reply("验证已过期")
        message.stop_propagation()
        return
    if data.operate == "verify" and message.from_user.id != session.user_id:
        logger.debug(
            f"忽略验证链接: 非本人操作 | user_id={message.from_user.id} | "
            f"target_user_id={session.user_id} | chat_id={session.chat_id}"
        )
        await message.reply("这不是你的验证")
        message.stop_propagation()
        return
    if data.operate != "verify" or data.value not in {"pass", "fail"}:
        await message.reply("验证已过期")
        message.stop_propagation()
        return

    await progress_start(client, message, data)
    message.stop_propagation()
