import abc
import re
import secrets

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from utils.util import get_hash


class CQData:
    prefix = "@"
    suffix = ":"

    def __init__(self, validator_id: str, rid: str, operate: str, value: str):
        self.validator_id = validator_id
        self.rid = rid
        self.operate = operate
        self.value = value

    @classmethod
    def parse(cls, data: str) -> "CQData":
        match = re.search(rf"{cls.prefix}(.*?){cls.suffix}", data or "")
        if not match:
            raise ValueError("invalid callback data")
        provider = match[1]
        parts = data.replace(f"{cls.prefix}{provider}{cls.suffix}", "").split(",")
        if len(parts) != 3:
            raise ValueError("invalid callback data")
        rid, operate, value = parts
        return cls(provider, rid, operate, value)

    def unparse(self) -> str:
        return f"{self.prefix}{self.validator_id}{self.suffix}{self.rid},{self.operate},{self.value}"

    def __repr__(self) -> str:
        return self.unparse()


class StartData:
    sep = "="

    def __init__(self, validator_id: str, rid: str, operate: str, value: str):
        self.validator_id = validator_id
        self.rid = rid
        self.operate = operate
        self.value = value

    @classmethod
    def parse(cls, data: str) -> "StartData":
        parts = (data or "").split(cls.sep, 3)
        if len(parts) != 4:
            raise ValueError("invalid start data")
        provider, rid, operate, value = parts
        return cls(provider, rid, operate, value)

    def unparse(self) -> str:
        return f"{self.validator_id}{self.sep}{self.rid}{self.sep}{self.operate}{self.sep}{self.value}"

    def __repr__(self) -> str:
        return self.unparse()


class BaseValidator(abc.ABC):
    validator_name: str = ""

    def __init__(self, chat_id: int, user_id: int, rid: str | None = None):
        self.chat_id = chat_id
        self.user_id = user_id
        self._rid = rid or secrets.token_urlsafe(8)

    @abc.abstractmethod
    async def init(self, bot: Bot) -> bool: ...

    @abc.abstractmethod
    async def start(self, bot: Bot) -> None: ...

    @abc.abstractmethod
    async def progress(
        self, bot: Bot, content: Message | CallbackQuery, payload: str | None = None
    ) -> None: ...

    @property
    def validator_id(self) -> str:
        return get_hash(f"{self.validator_name}_{self.chat_id}_{self.user_id}")[:8]

    @abc.abstractmethod
    def dumps(self) -> str: ...

    @classmethod
    @abc.abstractmethod
    def loads(cls, obj: str) -> "BaseValidator": ...

    @property
    def rid(self) -> str:
        return self._rid
