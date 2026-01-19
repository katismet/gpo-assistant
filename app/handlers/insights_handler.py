# app/handlers/insights_handler.py
"""Обработчик команды /insights для владельца."""

import datetime as dt
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.services.authz import get_user
from app.services.insights import collect_kpis, generate_insights

router = Router(name="insights")
log = logging.getLogger("gpo.insights_handler")


@router.message(Command("insights"))
@router.message(F.text.lower() == "/insights")
@router.message(F.text == "🤖 Инсайты")
async def insights_command(m: Message):
    """Генерация AI-инсайтов для владельца."""
    try:
        me = get_user(m.from_user.id)
        if not me or me.get("role", "").upper() not in ("OWNER", "ADMIN"):
            await m.answer("❌ Доступ запрещён. Эта функция доступна только владельцу и администратору.")
            return
        
        await m.answer("⏳ Генерирую инсайты...")
        
        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)
        
        k_today = await collect_kpis(today)
        k_yesterday = await collect_kpis(yesterday)
        
        txt = await generate_insights(k_today, k_yesterday)
        
        await m.answer(f"📈 Ежедневные инсайты\n\n{txt}")
        log.info(f"Generated insights for user {m.from_user.id}")
        
    except Exception as e:
        log.error(f"Error in insights_command: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка генерации инсайтов: {e}")

