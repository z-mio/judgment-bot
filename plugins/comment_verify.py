"""频道评论区验证: 未入群的评论者需在限定时间内完成验证, 超时删除评论"""

import asyncio
import json
import secrets
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Self, cast

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    CallbackQuery,
    Chat,
    LinkPreviewOptions,
    Message,
    ReplyParameters,
    User,
)
from pyrogram.types import InlineKeyboardButton as Ikb
from pyrogram.types import InlineKeyboardMarkup as Ikm

from log import logger
from plugins.helpers import (
    as_text,
    cancel_all_tasks,
    cancel_task,
    get_chat_link,
    get_hash,
    get_md_chat_link,
    member_is_admin,
    schedule_delayed,
)
from services.comment_guard_manager import comment_guard_manager
from services.redis_client import rc

logger = logger.bind(name="CommentVerify")

OPERATE = "comment"
CALLBACK_PREFIX = "cv="
VERIFY_SECONDS = 30
FAIL_BAN_LIMIT = 5
SESSION_KEY_PREFIX = "comment_verify:"
SESSION_TTL_SECONDS = 3600
INVITE_KEY_PREFIX = "comment_invite:"
INVITE_TTL_SECONDS = 86400 * 7

TASKS: dict[str, asyncio.Task[None]] = {}
LOCKS: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@dataclass(slots=True)
class CommentSession:
    chat_id: int
    user_id: int
    rid: str
    timeout_at: int
    msg_ids: list[int] = field(default_factory=list)
    prompt_id: int | None = None

    @classmethod
    def create(cls, chat_id: int, user_id: int, msg_id: int) -> Self:
        now = int(time.time())
        return cls(
            chat_id=chat_id,
            user_id=user_id,
            rid=secrets.token_urlsafe(8),
            timeout_at=now + VERIFY_SECONDS,
            msg_ids=[msg_id],
        )

    @classmethod
    def loads(cls, raw: str) -> Self:
        data = cast(dict[str, Any], json.loads(raw))
        data.pop("channel_id", None)
        return cls(**data)

    def dumps(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @property
    def sid(self) -> str:
        return session_id(self.chat_id, self.user_id)


def session_id(chat_id: int, user_id: int) -> str:
    return get_hash(f"{OPERATE}_{chat_id}_{user_id}")[:8]


def session_key(sid: str) -> str:
    return f"{SESSION_KEY_PREFIX}{sid}"


async def save_session(session: CommentSession) -> None:
    await rc.set(session_key(session.sid), session.dumps(), ex=SESSION_TTL_SECONDS)


async def load_session(sid: str) -> CommentSession | None:
    raw = await rc.get(session_key(sid))
    if not isinstance(raw, str):
        return None
    try:
        return CommentSession.loads(raw)
    except Exception:
        logger.warning(f"跳过无法解析的评论验证会话: sid={sid}")
        return None


async def pop_session_locked(session: CommentSession) -> CommentSession | None:
    """结束会话; 调用方必须持有会话锁"""
    current = await load_session(session.sid)
    if not current or current.rid != session.rid:
        return None
    await rc.delete(session_key(session.sid))
    cancel_tasks(current)
    return current


async def pop_session(session: CommentSession) -> CommentSession | None:
    """结束会话, 只有当前会话的第一个结束者能拿到最新数据"""
    async with LOCKS[session.sid]:
        return await pop_session_locked(session)


def task_key(session: CommentSession) -> str:
    return f"{session.sid}:{session.rid}"


def schedule_task(
    session: CommentSession,
    run_at: int,
    factory: Callable[[], Awaitable[None]],
) -> None:
    schedule_delayed(
        TASKS, task_key(session), run_at - time.time(), factory, "评论验证任务"
    )


def cancel_tasks(session: CommentSession) -> None:
    cancel_task(TASKS, task_key(session), skip_current=True)


async def cancel_all_comment_verify_tasks() -> None:
    await cancel_all_tasks(TASKS)


def schedule_session(client: Client, session: CommentSession) -> None:
    schedule_task(session, session.timeout_at, lambda: verify_timeout(client, session))


async def restore_comment_verify_sessions(client: Client) -> None:
    """重启后恢复评论验证计时, 已过期的立即按超时处理"""
    count = 0
    async for key in rc.scan_iter(match=f"{SESSION_KEY_PREFIX}*", count=100):
        session = await load_session(key.removeprefix(SESSION_KEY_PREFIX))
        if session:
            schedule_session(client, session)
            count += 1
    if count:
        logger.info(f"已恢复评论验证会话: {count} 个")


async def is_non_member(client: Client, chat_id: int, user_id: int) -> bool:
    """评论者是否未入群; 群成员会被短期缓存"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
    except UserNotParticipant:
        return True

    if member.status in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    }:
        await comment_guard_manager.mark_member(chat_id, user_id)
        return False
    if member.status == ChatMemberStatus.LEFT:
        return True
    if member.status == ChatMemberStatus.RESTRICTED:
        return member.is_member is False
    return False


def known_linked_channel_id(chat: Chat | None) -> int | None:
    if not chat:
        return None
    if chat.linked_chat_id:
        return chat.linked_chat_id
    if chat.linked_chat and chat.linked_chat.id:
        return chat.linked_chat.id
    return None


async def get_linked_channel_id(
    client: Client, chat_id: int, chat: Chat | None = None
) -> int | None:
    """获取讨论群当前关联的频道 ID"""
    if channel_id := known_linked_channel_id(chat):
        return channel_id
    try:
        full_chat = await client.get_chat(chat_id)
    except Exception as e:
        logger.warning(f"获取讨论群关联频道失败: chat_id={chat_id} | {e}")
        return None
    return known_linked_channel_id(full_chat)


async def member_is_group_or_channel_admin(
    client: Client, chat_id: int, user_id: int, channel_id: int | None
) -> bool:
    chat_ids = [chat_id]
    if channel_id and channel_id != chat_id:
        chat_ids.append(channel_id)
    results = await asyncio.gather(
        *(member_is_admin(client, item, user_id) for item in chat_ids)
    )
    return any(results)


async def is_comment_verification_exempt(
    client: Client, chat_id: int, user_id: int, chat: Chat | None = None
) -> bool:
    """群成员免验证; 频道管理员即使未入群也免验证"""
    if not await is_non_member(client, chat_id, user_id):
        return True
    channel_id = await get_linked_channel_id(client, chat_id, chat)
    if channel_id and await member_is_admin(client, channel_id, user_id):
        try:
            await comment_guard_manager.mark_channel_admin(chat_id, user_id)
        except Exception as e:
            logger.warning(f"缓存频道管理员免验证状态失败: chat_id={chat_id} | {e}")
        return True
    return False


def prompt_buttons(session: CommentSession) -> Ikm:
    return Ikm(
        [
            [
                Ikb(
                    text="😀",
                    callback_data=f"{CALLBACK_PREFIX}{session.sid},{session.rid},pass",
                )
            ]
        ]
    )


async def join_link(client: Client, chat: Chat) -> str | None:
    """群加入链接: 公开群用 t.me 链接, 私有群创建并缓存邀请链接"""
    if link := get_chat_link(chat):
        return link
    if chat.id is None:
        return None
    key = f"{INVITE_KEY_PREFIX}{chat.id}"
    cached = await rc.get(key)
    if isinstance(cached, str):
        return cached
    try:
        invite = await client.create_chat_invite_link(chat.id)
    except Exception as e:
        logger.warning(f"创建交流群邀请链接失败: chat_id={chat.id} | {e}")
        return None
    if not invite:
        return None
    await rc.set(key, invite.invite_link, ex=INVITE_TTL_SECONDS)
    return invite.invite_link


def user_link(user: User | None) -> str:
    return f"{get_md_chat_link(user)} " if user else ""


def prompt_text(
    user: User | None, session: CommentSession, join_url: str | None
) -> str:
    left = max(1, session.timeout_at - int(time.time()))
    link = user_link(user)
    join = f"[加入交流群]({join_url})" if join_url else "加入交流群"
    join_en = f"[Join the group]({join_url})" if join_url else "Join the group"
    return (
        f"{link}请在 **{left}** 秒内点击 😀 完成验证, 超时评论将被删除\n"
        f"💡 {join}后评论无需验证\n\n"
        f"{link}Click 😀 within **{left}** seconds, "
        f"or your comment will be deleted\n"
        f"💡 {join_en} to comment without verification"
    )


async def send_prompt(client: Client, msg: Message, session: CommentSession) -> None:
    sent = await client.send_message(
        session.chat_id,
        prompt_text(
            msg.from_user,
            session,
            await join_link(client, msg.chat) if msg.chat else None,
        ),
        reply_parameters=ReplyParameters(message_id=msg.id),
        reply_markup=prompt_buttons(session),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    if sent:
        session.prompt_id = sent.id


async def delete_prompt(client: Client, session: CommentSession) -> None:
    if session.prompt_id is None:
        return
    try:
        await client.delete_messages(session.chat_id, session.prompt_id)
    except Exception as e:
        logger.warning(f"删除评论验证提示失败: sid={session.sid} | {e}")


async def end_prompt(client: Client, session: CommentSession, text: str) -> None:
    if session.prompt_id is None:
        return
    user = await safe_get_user(client, session.user_id)
    prefix = user_link(user)
    try:
        await client.edit_message_text(
            session.chat_id,
            session.prompt_id,
            f"{prefix}{text}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        await asyncio.sleep(3)
    except Exception as e:
        logger.warning(f"更新评论验证提示失败: sid={session.sid} | {e}")
    await delete_prompt(client, session)


async def safe_get_user(client: Client, user_id: int) -> User | None:
    try:
        user = await client.get_users(user_id)
    except Exception:
        return None
    return user if isinstance(user, User) else None


async def verify_failed(client: Client, session: CommentSession, reason: str) -> bool:
    """删除评论并累计失败次数, 连续失败达到上限时封禁; 返回是否已封禁"""
    try:
        await client.delete_messages(session.chat_id, session.msg_ids)
    except Exception as e:
        logger.warning(f"删除未验证评论失败: sid={session.sid} | {e}")

    count = await comment_guard_manager.record_fail(session.chat_id, session.user_id)
    banned = False
    if count >= FAIL_BAN_LIMIT:
        try:
            await client.ban_chat_member(session.chat_id, session.user_id)
            await comment_guard_manager.clear_fail(session.chat_id, session.user_id)
            banned = True
        except Exception:
            logger.exception(f"封禁评论者失败: sid={session.sid}")

    logger.info(
        f"评论验证{reason}: user_id={session.user_id} | chat_id={session.chat_id} | "
        f"已删除 {len(session.msg_ids)} 条评论 | 连续失败 {count} 次"
        + (" | 已封禁" if banned else "")
    )
    await end_prompt(
        client,
        session,
        f"连续 {FAIL_BAN_LIMIT} 次验证未通过, 已封禁"
        if banned
        else "验证未通过, 评论已删除",
    )
    return banned


async def verify_timeout(client: Client, session: CommentSession) -> None:
    current = await pop_session(session)
    if not current:
        return
    if await comment_guard_manager.is_trusted(current.chat_id, current.user_id):
        logger.info(
            f"评论者已受信任, 跳过评论验证: user_id={current.user_id} | "
            f"chat_id={current.chat_id}"
        )
        await delete_prompt(client, current)
        return
    try:
        exempt = await is_comment_verification_exempt(
            client, current.chat_id, current.user_id
        )
    except Exception:
        exempt = False
    if exempt:
        logger.info(
            f"评论者已入群或为频道管理员, 跳过评论验证: user_id={current.user_id} | "
            f"chat_id={current.chat_id}"
        )
        await delete_prompt(client, current)
        return
    await verify_failed(client, current, "超时")


async def verify_passed(
    client: Client, session: CommentSession, operator_id: int | None = None
) -> None:
    await comment_guard_manager.mark_verified(session.chat_id, session.user_id)
    assisted = (
        f" | assisted_by={operator_id}"
        if operator_id is not None and operator_id != session.user_id
        else ""
    )
    logger.info(
        f"评论验证通过: user_id={session.user_id} | chat_id={session.chat_id}{assisted}"
    )
    await end_prompt(client, session, "验证通过")


@Client.on_message(
    filters.group & filters.admin & ~filters.service & ~filters.bot, group=2
)
async def comment_verify(client: Client, msg: Message) -> None:
    user = msg.from_user
    if not user or not msg.chat or msg.chat.id is None:
        return
    chat_id = msg.chat.id

    if await comment_guard_manager.is_trusted(chat_id, user.id):
        await comment_guard_manager.refresh_verified(user.id)
        return

    sid = session_id(chat_id, user.id)
    async with LOCKS[sid]:
        if session := await load_session(sid):
            session.msg_ids.append(msg.id)
            await save_session(session)
            return

        try:
            if await is_comment_verification_exempt(client, chat_id, user.id, msg.chat):
                return
        except Exception:
            logger.exception(
                f"获取评论者免验证状态失败: user_id={user.id} | chat_id={chat_id}"
            )
            return

        session = CommentSession.create(chat_id, user.id, msg.id)
        try:
            await send_prompt(client, msg, session)
        except Exception:
            logger.exception(
                f"发送评论验证提示失败: user_id={user.id} | chat_id={chat_id}"
            )
            return
        await save_session(session)

    logger.info(
        f"开始评论验证: {user.full_name} | user_id={user.id} | chat_id={chat_id}"
    )
    schedule_session(client, session)


@Client.on_callback_query(filters.regex(rf"^{CALLBACK_PREFIX}"))
async def comment_verify_callback(client: Client, callback: CallbackQuery) -> None:
    parts = as_text(callback.data).removeprefix(CALLBACK_PREFIX).split(",")
    session = (
        await load_session(parts[0])
        if len(parts) == 3 and parts[2] == "pass"
        else None
    )
    if not session or session.rid != parts[1]:
        await callback.answer("验证已过期", show_alert=True)
        return

    current = None
    denied = False
    expired = False
    is_self = False
    async with LOCKS[session.sid]:
        session = await load_session(parts[0])
        if not session or session.rid != parts[1]:
            expired = True
        else:
            is_self = callback.from_user.id == session.user_id
            if is_self:
                current = await pop_session_locked(session)
            else:
                channel_id = await get_linked_channel_id(client, session.chat_id)
                if await member_is_group_or_channel_admin(
                    client, session.chat_id, callback.from_user.id, channel_id
                ):
                    current = await pop_session_locked(session)
                else:
                    denied = True

    if expired:
        await callback.answer("验证已过期", show_alert=True)
        return
    if denied:
        await callback.answer("这不是你的验证", show_alert=True)
        return
    if not current:
        await callback.answer("验证已过期", show_alert=True)
        return

    try:
        if is_self:
            await callback.answer("验证通过, 现在可以正常评论了")
        else:
            await callback.answer("已代对方完成验证")
    except Exception as e:
        logger.warning(f"发送评论验证回执失败: sid={current.sid} | {e}")
    await verify_passed(client, current, operator_id=callback.from_user.id)
