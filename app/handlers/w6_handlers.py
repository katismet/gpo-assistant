# app/handlers/w6_handlers.py

import datetime as dt
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message

from app.services.w6_alerts import (
    build_daily_report, build_daily_report_for_shift, subscribe, unsubscribe,
    list_shifts_by_date, list_resources_by_shift, list_timesheets_by_shift
)

router = Router()
log = logging.getLogger("gpo.w6_handlers")

# Тестовый обработчик для проверки работы роутера
@router.message(Command("test_w6"))
async def test_handler(m: Message):
    """Тестовый обработчик для проверки работы роутера."""
    log.info(f"test_w6 handler called by user {m.from_user.id}")
    await m.answer("✅ Обработчик w6_handlers работает!")


# Обработчик для /daily_report с параметрами через Command
@router.message(Command("daily_report"))
async def daily_report_command(m: Message, command: CommandObject):
    """Обработчик команды /daily_report через Command фильтр."""
    try:
        log.info(f"daily_report_command handler called by user {m.from_user.id}, args: {command.args}")
        # Получаем аргументы команды
        args = command.args if command.args else ""
        args = args.strip()
        
        # Обработка параметра shift:<id>
        if args.startswith("shift:"):
            try:
                sid = int(args.split(":", 1)[1])
                log.info(f"User {m.from_user.id} requested daily report for shift {sid}")
                txt = await build_daily_report_for_shift(sid)
                await m.answer(txt)
                return
            except ValueError:
                await m.answer("Формат: /daily_report shift:<id>")
                return
        
        # Обработка даты
        if args:
            try:
                date = dt.datetime.strptime(args, "%Y-%m-%d").date()
                log.info(f"User {m.from_user.id} requested daily report for {date}")
            except ValueError:
                await m.answer("Формат: /daily_report YYYY-MM-DD или /daily_report shift:<id>")
                return
        else:
            date = dt.date.today()
            log.info(f"User {m.from_user.id} requested daily report for today")
        
        result = await build_daily_report(date)
        if isinstance(result, tuple):
            txt, shifts = result
        else:
            txt = result
            shifts = []
        
        # Создаем интерактивную клавиатуру с кнопками для ЛПА
        if shifts:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from app.bitrix_field_map import resolve_code
            from app.services.w6_alerts import _get_field_value
            
            kb = InlineKeyboardBuilder()
            f_fact = resolve_code("Смена", "UF_FACT_TOTAL")
            buttons_added = 0
            
            for s in shifts:
                sid = s["id"]
                fact_total = float((_get_field_value(s, f_fact) or 0))
                
                # Добавляем кнопку только для смен с фактическими данными
                if fact_total > 0:
                    kb.button(text=f"📄 ЛПА для смены #{sid}", callback_data=f"lpa_shift:{sid}")
                    buttons_added += 1
                    
                    # Ограничиваем количество кнопок (максимум 10)
                    if buttons_added >= 10:
                        break
            
            if buttons_added > 0:
                kb.adjust(1)  # По одной кнопке в ряд
                await m.answer(txt, reply_markup=kb.as_markup())
            else:
                await m.answer(txt)
        else:
            await m.answer(txt)
    except Exception as e:
        log.error(f"Error in daily_report_command: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка генерации сводки: {e}")


