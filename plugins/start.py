from pyrogram import Client, filters
from pyrogram.types import Message, BotCommand, LinkPreviewOptions

from utils.filters import is_admin


@Client.on_message(filters.command(["start", "help"]))
async def start(_, msg: Message):
    await msg.reply_text(
        "**呀哈喽!**\n\n**项目地址:** [Github](https://github.com/z-mio/judgment-bot)",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@Client.on_message(filters.command("menu") & is_admin)
async def set_menu(cli: Client, msg: Message):
    commands = {
        "kick": "封禁并踢出群聊",
        "start": "开始",
        "help": "帮助",
    }
    await cli.set_bot_commands(
        [BotCommand(command=k, description=v) for k, v in commands.items()]
    )
    await msg.reply("👌")
