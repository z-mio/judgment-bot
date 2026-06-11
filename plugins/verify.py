from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import CallbackQuery, ChatMemberUpdated, Message

from i18n import t_
from services.redis_client import rc
from utils.filters import new_members, start_filter
from utils.util import decode_start_payload
from validator import CQData, EasyValidator, StartData


@Client.on_chat_member_updated(new_members & filters.admin)
async def verify(client: Client, event: ChatMemberUpdated) -> None:
    if not event.chat.id:
        return
    v = EasyValidator(int(event.chat.id), event.from_user.id)
    if not await v.init(client):
        return
    await v.start(client)


@Client.on_callback_query(filters.regex(r"^@"))
async def verify_callback(client: Client, callback: CallbackQuery) -> None:
    _t = t_[callback.from_user]

    try:
        if not callback.data:
            raise ValueError("callback data is empty")
        data_text = (
            callback.data.decode()
            if isinstance(callback.data, bytes)
            else callback.data
        )
        data = CQData.parse(data_text)
        raw = await rc.get(data.validator_id)
        if not raw:
            raise ValueError("validator expired")
        v = EasyValidator.loads(raw)
    except Exception:
        await callback.answer(_t("验证已过期"), show_alert=True)
        return

    if (
        not callback.message
        or not callback.message.chat
        or callback.message.chat.id is None
    ):
        await callback.answer(_t("验证已过期"), show_alert=True)
        return

    try:
        click_user = await client.get_chat_member(
            int(callback.message.chat.id), callback.from_user.id
        )
    except Exception:
        await callback.answer(_t("验证已过期"), show_alert=True)
        return
    if data.rid != v.rid:
        await callback.answer(_t("验证已过期"), show_alert=True)
        return
    if data.operate == "verify" and click_user.user.id != v.user_id:
        await callback.answer(_t("这不是你的验证"), show_alert=True)
        return
    if data.operate == "admin" and click_user.status not in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }:
        await callback.answer(_t("权限不足"), show_alert=True)
        return

    if not await v.init(client):
        return None

    await v.progress(client, callback)
    return None


@Client.on_message(start_filter(".*"))
async def start_handler(client: Client, message: Message) -> None:
    _t = t_[message]

    text = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        text = parts[1] if len(parts) > 1 else ""
    try:
        try:
            text = decode_start_payload(text)
        except Exception:
            pass
        data = StartData.parse(text)
        raw = await rc.get(data.validator_id)
        if not raw:
            raise ValueError("validator expired")
        v = EasyValidator.loads(raw)
    except Exception:
        await message.reply(_t("验证已过期"))
        message.stop_propagation()
        return

    if not message.from_user:
        message.stop_propagation()
        return

    click_user_id = message.from_user.id
    if data.rid != v.rid:
        await message.reply(_t("验证已过期"))
        message.stop_propagation()
        return
    if data.operate == "verify" and click_user_id != v.user_id:
        await message.reply(_t("这不是你的验证"))
        message.stop_propagation()
        return

    if not await v.init(client):
        message.stop_propagation()
        return

    await v.progress(client, message, text)
    message.stop_propagation()
