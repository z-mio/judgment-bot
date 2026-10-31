from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from log import logger
from plugins.helpers import (
    full_chat_permissions,
    get_chat_link,
    get_md_chat_link,
    is_user_or_anonymous_admin,
    member_is_admin,
)
from plugins.verify import clear_verify_failed

logger = logger.bind(name="Unban")


@Client.on_message(
    ~filters.bot & filters.command("unban") & filters.group & filters.admin
)
async def unban(cli: Client, msg: Message) -> None:

    if not msg.chat or msg.chat.id is None:
        return
    # 匿名管理员: from_user 为 None, sender_chat 为群组本身
    if not is_user_or_anonymous_admin(msg):
        return

    chat_id = msg.chat.id
    operator = msg.from_user.id if msg.from_user else "匿名管理员"
    # 匿名管理员一定是管理员, 无需额外检查
    if msg.from_user and not await member_is_admin(cli, chat_id, msg.from_user.id):
        logger.warning(
            f"解封被拒: 权限不足 | user_id={msg.from_user.id} | chat_id={chat_id}"
        )
        await msg.reply("权限不足")
        return

    if not msg.command or not msg.command[1:]:
        logger.debug(
            f"忽略解封: 缺少用户名或 id | user_id={operator} | chat_id={chat_id}"
        )
        await msg.reply("请加上用户名或id\n例: `/unban @username`")
        return

    unban_id = msg.command[1]

    try:
        unban_user = await cli.get_chat(
            int(unban_id) if unban_id.isdigit() else unban_id
        )
    except Exception:
        logger.exception(f"获取解封目标信息失败: target={unban_id} | chat_id={chat_id}")
        await msg.reply(
            f"获取 `{unban_id}` 信息失败",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
    if not unban_user:
        return
    try:
        target_id = unban_user.id
        if not target_id:
            raise ValueError("no id")

        await cli.unban_chat_member(chat_id, target_id)
        await clear_verify_failed(chat_id, target_id)
        logger.info(
            f"已解封: {unban_user.full_name or unban_user.id} | user_id={target_id} | "
            f"chat_id={chat_id} | 操作人={operator}"
        )

        if unban_user.type != ChatType.PRIVATE:
            return

        try:
            await cli.restrict_chat_member(
                chat_id,
                target_id,
                permissions=full_chat_permissions(),
            )
        except Exception:
            logger.exception(
                f"恢复用户权限失败: user_id={target_id} | chat_id={chat_id}"
            )

        try:
            # 匿名管理员时 msg.from_user 为 None, 但 msg.sender_chat 存在
            action_user = msg.from_user or msg.sender_chat
            assert action_user is not None
            await cli.send_message(
                target_id,
                f"{get_md_chat_link(action_user)} 已在 {get_md_chat_link(msg.chat)} 中将你解除封禁",
                reply_markup=Ikm(
                    [
                        [
                            Ikb(
                                text="点击重新加入群组",
                                url=u,
                            )
                        ]
                    ]
                )
                if (u := get_chat_link(msg.chat))
                else None,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.warning(f"通知用户 [解除封禁] 失败: user_id={target_id} | {e}")

    except Exception:
        logger.exception(f"解封失败: target={unban_id} | chat_id={chat_id}")
        await msg.reply(
            f"放出 {get_md_chat_link(unban_user)} 失败",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
    else:
        await msg.reply(
            f"已放出 {get_md_chat_link(unban_user)}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
