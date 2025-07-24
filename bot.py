import sys

from pyrogram import Client
from config.config import cfg
from log import logger
from utils.optimized_event_loop import setup_optimized_event_loop

logger.remove()
if cfg.debug:
    logger.add(sys.stderr, level="DEBUG")
    logger.debug("Debug模式已启用")
else:
    logger.add("logs/bot.log", rotation="5 MB", level="INFO")
    logger.add(sys.stderr, level="INFO")


class Bot(Client):
    def __init__(self):
        self.cfg = cfg

        super().__init__(
            f"{self.cfg.bot_token.split(':')[0]}_bot",
            api_id=self.cfg.api_id,
            api_hash=self.cfg.api_hash,
            bot_token=self.cfg.bot_token,
            plugins=dict(root="plugins"),
            proxy=self.cfg.proxy.dict_format,
        )

    async def start(self, **kwargs):
        logger.info("Bot开始运行...")
        await super().start()

    async def stop(self, *args):
        await super().stop()


if __name__ == "__main__":
    setup_optimized_event_loop()
    bot = Bot()
    bot.run()
