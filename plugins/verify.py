from pyrogram.enums import ChatMemberStatus

from i18n import t_
from utils.filters import new_members, start_filter
from validator import CQData, EasyValidator, StartData
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
)
from services.redis_client import rc


@Client.on_chat_member_updated(new_members & filters.admin)
async def verify(cli: Client, msg: ChatMemberUpdated):
    v = EasyValidator(msg.chat.id, msg.from_user.id)
    if not await v.init(cli):
        return
    await v.start(cli)


@Client.on_callback_query(filters.regex(r"^@"))
async def verify_callback(cli: Client, cq: CallbackQuery):
    _t = t_[cq.from_user]

    data = CQData.parse(cq.data)
    try:
        v = EasyValidator.loads(await rc.get(data.validator_id))
    except Exception:
        return await cq.answer(_t("验证已过期"), show_alert=True)

    click_user = await cq.message.chat.get_member(cq.from_user.id)
    if data.operate == "verify" and click_user.user.id != v.user_id:
        return await cq.answer(_t("这不是你的验证"), show_alert=True)
    if data.operate == "admin" and click_user.status not in [
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    ]:
        return await cq.answer(_t("权限不足"), show_alert=True)

    if not await v.init(cli):
        return None

    await v.progress(cli, cq)
    return None


@Client.on_message(start_filter(".*"))
async def start_handler(cli: Client, msg: Message):
    _t = t_[msg]

    text = msg.text.replace("/start ", "")
    data = StartData.parse(text)
    try:
        v = EasyValidator.loads(await rc.get(data.validator_id))
    except Exception:
        await msg.reply(_t("验证已过期"))
        msg.stop_propagation()
        return

    click_user_id = msg.from_user.id
    if data.operate == "verify" and click_user_id != v.user_id:
        await msg.reply(_t("这不是你的验证"))
        msg.stop_propagation()
        return

    if not await v.init(cli):
        msg.stop_propagation()
        return

    await v.progress(cli, msg)
    msg.stop_propagation()
    return
