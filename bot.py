import asyncio


from pyrogram import Client
from pyrogram.handlers import ConnectHandler, DisconnectHandler
from core.config import bs, ws
from core.watchdog import on_connect, on_disconnect
from log import logger, setup_logging
from services.redis_client import check_redis_connection, rc
from utils.aps import aps
from utils.optimized_event_loop import setup_optimized_event_loop

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

setup_logging(debug=bs.debug)
setup_optimized_event_loop()


async def init():
    aps.start()
    if not await check_redis_connection():
        exit(1)


class Bot(Client):
    def __init__(self):
        self.bs = bs

        super().__init__(
            self.bs.bot_session_name,
            api_id=self.bs.api_id,
            api_hash=self.bs.api_hash,
            bot_token=self.bs.bot_token,
            plugins=dict(root="plugins"),
            proxy=self.bs.bot_proxy,
            loop=loop,
            workdir=self.bs.bot_workdir,
        )

    async def start(self, **kwargs):
        self.init_watchdog()
        logger.debug("DEBUG 已开启")
        await init()
        await super().start()

    async def stop(self, *args):
        ws.exit_flag = True
        await rc.aclose()
        await super().stop()

    def init_watchdog(self):
        self.add_handler(ConnectHandler(on_connect))
        self.add_handler(DisconnectHandler(on_disconnect))


if __name__ == "__main__":
    bot = Bot()
    bot.run()
