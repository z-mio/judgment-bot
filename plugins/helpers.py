import asyncio
import base64
import hashlib
from collections.abc import Callable, Iterable
from datetime import datetime

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.types import (
    Chat,
    ChatPermissions,
    LinkPreviewOptions,
    Message,
    User,
)

from log import logger

logger = logger.bind(name="Helper")

COMMANDS = {
    "kick": "封禁用户/频道",
    "unban": "解封用户/频道",
    "raid": "防轰炸模式",
    "start": "开始",
    "help": "帮助",
}


def get_hash(text: object) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


def get_md_chat_link(chat: User | Chat) -> str:
    name = chat.full_name or str(chat.id)

    if username := chat.username:
        return f"[{name}](https://t.me/{username})"

    if isinstance(chat, User):
        return f"[{name}](tg://user?id={chat.id})"

    chat_id = chat.id
    if str(chat_id).startswith("100"):
        chat_id = int(str(chat_id).removeprefix("100"))
    return f"[{name}](https://t.me/c/{chat_id})"


def get_chat_link(chat: Chat) -> str | None:
    if chat.username:
        return f"https://t.me/{chat.username}"
    if chat.invite_link:
        return chat.invite_link
    return None


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


def is_user_or_anonymous_admin(msg: Message) -> bool:
    return bool(
        msg.from_user
        or (msg.chat and msg.sender_chat and msg.sender_chat.id == msg.chat.id)
    )


async def member_is_admin(cli: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await cli.get_chat_member(chat_id, user_id)
    except Exception:
        logger.exception(f"获取成员权限失败: chat_id={chat_id} | user_id={user_id}")
        return False

    return member.status in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }


def joined_days(joined_date: datetime | None) -> int:
    if not joined_date:
        return 114514
    now = datetime.now(joined_date.tzinfo) if joined_date.tzinfo else datetime.now()
    return (now - joined_date).days


async def get_admin_mentions(chat: Chat) -> str:
    """获取群管理员 Markdown 链接, 一行一个"""
    return "\n".join(
        [
            f"• {get_md_chat_link(member.user)}"
            async for member in chat.get_members(
                filter=ChatMembersFilter.ADMINISTRATORS
            )
            if member.user and not member.user.is_bot
        ]
    )


async def send_ban_notice(cli: Client, chat: Chat, user_id: int, reason: str) -> None:
    """封禁后私信通知用户并附管理员联系方式, 失败仅记录日志"""
    try:
        admins = await get_admin_mentions(chat)
        await cli.send_message(
            user_id,
            f"{reason}\n如有异议请联系群组管理:\n{admins}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.warning(f"通知被封用户失败: user_id={user_id} | {e}")


async def delete_messages(
    cli: Client, chat_id: int, message_ids: list[int], delay: int = 5
) -> None:
    try:
        if delay:
            await asyncio.sleep(delay)
        ids = list(dict.fromkeys(message_ids))
        for index in range(0, len(ids), 100):
            chunk = ids[index : index + 100]
            try:
                await cli.delete_messages(chat_id, chunk)
            except Exception:
                logger.exception(
                    f"批量删除消息失败, 尝试逐条删除: chat_id={chat_id} | ids={chunk}"
                )
                for message_id in chunk:
                    try:
                        await cli.delete_messages(chat_id, message_id)
                    except Exception as e:
                        logger.warning(
                            f"删除消息失败: chat_id={chat_id} | "
                            f"message_id={message_id} | {e}"
                        )
    except Exception:
        logger.exception(f"删除消息流程失败: chat_id={chat_id} | ids={message_ids}")


async def reply_and_delete(cli: Client, msg: Message, chat_id: int, text: str) -> None:
    reply = await msg.reply(text)
    message_ids = [msg.id]
    if reply:
        message_ids.append(reply.id)
    await delete_messages(cli, chat_id, message_ids)


def decode_start_payload(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode()


def build_start_link(cli: Client, value: object) -> str:
    username = cli.me.username if cli.me else ""
    if not username:
        raise ValueError("没有 username")
    payload = base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")
    return f"https://t.me/{username}?start={payload}"


async def _delete_filtered_messages(
    cli: Client,
    chat_id: int,
    message_ids: Iterable[int],
    predicate: Callable[[Message], bool],
) -> int:
    msgs = await cli.get_messages(chat_id, message_ids=list(message_ids))
    dms = [m.id for m in msgs if not m.empty and predicate(m)]
    if dms:
        await cli.delete_messages(chat_id, dms)
    return len(dms)


async def delete_member_messages(
    cli: Client,
    chat_id: int,
    user_id: int,
    msg_id: int,
    limit: int = 100,
) -> int:
    """
    删除最近 100 条消息中该用户发送的消息, 返回删除条数
    """
    return await _delete_filtered_messages(
        cli,
        chat_id,
        range(max(msg_id - limit // 2, 1), msg_id + limit // 2 + 1),
        lambda m: bool(m.from_user and m.from_user.id == user_id),
    )


async def delete_bot_messages(
    cli: Client,
    chat_id: int,
    msg_id: int,
    limit: int = 30,
    delay: int = 3,
) -> int:
    """
    删除 msg_id 之后 limit 条范围内所有 bot 发送的消息, 返回删除条数
    """
    if delay:
        await asyncio.sleep(delay)
    return await _delete_filtered_messages(
        cli,
        chat_id,
        range(msg_id + 1, msg_id + limit + 1),
        lambda m: bool(m.from_user and m.from_user.is_bot),
    )
