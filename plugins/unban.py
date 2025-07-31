from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions, LinkPreviewOptions
from pyrogram.enums.chat_type import ChatType

from log import logger
from utils.util import member_is_admin, get_md_chat_link


@Client.on_message(filters.command("unban") & filters.group & filters.admin)
async def unban(cli: Client, msg: Message):
    if not await member_is_admin(cli, msg.chat.id, msg.from_user.id):
        return await msg.reply("权限不足")

    if not msg.command[1:]:
        return await msg.reply("请加上用户名或id\n例: `/unban @username`")

    unban_user = msg.command[1]

    try:
        unban_user = await cli.get_chat(unban_user)
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
        else:
            await msg.chat.unban_member(unban_user.id)

    except Exception as e:
        logger.exception(e)
        logger.error("放出用户失败, 以上为错误信息")
        return await msg.reply(
            f"放出 {get_md_chat_link(unban_user)} 失败",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    else:
        return await msg.reply(
            f"已放出 {get_md_chat_link(unban_user)}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
