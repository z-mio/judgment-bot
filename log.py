import inspect
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import loguru

if TYPE_CHECKING:
    from loguru import Logger

loguru.logger.configure(extra={"name": "Main"})
logger: "Logger" = loguru.logger.bind(name="Main")

LOG_FILE = "logs/bot.log"

THIRD_PARTY_LOG_LEVEL = "WARNING"
"""第三方库日志级别: 恒定收紧, 不受 DEBUG 开关影响

pyrogram/redis 等库的 INFO 属于库内部流程 (连接/任务启停/插件加载),
对本项目排障价值低且会淹没业务日志; 需要看库内部细节时临时改成 DEBUG
"""

CONSOLE_FORMAT = (
    "<green>{time:MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>[{extra[name]}]</cyan> "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> | "
    "[{extra[name]}] <level>{message}</level>"
)


def setup_logging(debug: bool = False) -> None:
    """配置日志: 控制台按 debug 开关, 文件始终记录 DEBUG 全量, 第三方库恒定收紧"""
    logger.remove()

    console_level = "DEBUG" if debug else "INFO"
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        sys.stderr,
        level=console_level,
        format=CONSOLE_FORMAT,
        backtrace=True,
        diagnose=debug,
    )
    logger.add(
        LOG_FILE,
        level="DEBUG",
        format=FILE_FORMAT,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    # 第三方库恒定收紧, DEBUG 开关只控制本项目日志
    logging.getLogger().setLevel(THIRD_PARTY_LOG_LEVEL)
    logging.getLogger("pyrogram").setLevel(THIRD_PARTY_LOG_LEVEL)

    logger.info(
        f"日志已初始化: 控制台={console_level} | "
        f"文件=DEBUG ({LOG_FILE}, 10MB 轮转/保留 30 天) | "
        f"第三方库={THIRD_PARTY_LOG_LEVEL}"
    )
    if debug:
        logger.debug("调试模式已启用")


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.bind(name=record.name.split(".")[0]).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level="WARNING", force=True)
