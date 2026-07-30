from plugins.filters import guest_bot_message
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
