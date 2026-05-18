import inspect
import json
from collections.abc import Awaitable
from typing import Any, cast

from services.redis_client import rc

RECENT_MESSAGE_LIMIT = 100
RECENT_MESSAGE_TTL = 12 * 60 * 60


async def maybe_await[T](value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


def recent_messages_key(chat_id: int) -> str:
    return f"recent_messages:{chat_id}"


async def add_recent_message(chat_id: int, user_id: int, message_id: int) -> None:
    key = recent_messages_key(chat_id)
    item = json.dumps(
        {"message_id": message_id, "user_id": user_id}, separators=(",", ":")
    )
    await maybe_await(rc.lpush(key, item))
    await maybe_await(rc.ltrim(key, 0, RECENT_MESSAGE_LIMIT - 1))
    await maybe_await(rc.expire(key, RECENT_MESSAGE_TTL))


async def get_recent_message_ids_by_user(chat_id: int, user_id: int) -> list[int]:
    items = cast(
        list[str],
        await maybe_await(
            rc.lrange(recent_messages_key(chat_id), 0, RECENT_MESSAGE_LIMIT - 1)
        ),
    )
    message_ids: list[int] = []

    for item in items:
        try:
            data = cast(dict[str, Any], json.loads(item))
            if int(data["user_id"]) == user_id:
                message_ids.append(int(data["message_id"]))
        except Exception:
            continue
    return message_ids
