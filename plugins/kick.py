from datetime import datetime

from pyrogram import Client, enums, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from i18n import t_
from log import logger
from services.kick_cooldown_manager import kick_cooldown
from services.recent_message_cache import get_recent_message_ids_by_user
from utils.util import delete_messages, get_md_chat_link, member_is_admin


@Client.on_message(filters.command("kick") & filters.group & filters.admin)
async def kick(client: Client, message: Message) -> None:
    _t = t_[message]

    if (
        not message.from_user
        or not message.from_user.id
        or not message.chat
        or message.chat.id is None
    ):
        return
    chat_id = int(message.chat.id)

    if not message.reply_to_message:
        m = await message.reply(_t("请回复一条消息"))
        await delete_messages(client, chat_id, [message.id, m.id])
    elif (
        message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == message.from_user.id
    ):
        await message.reply(_t("紫砂吗? 有意思"))
    elif (
        message.reply_to_message.from_user
        and client.me
        and message.reply_to_message.from_user.id == client.me.id
    ):
        await message.reply(_t("big胆!"))
    elif message.reply_to_message.sender_chat:
        await message.reply(_t("封禁频道请使用 /bc"))
    elif not message.reply_to_message.from_user:
        await message.reply(_t("无法识别目标用户"))
    else:
        if await member_is_admin(client, chat_id, int(message.from_user.id)):
            await admin_kick(message, client)
        else:
            await member_kick_button(message, client)


@Client.on_callback_query(filters.regex(r"^mk="))
async def member_kick_callback(client: Client, callback: CallbackQuery) -> None:
    _t = t_[callback.from_user]

    if not isinstance(callback.message, Message) or not callback.data:
        await callback.answer(_t("操作已失效"), show_alert=True)
        return
    if not callback.message.chat or callback.message.chat.id is None:
        await callback.answer(_t("操作已失效"), show_alert=True)
        return
    chat_id = int(callback.message.chat.id)
    data_text = (
        callback.data.decode() if isinstance(callback.data, bytes) else callback.data
    )

    try:
        data = parse_member_kick_data(data_text)
        action_user_id = int(data["u"])
        target_message_id = int(data["m"])
        target_user_id = int(data["t"])
        action = data["mk"]
    except Exception:
        await callback.answer(_t("操作已失效"), show_alert=True)
        return
    if callback.from_user.id != action_user_id:
        await callback.answer(_t("这不是你的操作"), show_alert=True)
        return

    if action == "c":
        await member_kick(
            callback.message, client, action_user_id, target_message_id, target_user_id
        )
    elif action == "x":
        await kick_cooldown.clear_cooldown(chat_id, action_user_id)
        await callback.message.edit_text(_t("已取消操作"))
        command_message_id = (
            callback.message.reply_to_message.id
            if callback.message.reply_to_message
            else None
        )
        ids = [callback.message.id]
        if command_message_id:
            ids.append(command_message_id)
        await delete_messages(client, chat_id, ids)


def parse_member_kick_data(data: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in data.split(";"))


def joined_days(joined_date: datetime | None) -> int:
    if not joined_date:
        return 114514
    now = datetime.now(joined_date.tzinfo) if joined_date.tzinfo else datetime.now()
    return (now - joined_date).days


