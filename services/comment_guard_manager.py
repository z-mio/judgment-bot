from dataclasses import dataclass

from services.redis_client import rc


@dataclass(slots=True)
class CommentGuardManager:
    """评论者信任缓存与连续验证失败计数; 验证通过全局生效, 成员缓存与失败按群"""

    verified_ttl_seconds: int = 30 * 24 * 3600
    member_ttl_seconds: int = 24 * 3600
    fail_ttl_seconds: int = 30 * 24 * 3600

    @staticmethod
    def _verified_key(user_id: int) -> str:
        return f"comment_verified:{user_id}"

    @staticmethod
    def _member_key(chat_id: int, user_id: int) -> str:
        return f"comment_member:{chat_id}_{user_id}"

    @staticmethod
    def _fail_key(chat_id: int, user_id: int) -> str:
        return f"comment_fail:{chat_id}_{user_id}"

    async def is_trusted(self, chat_id: int, user_id: int) -> bool:
        """本群成员或已在任意评论区通过验证的用户免验证"""
        async with rc.pipeline() as pipe:
            pipe.exists(self._member_key(chat_id, user_id))
            pipe.exists(self._verified_key(user_id))
            is_member, is_verified = await pipe.execute()
        return bool(is_member or is_verified)

    async def mark_member(self, chat_id: int, user_id: int) -> None:
        """群成员已通过入群验证, 短期缓存避免每条消息都查成员状态"""
        await rc.set(
            self._member_key(chat_id, user_id), "member", ex=self.member_ttl_seconds
        )

    async def mark_verified(self, chat_id: int, user_id: int) -> None:
        async with rc.pipeline() as pipe:
            pipe.set(
                self._verified_key(user_id), "verified", ex=self.verified_ttl_seconds
            )
            pipe.delete(self._fail_key(chat_id, user_id))
            await pipe.execute()

    async def refresh_verified(self, user_id: int) -> None:
        """已验证的评论者每次发言顺延缓存"""
        await rc.expire(self._verified_key(user_id), self.verified_ttl_seconds)

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
