from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    Chat,
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
)

from i18n import t_
from log import logger
from utils.util import get_chat_link, get_md_chat_link, html_code, member_is_admin
from validator.easy_validator import full_chat_permissions


@Client.on_message(filters.command("unban") & filters.group & filters.admin)
async def unban(client: Client, message: Message) -> None:
    _t = t_[message]

    if not message.from_user or not message.chat or message.chat.id is None:
        return
    chat_id = int(message.chat.id)
    if not await member_is_admin(client, chat_id, message.from_user.id):
        await message.reply(_t("权限不足"))
        return

    args = message.command[1:] if message.command else []
    if not args:
        await message.reply(_t("请加上用户名或id\n例: <code>/unban @username</code>"))
        return

    unban_user_id = args[0]

    try:
        unban_user = await client.get_chat(unban_user_id)
    except Exception as e:
        logger.exception(e)
        logger.error("获取用户信息失败, 以上为错误信息")
        await message.reply(
            _t(f"获取 {html_code(unban_user_id)} 信息失败"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    try:
        if unban_user.type == ChatType.PRIVATE:
            target_id = int(unban_user.id or 0)
            await client.unban_chat_member(chat_id, target_id)
            try:
                await client.restrict_chat_member(
                    chat_id,
                    target_id,
                    permissions=full_chat_permissions(),
                )
            except Exception as e:
                logger.exception(e)
                logger.error("恢复用户权限失败, 以上为错误信息")
            try:
                current_chat: Chat = message.chat
                await client.send_message(
                    target_id,
                    _t(
                        f"{get_md_chat_link(message.from_user)} 已在 {get_md_chat_link(current_chat)} 中将你解除封禁"
                    ),
                    reply_markup=Ikm(
                        [
                            [
                                Ikb(
                                    text=_t("点击重新加入群组"),
                                    url=get_chat_link(current_chat),
                                )
                            ]
                        ]
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception as e:
                logger.exception(e)
                logger.error("通知用户 [解除封禁] 失败, 以上为错误信息")
        else:
            await client.unban_chat_member(chat_id, int(unban_user.id or 0))

    except Exception as e:
        logger.exception(e)
        logger.error("放出用户失败, 以上为错误信息")
        await message.reply(
            _t(f"放出 {get_md_chat_link(unban_user)} 失败"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
    else:
        await message.reply(
            _t(f"已放出 {get_md_chat_link(unban_user)}"),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
