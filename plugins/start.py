from pyrogram import Client, filters
from pyrogram.types import BotCommand, LinkPreviewOptions, Message

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
async def start(_: Client, message: Message) -> None:
    if message.text:
        parts = message.text.split(maxsplit=1)
        if parts and parts[0].split("@", 1)[0] == "/start" and len(parts) > 1:
            return

    await message.reply(
        t_(
            f"<b>呀哈喽!</b>\n\n"
            f"命令列表:\n{cmd_list_text(message)}\n\n"
            '<b>项目地址:</b> <a href="https://github.com/z-mio/judgment-bot">Github</a>'
        )[message],
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@Client.on_message(filters.command("menu") & is_admin)
async def set_menu(client: Client, message: Message) -> None:
    await client.set_bot_commands(
        [BotCommand(k, v[message]) for k, v in COMMANDS.items()]
    )
    await message.reply("👌")


def cmd_list_text(message: Message) -> str:
    return "\n".join([f"/{k} - {v[message]}" for k, v in COMMANDS.items()])
