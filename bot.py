import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from core.config import bs
from log import logger, setup_logging
from plugins import (
    ban_channel,
    del_service_msg,
    delete_guest_bot_messages,
    kick,
    recent_messages,
    start,
    unban,
    verify,
)
from services.redis_client import check_redis_connection, rc
from utils.aps import aps
from utils.optimized_event_loop import setup_optimized_event_loop


def create_bot() -> Bot:
    session = AiohttpSession(proxy=bs.bot_proxy)
    return Bot(
        token=bs.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def register_routers(dp: Dispatcher) -> None:
    dp.include_router(verify.router)
    dp.include_router(start.router)
    dp.include_router(kick.router)
    dp.include_router(unban.router)
    dp.include_router(ban_channel.router)
    dp.include_router(del_service_msg.router)
    dp.include_router(delete_guest_bot_messages.router)
    dp.include_router(recent_messages.router)


async def main() -> None:
    if not await check_redis_connection():
        raise SystemExit(1)

    bot = create_bot()
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()
    register_routers(dp)

    aps.start()
    logger.success("Bot 开始运行...")
    try:
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types(), skip_updates=True
        )
    finally:
        if aps.running:
            aps.shutdown(wait=False)
        await rc.aclose()
        await bot.session.close()


if __name__ == "__main__":
    setup_logging(debug=bs.debug)
    setup_optimized_event_loop()
    asyncio.run(main())