# Альтернативный обработчик через регулярное выражение (для обратной совместимости)
@router.message(F.text.regexp(r"^/daily_report(\s+[\w\-:]+)?$"))
async def daily_report(m: Message):
    """Получить сводку за указанную дату, сегодня или по конкретной смене."""
    try:
        log.info(f"daily_report handler called by user {m.from_user.id}, text: {m.text}")
        if not m.text:
            log.warning(f"Message text is None for user {m.from_user.id}")
            return
        parts = m.text.strip().split()
        
        # Обработка параметра shift:<id>
        if len(parts) == 2 and parts[1].startswith("shift:"):
            try:
                sid = int(parts[1].split(":", 1)[1])
                log.info(f"User {m.from_user.id} requested daily report for shift {sid}")
                txt = await build_daily_report_for_shift(sid)
                await m.answer(txt)
                return
            except ValueError:
                await m.answer("Формат: /daily_report shift:<id>")
                return
        
        # Обработка даты
        if len(parts) == 2:
            try:
                date = dt.datetime.strptime(parts[1], "%Y-%m-%d").date()
                log.info(f"User {m.from_user.id} requested daily report for {date}")
            except ValueError:
                await m.answer("Формат: /daily_report YYYY-MM-DD или /daily_report shift:<id>")
                return
        else:
            date = dt.date.today()
            log.info(f"User {m.from_user.id} requested daily report for today")
        
        result = await build_daily_report(date)
        if isinstance(result, tuple):
            txt, shifts = result
        else:
            txt = result
            shifts = []
        
        # Создаем интерактивную клавиатуру с кнопками для ЛПА
        if shifts:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from app.bitrix_field_map import resolve_code
            from app.services.w6_alerts import _get_field_value
            
            kb = InlineKeyboardBuilder()
            f_fact = resolve_code("Смена", "UF_FACT_TOTAL")
            buttons_added = 0
            
            for s in shifts:
                sid = s["id"]
                fact_total = float((_get_field_value(s, f_fact) or 0))
                
                # Добавляем кнопку только для смен с фактическими данными
                if fact_total > 0:
                    kb.button(text=f"📄 ЛПА для смены #{sid}", callback_data=f"lpa_shift:{sid}")
                    buttons_added += 1
                    
                    # Ограничиваем количество кнопок (максимум 10)
                    if buttons_added >= 10:
                        break
            
            if buttons_added > 0:
                kb.adjust(1)  # По одной кнопке в ряд
                await m.answer(txt, reply_markup=kb.as_markup())
            else:
                await m.answer(txt)
        else:
            await m.answer(txt)
    except Exception as e:
        log.error(f"Error in daily_report: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка генерации сводки: {e}")


@router.message(Command("subscribe_alerts"))
async def sub_alerts(m: Message):
    """Подписка на ежедневные сводки."""
    try:
        log.info(f"User {m.from_user.id} subscribing to alerts (chat_id: {m.chat.id})")
        result = subscribe(m.chat.id)
        await m.answer(result)
        log.info(f"User {m.from_user.id} subscribed successfully")
    except Exception as e:
        log.error(f"Error subscribing user {m.from_user.id}: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка подписки: {e}")


@router.message(Command("unsubscribe_alerts"))
async def unsub_alerts(m: Message):
    """Отписка от ежедневных сводок."""
    try:
        log.info(f"User {m.from_user.id} unsubscribing from alerts")
        result = unsubscribe(m.chat.id)
        await m.answer(result)
        log.info(f"User {m.from_user.id} unsubscribed successfully")
    except Exception as e:
        log.error(f"Error unsubscribing user {m.from_user.id}: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка отписки: {e}")


@router.message(Command("status"))
async def status(m: Message):
    """Диагностика сводки: показать найденные смены и связанные ресурсы/табель."""
    try:
        log.info(f"status handler called by user {m.from_user.id}, text: {m.text}")
        d = dt.date.today()
        log.info(f"User {m.from_user.id} requested status for {d}")
        
        shifts = await list_shifts_by_date(d)
        
        if not shifts:
            await m.answer(
                f"Сегодня ({d:%d.%m}) смен не найдено.\n"
                f"Проверь поле «Дата» в СПА «Смена»."
            )
            return
        
        lines = [f"Сегодня ({d:%d.%m}) найдено смен: {len(shifts)}"]
        
        for s in shifts:
            sid = s["id"]
            res = await list_resources_by_shift(sid)
            ts = await list_timesheets_by_shift(sid)
            lines.append(f"— Смена #{sid}: ресурсов {len(res)}, табельных {len(ts)}")
        
        await m.answer("\n".join(lines))
        log.info(f"Status sent successfully for {len(shifts)} shifts")
        
    except Exception as e:
        log.error(f"Error in status: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка получения статуса: {e}")

