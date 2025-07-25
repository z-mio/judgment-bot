from pyrogram.enums import ChatMemberStatus

from utils.filters import new_members
from validator import CQData, EasyValidator
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
)
from services.redis_client import rc


@Client.on_chat_member_updated(new_members & filters.admin)
async def verify(cli: Client, msg: ChatMemberUpdated):
    v = EasyValidator(msg.chat.id, msg.from_user.id)
    await v.init(cli)
    await v.start()
    await rc.set(v.validator_id, v.dumps())


@Client.on_callback_query(filters.regex(r"^@"))
async def verify_callback(cli: Client, cq: CallbackQuery):
    data = CQData.parse(cq.data)
    v = EasyValidator.loads(await rc.get(data.validator_id))

    click_user = await cq.message.chat.get_member(cq.from_user.id)
    if data.operate == "verify" and click_user.user.id != v.user_id:
        return await cq.answer("这不是你的验证", show_alert=True)
    if data.operate == "admin" and click_user.status not in [
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    ]:
        return await cq.answer("权限不足", show_alert=True)

    await v.init(cli)
    await v.progress(cq)
    return await rc.delete(data.validator_id)
