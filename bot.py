from pathlib import Path

from pyrogram import Client, enums

from core.config import bs
from log import logger, setup_logging
from services.redis_client import check_redis_connection, rc
from utils.aps import aps
from utils.optimized_event_loop import setup_optimized_event_loop


class JudgmentBot(Client):
    def __init__(self) -> None:
        Path("sessions").mkdir(exist_ok=True)
        super().__init__(
            f"{bs.bot_token.split(':')[0]}_bot",
            api_id=bs.api_id,
            api_hash=bs.api_hash,
            bot_token=bs.bot_token,
            plugins=dict(root="plugins"),
            proxy=bs.pyrogram_proxy,
            parse_mode=enums.ParseMode.HTML,
            workdir="sessions",
        )

    async def start(self, **kwargs) -> None:
        if not await check_redis_connection():
            raise SystemExit(1)
        aps.start()
        logger.success("Bot 开始运行...")
        await super().start(**kwargs)

    async def stop(self, *args) -> None:
        if aps.running:
            aps.shutdown(wait=False)
        await rc.aclose()
        await super().stop(*args)


if __name__ == "__main__":
    setup_logging(debug=bs.debug)
    setup_optimized_event_loop()
    JudgmentBot().run()
