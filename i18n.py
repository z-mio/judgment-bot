from easy_ai18n.core.i18n import PostLocaleSelector
from pyrogram.types import Message, User
from easy_ai18n import EasyAI18n
from easy_ai18n.translator import OpenAIBulkTranslator


class MyPostLocaleSelector(PostLocaleSelector):
    def __getitem__(self, msg: Message | User | str | None):
        if isinstance(msg, Message):
            lang = msg.from_user.language_code if msg.from_user else None
        elif isinstance(msg, User):
            lang = msg.language_code
        else:
            lang = msg
        return super().__getitem__(lang)


i18n = EasyAI18n(func_names=["t_", "_t"])

t_ = i18n.i18n(post_locale_selector=MyPostLocaleSelector)

if __name__ == "__main__":
    i18n.build(
        to_locales=["en", "ru", "ja", "zh-hant"],
        translator=OpenAIBulkTranslator(model="gpt-4.1-mini"),
    )
