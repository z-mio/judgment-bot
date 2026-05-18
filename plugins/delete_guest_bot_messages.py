from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


router = Router()


@router.message(F.guest_bot_caller_chat | F.guest_bot_caller_user)
async def delete_guest_bot_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
