from urllib.parse import urlparse
from dotenv import load_dotenv
from os import getenv

load_dotenv()


class BotConfig:
    def __init__(self):
        self.admins: list[int] = list(
            map(int, getenv("ADMINS".replace(" ", "")).split(","))
        )
        self.bot_token = getenv("BOT_TOKEN")
        self.api_id = getenv("API_ID")
        self.api_hash = getenv("API_HASH")
        self.proxy: None | BotConfig._Proxy = self._Proxy(getenv("PROXY", None))
        self.debug = getenv("DEBUG", "False").lower() == "true"

    class _Proxy:
        def __init__(self, url: str):
            self._url = urlparse(url) if url else None
            self.url = self._url.geturl() if self._url else None

        @property
        def dict_format(self):
            if not self._url:
                return None
            return {
                "scheme": self._url.scheme,
                "hostname": self._url.hostname,
                "port": self._url.port,
                "username": self._url.username,
                "password": self._url.password,
            }


cfg = BotConfig()
