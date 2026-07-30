import asyncio
import base64
import hashlib

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus

from log import logger
from pyrogram.types import User, Chat

COMMANDS = {
    "kick": "封禁用户/频道",
    "unban": "解封用户/频道",
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


async def member_is_admin(cli: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await cli.get_chat_member(chat_id, user_id)
    except Exception as e:
        logger.exception(e)
        logger.warning(f"获取成员权限失败: chat_id={chat_id}, user_id={user_id}")
        return False

    return member.status in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }


async def delete_messages(
    cli: Client, chat_id: int, message_ids: list[int], delay: int = 5
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
                await cli.delete_messages(chat_id, chunk)
            except Exception as e:
                logger.exception(e)
                logger.warning(
                    f"批量删除消息失败, 尝试逐条删除: chat_id={chat_id}, ids={chunk}"
                )
                for message_id in chunk:
                    try:
                        await cli.delete_messages(chat_id, message_id)
                    except Exception as item_error:
                        logger.exception(item_error)
                        logger.warning(
                            f"删除消息失败: chat_id={chat_id}, message_id={message_id}"
                        )
    except Exception as e:
        logger.exception(e)
        logger.warning(f"删除消息流程失败: chat_id={chat_id}, ids={message_ids}")


def decode_start_payload(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode()


async def build_start_link(cli: Client, value: object) -> str:
    username = cli.me.username if cli.me else ""
    if not username:
        raise ValueError("没有 username")
    payload = base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")
    return f"https://t.me/{username}?start={payload}"


async def delete_member_messages(
    cli: Client,
    chat_id: int,
    user_id: int,
    msg_id: int,
    limit: int = 100,
    delay: int = 0,
) -> None:
    """
    删除最近 100 条消息
    """
    if delay:
        await asyncio.sleep(delay)
    msgs = await cli.get_messages(
        chat_id,
        message_ids=list(
            range(max(msg_id - (limit // 2), 1), msg_id + (limit // 2) + 1)
        ),
    )

    dms = [
        m.id for m in msgs if not m.empty and m.from_user and m.from_user.id == user_id
    ]
    await cli.delete_messages(chat_id, dms)
