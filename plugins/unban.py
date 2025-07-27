from pyrogram import Client, filters
from pyrogram.types import Message

from log import logger
from utils.util import member_is_admin


@Client.on_message(filters.command("unban") & filters.group & filters.admin)
async def unban(cli: Client, msg: Message):
    if not await member_is_admin(cli, msg.chat.id, msg.from_user.id):
        return await msg.reply("权限不足")

    if not msg.command[1:]:
        return await msg.reply("请加上用户名或id\n例: `/unban @username`")

    unban_user = msg.command[1]
    try:
        await msg.chat.unban_member(unban_user)
    except Exception as e:
        logger.exception(e)
        logger.error("放出用户失败, 以上为错误信息")
        return await msg.reply(f"放出 `{unban_user}` 失败")
    else:
        return await msg.reply(f"已放出 `{unban_user}`")
