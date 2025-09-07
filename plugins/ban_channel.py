from pyrogram import Client, filters
from pyrogram.types import Message, LinkPreviewOptions

from i18n import t_
from log import logger
from utils.util import delete_messages, get_md_chat_link, member_is_admin


@Client.on_message(filters.command("bc") & filters.group & filters.admin)
async def ban_channel(cli: Client, msg: Message):
    _t = t_(msg)

    if not await member_is_admin(cli, msg.chat.id, msg.from_user.id):
        return await msg.reply(_t("权限不足"))

    channel_msg = msg.reply_to_message
    if not channel_msg:
        m = await msg.reply(_t("请回复一条频道消息"))
        return await delete_messages(cli, msg.chat.id, [msg.id, m.id])
    if not channel_msg.sender_chat:
        m = await msg.reply(_t("请回复频道消息"))
        return await delete_messages(cli, msg.chat.id, [msg.id, m.id])

    try:
        await msg.chat.ban_member(channel_msg.sender_chat.id)
    except Exception as e:
        logger.exception(e)
        logger.error("封禁频道失败, 以上为错误信息")
        return await msg.reply(_t("封禁频道失败"))
    else:
        await msg.reply(
            _t(f"已封禁频道 {get_md_chat_link(channel_msg.sender_chat)}"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
