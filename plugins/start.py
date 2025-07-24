from pyrogram import Client, filters
from pyrogram.types import Message, BotCommand

from utils.filters import is_admin


@Client.on_message(filters.command(["start", "help"]))
async def start(_, msg: Message):
    await msg.reply_text("呀哈喽!")


@Client.on_message(filters.command("menu") & is_admin)
async def set_menu(cli: Client, msg: Message):
    commands = {"start": "开始", "help": "帮助"}
    await cli.set_bot_commands(
        [BotCommand(command=k, description=v) for k, v in commands.items()]
    )
    await msg.reply("👌")
