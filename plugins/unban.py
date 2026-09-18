from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    InlineKeyboardButton as Ikb,
    InlineKeyboardMarkup as Ikm,
    LinkPreviewOptions,
    Message,
    ChatPermissions,
)

from log import logger
from plugins.helpers import get_md_chat_link, get_chat_link, member_is_admin
from plugins.verify import clear_verify_failed


@Client.on_message(filters.command("unban") & filters.group & filters.admin)
async def unban(cli: Client, msg: Message) -> None:

    if not msg.chat or msg.chat.id is None:
        return
    # 匿名管理员: from_user 为 None, sender_chat 为群组本身
    if not msg.from_user and (not msg.sender_chat or msg.sender_chat.id != msg.chat.id):
        return

    chat_id = msg.chat.id
    # 匿名管理员一定是管理员, 无需额外检查
    if msg.from_user and not await member_is_admin(cli, chat_id, msg.from_user.id):
        await msg.reply("权限不足")
        return

    if not msg.command or not msg.command[1:]:
        await msg.reply("请加上用户名或id\n例: `/unban @username`")
        return

    unban_id = msg.command[1]

    try:
        unban_user = await cli.get_chat(
            int(unban_id) if unban_id.isdigit() else unban_id
        )
    except Exception as e:
        logger.exception(e)
        logger.error("获取用户信息失败, 以上为错误信息")
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

        if unban_user.type != ChatType.PRIVATE:
            return

        try:
            await cli.restrict_chat_member(
                chat_id,
                target_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_react_to_messages=True,
                    can_edit_tag=True,
                    can_invite_users=True,
                ),
            )
        except Exception as e:
            logger.exception(e)
            logger.error("恢复用户权限失败, 以上为错误信息")

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
            logger.exception(e)
            logger.error("通知用户 [解除封禁] 失败, 以上为错误信息")

    except Exception as e:
        logger.exception(e)
        logger.error("放出用户失败, 以上为错误信息")
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
