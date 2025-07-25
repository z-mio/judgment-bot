from os import getenv

from redis.asyncio import Redis
from redis.exceptions import ConnectionError, TimeoutError

from log import logger

rc = Redis(
    host=getenv("REDIS_HOST", "localhost"),
    port=int(getenv("REDIS_PORT", 6379)),
    password=getenv("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30,
)


async def check_redis_connection():
    try:
        await rc.ping()
        logger.info(
            f"Redis 连接成功: {getenv('REDIS_HOST', 'localhost')}:{getenv('REDIS_PORT', '6379')}"
        )
        return True
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Redis 连接失败: {e}")
        return False
    except Exception as e:
        logger.exception(f"Redis 连接出现未知错误: {e}")
