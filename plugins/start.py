from plugins.helpers import COMMANDS
from pyrogram import Client, filters
from pyrogram.types import LinkPreviewOptions, Message


@Client.on_message(~filters.bot & filters.command(["start", "help"]), group=1)
async def start(_: Client, message: Message) -> None:
    await message.reply(
        f"**呀哈喽!**\n\n"
        f"命令列表:\n{cmd_list_text()}\n\n"
        "**项目地址: **[Github](https://github.com/z-mio/judgment-bot)",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


def cmd_list_text() -> str:
    return "\n".join([f"/{k} - {v}" for k, v in COMMANDS.items()])
