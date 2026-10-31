from log import logger
from plugins.filters import guest_bot_message, verify_failed_member
from plugins.helpers import (
    delete_bot_messages,
    delete_messages,
    joined_days,
)
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logger.bind(name="Delete")

MEMBER_AGE_BYPASS_DAYS = 30


@Client.on_message(guest_bot_message & filters.admin)
async def delete_guest_bot_message(cli: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None:
        return

    caller = msg.guest_bot_caller_user or msg.guest_bot_caller_chat
    chat_id = msg.chat.id
    anchor_id = msg.reply_to_message.id if msg.reply_to_message else msg.id
    # 仅入群超过 30 天的成员可以使用游客 Bot, 其余调用一律删除
    member = None
    if caller and caller.id:
        try:
            member = await cli.get_chat_member(chat_id, caller.id)
        except Exception:
            pass
    days = joined_days(member.joined_date) if member else 0
    if days > MEMBER_AGE_BYPASS_DAYS:
        return

    try:
        await msg.delete()
        logger.debug(f"已删除游客 Bot 消息: chat_id={chat_id} | message_id={msg.id}")
        if msg.reply_to_message:
            await msg.reply_to_message.delete()
            logger.debug(
                f"已删除游客 Bot 回复的消息: chat_id={chat_id} | message_id={msg.id}"
            )
        # 广告中的命令/提及会触发其他 bot 响应一并清理
        deleted = await delete_bot_messages(cli, chat_id, anchor_id, delay=0)
        logger.debug(f"已删除后续 bot 消息: {deleted} 条 | chat_id={chat_id}")
    except Exception:
        logger.opt(exception=True).debug(
            f"删除游客 Bot 消息失败: chat_id={chat_id} | message_id={msg.id}"
        )

    try:
        notice = await cli.send_message(
            chat_id,
            f"入群 > 30 天才可使用游客 Bot\n当前入群天数: `{str(days)}`",
        )
        if notice:
            await delete_messages(cli, chat_id, [notice.id])
    except Exception:
        logger.opt(exception=True).debug(f"发送游客 Bot 提示失败: chat_id={chat_id}")


@Client.on_message(
    (filters.left_chat_member | filters.new_chat_members) & filters.admin
)
async def delete_service_message(_: Client, msg: Message) -> None:
    try:
        await msg.delete()
        logger.debug(
            f"已删除服务消息: chat_id={msg.chat.id if msg.chat else None} | "
            f"message_id={msg.id}"
        )
    except Exception:
        logger.opt(exception=True).debug(
            f"删除服务消息失败: chat_id={msg.chat.id if msg.chat else None} | "
            f"message_id={msg.id}"
        )


@Client.on_message(filters.group & filters.admin & verify_failed_member)
async def delete_verify_failed_message(cli: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None or not msg.from_user:
        return

    try:
        await msg.delete()
        logger.info(
            f"已删除验证失败用户的消息: {msg.from_user.full_name} | "
            f"user_id={msg.from_user.id} | chat_id={msg.chat.id} | message_id={msg.id}"
        )
    except Exception:
        logger.exception(
            f"删除验证失败用户的消息失败: user_id={msg.from_user.id} | "
            f"chat_id={msg.chat.id} | message_id={msg.id}"
        )

    try:
        await cli.ban_chat_member(msg.chat.id, msg.from_user.id)
        logger.info(
            f"击落验证失败用户完成: target_user_id={msg.from_user.id} | "
            f"target={msg.from_user.full_name} | chat_id={msg.chat.id}"
        )
    except Exception:
        logger.exception(
            f"击落验证失败用户失败: target_user_id={msg.from_user.id} | chat_id={msg.chat.id}"
        )
