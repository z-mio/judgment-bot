from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from i18n import t_
from services.redis_client import rc
from utils.filters import new_members
from validator import CQData, EasyValidator, StartData

router = Router()


@router.chat_member(new_members)
async def verify(event: ChatMemberUpdated, bot: Bot) -> None:
    v = EasyValidator(event.chat.id, event.from_user.id)
    if not await v.init(bot):
        return
    await v.start(bot)


@router.callback_query(F.data.startswith("@"))
async def verify_callback(callback: CallbackQuery, bot: Bot) -> None:
    _t = t_[callback.from_user]

    try:
        if not callback.data:
            raise ValueError("callback data is empty")
        data = CQData.parse(callback.data)
        v = EasyValidator.loads(await rc.get(data.validator_id))
    except Exception:
        await callback.answer(_t("验证已过期"), show_alert=True)
        return

    if not callback.message:
        await callback.answer(_t("验证已过期"), show_alert=True)
        return

    click_user = await bot.get_chat_member(
        callback.message.chat.id, callback.from_user.id
    )
    if data.operate == "verify" and click_user.user.id != v.user_id:
        await callback.answer(_t("这不是你的验证"), show_alert=True)
        return
    if data.operate == "admin" and click_user.status not in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
    }:
        await callback.answer(_t("权限不足"), show_alert=True)
        return

    if not await v.init(bot):
        return None

    await v.progress(bot, callback)
    return None


@router.message(CommandStart(deep_link=True, deep_link_encoded=True))
async def start_handler(message: Message, command: CommandObject, bot: Bot) -> None:
    _t = t_[message]

    text = command.args or ""
    try:
        data = StartData.parse(text)
        v = EasyValidator.loads(await rc.get(data.validator_id))
    except Exception:
        await message.reply(_t("验证已过期"))
        return

    if not message.from_user:
        return

    click_user_id = message.from_user.id
    if data.operate == "verify" and click_user_id != v.user_id:
        await message.reply(_t("这不是你的验证"))
        return

    if not await v.init(bot):
        return

    await v.progress(bot, message, text)
