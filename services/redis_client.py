from redis.asyncio import Redis

from core.config import bs
from redis.exceptions import ConnectionError, TimeoutError

from log import logger

rc = Redis(
    host=bs.redis_host,
    port=bs.redis_port,
    password=bs.redis_password,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    health_check_interval=30,
)


async def check_redis_connection():
    try:
        await rc.ping()
        logger.info(f"Redis 连接成功: {bs.redis_host}:{bs.redis_port}")
        return True
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Redis 连接失败: {e}")
        return False
    except Exception as e:
        logger.exception(f"Redis 连接出现未知错误: {e}")
