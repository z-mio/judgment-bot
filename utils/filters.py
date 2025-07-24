from pyrogram import filters
from pyrogram.types import Message
from config.config import cfg


async def _is_admin(_, __, msg: Message):
    return msg.from_user.id in cfg.admins


is_admin = filters.create(_is_admin)
