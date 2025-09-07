from pyrogram import Client, filters
from pyrogram.types import Message, BotCommand, LinkPreviewOptions

from i18n import t_
from utils.filters import is_admin

COMMANDS = {
    "kick": t_("封禁用户并踢出群聊"),
    "bc": t_("封禁频道马甲"),
    "unban": t_("解封用户/频道"),
    "start": t_("开始"),
    "help": t_("帮助"),
}


@Client.on_message(filters.command(["start", "help"]), group=1)
async def start(_, msg: Message):
    await msg.reply_text(
        t_(
            f"**呀哈喽!**\n\n"
            f"命令列表:\n{cmd_list_text(msg)}\n\n"
            "**项目地址:** [Github](https://github.com/z-mio/judgment-bot)"
        )[msg],
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@Client.on_message(filters.command("menu") & is_admin)
async def set_menu(cli: Client, msg: Message):
    await cli.set_bot_commands(
        [BotCommand(command=k, description=v) for k, v in COMMANDS.items()]
    )
    await msg.reply("👌")


def cmd_list_text(msg: Message):
    return "\n".join([f"/{k} - {v[msg]}" for k, v in COMMANDS.items()])
