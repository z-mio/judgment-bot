from services.redis_client import rc


class VerifyFailManager:
    def __init__(self, ttl_seconds: int = 30 * 24 * 3600):
        self.ttl_seconds = ttl_seconds
        self.key_prefix = "verify_fail"

    def _get_key(self, chat_id: int, user_id: int) -> str:
        """获取Redis键名"""
        return f"{self.key_prefix}:{chat_id}_{user_id}"

    async def mark_failed(self, chat_id: int, user_id: int) -> None:
        """标记用户验证失败"""
        key = self._get_key(chat_id, user_id)
        await rc.set(key, "1", ex=self.ttl_seconds)

    async def is_failed(self, chat_id: int, user_id: int) -> bool:
        """检查用户是否被标记为验证失败"""
        key = self._get_key(chat_id, user_id)
        exists = await rc.exists(key)
        return bool(exists)

    async def clear_failed(self, chat_id: int, user_id: int) -> bool:
        """清除用户验证失败标记"""
        key = self._get_key(chat_id, user_id)
        result = await rc.delete(key)
        return int(result) > 0


verify_fail_manager = VerifyFailManager()
