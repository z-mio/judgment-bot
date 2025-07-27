from datetime import datetime

from pyrogram import Client, filters
from pyrogram.errors import BadRequest
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup as Ikm,
    InlineKeyboardButton as Ikb,
    LinkPreviewOptions,
)

from log import logger
from services.redis_client import rc
from utils.util import get_md_user_url, member_is_admin, delete_messages


@Client.on_message(filters.command("kick") & filters.group & filters.admin)
async def kick(cli: Client, msg: Message):
    if not msg.reply_to_message:
        m = await msg.reply("请回复一条消息")
        await delete_messages(cli, msg.chat.id, [msg.id, m.id])
    elif msg.reply_to_message.sender_chat:
        await msg.reply("封禁频道请使用 /bc")
    else:
        if await member_is_admin(cli, msg.chat.id, msg.from_user.id):
            await admin_kick(cli, msg)
        else:
            await member_kick_button(cli, msg)


@Client.on_callback_query(filters.regex(r"^member_kick"))
async def member_kick_callback(cli: Client, cq: CallbackQuery):
    a, u = cq.data.split(";")
    action_user_id = int(u.split("=")[1])
    if cq.from_user.id != action_user_id:
        return await cq.answer("这不是你的操作", show_alert=True)

    action = a.split("=")[1]
    if action == "confirm":
        await set_kick_cooldown(cq.message.reply_to_message.from_user.id)
        await member_kick(cli, cq.message)
    elif action == "cancel":
        await cq.message.edit("已取消操作")


async def member_kick_button(_, msg: Message):
    member = await msg.chat.get_member(msg.from_user.id)
    least_joined_days = 30
    if (jd := joined_days(member.joined_date)) < least_joined_days:
        return await msg.reply(
            f"此功能需要入群天数大于 `{least_joined_days}` 天\n已入群天数: `{jd}` 天"
        )

    return await msg.reply(
        f"**确定要击落 {get_md_user_url(msg.reply_to_message.from_user)} 吗?**\n\n**本功能仅可用于击落广告哥, 切勿意气用事**\n否则将进行2倍返还: 被ban的人被封了1小时, 你会被反噬封2小时",
        reply_markup=Ikm(
            [
                [
                    Ikb(
                        "广告哥,击落!",
                        callback_data=f"member_kick=confirm;user={msg.from_user.id}",
                    ),
                    Ikb(
                        "手滑了",
                        callback_data=f"member_kick=cancel;user={msg.from_user.id}",
                    ),
                ]
            ]
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def member_kick(cli: Client, msg: Message):
    rm = msg.reply_to_message  # 用户发送的指令消息
    ad_msg = rm.reply_to_message  # 广告消息
    if await member_is_admin(cli, ad_msg.chat.id, ad_msg.from_user.id):
        return await msg.edit("造反吗? 有意思")

    try:
        await cli.ban_chat_member(ad_msg.chat.id, ad_msg.from_user.id)
    except BadRequest as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await msg.edit("击落失败")
    else:
        await ad_msg.delete()
        await msg.edit(
            f"{get_md_user_url(rm.from_user)} 已击落 {get_md_user_url(ad_msg.from_user)}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


async def admin_kick(cli: Client, msg: Message):
    rm = msg.reply_to_message

    if await member_is_admin(cli, msg.chat.id, rm.from_user.id):
        m = await msg.reply_text("禁止窝里斗")
        return await delete_messages(cli, msg.chat.id, [msg.id, m.id])

    try:
        await cli.ban_chat_member(rm.chat.id, rm.from_user.id)
    except BadRequest as e:
        await msg.reply_text("击落失败")
        logger.error(e)
    else:
        await rm.delete()
        m = await msg.reply_text("已击落")
        await delete_messages(cli, msg.chat.id, [msg.id, m.id])


def joined_days(joined_date: datetime):
    """获取入群天数"""
    now = datetime.now()
    delta = now - joined_date
    return delta.days


async def can_user_kick(user_id: int) -> bool:
    """检查用户是否可以kick"""
    key = f"kick_cooldown:{user_id}"
    exists = await rc.exists(key)
    return not exists


async def set_kick_cooldown(user_id: int):
    """设置用户kick冷却时间（1小时）"""
    key = f"kick_cooldown:{user_id}"
    await rc.set(key, "1", ex=3600)


async def get_kick_cooldown_remaining(user_id: int) -> int:
    """获取剩余冷却时间（秒）"""
    key = f"kick_cooldown:{user_id}"
    ttl = await rc.ttl(key)
    return max(0, ttl) if ttl > 0 else 0
