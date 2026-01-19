from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

async def safe_edit_markup(cq, **kw):
    try:
        return await cq.message.edit_reply_markup(**kw)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return None
        raise

async def safe_edit_text(cq, *a, **kw):
    try:
        return await cq.message.edit_text(*a, **kw)
    except TelegramAPIError:
        return await cq.message.answer(*a, **kw)

