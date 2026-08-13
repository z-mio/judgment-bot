from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from plugins.helpers import member_is_admin
from plugins.kick_flow import (
    admin_kick,
    ban_channel,
    cancel_member_kick,
    get_kick_command_context,
    member_kick,
    member_kick_button,
    parse_member_kick_data,
    reply_and_delete,
)


@Client.on_message(filters.command("kick") & filters.group & filters.admin)
async def kick(cli: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None:
        return
    # 匿名管理员: from_user 为 None, sender_chat 为群组本身
    if not msg.from_user and (not msg.sender_chat or msg.sender_chat.id != msg.chat.id):
        return

    if not msg.reply_to_message:
        await reply_and_delete(cli, msg, msg.chat.id, "请回复一条消息")
        return

    context = get_kick_command_context(msg)
    if not context:
        return

    if (msg.sender_chat == context.reply.sender_chat) or (
        context.action_user
        and context.reply.from_user
        and context.reply.from_user.id == context.action_user.id
    ):
        await msg.reply("紫砂吗? 有意思")
        return

    if context.reply.from_user and cli.me and context.reply.from_user.id == cli.me.id:
        await msg.reply("big胆!")
        return

    if context.reply.sender_chat:
        await ban_channel(cli, msg)
        return

    if not context.reply.from_user:
        await msg.reply("无法识别目标用户")
        return

    # 匿名管理员一定是管理员, 直接走 admin_kick
    if not context.action_user:
        await admin_kick(cli, msg)
        return

    if await member_is_admin(cli, context.chat_id, context.action_user.id):
        await admin_kick(cli, msg)
    else:
        await member_kick_button(msg)


@Client.on_callback_query(filters.regex(r"^mk="))
async def member_kick_callback(cli: Client, cq: CallbackQuery) -> None:
    if not isinstance(cq.message, Message) or not cq.data:
        await cq.answer("操作已失效", show_alert=True)
        return

    message = cq.message
    if not message.chat or message.chat.id is None:
        await cq.answer("操作已失效", show_alert=True)
        return

    chat_id = message.chat.id
    data_text = cq.data.decode() if isinstance(cq.data, bytes) else cq.data

    try:
        data = parse_member_kick_data(data_text)
    except Exception:
        await cq.answer("操作已失效", show_alert=True)
        return

    if cq.from_user.id != data.action_user_id:
        await cq.answer("这不是你的操作", show_alert=True)
        return

    if data.action == "c":
        await member_kick(
            message,
            cli,
            data.action_user_id,
            data.target_message_id,
            data.target_user_id,
        )
    elif data.action == "x":
        await cancel_member_kick(cli, message, chat_id, data.action_user_id)
