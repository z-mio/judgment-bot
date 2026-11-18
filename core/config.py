from pathlib import Path
from typing import Any
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    @field_validator("redis_password", "bot_proxy", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: str | None = None) -> str | None:
        return v or None


bs = BotSettings()  # type: ignore
