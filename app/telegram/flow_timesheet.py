"""W4 Timesheet Management - Диалог добавления табеля."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from app.telegram.fsm_states import TimesheetFlow
from app.services.objects import fetch_all_objects
from app.telegram.objects_ui import page_kb
from app.services.bitrix_files import upload_photos_to_bitrix_field
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.http_client import bx
from app.telegram.keyboards import get_main_menu_keyboard

router = Router()

# Функция для запуска табеля (используется из разных мест)
async def start_timesheet_flow(cq: CallbackQuery, state: FSMContext):
    """Начало диалога добавления табеля."""
    await cq.answer()
    await state.clear()
    
    logger.info("[TIMESHEET] entry - starting timesheet flow")
    
    # Загружаем объекты
    objects = await fetch_all_objects()
    await state.update_data(objects_cache=objects, page=0)
    await state.set_state(TimesheetFlow.choose_object)
    
    await cq.message.answer(
        "👥 <b>Добавление табеля</b>\n\n"
        "Выберите объект:",
        reply_markup=page_kb(objects, 0, "tsobj"),
        parse_mode="HTML"
    )

# Хендлер для кнопки "Табель" из главного меню (callback_data="act:tab")
@router.callback_query(F.data == "act:tab")
async def start_timesheet_from_main_menu(cq: CallbackQuery, state: FSMContext):
    """Обработчик кнопки "Табель" из главного меню."""
    await start_timesheet_flow(cq, state)

# Хендлер для callback_data="act:timesheet" (для обратной совместимости)
@router.callback_query(F.data == "act:timesheet")
async def start_timesheet_from_legacy(cq: CallbackQuery, state: FSMContext):
    """Обработчик для обратной совместимости."""
    await start_timesheet_flow(cq, state)

@router.callback_query(TimesheetFlow.choose_object, F.data.startswith("tsobj:page:"))
async def timesheet_object_page(cq: CallbackQuery, state: FSMContext):
    """Пагинация объектов для табеля."""
    await cq.answer()
    page = int(cq.data.split(":")[-1])
    data = await state.get_data()
    objects = data.get("objects_cache", [])
    await cq.message.edit_reply_markup(reply_markup=page_kb(objects, page, "tsobj"))
    await state.update_data(page=page)

@router.callback_query(TimesheetFlow.choose_object, F.data.startswith("tsobj:") & ~F.data.contains(":page:"))
async def timesheet_object_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор объекта для табеля."""
    await cq.answer()
    # Извлекаем Bitrix ID объекта из callback_data
    object_bitrix_id = int(cq.data.split(":")[1])
    
    # Получаем название объекта из кэша (поддерживаем старый и новый формат)
    data = await state.get_data()
    objects_cache = data.get("objects_cache", [])
    # Поддерживаем формат (bitrix_id, title, code) и (bitrix_id, title)
    object_name = None
    for obj_data in objects_cache:
        obj_id = obj_data[0] if isinstance(obj_data, (list, tuple)) else obj_data
        if obj_id == object_bitrix_id:
            object_name = obj_data[1] if len(obj_data) > 1 else f"Объект #{object_bitrix_id}"
            break
    if not object_name:
        object_name = f"Объект #{object_bitrix_id}"
    
    # Сохраняем и object_bitrix_id, и object_name в FSM
    await state.update_data(
        object_id=object_bitrix_id,  # Для обратной совместимости
        object_bitrix_id=object_bitrix_id,  # Bitrix ID объекта
        object_name=object_name  # Полное название из Bitrix
    )
    logger.info(f"[OBJECT] Selected object: bitrix_id={object_bitrix_id}, name={object_name}")
    await state.set_state(TimesheetFlow.choose_shift)
    
    # Создаем клавиатуру для выбора смены
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Сегодня (день)", callback_data="ts_shift:today:day")
    kb.button(text="🌙 Сегодня (ночь)", callback_data="ts_shift:today:night")
    kb.button(text="📅 Завтра (день)", callback_data="ts_shift:tomorrow:day")
    kb.button(text="🌙 Завтра (ночь)", callback_data="ts_shift:tomorrow:night")
    kb.button(text="❌ Отмена", callback_data="cancel_timesheet")
    kb.adjust(2, 2, 1)
    
    await cq.message.answer(
        f"📅 <b>Выбор смены</b>\n\n"
        f"<b>Объект:</b> {object_name}\n\n"
        f"Выберите дату и тип смены:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(TimesheetFlow.choose_shift, F.data.startswith("ts_shift:"))
async def timesheet_shift_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор смены для табеля."""
    await cq.answer()
    
    parts = cq.data.split(":")
    date_key = parts[1]  # today/tomorrow
    shift_type = parts[2]  # day/night
    
    await state.update_data(date_key=date_key, shift_type=shift_type)
    await state.set_state(TimesheetFlow.input_worker)
    
    await cq.message.answer(
        "👤 <b>Бригада/сотрудник</b>\n\n"
        "Введите название бригады или ФИО сотрудника:",
        parse_mode="HTML"
    )

@router.message(TimesheetFlow.input_worker)
async def timesheet_worker_input(message: Message, state: FSMContext):
    """Ввод бригады/сотрудника."""
    import re
    worker = message.text.strip()
    if not worker:
        await message.answer("❌ Введите название бригады или ФИО сотрудника:")
        return
    
    # Парсим количество человек из названия бригады
    # Форматы: "бригада 2 (5 человек)", "бригада 2 (5)", "5 человек", "(5 чел)"
    workers_count = 1  # По умолчанию 1 человек
    patterns = [
        r'\((\d+)\s*(?:человек|чел|чел\.|человека)\)',  # (5 человек), (5 чел)
        r'\((\d+)\)',  # (5)
        r'(\d+)\s*(?:человек|чел|чел\.|человека)',  # 5 человек
    ]
    for pattern in patterns:
        match = re.search(pattern, worker, re.IGNORECASE)
        if match:
            try:
                workers_count = int(match.group(1))
                break
            except (ValueError, IndexError):
                pass
    
    await state.update_data(worker=worker, workers_count=workers_count)
    await state.set_state(TimesheetFlow.input_hours)
    
    count_text = f" ({workers_count} чел.)" if workers_count > 1 else ""
    await message.answer(
        f"⏰ <b>Часы работы</b>\n\n"
        f"<b>Бригада/сотрудник:</b> {worker}{count_text}\n\n"
        f"Введите количество отработанных часов:",
        parse_mode="HTML"
    )

@router.message(TimesheetFlow.input_hours)
async def timesheet_hours_input(message: Message, state: FSMContext):
    """Ввод часов работы."""
    try:
        hours = float(message.text)
        if hours <= 0:
            await message.answer("❌ Количество часов должно быть больше 0. Попробуйте еще раз:")
            return
        
        await state.update_data(hours=hours)
        await state.set_state(TimesheetFlow.input_rate)
        
        await message.answer(
            f"💵 <b>Ставка</b>\n\n"
            f"<b>Часы:</b> {hours}\n\n"
            f"Введите ставку в рублях за час:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте еще раз:")

@router.message(TimesheetFlow.input_rate)
async def timesheet_rate_input(message: Message, state: FSMContext):
    """Ввод ставки."""
    try:
        rate = float(message.text)
        if rate <= 0:
            await message.answer("❌ Ставка должна быть больше 0. Попробуйте еще раз:")
            return
        
        await state.update_data(rate=rate)
        await state.set_state(TimesheetFlow.timesheet_comment)
        
        kb = InlineKeyboardBuilder()
        kb.button(text="⏭ Пропустить", callback_data="skip_ts_comment")
        kb.button(text="❌ Отмена", callback_data="cancel_timesheet")
        kb.adjust(1, 1)
        
        await message.answer(
            "💬 <b>Комментарий к табелю</b> (опционально)\n\n"
            "Введите комментарий или нажмите «Пропустить»:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте еще раз:")

@router.callback_query(TimesheetFlow.timesheet_comment, F.data == "skip_ts_comment")
async def skip_timesheet_comment(cq: CallbackQuery, state: FSMContext):
    """Пропуск комментария к табелю."""
    await cq.answer()
    await state.update_data(timesheet_comment="")
    await _ask_timesheet_photos(cq.message, state)

@router.message(TimesheetFlow.timesheet_comment)
async def timesheet_comment_input(message: Message, state: FSMContext):
    """Ввод комментария к табелю."""
    await state.update_data(timesheet_comment=message.text)
    await _ask_timesheet_photos(message, state)

async def _ask_timesheet_photos(message: Message, state: FSMContext):
    """Спросить о фото для табеля."""
    await state.set_state(TimesheetFlow.timesheet_photos)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📷 Добавить фото", callback_data="add_ts_photos")
    kb.button(text="⏭ Пропустить", callback_data="skip_ts_photos")
    kb.button(text="❌ Отмена", callback_data="cancel_timesheet")
    kb.adjust(1, 1, 1)
    
    await message.answer(
        "📷 <b>Фото табеля</b> (опционально)\n\n"
        "Вы можете добавить несколько фото. Отправьте фото или нажмите «Пропустить»:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(TimesheetFlow.timesheet_photos, F.data == "skip_ts_photos")
async def skip_timesheet_photos(cq: CallbackQuery, state: FSMContext):
    """Пропуск фото для табеля."""
    await cq.answer()
    await state.update_data(timesheet_photos=[])
    await _show_timesheet_summary(cq.message, state)

@router.callback_query(TimesheetFlow.timesheet_photos, F.data == "add_ts_photos")
async def add_timesheet_photos_start(cq: CallbackQuery, state: FSMContext):
    """Начало добавления фото."""
    await cq.answer()
    await state.update_data(timesheet_photos=[])
    await cq.message.answer(
        "📷 Отправьте фото. Можно несколько. После отправки всех фото нажмите «Готово»:",
        reply_markup=None
    )

@router.message(TimesheetFlow.timesheet_photos, F.photo)
async def timesheet_photo_received(message: Message, state: FSMContext):
    """Получено фото для табеля."""
    data = await state.get_data()
    photos = data.get("timesheet_photos", [])
    photos.append(message)
    await state.update_data(timesheet_photos=photos)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data="ts_photos_done")
    kb.button(text="📷 Добавить ещё", callback_data="add_ts_photos")
    kb.button(text="❌ Отмена", callback_data="cancel_timesheet")
    kb.adjust(1, 1, 1)
    
    await message.answer(
        f"✅ Фото добавлено ({len(photos)} шт.)\n\n"
        "Отправьте ещё фото или нажмите «Готово»:",
        reply_markup=kb.as_markup()
    )

@router.callback_query(TimesheetFlow.timesheet_photos, F.data == "ts_photos_done")
async def timesheet_photos_done(cq: CallbackQuery, state: FSMContext):
    """Завершение добавления фото."""
    await cq.answer()
    await _show_timesheet_summary(cq.message, state)

async def _show_timesheet_summary(message: Message, state: FSMContext):
    """Показывает сводку табеля для подтверждения."""
    data = await state.get_data()
    
    hours = float(data.get('hours', 0))
    rate = float(data.get('rate', 0))
    workers_count = int(data.get('workers_count', 1))
    
    # Сумма = часы * ставка * количество человек
    total = hours * rate * workers_count
    
    summary = (
        f"👤 <b>Бригада/сотрудник:</b> {data.get('worker')}\n"
        f"👥 <b>Количество человек:</b> {workers_count}\n"
        f"⏰ <b>Часы:</b> {hours:.1f}\n"
        f"💵 <b>Ставка:</b> {rate:.2f} руб/час\n"
        f"💰 <b>Итого:</b> {total:.2f} руб"
    )
    if workers_count > 1:
        summary += f"\n   ({hours:.1f} ч × {rate:.2f} руб/ч × {workers_count} чел.)"
    
    comment = data.get("timesheet_comment", "")
    photos_count = len(data.get("timesheet_photos", []))
    
    if comment:
        summary += f"\n\n💬 <b>Комментарий:</b> {comment}"
    if photos_count > 0:
        summary += f"\n📷 <b>Фото:</b> {photos_count} шт."
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm_timesheet")
    kb.button(text="❌ Отмена", callback_data="cancel_timesheet")
    kb.adjust(1, 1)
    
    await state.set_state(TimesheetFlow.confirm_timesheet)
    await message.answer(
        f"📋 <b>Сводка табеля</b>\n\n{summary}\n\n"
        f"Подтвердите добавление табеля:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(TimesheetFlow.confirm_timesheet, F.data == "confirm_timesheet")
async def confirm_timesheet_add(cq: CallbackQuery, state: FSMContext):
    """Подтверждение добавления табеля."""
    await cq.answer()
    
    try:
        data = await state.get_data()
        
        # Получаем или создаем смену
        from datetime import date, timedelta
        from app.services.shift_client import bitrix_get_shift_for_object_and_date
        
        shift_date = date.today() if data.get("date_key") == "today" else date.today() + timedelta(days=1)
        # ВАЖНО: Используем object_bitrix_id из FSM (это Bitrix ID объекта)
        object_bitrix_id = data.get("object_bitrix_id") or data.get("object_id")
        
        logger.info(f"[TIMESHEET] Looking for shift: object_bitrix_id={object_bitrix_id}, date={shift_date}")
        
        if not object_bitrix_id:
            logger.error(f"[TIMESHEET] object_bitrix_id not found in state data: {list(data.keys())}")
            await cq.message.answer(
                "❌ <b>Ошибка</b>\n\n"
                "Не найден ID объекта. Начните заново.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Получаем смену (НЕ создаем новую, только ищем существующую)
        shift_id, _ = await bitrix_get_shift_for_object_and_date(
            object_bitrix_id=object_bitrix_id,
            target_date=shift_date,
            create_if_not_exists=False,
        )
        
        if not shift_id:
            logger.warning(f"[SHIFT] no shift found for timesheet object={object_bitrix_id} date={shift_date} – plan missing")
            await cq.message.answer(
                "❌ <b>Не найден план</b>\n\n"
                f"Не найдена смена с планом для объекта и даты.\n\n"
                "Сначала сформируйте <b>ПЛАН</b> для этого объекта.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # ВАЖНО: shift_id здесь - это уже Bitrix ID смены (возвращается из bitrix_get_shift_for_object_and_date)
        shift_bitrix_id = shift_id
        logger.info(f"[TIMESHEET] Using shift_bitrix_id={shift_bitrix_id} for object_bitrix_id={object_bitrix_id}, date={shift_date}")
        
        # Получаем коды полей
        f_shift_id = resolve_code("Табель", "UF_SHIFT_ID")
        f_worker = resolve_code("Табель", "UF_WORKER")
        f_hours = resolve_code("Табель", "UF_HOURS")
        f_rate = resolve_code("Табель", "UF_RATE")
        
        # Логируем перед сохранением
        logger.info(f"[TIMESHEET] ===== START add item =====")
        logger.info(f"[TIMESHEET] Creating item: shift_bitrix_id={shift_bitrix_id}, object_bitrix_id={object_bitrix_id}, worker={data.get('worker')}, hours={data.get('hours')}, rate={data.get('rate')}")
        logger.info(f"[TIMESHEET] Field codes: UF_SHIFT_ID={f_shift_id}, UF_WORKER={f_worker}, UF_HOURS={f_hours}, UF_RATE={f_rate}")
        
        # Создаем табель в Bitrix24
        # ВАЖНО: используем shift_bitrix_id (Bitrix ID смены), а не локальный shift_id!
        title = f"{data.get('worker')} / {data.get('hours')} ч"
        fields = {
            "TITLE": title,
            upper_to_camel(f_shift_id): shift_bitrix_id,  # Bitrix ID смены!
            upper_to_camel(f_worker): data.get("worker"),
            upper_to_camel(f_hours): float(data.get("hours")),
            upper_to_camel(f_rate): float(data.get("rate")),
        }
        
        logger.info(f"[TIMESHEET] Payload to crm.item.add: entityTypeId=1060, fields keys={list(fields.keys())}")
        logger.info(f"[TIMESHEET] Shift ID field value: {fields.get(upper_to_camel(f_shift_id))}")
        
        result = await bx("crm.item.add", {
            "entityTypeId": 1060,  # ENTITY_TIMESHEET
            "fields": fields
        })
        
        timesheet_id = result.get("item", {}).get("id") if isinstance(result, dict) else None
        logger.info(f"[TIMESHEET] Item added successfully: timesheet_id={timesheet_id}, shift_bitrix_id={shift_bitrix_id}")
        
        # Обновляем комментарий, если есть
        comment = data.get("timesheet_comment", "").strip()
        if comment:
            f_comment = resolve_code("Табель", "UF_TS_COMMENT")
            await bx("crm.item.update", {
                "entityTypeId": 1060,
                "id": timesheet_id,
                "fields": {
                    upper_to_camel(f_comment): comment
                }
            })
        
        # Загружаем фото, если есть
        photos = data.get("timesheet_photos", [])
        if photos:
            await upload_photos_to_bitrix_field(
                bot=cq.bot,
                entity_type_id=1060,
                item_id=timesheet_id,
                field_logical_name="UF_TS_PHOTOS",
                entity_ru_name="Табель",
                photo_messages=photos
            )
        
        await cq.message.answer(
            f"✅ <b>Табель добавлен!</b>\n\n"
            f"ID в Bitrix24: {timesheet_id}\n\n"
            f"Возвращаемся в главное меню:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        
        await state.clear()
        logger.info(f"[TIMESHEET] ===== END add item: SUCCESS =====")
        logger.info(f"Timesheet added successfully: {data}")
        
    except Exception as e:
        logger.error(f"Error adding timesheet: {e}", exc_info=True)
        await cq.message.answer(
            f"❌ <b>Ошибка добавления табеля</b>\n\n"
            f"Произошла ошибка: {str(e)}\n\n"
            f"Попробуйте позже или обратитесь к администратору.",
            parse_mode="HTML"
        )
        await state.clear()

@router.callback_query(F.data == "cancel_timesheet")
async def cancel_timesheet_flow(cq: CallbackQuery, state: FSMContext):
    """Отмена добавления табеля."""
    await cq.answer()
    await state.clear()
    
    await cq.message.answer(
        "❌ <b>Добавление табеля отменено</b>\n\n"
        "Возвращаемся в главное меню:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )

