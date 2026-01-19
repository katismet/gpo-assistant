"""W3 Resource Management - Диалог добавления ресурсов."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from app.telegram.fsm_states import ResourceFlow
from app.services.objects import fetch_all_objects
from app.telegram.objects_ui import page_kb
from app.services.catalogs import (
    get_equip_type_keyboard, get_mat_type_keyboard, 
    get_rate_type_keyboard, get_unit_keyboard
)
from app.services.resource_client import (
    bitrix_add_resource,
    validate_resource_data, format_resource_summary
)
from app.services.shift_client import bitrix_get_shift_for_object_and_date
from app.telegram.keyboards import get_main_menu_keyboard

router = Router()

@router.callback_query(F.data == "act:resources")
async def start_resource_flow(cq: CallbackQuery, state: FSMContext):
    """Начало диалога добавления ресурса."""
    await cq.answer()
    await state.clear()
    
    logger.info("[RESOURCE] entry - starting resource flow")
    
    try:
        # Загружаем объекты
        objects = await fetch_all_objects()
        await state.update_data(objects_cache=objects, page=0)
        await state.set_state(ResourceFlow.choose_object)
        
        await cq.message.answer(
            "🔧 <b>Добавление ресурса</b>\n\n"
            "Выберите объект:",
            reply_markup=page_kb(objects, 0, "resobj"),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception("[RESOURCE] error in start_resource_flow")
        await cq.message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при загрузке объектов. Попробуйте позже.",
            parse_mode="HTML"
        )

@router.callback_query(ResourceFlow.choose_object, F.data.startswith("resobj:page:"))
async def resource_object_page(cq: CallbackQuery, state: FSMContext):
    """Пагинация объектов для ресурсов."""
    await cq.answer()
    page = int(cq.data.split(":")[-1])
    data = await state.get_data()
    objects = data.get("objects_cache", [])
    await cq.message.edit_reply_markup(reply_markup=page_kb(objects, page, "resobj"))
    await state.update_data(page=page)

@router.callback_query(ResourceFlow.choose_object, F.data.startswith("resobj:") & ~F.data.contains(":page:"))
async def resource_object_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор объекта для ресурса."""
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
    await state.set_state(ResourceFlow.choose_shift)
    
    # Создаем клавиатуру для выбора смены
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Сегодня (день)", callback_data="shift:today:day")
    kb.button(text="🌙 Сегодня (ночь)", callback_data="shift:today:night")
    kb.button(text="📅 Завтра (день)", callback_data="shift:tomorrow:day")
    kb.button(text="🌙 Завтра (ночь)", callback_data="shift:tomorrow:night")
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(2, 2, 1)
    
    await cq.message.answer(
        f"📅 <b>Выбор смены</b>\n\n"
        f"<b>Объект:</b> {object_name}\n\n"
        f"Выберите дату и тип смены:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(ResourceFlow.choose_shift, F.data.startswith("shift:"))
async def resource_shift_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор смены для ресурса."""
    await cq.answer()
    
    parts = cq.data.split(":")
    date_key = parts[1]  # today/tomorrow
    shift_type = parts[2]  # day/night
    
    await state.update_data(date_key=date_key, shift_type=shift_type)
    await state.set_state(ResourceFlow.choose_type)
    
    # Создаем клавиатуру для выбора типа ресурса
    kb = InlineKeyboardBuilder()
    kb.button(text="🔧 Техника", callback_data="type:EQUIP")
    kb.button(text="📦 Материалы", callback_data="type:MAT")
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(2, 1)
    
    await cq.message.answer(
        "🔧 <b>Тип ресурса</b>\n\n"
        "Выберите тип ресурса:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(ResourceFlow.choose_type, F.data.startswith("type:"))
async def resource_type_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор типа ресурса."""
    await cq.answer()
    
    resource_type = cq.data.split(":")[1]
    await state.update_data(resource_type=resource_type)
    
    if resource_type == "EQUIP":
        await state.set_state(ResourceFlow.equip_type)
        await cq.message.answer(
            "🔧 <b>Тип техники</b>\n\n"
            "Выберите тип техники:",
            reply_markup=get_equip_type_keyboard(),
            parse_mode="HTML"
        )
    else:
        await state.set_state(ResourceFlow.mat_type)
        await cq.message.answer(
            "📦 <b>Тип материала</b>\n\n"
            "Выберите тип материала:",
            reply_markup=get_mat_type_keyboard(),
            parse_mode="HTML"
        )

# Обработчики для техники
@router.callback_query(ResourceFlow.equip_type, F.data.startswith("equip_type:"))
async def equip_type_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор типа техники."""
    await cq.answer()
    
    if cq.data.startswith("equip_type:page:"):
        # Пагинация
        page = int(cq.data.split(":")[-1])
        await cq.message.edit_reply_markup(reply_markup=get_equip_type_keyboard(page))
        return
    
    equip_type = cq.data.split(":", 1)[1]
    await state.update_data(equip_type=equip_type)
    await state.set_state(ResourceFlow.equip_hours)
    
    await cq.message.answer(
        f"⏰ <b>Часы работы</b>\n\n"
        f"<b>Техника:</b> {equip_type}\n\n"
        f"Укажите количество часов работы или рейсов:",
        parse_mode="HTML"
    )

@router.message(ResourceFlow.equip_hours)
async def equip_hours_input(message: Message, state: FSMContext):
    """Ввод часов работы техники."""
    try:
        hours = float(message.text)
        if hours <= 0:
            await message.answer("❌ Количество часов должно быть больше 0. Попробуйте еще раз:")
            return
        
        await state.update_data(equip_hours=hours)
        await state.set_state(ResourceFlow.equip_rate_type)
        
        await message.answer(
            f"💰 <b>Тип тарифа</b>\n\n"
            f"<b>Техника:</b> {message.text} часов\n\n"
            f"Выберите тип тарифа:",
            reply_markup=get_rate_type_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте еще раз:")

@router.callback_query(ResourceFlow.equip_rate_type, F.data.startswith("rate_type:"))
async def equip_rate_type_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор типа тарифа для техники."""
    await cq.answer()
    
    rate_type = cq.data.split(":")[1]
    await state.update_data(equip_rate_type=rate_type)
    await state.set_state(ResourceFlow.equip_rate)
    
    await cq.message.answer(
        f"💵 <b>Ставка</b>\n\n"
        f"<b>Тип тарифа:</b> {rate_type}\n\n"
        f"Укажите ставку в рублях:",
        parse_mode="HTML"
    )

@router.message(ResourceFlow.equip_rate)
async def equip_rate_input(message: Message, state: FSMContext):
    """Ввод ставки для техники."""
    try:
        rate = float(message.text)
        if rate <= 0:
            await message.answer("❌ Ставка должна быть больше 0. Попробуйте еще раз:")
            return
        
        await state.update_data(equip_rate=rate)
        await state.set_state(ResourceFlow.resource_comment)
        
        kb = InlineKeyboardBuilder()
        kb.button(text="⏭ Пропустить", callback_data="skip_comment")
        kb.button(text="❌ Отмена", callback_data="cancel_resource")
        kb.adjust(1, 1)
        
        await message.answer(
            "💬 <b>Комментарий к ресурсу</b> (опционально)\n\n"
            "Введите комментарий или нажмите «Пропустить»:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте еще раз:")

# Обработчики для материалов
@router.callback_query(ResourceFlow.mat_type, F.data.startswith("mat_type:"))
async def mat_type_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор типа материала."""
    await cq.answer()
    
    if cq.data.startswith("mat_type:page:"):
        # Пагинация
        page = int(cq.data.split(":")[-1])
        await cq.message.edit_reply_markup(reply_markup=get_mat_type_keyboard(page))
        return
    
    mat_type = cq.data.split(":", 1)[1]
    await state.update_data(mat_type=mat_type)
    await state.set_state(ResourceFlow.mat_qty)
    
    await cq.message.answer(
        f"📊 <b>Количество</b>\n\n"
        f"<b>Материал:</b> {mat_type}\n\n"
        f"Укажите количество:",
        parse_mode="HTML"
    )

@router.message(ResourceFlow.mat_qty)
async def mat_qty_input(message: Message, state: FSMContext):
    """Ввод количества материала."""
    try:
        qty = float(message.text)
        if qty <= 0:
            await message.answer("❌ Количество должно быть больше 0. Попробуйте еще раз:")
            return
        
        await state.update_data(mat_qty=qty)
        await state.set_state(ResourceFlow.mat_unit)
        
        await message.answer(
            f"📏 <b>Единица измерения</b>\n\n"
            f"<b>Количество:</b> {message.text}\n\n"
            f"Выберите единицу измерения:",
            reply_markup=get_unit_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте еще раз:")

@router.callback_query(ResourceFlow.mat_unit, F.data.startswith("unit:"))
async def mat_unit_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор единицы измерения материала."""
    await cq.answer()
    
    unit = cq.data.split(":")[1]
    await state.update_data(mat_unit=unit)
    await state.set_state(ResourceFlow.mat_price)
    
    await cq.message.answer(
        f"💵 <b>Цена</b>\n\n"
        f"<b>Единица:</b> {unit}\n\n"
        f"Укажите цену за единицу в рублях:",
        parse_mode="HTML"
    )

@router.message(ResourceFlow.mat_price)
async def mat_price_input(message: Message, state: FSMContext):
    """Ввод цены материала."""
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Попробуйте еще раз:")
            return
        
        await state.update_data(mat_price=price)
        await state.set_state(ResourceFlow.resource_comment)
        
        kb = InlineKeyboardBuilder()
        kb.button(text="⏭ Пропустить", callback_data="skip_comment")
        kb.button(text="❌ Отмена", callback_data="cancel_resource")
        kb.adjust(1, 1)
        
        await message.answer(
            "💬 <b>Комментарий к ресурсу</b> (опционально)\n\n"
            "Введите комментарий или нажмите «Пропустить»:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте еще раз:")

@router.callback_query(ResourceFlow.resource_comment, F.data == "skip_comment")
async def skip_resource_comment(cq: CallbackQuery, state: FSMContext):
    """Пропуск комментария к ресурсу."""
    await cq.answer()
    await state.update_data(resource_comment="")
    await _ask_resource_photos(cq.message, state)

@router.message(ResourceFlow.resource_comment)
async def resource_comment_input(message: Message, state: FSMContext):
    """Ввод комментария к ресурсу."""
    await state.update_data(resource_comment=message.text)
    await _ask_resource_photos(message, state)

async def _ask_resource_photos(message: Message, state: FSMContext):
    """Спросить о фото для ресурса."""
    await state.set_state(ResourceFlow.resource_photos)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📷 Добавить фото", callback_data="add_photos")
    kb.button(text="⏭ Пропустить", callback_data="skip_photos")
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(1, 1, 1)
    
    await message.answer(
        "📷 <b>Фото ресурса</b> (опционально)\n\n"
        "Вы можете добавить несколько фото. Отправьте фото или нажмите «Пропустить»:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(ResourceFlow.resource_photos, F.data == "skip_photos")
async def skip_resource_photos(cq: CallbackQuery, state: FSMContext):
    """Пропуск фото для ресурса."""
    await cq.answer()
    await state.update_data(resource_photos=[])
    await _show_resource_summary(cq.message, state)

@router.callback_query(ResourceFlow.resource_photos, F.data == "add_photos")
async def add_resource_photos_start(cq: CallbackQuery, state: FSMContext):
    """Начало добавления фото."""
    await cq.answer()
    await state.update_data(resource_photos=[])
    await cq.message.answer(
        "📷 Отправьте фото. Можно несколько. После отправки всех фото нажмите «Готово»:",
        reply_markup=None
    )

@router.message(ResourceFlow.resource_photos, F.photo)
async def resource_photo_received(message: Message, state: FSMContext):
    """Получено фото для ресурса."""
    data = await state.get_data()
    photos = data.get("resource_photos", [])
    photos.append(message)
    await state.update_data(resource_photos=photos)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data="photos_done")
    kb.button(text="📷 Добавить ещё", callback_data="add_photos")
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(1, 1, 1)
    
    await message.answer(
        f"✅ Фото добавлено ({len(photos)} шт.)\n\n"
        "Отправьте ещё фото или нажмите «Готово»:",
        reply_markup=kb.as_markup()
    )

@router.callback_query(ResourceFlow.resource_photos, F.data == "photos_done")
async def resource_photos_done(cq: CallbackQuery, state: FSMContext):
    """Завершение добавления фото."""
    await cq.answer()
    await _show_resource_summary(cq.message, state)

async def _show_resource_summary(message: Message, state: FSMContext):
    """Показывает сводку ресурса для подтверждения."""
    data = await state.get_data()
    
    # Форматируем сводку
    summary = format_resource_summary(data)
    
    # Добавляем информацию о комментарии и фото
    comment = data.get("resource_comment", "")
    photos_count = len(data.get("resource_photos", []))
    
    if comment:
        summary += f"\n\n💬 <b>Комментарий:</b> {comment}"
    if photos_count > 0:
        summary += f"\n📷 <b>Фото:</b> {photos_count} шт."
    
    # Создаем клавиатуру подтверждения
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm_resource")
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(1, 1)
    
    await state.set_state(ResourceFlow.confirm_resource)
    await message.answer(
        f"📋 <b>Сводка ресурса</b>\n\n{summary}\n\n"
        f"Подтвердите добавление ресурса:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(ResourceFlow.confirm_resource, F.data == "confirm_resource")
async def confirm_resource_add(cq: CallbackQuery, state: FSMContext):
    """Подтверждение добавления ресурса."""
    await cq.answer()
    
    try:
        data = await state.get_data()
        
        # Валидируем данные
        errors = validate_resource_data(data)
        if errors:
            await cq.message.answer(
                f"❌ <b>Ошибки валидации:</b>\n\n" + "\n".join(f"• {error}" for error in errors),
                parse_mode="HTML"
            )
            return
        
        # Получаем или создаем смену
        from datetime import date, timedelta
        shift_date = date.today() if data.get("date_key") == "today" else date.today() + timedelta(days=1)
        # ВАЖНО: Используем object_bitrix_id из FSM (это Bitrix ID объекта)
        object_bitrix_id = data.get("object_bitrix_id") or data.get("object_id")
        
        logger.info(f"[RESOURCE] Looking for shift: object_bitrix_id={object_bitrix_id}, date={shift_date}")
        
        if not object_bitrix_id:
            logger.error(f"[RESOURCE] object_bitrix_id not found in state data: {list(data.keys())}")
            await cq.message.answer(
                "❌ <b>Ошибка</b>\n\n"
                "Не найден ID объекта. Начните заново.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Получаем Bitrix ID смены (НЕ создаем новую, только ищем существующую)
        shift_bitrix_id, _ = await bitrix_get_shift_for_object_and_date(
            object_bitrix_id=object_bitrix_id,
            target_date=shift_date,
            create_if_not_exists=False,
        )
        
        if not shift_bitrix_id:
            logger.warning(f"[SHIFT] no shift found for resource object={object_bitrix_id} date={shift_date} – plan missing")
            await cq.message.answer(
                "❌ <b>Не найден план</b>\n\n"
                f"Не найдена смена с планом для объекта и даты.\n\n"
                "Сначала сформируйте <b>ПЛАН</b> для этого объекта.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        logger.info(f"[RESOURCE] Using shift_bitrix_id={shift_bitrix_id} for object_bitrix_id={object_bitrix_id}, date={shift_date}")
        
        # Добавляем shift_bitrix_id в данные (ВАЖНО: используем Bitrix ID, а не локальный!)
        data["shift_id"] = shift_bitrix_id
        
        # Логируем перед созданием ресурса
        resource_type = data.get("resource_type", "UNKNOWN")
        logger.info(f"[RESOURCE] Creating item: shift_bitrix_id={shift_bitrix_id}, object_bitrix_id={object_bitrix_id}, type={resource_type}")
        if resource_type == "EQUIP":
            logger.info(f"[RESOURCE] Equipment: type={data.get('equip_type')}, hours={data.get('equip_hours')}, rate={data.get('equip_rate')}")
        else:
            logger.info(f"[RESOURCE] Material: type={data.get('mat_type')}, qty={data.get('mat_qty')}, price={data.get('mat_price')}")
        
        # Создаем ресурс в Bitrix24
        result = await bitrix_add_resource(data)
        resource_id = result.get('result', {}).get('item', {}).get('id') if isinstance(result, dict) else None
        logger.info(f"[RESOURCE] Resource created successfully: resource_id={resource_id}, shift_bitrix_id={shift_bitrix_id}")
        
        # Загружаем комментарий и фото, если есть
        from app.services.bitrix_files import upload_photos_to_bitrix_field
        from app.bitrix_field_map import resolve_code, upper_to_camel
        from app.services.http_client import bx
        
        update_fields = {}
        
        # Комментарий
        comment = data.get("resource_comment", "").strip()
        if comment:
            f_comment = resolve_code("Ресурс", "UF_RES_COMMENT")
            update_fields[upper_to_camel(f_comment)] = comment
        
        # Обновляем комментарий, если есть
        if update_fields:
            await bx("crm.item.update", {
                "entityTypeId": 1056,  # ENTITY_RESOURCE
                "id": resource_id,
                "fields": update_fields
            })
        
        # Фото
        photos = data.get("resource_photos", [])
        if photos:
            await upload_photos_to_bitrix_field(
                bot=cq.bot,
                entity_type_id=1056,  # ENTITY_RESOURCE
                item_id=resource_id,
                field_logical_name="UF_RES_PHOTOS",
                entity_ru_name="Ресурс",
                photo_messages=photos
            )
        
        await cq.message.answer(
            f"✅ <b>Ресурс добавлен!</b>\n\n"
            f"ID в Bitrix24: {resource_id}\n\n"
            f"Возвращаемся в главное меню:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        
        await state.clear()
        logger.info(f"[RESOURCE] Resource added successfully: resource_id={resource_id}, shift_bitrix_id={shift_bitrix_id}")
        
    except Exception as e:
        logger.exception("[RESOURCE] error in confirm_resource_add")
        await cq.message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при добавлении ресурса. Попробуйте позже.",
            parse_mode="HTML"
        )
        await state.clear()

@router.callback_query(F.data == "cancel_resource")
async def cancel_resource_flow(cq: CallbackQuery, state: FSMContext):
    """Отмена добавления ресурса."""
    await cq.answer()
    await state.clear()
    
    await cq.message.answer(
        "❌ <b>Добавление ресурса отменено</b>\n\n"
        "Возвращаемся в главное меню:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )