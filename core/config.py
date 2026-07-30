from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse
import os
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admins: Annotated[list[int], NoDecode]
    api_id: int
    api_hash: str
    bot_token: str
    bot_proxy: str | None = Field(
        default=None, validation_alias=AliasChoices("BOT_PROXY", "PROXY")
    )
    debug: bool = Field(default=False)
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_password: str | None = Field(default=None)

    def model_post_init(self, __context: Any) -> None:
        """模型初始化后的操作"""
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    @property
    def sessions_path(self) -> Path:
        return Path("sessions")

    @property
    def bot_session_name(self) -> str:
        return f"bot_{self.bot_token.split(':')[0]}"

    @field_validator("admins", mode="before")
    @classmethod
    def parse_admins(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [int(x) if not isinstance(x, int) else x for x in v]
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [int(x.strip()) for x in v.replace(" ", "").split(",") if x.strip()]
        return v

    @field_validator("redis_password", "bot_proxy", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: str | None = None) -> str | None:
        return v or None

    @property
    def pyrogram_proxy(self) -> dict[str, str | int | None] | None:
        if not self.bot_proxy:
            return None

        parsed = urlparse(self.bot_proxy)
        return {
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username,
            "password": parsed.password,
        }


class WatchdogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        env_prefix="WD_",
    )
    is_running: bool = Field(default=False)
    """运行中"""
    restart_count: int = Field(default=0)
    """重启次数"""
    disconnect_count: int = Field(default=0)
    """断开连接次数"""
    max_disconnect_count: int = Field(default=3)
    """最大断开连接次数, 超过后重启"""
    remove_session_after_restart: int = Field(default=3)
    """重启失败几次后删除会话文件"""
    max_restart_count: int = Field(default=6)
    """意外断开连接时，最大重启次数"""
    exit_flag: bool = Field(default=False)
    """退出标志"""

    def update_bot_restart_count(self) -> None:
        self.restart_count += 1
        os.environ["WD_RESTART_COUNT"] = str(self.restart_count)

    def reset_bot_restart_count(self) -> None:
        self.restart_count = 0
        os.environ["WD_RESTART_COUNT"] = "0"

    def update_bot_disconnect_count(self) -> None:
        self.disconnect_count += 1
        os.environ["WD_DISCONNECT_COUNT"] = str(self.disconnect_count)

    def reset_bot_disconnect_count(self) -> None:
        self.disconnect_count = 0
        os.environ["WD_DISCONNECT_COUNT"] = "0"


bs = BotSettings()  # type: ignore
ws = WatchdogSettings()
