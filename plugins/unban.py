from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    ChatPermissions,
    LinkPreviewOptions,
    InlineKeyboardMarkup as Ikm,
    InlineKeyboardButton as Ikb,
)
from pyrogram.enums.chat_type import ChatType

from log import logger
from utils.util import member_is_admin, get_md_chat_link, get_chat_link


@Client.on_message(filters.command("unban") & filters.group & filters.admin)
async def unban(cli: Client, msg: Message):
    if not await member_is_admin(cli, msg.chat.id, msg.from_user.id):
        await msg.reply("权限不足")
        return

    if not msg.command[1:]:
        await msg.reply("请加上用户名或id\n例: `/unban @username`")
        return

    unban_user = msg.command[1]

    try:
        unban_user = await cli.get_chat(unban_user)
    except Exception as e:
        logger.exception(e)
        logger.error("获取用户信息失败, 以上为错误信息")
        await msg.reply(
            f"获取 `{unban_user}` 信息失败",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    try:
        if unban_user.type == ChatType.PRIVATE:
            await msg.chat.restrict_member(
                unban_user.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_invite_users=True,
                    can_add_web_page_previews=True,
                ),
            )
            try:
                await cli.send_message(
                    unban_user.id,
                    f"{get_md_chat_link(msg.from_user)} 已在 {get_md_chat_link(msg.chat)} 中将你解除封禁",
                    reply_markup=Ikm([[Ikb("点击重新加入群组", url=get_chat_link(msg.chat))]]),
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            except Exception as e:
                logger.exception(e)
                logger.error("通知用户 [解除封禁] 失败, 以上为错误信息")
        else:
            await msg.chat.unban_member(unban_user.id)

    except Exception as e:
        logger.exception(e)
        logger.error("放出用户失败, 以上为错误信息")
        await msg.reply(
            f"放出 {get_md_chat_link(unban_user)} 失败",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
    else:
        await msg.reply(
            f"已放出 {get_md_chat_link(unban_user)}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
