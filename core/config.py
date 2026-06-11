from typing import Annotated, Any
from urllib.parse import urlparse

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


bs = BotSettings()  # type: ignore
