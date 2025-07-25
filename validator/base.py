import abc
import re
from typing import TypeVar, Generic

from utils.util import get_hash

T = TypeVar("T")


class CQData:
    prefix = "@"
    suffix = ":"

    def __init__(self, validator_id: str, rid: str, operate: str, value: str):
        self.validator_id = validator_id
        self.rid = rid
        self.operate = operate
        self.value = value

    @classmethod
    def parse(cls, data: str):
        provider = re.search(rf"{cls.prefix}(.*?){cls.suffix}", data)[1]
        rid, operate, value = data.replace(
            f"{cls.prefix}{provider}{cls.suffix}", ""
        ).split(",")
        return cls(provider, rid, operate, value)

    def unparse(self):
        return f"{self.prefix}{self.validator_id}{self.suffix}{self.rid},{self.operate},{self.value}"

    def __repr__(self) -> str:
        return self.unparse()


class BaseValidator(abc.ABC, Generic[T]):
    validator_name: str = ""

    def __init__(self, chat_id: int, user_id: int):
        self.chat_id = chat_id
        self.user_id = user_id

    @abc.abstractmethod
    async def init(self, *args, **kwargs): ...

    @abc.abstractmethod
    async def start(self): ...

    @abc.abstractmethod
    async def progress(self, content: T): ...

    @abc.abstractmethod
    async def verify_pass(self, content: T): ...

    @abc.abstractmethod
    async def admin_verify_fail(self, content: T): ...

    @abc.abstractmethod
    async def verify_fail(self, content: T): ...

    @abc.abstractmethod
    async def verify_timeout(self): ...

    @property
    def validator_id(self) -> str:
        return get_hash(f"{self.validator_name}_{self.chat_id}_{self.user_id}")

    @abc.abstractmethod
    def dumps(self): ...

    @classmethod
    def loads(cls, obj: str) -> "BaseValidator": ...

    @property
    def rid(self) -> str:
        return f"{self.chat_id}_{self.user_id}"
