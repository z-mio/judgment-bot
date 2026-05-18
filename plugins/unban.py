from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from i18n import t_
from log import logger
from utils.util import get_chat_link, get_md_chat_link, html_code, member_is_admin
from validator.easy_validator import full_chat_permissions

router = Router()


@router.message(Command("unban"), F.chat.type.in_({"group", "supergroup"}))
async def unban(message: Message, command: CommandObject, bot: Bot) -> None:
    _t = t_[message]

    if not message.from_user or not await member_is_admin(
        bot, message.chat.id, message.from_user.id
    ):
        await message.reply(_t("权限不足"))
        return

    if not command.args:
        await message.reply(_t("请加上用户名或id\n例: <code>/unban @username</code>"))
        return

    unban_user_id = command.args.split(maxsplit=1)[0]

    try:
        unban_user = await bot.get_chat(unban_user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("获取用户信息失败, 以上为错误信息")
        await message.reply(
            _t(f"获取 {html_code(unban_user_id)} 信息失败"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    try:
        if unban_user.type == ChatType.PRIVATE:
            await bot.unban_chat_member(
                message.chat.id,
                unban_user.id,
                only_if_banned=True,
            )
            try:
                await bot.restrict_chat_member(
                    message.chat.id,
                    unban_user.id,
                    permissions=full_chat_permissions(),
                )
            except Exception as e:
                logger.exception(e)
                logger.error("恢复用户权限失败, 以上为错误信息")
            try:
                await bot.send_message(
                    unban_user.id,
                    _t(
                        f"{get_md_chat_link(message.from_user)} 已在 {get_md_chat_link(message.chat)} 中将你解除封禁"
                    ),
                    reply_markup=Ikm(
                        inline_keyboard=[
                            [
                                Ikb(
                                    text=_t("点击重新加入群组"),
                                    url=get_chat_link(message.chat),
                                )
                            ]
                        ]
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception as e:
                logger.exception(e)
                logger.error("通知用户 [解除封禁] 失败, 以上为错误信息")
        else:
            await bot.unban_chat_sender_chat(message.chat.id, unban_user.id)

    except Exception as e:
        logger.exception(e)
        logger.error("放出用户失败, 以上为错误信息")
        await message.reply(
            _t(f"放出 {get_md_chat_link(unban_user)} 失败"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
    else:
        await message.reply(
            _t(f"已放出 {get_md_chat_link(unban_user)}"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
