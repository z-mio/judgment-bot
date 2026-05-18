from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message

from i18n import t_
from log import logger
from utils.util import delete_messages, get_md_chat_link, member_is_admin

router = Router()


@router.message(Command("bc"), F.chat.type.in_({"group", "supergroup"}))
async def ban_channel(message: Message, bot: Bot) -> None:
    _t = t_[message]

    if not message.from_user or not await member_is_admin(
        bot, message.chat.id, message.from_user.id
    ):
        await message.reply(_t("权限不足"))
        return

    channel_msg = message.reply_to_message
    if not channel_msg:
        m = await message.reply(_t("请回复一条频道消息"))
        await delete_messages(bot, message.chat.id, [message.message_id, m.message_id])
        return
    if not channel_msg.sender_chat:
        m = await message.reply(_t("请回复频道消息"))
        await delete_messages(bot, message.chat.id, [message.message_id, m.message_id])
        return

    try:
        await bot.ban_chat_sender_chat(message.chat.id, channel_msg.sender_chat.id)
    except Exception as e:
        logger.exception(e)
        logger.error("封禁频道失败, 以上为错误信息")
        await message.reply(_t("封禁频道失败"))
        return
    else:
        await message.reply(
            _t(f"已封禁频道 {get_md_chat_link(channel_msg.sender_chat)}"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
