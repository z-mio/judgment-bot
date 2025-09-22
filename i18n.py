from pyrogram.types import Message, User
from easy_ai18n import EasyAI18n, PostLanguageSelector
from easy_ai18n.translator import OpenAIBulkTranslator


class MyPostLanguageSelector(PostLanguageSelector):
    def __getitem__(self, msg: Message | User | str | None):
        if isinstance(msg, Message):
            lang = msg.from_user.language_code
        elif isinstance(msg, User):
            lang = msg.language_code
        else:
            lang = msg
        return super().__getitem__(lang)


i18n = EasyAI18n(i18n_function_names=["t_", "_t"])

t_ = i18n.i18n(post_lang_selector=MyPostLanguageSelector)

if __name__ == "__main__":
    i18n.build(
        target_lang=["en", "ru", "ja", "zh-hant"],
        translator=OpenAIBulkTranslator(model="gpt-4.1-mini"),
    )
