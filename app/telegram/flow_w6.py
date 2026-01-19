"""W6: Ежедневные уведомления и расчёт эффективности смен."""

import logging
from datetime import date, datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.services.w6_alerts import (
    subscribe,
    unsubscribe,
    build_daily_report,
    list_subscribers,
)

router = Router(name="w6")
log = logging.getLogger("gpo.w6")


@router.message(Command("w6_subscribe"))
async def cmd_subscribe(m: Message):
    """Подписка на ежедневные сводки."""
    try:
        result = subscribe(m.from_user.id)
        await m.answer(result)
        log.info(f"User {m.from_user.id} subscribed to W6 alerts")
    except Exception as e:
        log.error(f"Error subscribing user {m.from_user.id}: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка подписки: {e}")


@router.message(Command("w6_unsubscribe"))
async def cmd_unsubscribe(m: Message):
    """Отписка от ежедневных сводок."""
    try:
        result = unsubscribe(m.from_user.id)
        await m.answer(result)
        log.info(f"User {m.from_user.id} unsubscribed from W6 alerts")
    except Exception as e:
        log.error(f"Error unsubscribing user {m.from_user.id}: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка отписки: {e}")


@router.message(Command("w6_report"))
async def cmd_report(m: Message):
    """Получить сводку за сегодня."""
    try:
        today = date.today()
        report, _ = await build_daily_report(today)
        await m.answer(f"📊 {report}")
        log.info(f"User {m.from_user.id} requested W6 report for {today}")
    except Exception as e:
        log.error(f"Error generating W6 report: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка генерации сводки: {e}")



