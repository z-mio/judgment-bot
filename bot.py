from pyrogram import Client, enums
from pyrogram.types import BotCommand

from core.config import bs
from log import logger, setup_logging
from plugins.comment_verify import (
    cancel_all_comment_verify_tasks,
    restore_comment_verify_sessions,
)
from plugins.helpers import COMMANDS
from plugins.verify import cancel_all_verify_tasks, restore_verify_sessions
from services.redis_client import check_redis_connection, rc

logger = logger.bind(name="Bot")


class JudgmentBot(Client):
    def __init__(self) -> None:
        super().__init__(
            bs.bot_session_name,
            api_id=bs.api_id,
            api_hash=bs.api_hash,
            bot_token=bs.bot_token,
            plugins={"root": "plugins"},
            proxy=bs.bot_proxy,
            parse_mode=enums.ParseMode.MARKDOWN,
            workdir=bs.sessions_path,
        )

    async def start(self, **kwargs) -> Client:
        if not await check_redis_connection():
            raise SystemExit(1)
        await super().start(**kwargs)
        await self.set_menu()
        await restore_verify_sessions(self)
        await restore_comment_verify_sessions(self)
        return self

    async def stop(self, *args, **kwargs) -> Client:
        logger.info("Bot 正在停止...")
        await cancel_all_verify_tasks()
        await cancel_all_comment_verify_tasks()
        await rc.aclose()
        await super().stop(*args)
        await logger.complete()
        return self

    async def set_menu(self) -> None:
        commands = await self.get_bot_commands()
        if len(commands) == len(COMMANDS) and all(
            c.description in str(COMMANDS.values()) for c in commands
        ):
            logger.debug("菜单无变化, 跳过设置")
            return
        await self.set_bot_commands(
            [BotCommand(command=k, description=v) for k, v in COMMANDS.items()]
        )
        logger.info(f"命令菜单已设置: {COMMANDS}")


if __name__ == "__main__":
    setup_logging(debug=bs.debug)
    JudgmentBot().run()
