from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, LinkPreviewOptions, Message

from i18n import t_
from utils.filters import is_admin

router = Router()

COMMANDS = {
    "kick": t_("封禁用户并踢出群聊"),
    "bc": t_("封禁频道马甲"),
    "unban": t_("解封用户/频道"),
    "start": t_("开始"),
    "help": t_("帮助"),
}


@router.message(CommandStart(deep_link=False))
@router.message(Command("help"))
async def start(message: Message) -> None:
    await message.answer(
        t_(
            f"<b>呀哈喽!</b>\n\n"
            f"命令列表:\n{cmd_list_text(message)}\n\n"
            '<b>项目地址:</b> <a href="https://github.com/z-mio/judgment-bot">Github</a>'
        )[message],
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.message(
    Command("menu"), F.chat.type.in_({"group", "supergroup", "private"}), is_admin
)
async def set_menu(message: Message, bot: Bot) -> None:
    await bot.set_my_commands(
        [BotCommand(command=k, description=v[message]) for k, v in COMMANDS.items()]
    )
    await message.answer("👌")


def cmd_list_text(message: Message) -> str:
    return "\n".join([f"/{k} - {v[message]}" for k, v in COMMANDS.items()])
