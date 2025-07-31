from services.redis_client import rc


class KickCooldownManager:
    def __init__(self, cooldown_seconds: int = 3600):
        self.cooldown_seconds = cooldown_seconds
        self.key_prefix = "kick_cooldown"

    def _get_key(self, user_id: int) -> str:
        """获取Redis键名"""
        return f"{self.key_prefix}:{user_id}"

    async def can_user_kick(self, user_id: int) -> bool:
        """检查用户是否可以kick"""
        key = self._get_key(user_id)
        exists = await rc.exists(key)
        return not exists

    async def set_cooldown(self, user_id: int) -> None:
        """设置用户kick冷却时间"""
        key = self._get_key(user_id)
        await rc.set(key, "1", ex=self.cooldown_seconds)

    async def clear_cooldown(self, user_id: int) -> bool:
        """清除用户kick冷却时间"""
        key = self._get_key(user_id)
        result = await rc.delete(key)
        return result > 0

    async def get_remaining_time(self, user_id: int) -> int:
        """获取剩余冷却时间（秒）"""
        key = self._get_key(user_id)
        ttl = await rc.ttl(key)
        return max(0, ttl) if ttl > 0 else 0

    async def get_remaining_time_formatted(self, user_id: int) -> str | None:
        """获取格式化的剩余冷却时间"""
        remaining = await self.get_remaining_time(user_id)

        if remaining <= 0:
            return None

        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60

        time_parts = []
        if hours > 0:
            time_parts.append(f"`{hours}` 小时")
        if minutes > 0:
            time_parts.append(f"`{minutes}` 分钟")
        if seconds > 0 or not time_parts:
            time_parts.append(f"`{seconds}` 秒")

        return "".join(time_parts)


kick_cooldown = KickCooldownManager()
