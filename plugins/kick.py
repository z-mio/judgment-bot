from datetime import datetime

from pyrogram import Client, filters, enums
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup as Ikm,
    InlineKeyboardButton as Ikb,
    LinkPreviewOptions,
)

from log import logger
from services.kick_cooldown_manager import kick_cooldown
from utils.util import get_md_chat_link, member_is_admin, delete_messages


@Client.on_message(filters.command("kick") & filters.group & filters.admin)
async def kick(cli: Client, msg: Message):
    if not msg.reply_to_message:
        m = await msg.reply("请回复一条消息")
        await delete_messages(cli, msg.chat.id, [msg.id, m.id])
    elif msg.reply_to_message.from_user.id == msg.from_user.id:
        await msg.reply("紫砂吗? 有意思")
    elif msg.reply_to_message.from_user.id == cli.me.id:
        await msg.reply("big胆!")
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
        await member_kick(cli, cq.message)
    elif action == "cancel":
        await kick_cooldown.clear_cooldown(action_user_id)
        await cq.message.edit("已取消操作")


async def member_kick_button(_, msg: Message):
    least_joined_days = 30
    ad_joined_days = 30

    member = await msg.chat.get_member(msg.from_user.id)
    try:
        ad_member = await msg.chat.get_member(msg.reply_to_message.from_user.id)
    except UserNotParticipant:
        ...  # 从关联频道发送的广告, 不在群里
    else:
        if (ad_jd := joined_days(ad_member.joined_date)) > ad_joined_days:
            return await msg.reply(
                f"{get_md_chat_link(ad_member.user)} 入群天数 `{ad_jd}` 大于 `{ad_joined_days}` 天, 无法击落",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
    if (jd := joined_days(member.joined_date)) < least_joined_days:
        return await msg.reply(
            f"此功能需要入群天数大于 `{least_joined_days}` 天\n已入群天数: `{jd}` 天"
        )
    if await kick_cooldown.can_user_kick(msg.from_user.id):
        await kick_cooldown.set_cooldown(msg.from_user.id)
    else:
        return await msg.reply(
            f"冷却中... | 剩余: {await kick_cooldown.get_remaining_time_formatted(msg.from_user.id)}"
        )

    return await msg.reply(
        f"**确定要击落 {get_md_chat_link(msg.reply_to_message.from_user)} 吗?**\n\n**本功能仅可用于击落广告哥, 切勿意气用事**\n否则将进行2倍返还: 被ban的人被封了1小时, 你会被反噬封2小时",
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
        await msg.edit("造反吗? 有意思")
        await kick_cooldown.clear_cooldown(rm.from_user.id)
        return

    try:
        await cli.ban_chat_member(ad_msg.chat.id, ad_msg.from_user.id)
    except Exception as e:
        logger.exception(e)
        logger.error("击落失败, 以上为错误信息")
        await msg.edit("击落失败")
        await kick_cooldown.clear_cooldown(rm.from_user.id)
    else:
        await delete_member_messages(
            cli, ad_msg.chat.id, ad_msg.from_user.id, ad_msg.id
        )
        await msg.edit(
            f"{get_md_chat_link(rm.from_user)} 已击落 {get_md_chat_link(ad_msg.from_user)}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        admins = "\n".join(
            [
                f"• {get_md_chat_link(member.user)}"
                async for member in rm.chat.get_members(
                    filter=enums.ChatMembersFilter.ADMINISTRATORS
                )
            ]
        )
        try:
            await cli.send_message(
                ad_msg.from_user.id,
                f"**你已被 {get_md_chat_link(rm.from_user)} 踢出 {get_md_chat_link(rm.chat)}**\n如有异议请联系群组管理:\n"
                f"{admins}",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.exception(e)
            logger.error("通知用户失败, 以上为错误信息")


async def admin_kick(cli: Client, msg: Message):
    rm = msg.reply_to_message
    if await member_is_admin(cli, msg.chat.id, rm.from_user.id):
        m = await msg.reply_text("禁止窝里斗")
        return await delete_messages(cli, msg.chat.id, [msg.id, m.id])

    try:
        await cli.ban_chat_member(rm.chat.id, rm.from_user.id)
    except Exception as e:
        await msg.reply_text("击落失败")
        logger.error(e)
    else:
        await delete_member_messages(cli, rm.chat.id, rm.from_user.id, rm.id)
        m = await msg.reply_text("已击落")
        await delete_messages(cli, msg.chat.id, [msg.id, m.id])


async def delete_member_messages(
    cli: Client, chat_id: int, user_id: int, msg_id: int, limit: int = 100
):
    """
    删除最近 100 条消息
    """
    msgs = await cli.get_messages(
        chat_id,
        message_ids=list(
            range(max(msg_id - (limit // 2), 1), msg_id + (limit // 2) + 1)
        ),
    )
    for m in msgs:
        if m.empty:
            continue
        if m.from_user:
            if m.from_user.id == user_id:
                await m.delete()


def joined_days(joined_date: datetime | None):
    """获取入群天数"""
    if not joined_date:
        return 114514
    now = datetime.now()
    delta = now - joined_date
    return delta.days
