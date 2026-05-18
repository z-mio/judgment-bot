from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

router = Router()


@router.message(F.left_chat_member | F.new_chat_members)
async def delete_service_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
