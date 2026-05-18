from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from i18n import t_
from log import logger
from services.kick_cooldown_manager import kick_cooldown
from utils.util import delete_messages, get_md_chat_link, member_is_admin

router = Router()


@router.message(Command("kick"), F.chat.type.in_({"group", "supergroup"}))
async def kick(message: Message, bot: Bot) -> None:
    _t = t_[message]

    if not message.from_user:
        return

    if not message.reply_to_message:
        m = await message.reply(_t("请回复一条消息"))
        await delete_messages(bot, message.chat.id, [message.message_id, m.message_id])
    elif (
        message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == message.from_user.id
    ):
        await message.reply(_t("紫砂吗? 有意思"))
    elif (
        message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot.id
    ):
        await message.reply(_t("big胆!"))
    elif message.reply_to_message.sender_chat:
        await message.reply(_t("封禁频道请使用 /bc"))
    elif not message.reply_to_message.from_user:
        await message.reply(_t("无法识别目标用户"))
    else:
        if await member_is_admin(bot, message.chat.id, message.from_user.id):
            await admin_kick(message, bot)
        else:
            await member_kick_button(message, bot)


@router.callback_query(F.data.startswith("mk="))
async def member_kick_callback(callback: CallbackQuery, bot: Bot) -> None:
    _t = t_[callback.from_user]

    if not isinstance(callback.message, Message) or not callback.data:
        await callback.answer(_t("操作已失效"), show_alert=True)
        return

    try:
        data = parse_member_kick_data(callback.data)
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
            callback.message, bot, action_user_id, target_message_id, target_user_id
        )
    elif action == "x":
        await kick_cooldown.clear_cooldown(callback.message.chat.id, action_user_id)
        await callback.message.edit_text(_t("已取消操作"))
        command_message_id = (
            callback.message.reply_to_message.message_id
            if callback.message.reply_to_message
            else None
        )
        ids = [callback.message.message_id]
        if command_message_id:
            ids.append(command_message_id)
        await delete_messages(bot, callback.message.chat.id, ids)


def parse_member_kick_data(data: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in data.split(";"))


async def member_kick_button(message: Message, bot: Bot) -> None:
    _t = t_[message]
    from_user = message.from_user
    if not from_user:
        return

    try:
        await bot.get_chat_member(message.chat.id, from_user.id)
    except TelegramBadRequest:
        await message.reply(_t("非群组成员, 请先加入群组"))
        return

    if await kick_cooldown.can_user_kick(message.chat.id, from_user.id):
        await kick_cooldown.set_cooldown(message.chat.id, from_user.id)
    else:
        remaining_time = await kick_cooldown.get_remaining_time_formatted(
            message.chat.id, from_user.id
        )
        await message.reply(
            _t(
                f"<b>冷却中... | 剩余: {remaining_time}</b>\n如有广告哥, 可喊其他群友帮忙砍一刀"
            )
        )
        return

    target = message.reply_to_message
    if not target or not target.from_user:
        await message.reply(_t("无法识别目标用户"))
        return
    callback_base = f"u={from_user.id};m={target.message_id};t={target.from_user.id}"

    await message.reply(
        _t(
            f"<b>确定要击落 {get_md_chat_link(target.from_user)} 吗?</b>\n\n<b>本功能仅可用于击落广告哥, 切勿意气用事</b>"
        ),
        reply_markup=Ikm(
            inline_keyboard=[
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
    bot: Bot,
    action_user_id: int,
    target_message_id: int,
    target_user_id: int,
) -> None:
    command_message = message.reply_to_message
    _t = t_[command_message or message]

    try:
        if await member_is_admin(bot, message.chat.id, target_user_id):
            await message.edit_text(_t("造反吗? 有意思"))
            await kick_cooldown.clear_cooldown(message.chat.id, action_user_id)
            return

        target_user = await bot.get_chat_member(message.chat.id, target_user_id)
        await bot.ban_chat_member(message.chat.id, target_user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await message.edit_text(_t("击落失败"))
        await kick_cooldown.clear_cooldown(message.chat.id, action_user_id)
    else:
        command_message_id = command_message.message_id if command_message else None
        ids = [target_message_id]
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
        await delete_messages(bot, message.chat.id, ids, delay=0)
        if target_user.user.is_bot:
            return

        admins = "\n".join(
            [
                f"• {get_md_chat_link(member.user)}"
                for member in await bot.get_chat_administrators(message.chat.id)
                if member.user.is_bot is False
            ]
        )
        try:
            await bot.send_message(
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


async def admin_kick(message: Message, bot: Bot) -> None:
    _t = t_[message]
    rm = message.reply_to_message
    if not rm or not rm.from_user:
        return

    if await member_is_admin(bot, message.chat.id, rm.from_user.id):
        m = await message.reply(_t("禁止窝里斗"))
        await delete_messages(bot, message.chat.id, [message.message_id, m.message_id])
        return

    try:
        await bot.ban_chat_member(rm.chat.id, rm.from_user.id)
    except Exception as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await message.reply(_t("击落失败"))
    else:
        await delete_messages(
            bot, rm.chat.id, [rm.message_id, message.message_id], delay=0
        )
        m = await message.answer(_t("已击落"))
        await delete_messages(bot, message.chat.id, [m.message_id])
