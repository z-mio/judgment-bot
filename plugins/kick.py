from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from log import logger
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

logger = logger.bind(name="Kick")


@Client.on_message(filters.command("kick") & filters.group & filters.admin)
async def kick(cli: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None:
        return
    # 匿名管理员: from_user 为 None, sender_chat 为群组本身
    if not msg.from_user and (not msg.sender_chat or msg.sender_chat.id != msg.chat.id):
        return

    actor = msg.from_user.id if msg.from_user else "匿名管理员"

    if not msg.reply_to_message:
        logger.debug(f"忽略击落: 未回复消息 | user_id={actor} | chat_id={msg.chat.id}")
        await reply_and_delete(cli, msg, msg.chat.id, "请回复一条消息")
        return

    context = get_kick_command_context(msg)
    if not context:
        return

    if (msg.sender_chat and (msg.sender_chat == context.reply.sender_chat)) or (
        context.action_user
        and context.reply.from_user
        and context.reply.from_user.id == context.action_user.id
    ):
        logger.info(
            f"击落被拒: 目标是自己 | user_id={actor} | chat_id={context.chat_id}"
        )
        await msg.reply("紫砂吗? 有意思")
        return

    if context.reply.from_user and cli.me and context.reply.from_user.id == cli.me.id:
        logger.info(
            f"击落被拒: 目标是 Bot | user_id={actor} | chat_id={context.chat_id}"
        )
        await msg.reply("big胆!")
        return

    if context.reply.sender_chat:
        await ban_channel(cli, msg)
        return

    if not context.reply.from_user:
        logger.info(
            f"击落被拒: 无法识别目标用户 | user_id={actor} | chat_id={context.chat_id}"
        )
        await msg.reply("无法识别目标用户")
        return

    # 匿名管理员一定是管理员, 直接走 admin_kick
    if not context.action_user:
        await admin_kick(cli, msg)
        return

    if await member_is_admin(cli, context.chat_id, context.action_user.id):
        logger.debug(
            f"击落分支: 管理员直接击落 | user_id={actor} | chat_id={context.chat_id}"
        )
        await admin_kick(cli, msg)
    else:
        logger.debug(
            f"击落分支: 群友确认流程 | user_id={actor} | chat_id={context.chat_id}"
        )
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
