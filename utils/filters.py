from pyrogram import filters
from pyrogram.types import Message, ChatMemberUpdated
from config.config import cfg


async def _is_admin(_, __, msg: Message):
    return msg.from_user.id in cfg.admins


is_admin = filters.create(_is_admin)


async def _new_members(_, __, update: ChatMemberUpdated):
    """自带的 filters.new_chat_members 不支持超级群组, 必须用 on_chat_member_updated 来实现"""
    try:
        return update.from_user.id == update.new_chat_member.user.id and (
            not update.old_chat_member or not update.old_chat_member.is_member
        )
    except Exception:
        return False


new_members = filters.create(_new_members)
"""新成员入群"""
