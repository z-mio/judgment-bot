from pyrogram import Client, filters
from pyrogram.types import Message

from services.recent_message_cache import add_recent_message


@Client.on_message(filters.group, group=10)
async def track_recent_message(_: Client, message: Message) -> None:
    if not message.from_user or not message.chat or message.chat.id is None:
        return

    await add_recent_message(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        message_id=message.id,
    )
