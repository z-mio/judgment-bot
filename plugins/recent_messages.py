from aiogram import F, Router
from aiogram.types import Message

from services.recent_message_cache import add_recent_message

router = Router()


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def track_recent_message(message: Message) -> None:
    if not message.from_user:
        return

    await add_recent_message(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        message_id=message.message_id,
    )