async def member_kick_button(message: Message, client: Client) -> None:
    _t = t_[message]
    from_user = message.from_user
    if not from_user or not from_user.id or not message.chat or message.chat.id is None:
        return
    chat_id = int(message.chat.id)
    action_user_id = int(from_user.id)

    target = message.reply_to_message
    if not target or not target.from_user or not target.from_user.id:
        await message.reply(_t("无法识别目标用户"))
        return
    target_user_id = int(target.from_user.id)

    least_joined_days = 30
    target_joined_days = 30
    try:
        member = await message.chat.get_member(action_user_id)
    except UserNotParticipant:
        await message.reply(_t("非群组成员, 请先加入群组"))
        return

    try:
        target_member = await message.chat.get_member(target_user_id)
    except UserNotParticipant:
        pass
    else:
        target_days = joined_days(target_member.joined_date)
        if target_days > target_joined_days:
            await message.reply(
                _t(
                    f"{get_md_chat_link(target_member.user)} 入群天数 <code>{target_days}</code> 天, "
                    f"大于 <code>{target_joined_days}</code> 天, 无法击落"
                ),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            return

    action_days = joined_days(member.joined_date)
    if action_days < least_joined_days:
        await message.reply(
            _t(
                f"此功能需要入群天数大于 <code>{least_joined_days}</code> 天\n"
                f"已入群天数: <code>{action_days}</code> 天"
            )
        )
        return

    if await kick_cooldown.can_user_kick(chat_id, action_user_id):
        await kick_cooldown.set_cooldown(chat_id, action_user_id)
    else:
        remaining_time = await kick_cooldown.get_remaining_time_formatted(
            chat_id, action_user_id
        )
        await message.reply(
            _t(
                f"<b>冷却中... | 剩余: {remaining_time}</b>\n如有广告哥, 可喊其他群友帮忙砍一刀"
            )
        )
        return

    callback_base = f"u={action_user_id};m={target.id};t={target_user_id}"

    await message.reply(
        _t(
            f"<b>确定要击落 {get_md_chat_link(target.from_user)} 吗?</b>\n\n<b>本功能仅可用于击落广告哥, 切勿意气用事</b>"
        ),
        reply_markup=Ikm(
            [
                [
                    Ikb(
                        text=_t("广告哥,击落!"),
                        callback_data=f"mk=c;{callback_base}",
                    ),
                    Ikb(
                        text=_t("手滑了"),
                        callback_data=f"mk=x;{callback_base}",
                    ),
                ]
            ]
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def member_kick(
    message: Message,
    client: Client,
    action_user_id: int,
    target_message_id: int,
    target_user_id: int,
) -> None:
    command_message = message.reply_to_message
    _t = t_[command_message or message]
    if not message.chat or message.chat.id is None:
        await message.edit_text(_t("击落失败"))
        return
    chat_id = int(message.chat.id)

    try:
        if await member_is_admin(client, chat_id, target_user_id):
            await message.edit_text(_t("造反吗? 有意思"))
            await kick_cooldown.clear_cooldown(chat_id, action_user_id)
            return

        target_user = await client.get_chat_member(chat_id, target_user_id)
        await client.ban_chat_member(chat_id, target_user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await message.edit_text(_t("击落失败"))
        await kick_cooldown.clear_cooldown(chat_id, action_user_id)
    else:
        command_message_id = command_message.id if command_message else None
        ids = await get_recent_message_ids_by_user(chat_id, target_user_id)
        ids.append(target_message_id)
        if command_message_id:
            ids.append(command_message_id)

        action_user_link = (
            get_md_chat_link(command_message.from_user)
            if command_message and command_message.from_user
            else str(action_user_id)
        )
        target_user_link = get_md_chat_link(target_user.user)
        await message.edit_text(
            _t(f"{action_user_link} 已击落 {target_user_link}"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        await delete_messages(client, chat_id, ids, delay=0)
        if target_user.user.is_bot:
            return

        admins = "\n".join(
            [
                f"• {get_md_chat_link(member.user)}"
                async for member in message.chat.get_members(
                    filter=enums.ChatMembersFilter.ADMINISTRATORS
                )
                if member.user.is_bot is False
            ]
        )
        try:
            await client.send_message(
                target_user_id,
                _t(
                    f"<b>你已被 {action_user_link} 踢出 {get_md_chat_link(message.chat)}</b>\n如有异议请联系群组管理:\n"
                    f"{admins}"
                ),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.exception(e)
            logger.error("通知用户失败, 以上为错误信息")


async def admin_kick(message: Message, client: Client) -> None:
    _t = t_[message]
    rm = message.reply_to_message
    if (
        not rm
        or not rm.from_user
        or not rm.from_user.id
        or not message.chat
        or message.chat.id is None
    ):
        return
    chat_id = int(message.chat.id)
    target_user_id = int(rm.from_user.id)

    if await member_is_admin(client, chat_id, target_user_id):
        m = await message.reply(_t("禁止窝里斗"))
        await delete_messages(client, chat_id, [message.id, m.id])
        return

    try:
        await client.ban_chat_member(chat_id, target_user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await message.reply(_t("击落失败"))
    else:
        m = await message.reply(_t("已击落"))
        ids = await get_recent_message_ids_by_user(chat_id, target_user_id)
        ids.extend([rm.id, message.id, m.id])
        await delete_messages(client, chat_id, ids, delay=0)
