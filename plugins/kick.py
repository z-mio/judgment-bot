import asyncio

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import BadRequest
from pyrogram.types import Message


@Client.on_message(filters.command("kick") & filters.group & filters.admin)
async def kick(cli: Client, msg: Message):
    user = await msg.chat.get_member(msg.from_user.id)
    if user.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
        m = await msg.reply_text("🤡")
        return await delete_messages(cli, msg.chat.id, [msg.id, m.id])

    if rm := msg.reply_to_message:
        try:
            await cli.ban_chat_member(rm.chat.id, rm.from_user.id)
        except BadRequest:
            m = await msg.reply_text("禁止窝里斗")
            await delete_messages(cli, msg.chat.id, [msg.id, m.id])
        else:
            await rm.delete()
            m = await msg.reply_text("已击落")
            await delete_messages(cli, msg.chat.id, [msg.id, m.id])
    else:
        m = await msg.reply("请回复一条消息")
        return await delete_messages(cli, msg.chat.id, [msg.id, m.id])


async def delete_messages(cli: Client, chat_id: int, message_ids: list[int]):
    try:
        await asyncio.sleep(5)
        await cli.delete_messages(chat_id, message_ids)
    except Exception:
        ...
