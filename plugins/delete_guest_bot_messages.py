from typing import Any

from pyrogram import Client, filters
from pyrogram.types import Message


async def _guest_bot_message(_: Any, __: Any, message: Message) -> bool:
    return bool(
        getattr(message, "guest_bot_caller_chat", None)
        or getattr(message, "guest_bot_caller_user", None)
    )


guest_bot_message = filters.create(_guest_bot_message)


@Client.on_message(guest_bot_message & filters.admin)
async def delete_guest_bot_message(_: Client, message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass
