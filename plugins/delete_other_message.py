from log import logger
from plugins.filters import guest_bot_message, verify_failed_member
from pyrogram import Client, filters
from pyrogram.types import Message


@Client.on_message(guest_bot_message & filters.admin)
async def delete_guest_bot_message(_: Client, msg: Message) -> None:
    try:
        await msg.delete()
    except Exception:
        pass


@Client.on_message(
    (filters.left_chat_member | filters.new_chat_members) & filters.admin
)
async def delete_service_message(_: Client, msg: Message) -> None:
    try:
        await msg.delete()
    except Exception:
        pass


@Client.on_message(filters.group & filters.admin & verify_failed_member)
async def delete_verify_failed_message(_: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None or not msg.from_user:
        return

    try:
        await msg.delete()
    except Exception as e:
        logger.exception(e)
        logger.warning(
            f"删除验证失败用户的消息失败: chat_id={msg.chat.id}, "
            f"user_id={msg.from_user.id}, message_id={msg.id}"
        )
        return

    logger.info(
        f"已删除验证失败用户的消息: {msg.from_user.full_name} | "
        f"{msg.from_user.id} | {msg.chat.id}"
    )
