from pyrogram import Client, filters
from pyrogram.types import LinkPreviewOptions, Message

from i18n import t_
from log import logger
from utils.util import delete_messages, get_md_chat_link, member_is_admin


@Client.on_message(filters.command("bc") & filters.group & filters.admin)
async def ban_channel(client: Client, message: Message) -> None:
    _t = t_[message]

    if not message.from_user or not message.chat or message.chat.id is None:
        return
    chat_id = int(message.chat.id)
    if not await member_is_admin(client, chat_id, message.from_user.id):
        await message.reply(_t("权限不足"))
        return

    channel_msg = message.reply_to_message
    if not channel_msg:
        m = await message.reply(_t("请回复一条频道消息"))
        await delete_messages(client, chat_id, [message.id, m.id])
        return
    if not channel_msg.sender_chat or channel_msg.sender_chat.id is None:
        m = await message.reply(_t("请回复频道消息"))
        await delete_messages(client, chat_id, [message.id, m.id])
        return

    try:
        await client.ban_chat_member(chat_id, int(channel_msg.sender_chat.id))
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
