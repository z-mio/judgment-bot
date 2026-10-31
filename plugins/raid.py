import time

from pyrogram import Client, filters
from pyrogram.types import Message

from log import logger
from plugins.helpers import (
    delete_messages,
    is_user_or_anonymous_admin,
    member_is_admin,
    reply_and_delete,
)
from plugins.verify import clear_pending_verifies, send_raid_notice
from services.raid_guard_manager import raid_guard_manager
from utils.formatting import format_seconds

logger = logger.bind(name="Raid")


@Client.on_message(
    ~filters.bot & filters.command("raid") & filters.group & filters.admin
)
async def raid(cli: Client, msg: Message) -> None:
    if not msg.chat or msg.chat.id is None:
        return
    if not is_user_or_anonymous_admin(msg):
        return

    chat_id = msg.chat.id
    operator_id = msg.from_user.id if msg.from_user else None
    operator = (
        msg.from_user.full_name or str(msg.from_user.id)
        if msg.from_user
        else "匿名管理员"
    )
    if msg.from_user and not await member_is_admin(cli, chat_id, msg.from_user.id):
        logger.warning(
            f"防轰炸操作被拒: 权限不足 | user_id={msg.from_user.id} | chat_id={chat_id}"
        )
        await reply_and_delete(cli, msg, chat_id, "权限不足")
        return

    args = msg.command[1:] if msg.command else []
    if not args:
        mode = await raid_guard_manager.get_mode(chat_id)
        stats = await raid_guard_manager.stats(chat_id)
        if not mode:
            mode_text = "防轰炸模式: 关闭"
        else:
            source = "自动开启" if mode.source == "auto" else "手动开启"
            duration = format_seconds(int(time.time() - mode.since))
            mode_text = f"防轰炸模式: {source}, 已持续 {duration}"
        pass_rate = "-" if stats.pass_rate is None else f"{stats.pass_rate:.0%}"
        text = (
            f"{mode_text}\n"
            f"近 5 分钟进群: {stats.joins} | 近 1 分钟: {stats.burst_joins}\n"
            f"近 5 分钟验证: {stats.results} 人, 通过率 {pass_rate}"
        )
        await reply_and_delete(cli, msg, chat_id, text)
        return

    action = args[0].lower()
    if action == "on" and len(args) == 1:
        await raid_guard_manager.enable_manual(chat_id, by=operator_id)
        await delete_messages(cli, chat_id, [msg.id], delay=0)
        await send_raid_notice(cli, chat_id)
        await clear_pending_verifies(cli, chat_id)
        logger.info(
            f"防轰炸模式手动开启: {operator} | user_id={operator_id} | "
            f"chat_id={chat_id}"
        )
        return
    if action == "off" and len(args) == 1:
        await raid_guard_manager.disable(chat_id)
        logger.info(
            f"防轰炸模式手动关闭: {operator} | user_id={operator_id} | "
            f"chat_id={chat_id}"
        )
        await reply_and_delete(cli, msg, chat_id, "已关闭防轰炸模式")
        return

    await reply_and_delete(cli, msg, chat_id, "用法: `/raid [on|off]`")
