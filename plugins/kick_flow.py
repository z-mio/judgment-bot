from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pyrogram import Client, enums
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    Chat,
    ChatMember,
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
    User,
)

from log import logger
from plugins.helpers import (
    delete_messages,
    get_md_chat_link,
    member_is_admin,
    delete_member_messages,
)
from services.kick_cooldown_manager import kick_cooldown

LEAST_JOINED_DAYS = 30
TARGET_JOINED_DAYS = 30


@dataclass(slots=True)
class KickCommandContext:
    chat: Chat
    chat_id: int
    action_user: User | None  # 匿名管理员时为 None
    reply: Message


@dataclass(slots=True)
class MemberKickConfirmData:
    action: Literal["c", "x"]
    action_user_id: int
    target_message_id: int
    target_user_id: int


def get_kick_command_context(msg: Message) -> KickCommandContext | None:
    if not msg.chat or msg.chat.id is None or not msg.reply_to_message:
        return None
    # 匿名管理员: from_user 为 None, sender_chat 为群组本身
    if not msg.from_user and not msg.sender_chat:
        return None
    return KickCommandContext(
        chat=msg.chat,
        chat_id=msg.chat.id,
        action_user=msg.from_user,
        reply=msg.reply_to_message,
    )


def parse_member_kick_data(data: str) -> MemberKickConfirmData:
    parts = dict(part.split("=", 1) for part in data.split(";"))
    return MemberKickConfirmData(
        action=parts["mk"],  # type: ignore[arg-type]
        action_user_id=int(parts["u"]),
        target_message_id=int(parts["m"]),
        target_user_id=int(parts["t"]),
    )


def joined_days(joined_date: datetime | None) -> int:
    if not joined_date:
        return 114514
    now = datetime.now(joined_date.tzinfo) if joined_date.tzinfo else datetime.now()
    return (now - joined_date).days


async def reply_and_delete(cli: Client, msg: Message, chat_id: int, text: str) -> None:
    reply = await msg.reply(text)
    message_ids = [msg.id]
    if reply:
        message_ids.append(reply.id)
    await delete_messages(cli, chat_id, message_ids)


async def assert_member_is_admin(
    cli: Client, chat_id: int, user_id: int, msg: Message
) -> bool:
    if await member_is_admin(cli, chat_id, user_id):
        return True
    await msg.reply("权限不足")
    return False


