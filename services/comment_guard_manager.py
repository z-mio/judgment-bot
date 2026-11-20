from dataclasses import dataclass

from services.redis_client import rc


@dataclass(slots=True)
class CommentGuardManager:
    """未入群评论者的信任缓存与连续验证失败计数"""

    verified_ttl_seconds: int = 30 * 24 * 3600
    member_ttl_seconds: int = 24 * 3600
    fail_ttl_seconds: int = 30 * 24 * 3600

    @staticmethod
    def _trusted_key(chat_id: int, user_id: int) -> str:
        return f"comment_trusted:{chat_id}_{user_id}"

    @staticmethod
    def _fail_key(chat_id: int, user_id: int) -> str:
        return f"comment_fail:{chat_id}_{user_id}"

    async def is_trusted(self, chat_id: int, user_id: int) -> bool:
        return bool(await rc.exists(self._trusted_key(chat_id, user_id)))

    async def mark_member(self, chat_id: int, user_id: int) -> None:
        """群成员已通过入群验证, 短期缓存避免每条消息都查成员状态"""
        await rc.set(
            self._trusted_key(chat_id, user_id), "member", ex=self.member_ttl_seconds
        )

    async def mark_verified(self, chat_id: int, user_id: int) -> None:
        async with rc.pipeline() as pipe:
            pipe.set(
                self._trusted_key(chat_id, user_id),
                "verified",
                ex=self.verified_ttl_seconds,
            )
            pipe.delete(self._fail_key(chat_id, user_id))
            await pipe.execute()

    async def refresh_verified(self, chat_id: int, user_id: int) -> None:
        """已验证的评论者每次发言顺延缓存"""
        key = self._trusted_key(chat_id, user_id)
        if await rc.get(key) == "verified":
            await rc.expire(key, self.verified_ttl_seconds)

    async def record_fail(self, chat_id: int, user_id: int) -> int:
        """记录一次验证失败, 返回连续失败次数"""
        key = self._fail_key(chat_id, user_id)
        async with rc.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, self.fail_ttl_seconds)
            count, _ = await pipe.execute()
        return int(count)

    async def clear_fail(self, chat_id: int, user_id: int) -> None:
        await rc.delete(self._fail_key(chat_id, user_id))


comment_guard_manager = CommentGuardManager()
