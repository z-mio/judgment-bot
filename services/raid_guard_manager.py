import json
import time
from dataclasses import dataclass
from typing import Literal, cast

from log import logger
from services.redis_client import rc

logger = logger.bind(name="RaidGuard")

WINDOW_SECONDS = 300  # 统计窗口
JOIN_THRESHOLD = 15  # 窗口内进群数
MIN_RESULTS = 10  # 窗口内最少验证结果数
MAX_PASS_RATE = 0.2  # 通过率上限
BURST_WINDOW_SECONDS = 60
BURST_JOIN_THRESHOLD = 20  # 60s 内进群数, 纯速率兜底
AUTO_MIN_SECONDS = 600  # 自动开启后至少持续
EXIT_JOIN_THRESHOLD = 5  # 窗口内进群 < 该值才自动关闭


@dataclass(slots=True)
class RaidMode:
    source: Literal["auto", "manual"]
    since: float
    by: int | None = None


@dataclass(slots=True)
class RaidStats:
    joins: int
    burst_joins: int
    results: int
    passed: int

    @property
    def pass_rate(self) -> float | None:
        if self.results == 0:
            return None
        return self.passed / self.results


class RaidGuardManager:
    def _mode_key(self, chat_id: int) -> str:
        return f"raid_guard:mode:{chat_id}"

    def _joins_key(self, chat_id: int) -> str:
        return f"raid_guard:joins:{chat_id}"

    def _results_key(self, chat_id: int) -> str:
        return f"raid_guard:results:{chat_id}"

    async def record_join(self, chat_id: int, user_id: int) -> None:
        now = time.time()
        key = self._joins_key(chat_id)
        async with rc.pipeline() as pipe:
            pipe.zadd(key, {f"{user_id}:{time.time_ns()}": now})
            pipe.zremrangebyscore(key, "-inf", f"({now - WINDOW_SECONDS}")
            pipe.expire(key, WINDOW_SECONDS * 2)
            await pipe.execute()

    async def record_result(self, chat_id: int, rid: str, passed: bool) -> None:
        now = time.time()
        key = self._results_key(chat_id)
        outcome = "pass" if passed else "fail"
        async with rc.pipeline() as pipe:
            pipe.zadd(key, {f"{rid}:{outcome}": now})
            pipe.zremrangebyscore(key, "-inf", f"({now - WINDOW_SECONDS}")
            pipe.expire(key, WINDOW_SECONDS * 2)
            await pipe.execute()

    async def stats(self, chat_id: int) -> RaidStats:
        now = time.time()
        results_key = self._results_key(chat_id)
        async with rc.pipeline() as pipe:
            pipe.zcount(self._joins_key(chat_id), now - WINDOW_SECONDS, "+inf")
            pipe.zcount(
                self._joins_key(chat_id), now - BURST_WINDOW_SECONDS, "+inf"
            )
            pipe.zrangebyscore(results_key, now - WINDOW_SECONDS, "+inf")
            counts = await pipe.execute()
        result_members = cast(list[str], counts[2])
        passed = len(
            [member for member in result_members if member.endswith(":pass")]
        )
        results = len(result_members)
        return RaidStats(
            joins=int(counts[0]),
            burst_joins=int(counts[1]),
            results=results,
            passed=passed,
        )

    async def get_mode(self, chat_id: int) -> RaidMode | None:
        raw = await rc.get(self._mode_key(chat_id))
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise ValueError("invalid raid mode data")
        data = json.loads(raw)
        source = data.get("source")
        since = data.get("since")
        by = data.get("by")
        if source not in {"auto", "manual"} or not isinstance(since, (int, float)):
            raise ValueError("invalid raid mode data")
        if by is not None and not isinstance(by, int):
            raise ValueError("invalid raid mode data")
        return RaidMode(source=source, since=float(since), by=by)

    async def evaluate(self, chat_id: int) -> tuple[RaidMode | None, bool]:
        now = time.time()
        mode = await self.get_mode(chat_id)
        st = await self.stats(chat_id)
        if (
            mode
            and mode.source == "auto"
            and now - mode.since >= AUTO_MIN_SECONDS
            and st.joins < EXIT_JOIN_THRESHOLD
        ):
            await rc.delete(self._mode_key(chat_id))
            logger.info(
                f"防轰炸模式自动关闭: chat_id={chat_id} | "
                f"持续 {int(now - mode.since)}s | 近5分钟进群 {st.joins}"
            )
            return None, False
        if mode:
            return mode, False

        reason_a = (
            st.joins >= JOIN_THRESHOLD
            and st.results >= MIN_RESULTS
            and st.pass_rate is not None
            and st.pass_rate <= MAX_PASS_RATE
        )
        reason_b = st.burst_joins >= BURST_JOIN_THRESHOLD
        if not reason_a and not reason_b:
            return None, False

        data = json.dumps(
            {"source": "auto", "since": now, "by": None},
            separators=(",", ":"),
        )
        enabled = await rc.set(self._mode_key(chat_id), data, nx=True)
        if not enabled:
            return await self.get_mode(chat_id), False

        reason = "速率+通过率" if reason_a else "突发速率"
        pass_rate = "-" if st.pass_rate is None else f"{st.pass_rate:.0%}"
        logger.info(
            f"防轰炸模式自动开启: chat_id={chat_id} | 原因={reason} | "
            f"近5分钟进群 {st.joins} | 近1分钟进群 {st.burst_joins} | "
            f"结果 {st.results} | 通过率 {pass_rate}"
        )
        return RaidMode(source="auto", since=now), True

    async def enable_manual(self, chat_id: int, by: int | None) -> None:
        data = json.dumps(
            {"source": "manual", "since": time.time(), "by": by},
            separators=(",", ":"),
        )
        await rc.set(self._mode_key(chat_id), data)

    async def disable(self, chat_id: int) -> None:
        await rc.delete(
            self._mode_key(chat_id),
            self._joins_key(chat_id),
            self._results_key(chat_id),
        )


raid_guard_manager = RaidGuardManager()