async def ban_channel(cli: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None:
        return
    # 匿名管理员: from_user 为 None, 但 sender_chat 存在
    if not msg.from_user and not msg.sender_chat:
        return

    chat_id = msg.chat.id
    # 匿名管理员一定是管理员, 无需额外检查
    if msg.from_user and not await assert_member_is_admin(
        cli, chat_id, msg.from_user.id, msg
    ):
        return

    channel_msg = msg.reply_to_message
    if not channel_msg:
        await reply_and_delete(cli, msg, chat_id, "请回复一条频道消息")
        return

    sender_chat = channel_msg.sender_chat
    if not sender_chat or sender_chat.id is None:
        await reply_and_delete(cli, msg, chat_id, "请回复频道消息")
        return

    try:
        await cli.ban_chat_member(chat_id, sender_chat.id)
    except Exception as e:
        logger.exception(e)
        logger.error("封禁频道失败, 以上为错误信息")
        await msg.reply("封禁频道失败")
        return

    await msg.reply(
        f"已封禁频道 {get_md_chat_link(sender_chat)}",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def member_kick_button(msg: Message) -> None:
    context = get_kick_command_context(msg)
    if not context or context.action_user is None:
        return

    target_user = context.reply.from_user
    if not target_user:
        await msg.reply("无法识别目标用户")
        return

    try:
        member = await context.chat.get_member(context.action_user.id)
    except UserNotParticipant:
        await msg.reply("非群组成员, 请先加入群组")
        return

    if not await can_kick_target(msg, context.chat, target_user.id):
        return

    action_days = joined_days(member.joined_date)
    if action_days < LEAST_JOINED_DAYS:
        await msg.reply(
            f"此功能需要入群天数大于 `{LEAST_JOINED_DAYS}` 天\n"
            f"已入群天数: `{action_days}` 天"
        )
        return

    if not await start_kick_cooldown(msg, context.chat_id, context.action_user.id):
        return

    await send_member_kick_confirm(msg, context.action_user.id, context.reply)


async def can_kick_target(msg: Message, chat: Chat, target_user_id: int) -> bool:
    try:
        target_member = await chat.get_member(target_user_id)
    except UserNotParticipant:
        return True
    if not target_member or not target_member.user:
        return False
    target_days = joined_days(target_member.joined_date)
    if target_days > TARGET_JOINED_DAYS:
        await msg.reply(
            f"{get_md_chat_link(target_member.user)} 入群天数 `{target_days}` 天, "
            f"大于 `{TARGET_JOINED_DAYS}` 天, 无法击落",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return False
    return True


async def start_kick_cooldown(msg: Message, chat_id: int, action_user_id: int) -> bool:
    if await kick_cooldown.can_user_kick(chat_id, action_user_id):
        await kick_cooldown.set_cooldown(chat_id, action_user_id)
        return True

    remaining_time = await kick_cooldown.get_remaining_time_formatted(
        chat_id, action_user_id
    )
    await msg.reply(
        f"**冷却中... | 剩余: {remaining_time}**\n如有广告哥, 可喊其他群友帮忙砍一刀"
    )
    return False


async def send_member_kick_confirm(
    msg: Message, action_user_id: int, target: Message
) -> None:
    if not target.from_user:
        await msg.reply("无法识别目标用户")
        return

    callback_base = f"u={action_user_id};m={target.id};t={target.from_user.id}"
    await msg.reply(
        f"**确定要击落 {get_md_chat_link(target.from_user)} 吗?**\n\n**本功能仅可用于击落广告哥, 切勿意气用事**",
        reply_markup=Ikm(
            [
                [
                    Ikb(
                        text="广告哥,击落!",
                        callback_data=f"mk=c;{callback_base}",
                    ),
                    Ikb(
                        text="手滑了",
                        callback_data=f"mk=x;{callback_base}",
                    ),
                ]
            ]
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def cancel_member_kick(
    cli: Client, msg: Message, chat_id: int, action_user_id: int
) -> None:
    await kick_cooldown.clear_cooldown(chat_id, action_user_id)
    await msg.edit_text("已取消操作")

    ids = [msg.id]
    if msg.reply_to_message:
        ids.append(msg.reply_to_message.id)
    await delete_messages(cli, chat_id, ids)


async def get_target_member(
    cli: Client, chat_id: int, target_user_id: int
) -> ChatMember | None:
    try:
        return await cli.get_chat_member(chat_id, target_user_id)
    except Exception as e:
        logger.exception(e)
        logger.warning("获取被击落用户信息失败, 将继续执行 ban 和删除消息")
        return None


async def ban_member(cli: Client, chat_id: int, target_user_id: int) -> bool:
    try:
        await cli.ban_chat_member(chat_id, target_user_id)
        return True
    except Exception as e:
        logger.exception(e)
        logger.error("击落用户失败, 将继续删除广告消息")
        return False


async def notify_kicked_member(
    cli: Client, chat: Chat, target_user_id: int, action_user_link: str
) -> None:
    admins = "\n".join(
        [
            f"• {get_md_chat_link(member.user)}"
            async for member in chat.get_members(
                filter=enums.ChatMembersFilter.ADMINISTRATORS
            )
            if member.user and not member.user.is_bot
        ]
    )

    try:
        await cli.send_message(
            target_user_id,
            f"**你已被 {action_user_link} 踢出 {get_md_chat_link(chat)}**\n如有异议请联系群组管理:\n"
            f"{admins}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.exception(e)
        logger.error("通知用户失败, 以上为错误信息")


async def member_kick(
    msg: Message,
    cli: Client,
    action_user_id: int,
    target_message_id: int,
    target_user_id: int,
) -> None:
    command_message = msg.reply_to_message

    if not msg.chat or msg.chat.id is None:
        await msg.edit_text("击落失败")
        return

    chat_id = msg.chat.id
    if await member_is_admin(cli, chat_id, target_user_id):
        await msg.edit_text("造反吗? 有意思")
        await kick_cooldown.clear_cooldown(chat_id, action_user_id)
        return

    target_member = await get_target_member(cli, chat_id, target_user_id)
    ban_success = await ban_member(cli, chat_id, target_user_id)
    await delete_member_messages(cli, chat_id, target_user_id, target_message_id)

    action_user_link = (
        get_md_chat_link(command_message.from_user)
        if command_message and command_message.from_user
        else str(action_user_id)
    )
    target_user_link = (
        get_md_chat_link(target_member.user)
        if target_member and target_member.user
        else str(target_user_id)
    )
    result_text = (
        f"{action_user_link} 已击落 {target_user_link}"
        if ban_success
        else f"{action_user_link} 已删除广告消息, 但击落 {target_user_link} 失败"
    )
    await msg.edit_text(
        result_text,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

    if not ban_success:
        await kick_cooldown.clear_cooldown(chat_id, action_user_id)
        return
    if not target_member or not target_member.user or target_member.user.is_bot:
        return

    await notify_kicked_member(cli, msg.chat, target_user_id, action_user_link)


async def admin_kick(cli: Client, msg: Message) -> None:
    rm = msg.reply_to_message
    if not rm or not rm.from_user or not msg.chat or msg.chat.id is None:
        return

    chat_id = msg.chat.id
    target_user_id = rm.from_user.id

    if await member_is_admin(cli, chat_id, target_user_id):
        await reply_and_delete(cli, msg, chat_id, "禁止窝里斗")
        return

    try:
        await cli.ban_chat_member(chat_id, target_user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await msg.reply("击落失败")
        return

    m = await msg.reply("已击落")
    await delete_member_messages(cli, chat_id, target_user_id, rm.id)
    message_ids = [msg.id]
    if m:
        message_ids.append(m.id)
    await delete_messages(cli, msg.chat.id, message_ids)
