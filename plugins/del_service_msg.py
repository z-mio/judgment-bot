from pyrogram import Client, filters
from pyrogram.types import Message


@Client.on_message(filters.left_chat_member & filters.new_chat_members & filters.admin)
async def delete_service_message(_, msg: Message):
    await msg.delete()
