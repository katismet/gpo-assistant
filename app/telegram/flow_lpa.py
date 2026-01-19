"""Flow для генерации ЛПА (Лист производственного анализа)."""

from aiogram import Router, F
from aiogram import types
from aiogram.types import CallbackQuery, Message, Document, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import logging

from app.services.objects import fetch_all_objects
from app.services.shift_repo import get_last_closed_shift
from app.services.lpa_data import collect_lpa_data
from app.services.lpa_pdf import LPAPlaceholderError
from app.telegram.objects_ui import page_kb
from app.services.shift_client import bitrix_update_shift_aggregates

router = Router()

# Настраиваем дополнительное логирование для тестирования
log = logging.getLogger("gpo.lpa")

PLACEHOLDER_ERROR_TEXT = (
    "❌ <b>Ошибка генерации ЛПА</b>\n\n"
    "Не удалось сформировать ЛПА. В шаблоне остались пустые поля.\n"
    "Передайте это сообщение разработчику."
)

GENERAL_ERROR_TEXT = (
    "❌ <b>Ошибка генерации ЛПА</b>\n\n"
    "Не удалось сгенерировать файл. Проверьте логи."
)


class LPAFlow(StatesGroup):
    """Состояния для генерации ЛПА."""
    select_object = State()
    select_shift = State()
    generate_pdf = State()


@router.callback_query(F.data == "act:lpa")
async def start_lpa(cq: CallbackQuery, state: FSMContext):
    """Начало генерации ЛПА."""
    await cq.answer()
    await state.clear()
    
    # Получаем список объектов
    objs = await fetch_all_objects()
    await state.update_data(objects_cache=objs, page=0)
    await state.set_state(LPAFlow.select_object)
    
    await cq.message.answer(
        "📄 <b>Генерация ЛПА (Лист производственного анализа)</b>\n\n"
        "Выберите объект для которого нужно сформировать ЛПА:",
        reply_markup=page_kb(objs, 0, "lpaobj"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("lpa_shift:"))
async def lpa_from_shift(cq: CallbackQuery, state: FSMContext):
    """Генерация ЛПА для конкретной смены из сводки."""
    await cq.answer("⏳ Загружаем данные смены...")
    
    try:
        shift_id = int(cq.data.split(":")[1])
        user_id = cq.from_user.id if cq.from_user else "unknown"
        logger.info(f"[LPA] User {user_id} requested LPA for shift {shift_id} from summary")
        log.info(f"[LPA] User {user_id} requested LPA for shift {shift_id} from summary")
        
        # Получаем данные смены из Bitrix24
        from app.services.http_client import bx
        from app.services.bitrix_ids import SHIFT_ETID, UF_OBJECT_LINK
        from app.bitrix_field_map import resolve_code, upper_to_camel
        from app.services.w6_alerts import _get_field_value
        
        # Получаем смену по ID
        shift_res = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id
        })
        
        # Правильно обрабатываем ответ от Bitrix24
        if not isinstance(shift_res, dict):
            await cq.message.answer("❌ Ошибка при получении данных смены из Bitrix24")
            logger.error(f"[LPA] shift_res is not a dict: {type(shift_res)}")
            return
        
        # Bitrix24 может вернуть результат в "item" или напрямую
        shift_item = shift_res.get("item", shift_res) if isinstance(shift_res, dict) else {}
        
        if not shift_item:
            await cq.message.answer("❌ Смена не найдена в Bitrix24")
            return
        
        # Извлекаем данные смены
        f_date = resolve_code("Смена", "UF_DATE")
        f_date_camel = upper_to_camel(f_date)
        f_plan_code = resolve_code("Смена", "UF_PLAN_TOTAL")
        f_fact_code = resolve_code("Смена", "UF_FACT_TOTAL")
        f_eff_code = resolve_code("Смена", "UF_EFF_FINAL")
        f_status_code = resolve_code("Смена", "UF_STATUS")
        f_status_camel = upper_to_camel(f_status_code)
        f_fact_camel = upper_to_camel(f_fact_code)
        f_plan_camel = upper_to_camel(f_plan_code)
        f_eff_camel = upper_to_camel(f_eff_code)
        
        plan_total = float(shift_item.get(f_plan_camel) or shift_item.get(f_plan_code) or 0)
        fact_total = float(shift_item.get(f_fact_camel) or shift_item.get(f_fact_code) or 0)
        eff_final = float(shift_item.get(f_eff_camel) or shift_item.get(f_eff_code) or 0)
        
        # Проверяем, есть ли фактические данные
        if not fact_total or fact_total == 0:
            await cq.message.answer(
                "❌ <b>Невозможно сгенерировать ЛПА</b>\n\n"
                f"Смена #{shift_id} не имеет фактических данных.\n"
                "Сначала создайте отчёт для этой смены.",
                parse_mode="HTML"
            )
            return
        
        # Получаем ID объекта
        obj_link = shift_item.get(UF_OBJECT_LINK)
        if not obj_link:
            await cq.message.answer("❌ Не удалось определить объект для смены")
            return
        
        # Извлекаем ID объекта
        if isinstance(obj_link, list) and len(obj_link) > 0:
            obj_str = obj_link[0]
        elif isinstance(obj_link, str):
            obj_str = obj_link
        else:
            await cq.message.answer("❌ Не удалось определить объект для смены")
            return
        
        try:
            if isinstance(obj_str, str) and obj_str.startswith("D_"):
                obj_id = int(obj_str[2:])
            else:
                obj_id = int(obj_str)
        except (ValueError, TypeError):
            await cq.message.answer("❌ Не удалось определить объект для смены")
            return
        
        # Получаем название объекта
        from app.services.objects import fetch_all_objects
        objs = await fetch_all_objects()
        obj_name = next((o.get("name", f"Объект #{obj_id}") for o in objs if o.get("id") == obj_id), f"Объект #{obj_id}")
        
        # Получаем дату смены
        shift_date_str = shift_item.get(f_date_camel) or shift_item.get(f_date)
        if shift_date_str:
            from datetime import datetime
            try:
                if isinstance(shift_date_str, str):
                    shift_date = datetime.fromisoformat(shift_date_str.replace("Z", "+00:00")).date()
                else:
                    shift_date = shift_date_str
                shift_date_formatted = shift_date.strftime("%d.%m.%Y")
            except:
                shift_date_formatted = "Не указана"
        else:
            shift_date_formatted = "Не указана"
        
        # Формируем данные для ЛПА
        shift_data = {
            "plan": {
                "plan_total": plan_total,
                "object_name": obj_name,
                "date": shift_date_formatted,
            },
            "fact": {"fact_total": fact_total},
            "efficiency": eff_final,
            "date": shift_date_formatted,
            "type": "day",
            "status": "closed"
        }
        
        await state.update_data(
            object_id=obj_id,
            shift_id=shift_id,
            shift_data=shift_data
        )
        await state.set_state(LPAFlow.generate_pdf)
        
        # Показываем информацию о смене и кнопку генерации
        efficiency = f"{eff_final:.1f}%" if eff_final else "Не рассчитана"
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text="📄 Сгенерировать ЛПА", callback_data="generate_lpa")
        kb.button(text="❌ Отмена", callback_data="cancel_lpa")
        kb.adjust(1, 1)
        
        await cq.message.answer(
            f"📄 <b>ЛПА для смены #{shift_id}</b>\n\n"
            f"<b>Объект:</b> {obj_name}\n"
            f"<b>Дата:</b> {shift_date_formatted}\n"
            f"<b>План:</b> {plan_total:.2f}\n"
            f"<b>Факт:</b> {fact_total:.2f}\n"
            f"<b>Эффективность:</b> {efficiency}\n\n"
            f"Нажмите кнопку для генерации ЛПА:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error generating LPA from shift {shift_id}: {e}", exc_info=True)
        log.error(f"[LPA] Error generating LPA from shift: {e}", exc_info=True)
        await cq.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("lpaobj:page:"))
async def lpa_obj_page(cq: CallbackQuery, state: FSMContext):
    """Пагинация объектов для ЛПА."""
    await cq.answer()
    page = int(cq.data.split(":")[-1])
    data = await state.get_data()
    objs = data.get("objects_cache", [])
    await cq.message.edit_reply_markup(reply_markup=page_kb(objs, page, "lpaobj"))
    await state.update_data(page=page)


@router.callback_query(F.data.startswith("lpaobj:") & ~F.data.contains(":page:"))
async def lpa_obj_pick(cq: CallbackQuery, state: FSMContext):
    """Выбор объекта для ЛПА."""
    await cq.answer()
    obj_id = int(cq.data.split(":")[1])
    
    # Логируем начало поиска
    user_id = cq.from_user.id if cq.from_user else "unknown"
    logger.info(f"[LPA] User {user_id} selected object {obj_id} for LPA generation")
    log.info(f"[LPA] User {user_id} selected object {obj_id} for LPA generation")
    
    # ПРИОРИТЕТ: Сначала ищем закрытую смену в локальной БД (там есть детальные данные из чата)
    from datetime import date, timedelta
    from app.services.http_client import bx
    from app.services.bitrix_ids import SHIFT_ETID, UF_OBJECT_LINK, UF_STATUS
    from app.bitrix_field_map import resolve_code, upper_to_camel
    from app.services.w6_alerts import _get_field_value
    # get_last_closed_shift уже импортирован в начале файла
    
    shift_data = None
    shift_id = None
    bitrix_shift_id = None
    
    # СНАЧАЛА ищем в локальной БД - там есть детальные данные из чата
    logger.info(f"[LPA] ===== START: Searching for closed shift in LOCAL DB for object {obj_id} =====")
    log.info(f"[LPA] ===== START: Searching for closed shift in LOCAL DB for object {obj_id} =====")
    print(f"[LPA] Ищем закрытую смену для объекта {obj_id} в локальной БД...")
    result = get_last_closed_shift(obj_id)
    if result:
        shift_id, shift_data = result
        logger.info(f"✅ Found closed shift in LOCAL DB: {shift_id}")
        log.info(f"[LPA] ✅ Found closed shift in LOCAL DB: {shift_id}")
        print(f"[LPA] ✅ Найдена закрытая смена в локальной БД: shift_id={shift_id}")
        
        plan_data_check = shift_data.get('plan', {}) if isinstance(shift_data, dict) else {}
        fact_data_check = shift_data.get('fact', {}) if isinstance(shift_data, dict) else {}
        
        # Проверяем тип перед вызовом .keys()
        if isinstance(plan_data_check, dict):
            logger.info(f"[LPA] plan_data keys: {list(plan_data_check.keys())}")
            logger.info(f"[LPA] plan_data sample: {dict(list(plan_data_check.items())[:10])}")
            print(f"[LPA] План: {list(plan_data_check.keys())[:5]}...")
        else:
            logger.info(f"[LPA] plan_data type: {type(plan_data_check)}, value: {plan_data_check}")
            print(f"[LPA] План: {type(plan_data_check)}")
        
        if isinstance(fact_data_check, dict):
            logger.info(f"[LPA] fact_data keys: {list(fact_data_check.keys())}")
            logger.info(f"[LPA] fact_data sample: {dict(list(fact_data_check.items())[:10])}")
            print(f"[LPA] Факт: {list(fact_data_check.keys())[:5]}...")
        else:
            logger.info(f"[LPA] fact_data type: {type(fact_data_check)}, value: {fact_data_check}")
            print(f"[LPA] Факт: {type(fact_data_check)}")
        
        # Получаем bitrix_id для загрузки фото и проверки данных в Bitrix24
        from app.db import session_scope
        from app.models import Shift
        bitrix_shift_id = None
        try:
            with session_scope() as s:
                sh = s.get(Shift, shift_id)
                if sh and sh.bitrix_id:
                    bitrix_shift_id = sh.bitrix_id
                    logger.info(f"[LPA] Got bitrix_id={bitrix_shift_id} for local shift {shift_id}")
        except Exception as e:
            logger.warning(f"[LPA] Could not get bitrix_id: {e}")
        
        # Проверяем, есть ли работы в плане из локальной БД
        # Список служебных полей
        service_fields = ["object_name", "date", "section", "foreman", "shift_type", "type", "plan_total"]
        if isinstance(plan_data_check, dict):
            plan_works = {k: v for k, v in plan_data_check.items() if k not in service_fields and isinstance(v, (int, float)) and v != 0}
        else:
            plan_works = {}
        
        logger.info(f"[LPA] Plan works from local DB: {list(plan_works.keys())}")
        log.info(f"[LPA] Plan works from local DB: {list(plan_works.keys())}")
        
        # ВСЕГДА пробуем получить данные из Bitrix24 для объединения (даже если есть в локальной БД)
        if bitrix_shift_id:
            logger.info(f"[LPA] Trying to get/merge data from Bitrix24 (shift {bitrix_shift_id})")
            log.info(f"[LPA] Trying to get/merge data from Bitrix24 (shift {bitrix_shift_id})")
            
            try:
                import json
                from app.services.http_client import bx
                from app.services.bitrix_ids import SHIFT_ETID
                
                # Получаем смену из Bitrix24
                shift_res = await bx("crm.item.get", {
                    "entityTypeId": SHIFT_ETID,
                    "id": bitrix_shift_id
                })
                
                # Правильно обрабатываем ответ от Bitrix24
                if not isinstance(shift_res, dict):
                    logger.warning(f"[LPA] shift_res is not a dict: {type(shift_res)}")
                    raise ValueError(f"Unexpected response type from Bitrix24: {type(shift_res)}")
                
                # Bitrix24 может вернуть результат в "item" или напрямую
                item = shift_res.get("item", shift_res) if isinstance(shift_res, dict) else {}
                
                # Пробуем получить JSON из Bitrix24
                f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
                f_fact_json = resolve_code("Смена", "UF_FACT_JSON")
                
                plan_json_str = None
                fact_json_str = None
                
                if f_plan_json:
                    f_plan_json_camel = upper_to_camel(f_plan_json)
                    plan_json_str = item.get(f_plan_json_camel) or item.get(f_plan_json)
                
                if f_fact_json:
                    f_fact_json_camel = upper_to_camel(f_fact_json)
                    fact_json_str = item.get(f_fact_json_camel) or item.get(f_fact_json)
                
                # Парсим JSON, если есть
                plan_data_from_json = {}
                fact_data_from_json = {}
                
                if plan_json_str:
                    try:
                        plan_data_from_json = json.loads(plan_json_str) if isinstance(plan_json_str, str) else plan_json_str
                        logger.info(f"[LPA] ✅ Loaded plan_json from Bitrix24: {len(plan_data_from_json)} items, keys: {list(plan_data_from_json.keys())}")
                        log.info(f"[LPA] ✅ Loaded plan_json from Bitrix24: {len(plan_data_from_json)} items, keys: {list(plan_data_from_json.keys())}")
                    except Exception as e:
                        logger.warning(f"[LPA] Could not parse plan_json from Bitrix24: {e}")
                
                if fact_json_str:
                    try:
                        fact_data_from_json = json.loads(fact_json_str) if isinstance(fact_json_str, str) else fact_json_str
                        logger.info(f"[LPA] ✅ Loaded fact_json from Bitrix24: {len(fact_data_from_json)} items, keys: {list(fact_data_from_json.keys())}")
                        log.info(f"[LPA] ✅ Loaded fact_json from Bitrix24: {len(fact_data_from_json)} items, keys: {list(fact_data_from_json.keys())}")
                    except Exception as e:
                        logger.warning(f"[LPA] Could not parse fact_json from Bitrix24: {e}")
                
                # ОБЪЕДИНЯЕМ данные: локальная БД + Bitrix24
                # Получаем актуальное название объекта
                from app.services.objects import fetch_all_objects
                objs = await fetch_all_objects()
                # Проверяем, что objs - это список
                if not isinstance(objs, list):
                    logger.warning(f"[LPA] objs is not a list: {type(objs)}")
                    objs = []
                obj_name_current = next((o.get("name", f"Объект #{obj_id}") for o in objs if isinstance(o, dict) and o.get("id") == obj_id), f"Объект #{obj_id}")
                
                # Объединяем план: сначала локальная БД, потом Bitrix24 (Bitrix24 имеет приоритет для работ)
                plan_merged = plan_data_check.copy()  # Начинаем с локальных данных
                
                # Удаляем служебные поля из plan_data_from_json перед объединением
                # Проверяем, что plan_data_from_json - это словарь
                if isinstance(plan_data_from_json, dict):
                    plan_data_clean = {k: v for k, v in plan_data_from_json.items() if k != "object_name"}
                    
                    # Объединяем: работы из Bitrix24 перезаписывают локальные (если есть)
                    for k, v in plan_data_clean.items():
                        if k not in service_fields:  # Только работы, не служебные поля
                            plan_merged[k] = v
                    
                    # Обновляем shift_data с объединенными данными
                    shift_data["plan"] = {
                        **plan_merged,
                        "object_name": obj_name_current,  # Всегда актуальное название
                        "date": plan_data_check.get("date") or plan_data_from_json.get("date"),
                        "section": plan_data_check.get("section") or plan_data_from_json.get("section", "Не указан"),
                        "foreman": plan_data_check.get("foreman") or plan_data_from_json.get("foreman", "Не указан"),
                    }
                else:
                    # Если plan_data_from_json не словарь, используем только локальные данные
                    logger.warning(f"[LPA] plan_data_from_json is not a dict: {type(plan_data_from_json)}")
                    shift_data["plan"] = {
                        **plan_merged,
                        "object_name": obj_name_current,
                        "date": plan_data_check.get("date"),
                        "section": plan_data_check.get("section", "Не указан"),
                        "foreman": plan_data_check.get("foreman", "Не указан"),
                    }
                
                logger.info(f"[LPA] ✅ Merged plan_data: {list(shift_data['plan'].keys())}")
                log.info(f"[LPA] ✅ Merged plan_data keys: {list(shift_data['plan'].keys())}")
                
                # Объединяем факт: Bitrix24 имеет приоритет
                if fact_data_from_json:
                    shift_data["fact"] = fact_data_from_json
                    logger.info(f"[LPA] ✅ Updated fact_data from Bitrix24")
                    log.info(f"[LPA] ✅ Updated fact_data from Bitrix24")
                elif not fact_data_check:
                    # Если нет факта ни в локальной БД, ни в Bitrix24, оставляем пустым
                    shift_data["fact"] = {}
                
            except Exception as e:
                logger.warning(f"[LPA] Could not get data from Bitrix24: {e}")
                log.warning(f"[LPA] Could not get data from Bitrix24: {e}")
    
    # Если не нашли в локальной БД, тогда ищем в Bitrix24
    
    # Если не нашли в локальной БД, ищем в Bitrix24 (но там только итоговые данные)
    if not shift_data:
        logger.info(f"[LPA] Not found in local DB, searching in Bitrix24...")
        log.info(f"[LPA] Not found in local DB, searching in Bitrix24...")
        
        # Ищем смены с фактическими данными в Bitrix24 за последние 60 дней
        today = date.today()
        
        logger.info(f"[LPA] ===== Searching for closed shifts with fact data for object {obj_id} in Bitrix24 (last 60 days) =====")
        log.info(f"[LPA] ===== Searching for closed shifts with fact data for object {obj_id} in Bitrix24 (last 60 days) =====")
        print(f"[LPA] ===== Searching for closed shifts in Bitrix24 for object {obj_id} =====")
        
        try:
            logger.info(f"[LPA] Inside try block, starting Bitrix24 search")
            log.info(f"[LPA] Inside try block, starting Bitrix24 search")
            
            # Получаем коды полей один раз
            f_date = resolve_code("Смена", "UF_DATE")
            f_date_camel = upper_to_camel(f_date)
            f_plan_code = resolve_code("Смена", "UF_PLAN_TOTAL")
            f_fact_code = resolve_code("Смена", "UF_FACT_TOTAL")
            f_eff_code = resolve_code("Смена", "UF_EFF_FINAL")
            f_status_code = resolve_code("Смена", "UF_STATUS")
            f_status_camel = upper_to_camel(f_status_code)
            f_fact_camel = upper_to_camel(f_fact_code)
            f_plan_camel = upper_to_camel(f_plan_code)
            f_eff_camel = upper_to_camel(f_eff_code)
            
            # СНАЧАЛА пробуем найти смены напрямую по объекту (более эффективно)
            # Ищем смены с привязкой к объекту за последние 60 дней
            logger.info(f"[LPA] Trying direct search by object {obj_id} in Bitrix24")
            log.info(f"[LPA] Trying direct search by object {obj_id} in Bitrix24")
            
            # Формируем фильтр по объекту (пробуем разные форматы)
            obj_filter_values = [
                f"D_{obj_id}",  # Формат "D_1046"
                str(obj_id),    # Просто число
            ]
            
            # Пробуем найти смены напрямую по объекту (используем фильтр)
            try:
                # Пробуем использовать фильтр по объекту напрямую
                # Bitrix24 может требовать формат "D_1046" для фильтрации
                obj_filter_value = f"D_{obj_id}"
                
                # Пробуем найти смены с фильтром по объекту
                shifts_res = await bx("crm.item.list", {
                    "entityTypeId": SHIFT_ETID,
                    "filter": {
                        UF_OBJECT_LINK: obj_filter_value
                    },
                    "select": ["id", f_date_camel, UF_OBJECT_LINK, f_status_camel, f_plan_camel, f_fact_camel, f_eff_camel, "*"],
                    "order": {"id": "desc"},
                    "limit": 200
                })
                
                items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
                
                # Если фильтр сработал и нашли смены, считаем что они уже отфильтрованы
                if items:
                    logger.info(f"[LPA] Found {len(items)} shifts for object {obj_id} using filter")
                    log.info(f"[LPA] Found {len(items)} shifts for object {obj_id} using filter")
                    matching_items = items  # Уже отфильтрованы Bitrix24
                else:
                    # Если фильтр не сработал, пробуем без фильтра (старый метод)
                    logger.info(f"[LPA] Filter by object didn't work, trying without filter")
                    log.info(f"[LPA] Filter by object didn't work, trying without filter")
                    shifts_res = await bx("crm.item.list", {
                        "entityTypeId": SHIFT_ETID,
                        "select": ["id", f_date_camel, UF_OBJECT_LINK, f_status_camel, f_plan_camel, f_fact_camel, f_eff_camel, "*"],
                        "order": {"id": "desc"},
                        "limit": 200  # Увеличиваем лимит для поиска по объекту
                    })
                    
                    items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
                    logger.info(f"[LPA] Found {len(items)} total shifts in Bitrix24, filtering by object {obj_id}")
                    log.info(f"[LPA] Found {len(items)} total shifts in Bitrix24, filtering by object {obj_id}")
                    
                    # Фильтруем по объекту вручную
                    matching_items = []
                    logger.info(f"[LPA] Filtering {len(items)} shifts by object {obj_id}")
                    log.info(f"[LPA] Filtering {len(items)} shifts by object {obj_id}")
                    
                    for idx, item in enumerate(items):
                        shift_id_item = item.get("id", "unknown")
                        obj_link = item.get(UF_OBJECT_LINK)
                        
                        if idx < 5:  # Логируем первые 5 смен для диагностики
                            logger.info(f"[LPA] Shift {shift_id_item}: UF_OBJECT_LINK = {obj_link} (type: {type(obj_link).__name__})")
                            log.info(f"[LPA] Shift {shift_id_item}: UF_OBJECT_LINK = {obj_link} (type: {type(obj_link).__name__})")
                        
                        if not obj_link:
                            if idx < 5:
                                logger.debug(f"[LPA] Shift {shift_id_item}: no UF_OBJECT_LINK, skipping")
                            continue
                        
                        # Bitrix24 может возвращать "Array" как строку, если поле множественное
                        # Пробуем получить реальное значение через другие поля или методы
                        obj_str = None
                        
                        # Пробуем разные варианты получения привязки
                        if isinstance(obj_link, list) and len(obj_link) > 0:
                            obj_str = obj_link[0]
                            if idx < 5:
                                logger.info(f"[LPA] Shift {shift_id_item}: obj_link is list, first element: {obj_str}")
                        elif isinstance(obj_link, str):
                            # Если это строка "Array", значит Bitrix24 вернул массив как строку
                            # Пробуем получить через camelCase версию поля
                            obj_link_camel = item.get(upper_to_camel(UF_OBJECT_LINK))
                            if obj_link_camel and isinstance(obj_link_camel, list) and len(obj_link_camel) > 0:
                                obj_str = obj_link_camel[0]
                                if idx < 5:
                                    logger.info(f"[LPA] Shift {shift_id_item}: got obj from camelCase list: {obj_str}")
                            elif obj_link_camel and isinstance(obj_link_camel, str) and obj_link_camel != "Array":
                                obj_str = obj_link_camel
                                if idx < 5:
                                    logger.info(f"[LPA] Shift {shift_id_item}: got obj from camelCase str: {obj_str}")
                            elif obj_link != "Array":
                                obj_str = obj_link
                                if idx < 5:
                                    logger.info(f"[LPA] Shift {shift_id_item}: using obj_link directly: {obj_str}")
                        
                        if not obj_str or obj_str == "Array":
                            # Пробуем получить через все возможные варианты имени поля
                            for field_name in [UF_OBJECT_LINK, upper_to_camel(UF_OBJECT_LINK), "ufCrm7UfCrmObject"]:
                                field_value = item.get(field_name)
                                if field_value:
                                    if isinstance(field_value, list) and len(field_value) > 0:
                                        obj_str = field_value[0]
                                        if idx < 5:
                                            logger.info(f"[LPA] Shift {shift_id_item}: got obj from field {field_name} (list): {obj_str}")
                                        break
                                    elif isinstance(field_value, str) and field_value != "Array":
                                        obj_str = field_value
                                        if idx < 5:
                                            logger.info(f"[LPA] Shift {shift_id_item}: got obj from field {field_name} (str): {obj_str}")
                                        break
                        
                        if not obj_str or obj_str == "Array":
                            if idx < 5:
                                logger.warning(f"[LPA] Shift {shift_id_item}: could not extract object ID, obj_str={obj_str}")
                            continue
                        
                        # Парсим ID объекта
                        try:
                            if isinstance(obj_str, str) and obj_str.startswith("D_"):
                                obj_id_from_bitrix = int(obj_str[2:])
                            else:
                                obj_id_from_bitrix = int(obj_str)
                            
                            if idx < 5:
                                logger.info(f"[LPA] Shift {shift_id_item}: parsed object ID = {obj_id_from_bitrix}, looking for {obj_id}")
                            
                            if obj_id_from_bitrix == obj_id:
                                matching_items.append(item)
                                logger.info(f"[LPA] ✅ Match found: shift {shift_id_item} -> object {obj_id_from_bitrix}")
                                log.info(f"[LPA] ✅ Match found: shift {shift_id_item} -> object {obj_id_from_bitrix}")
                        except (ValueError, TypeError) as e:
                            if idx < 5:
                                logger.warning(f"[LPA] Shift {shift_id_item}: Could not parse object ID from '{obj_str}': {e}")
                            continue
                    
                    logger.info(f"[LPA] Found {len(matching_items)} shifts for object {obj_id} in Bitrix24")
                    log.info(f"[LPA] Found {len(matching_items)} shifts for object {obj_id} in Bitrix24")
                    
                    # Если нашли смены по объекту, обрабатываем их
                    if matching_items:
                        items = matching_items
                        logger.info(f"[LPA] Processing {len(items)} shifts found by direct object filter")
                        log.info(f"[LPA] Processing {len(items)} shifts found by direct object filter")
                        
                        # Обрабатываем найденные смены
                        for item in items:
                            bitrix_shift_id = item.get("id")
                            if not bitrix_shift_id:
                                continue
                            
                            # Читаем значения полей
                            plan_total = float(item.get(f_plan_camel) or item.get(f_plan_code) or item.get("ufCrm7UfCrmPlanTotal") or 0)
                            fact_total = float(item.get(f_fact_camel) or item.get(f_fact_code) or item.get("ufCrm7UfCrmFactTotal") or 0)
                            eff_final = float(item.get(f_eff_camel) or item.get(f_eff_code) or item.get("ufCrm7UfCrmEffFinal") or 0)
                            
                            # Проверяем статус смены
                            item_status = ""
                            try:
                                item_status = _get_field_value(item, f_status_camel) or _get_field_value(item, f_status_code) or ""
                                if isinstance(item_status, str):
                                    item_status = item_status.lower().strip()
                            except Exception as e:
                                logger.debug(f"Could not get status for shift {bitrix_shift_id}: {e}")
                                item_status = ""
                            
                            logger.info(f"Shift {bitrix_shift_id}: obj={obj_id}, plan={plan_total}, fact={fact_total}, eff={eff_final}, status='{item_status}'")
                            log.info(f"[LPA] Shift {bitrix_shift_id}: obj={obj_id}, plan={plan_total}, fact={fact_total}, eff={eff_final}, status='{item_status}'")
                            
                            # Пропускаем смены без фактических данных
                            if not fact_total or fact_total == 0:
                                logger.debug(f"Skipping shift {bitrix_shift_id} - no fact data (fact_total={fact_total})")
                                log.debug(f"[LPA] Skipping shift {bitrix_shift_id} - no fact data (fact_total={fact_total})")
                                continue
                            
                            # Проверяем, закрыта ли смена
                            is_closed = (
                                item_status in ("closed", "закрыта", "закрыто") or
                                not item_status or
                                item_status == "" or
                                (item_status != "open" and fact_total > 0)
                            )
                            
                            if not is_closed:
                                logger.info(f"Skipping shift {bitrix_shift_id} - not closed (status='{item_status}', fact={fact_total})")
                                log.info(f"[LPA] Skipping shift {bitrix_shift_id} - not closed (status='{item_status}', fact={fact_total})")
                                continue
                            
                            # Нашли закрытую смену!
                            logger.info(f"✅ Found closed shift in Bitrix24: {bitrix_shift_id} for object {obj_id} (fact={fact_total}, status='{item_status}')")
                            log.info(f"[LPA] ✅ Found closed shift in Bitrix24: {bitrix_shift_id} for object {obj_id} (fact={fact_total}, status='{item_status}')")
                            print(f"[LPA] ✅ Found closed shift: {bitrix_shift_id} for object {obj_id} (fact={fact_total}, status='{item_status}')")
                            
                            # Получаем дату смены
                            shift_date_str = item.get(f_date_camel) or item.get(f_date)
                            if shift_date_str:
                                try:
                                    from datetime import datetime
                                    if isinstance(shift_date_str, str):
                                        shift_date_obj = datetime.fromisoformat(shift_date_str.replace("Z", "+00:00")).date()
                                    else:
                                        shift_date_obj = shift_date_str
                                    shift_date = shift_date_obj.strftime("%d.%m.%Y")
                                except:
                                    shift_date = "Не указана"
                            else:
                                shift_date = "Не указана"
                            
                            # Получаем название объекта
                            from app.services.objects import fetch_all_objects
                            objs = await fetch_all_objects()
                            # objs это список кортежей (id, title)
                            obj_name = next((title for oid, title in objs if oid == obj_id), f"Объект #{obj_id}")
                            
                            # Пытаемся получить детальные данные из локальной БД
                            from app.services.shift_repo import get_shift_by_bitrix_id
                            from app.db import session_scope
                            from app.models import Shift
                            local_shift = get_shift_by_bitrix_id(bitrix_shift_id)
                            
                            if local_shift:
                                # Если нашли в локальной БД, получаем полные данные
                                local_shift_id, _ = local_shift
                                # Получаем данные через get_last_closed_shift, но нужно проверить объект
                                with session_scope() as s:
                                    from app.models import Shift
                                    sh = s.get(Shift, local_shift_id)
                                    if sh and sh.object_id == obj_id:
                                        # Получаем полные данные
                                        object_name_local = sh.object.name if sh.object else obj_name
                                        formatted_date_local = sh.date.strftime("%d.%m.%Y") if sh.date else shift_date
                                        plan_data_full = sh.plan_json or {}
                                        fact_data_full = sh.fact_json or {}
                                        
                                        shift_data = {
                                            "plan": {
                                                **plan_data_full,
                                                "object_name": object_name_local,
                                                "date": formatted_date_local,
                                                "section": plan_data_full.get("section", "Не указан"),
                                                "foreman": plan_data_full.get("foreman", "Не указан"),
                                                "shift_type": sh.type.value if sh.type else "day"
                                            },
                                            "fact": fact_data_full,
                                            "efficiency": sh.eff_final or eff_final,
                                            "date": formatted_date_local,
                                            "type": sh.type.value if sh.type else "day",
                                            "status": sh.status.value if sh.status else "closed"
                                        }
                                        shift_id = local_shift_id
                                        logger.info(f"[LPA] ✅ Got detailed data from local DB for shift {bitrix_shift_id} -> local {local_shift_id}")
                                        log.info(f"[LPA] ✅ Got detailed data from local DB for shift {bitrix_shift_id} -> local {local_shift_id}")
                                    else:
                                        # Объект не совпадает, используем данные из Bitrix24
                                        shift_data = {
                                            "plan": {
                                                "plan_total": plan_total,
                                                "object_name": obj_name,  # Используем актуальное название из выбранного объекта
                                                "date": shift_date,
                                            },
                                            "fact": {"fact_total": fact_total},
                                            "efficiency": eff_final,
                                            "date": shift_date,
                                            "type": "day",
                                            "status": item_status if item_status else "closed"
                                        }
                                        shift_id = bitrix_shift_id
                            else:
                                # Не нашли в локальной БД, пробуем получить детальные данные из Bitrix24 (JSON)
                                logger.info(f"[LPA] Shift {bitrix_shift_id} not found in local DB, trying to get JSON from Bitrix24")
                                log.info(f"[LPA] Shift {bitrix_shift_id} not found in local DB, trying to get JSON from Bitrix24")
                                
                                # Пробуем получить JSON из Bitrix24
                                import json
                                f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
                                f_fact_json = resolve_code("Смена", "UF_FACT_JSON")
                                
                                plan_json_str = None
                                fact_json_str = None
                                
                                if f_plan_json:
                                    f_plan_json_camel = upper_to_camel(f_plan_json)
                                    plan_json_str = item.get(f_plan_json_camel) or item.get(f_plan_json)
                                
                                if f_fact_json:
                                    f_fact_json_camel = upper_to_camel(f_fact_json)
                                    fact_json_str = item.get(f_fact_json_camel) or item.get(f_fact_json)
                                
                                # Парсим JSON, если есть
                                plan_data_from_json = {}
                                fact_data_from_json = {}
                                
                                if plan_json_str:
                                    try:
                                        plan_data_from_json = json.loads(plan_json_str) if isinstance(plan_json_str, str) else plan_json_str
                                        logger.info(f"[LPA] ✅ Loaded plan_json from Bitrix24: {len(plan_data_from_json)} items")
                                        log.info(f"[LPA] ✅ Loaded plan_json from Bitrix24: {len(plan_data_from_json)} items")
                                    except Exception as e:
                                        logger.warning(f"[LPA] Could not parse plan_json from Bitrix24: {e}")
                                
                                if fact_json_str:
                                    try:
                                        fact_data_from_json = json.loads(fact_json_str) if isinstance(fact_json_str, str) else fact_json_str
                                        logger.info(f"[LPA] ✅ Loaded fact_json from Bitrix24: {len(fact_data_from_json)} items")
                                        log.info(f"[LPA] ✅ Loaded fact_json from Bitrix24: {len(fact_data_from_json)} items")
                                    except Exception as e:
                                        logger.warning(f"[LPA] Could not parse fact_json from Bitrix24: {e}")
                                
                                # Используем данные из JSON, если они есть, иначе только итоговые значения
                                if plan_data_from_json or fact_data_from_json:
                                    shift_data = {
                                        "plan": {
                                            **plan_data_from_json,
                                            "object_name": obj_name,  # Всегда используем актуальное название из выбранного объекта
                                            "date": plan_data_from_json.get("date") or shift_date,
                                            "section": plan_data_from_json.get("section", "Не указан"),
                                            "foreman": plan_data_from_json.get("foreman", "Не указан"),
                                            "shift_type": plan_data_from_json.get("shift_type", "day")
                                        },
                                        "fact": fact_data_from_json if fact_data_from_json else {"fact_total": fact_total},
                                        "efficiency": eff_final,
                                        "date": plan_data_from_json.get("date") or shift_date,
                                        "type": "day",
                                        "status": item_status if item_status else "closed"
                                    }
                                    logger.info(f"[LPA] ✅ Using detailed data from Bitrix24 JSON fields")
                                    log.info(f"[LPA] ✅ Using detailed data from Bitrix24 JSON fields")
                                else:
                                    # Используем только итоговые данные из Bitrix24
                                    logger.warning(f"[LPA] Shift {bitrix_shift_id} not found in local DB and no JSON in Bitrix24, using summary data only")
                                    log.warning(f"[LPA] Shift {bitrix_shift_id} not found in local DB and no JSON in Bitrix24, using summary data only")
                                    shift_data = {
                                        "plan": {
                                            "plan_total": plan_total,
                                            "object_name": obj_name,
                                            "date": shift_date,
                                        },
                                        "fact": {"fact_total": fact_total},
                                        "efficiency": eff_final,
                                        "date": shift_date,
                                        "type": "day",
                                        "status": item_status if item_status else "closed"
                                    }
                                shift_id = bitrix_shift_id
                            break  # Нашли смену, выходим из цикла for item in items
                    else:
                        # Если не нашли напрямую, используем старый метод - поиск по дням
                        logger.info(f"[LPA] No shifts found by direct object filter, trying day-by-day search")
                        log.info(f"[LPA] No shifts found by direct object filter, trying day-by-day search")
                        items = []
            
            except Exception as e:
                logger.error(f"Error in direct object search: {e}", exc_info=True)
                log.error(f"[LPA] Error in direct object search: {e}", exc_info=True)
                items = []
            
            # Если не нашли напрямую, используем поиск по дням (старый метод)
            if not shift_data:
                logger.info(f"[LPA] Using day-by-day search for object {obj_id}")
                log.info(f"[LPA] Using day-by-day search for object {obj_id}")
                
                # ВАЖНО: Если поле UF_OBJECT_LINK пустое в старых сменах, 
            # ищем смены с fact_total > 0 БЕЗ фильтрации по объекту,
            # а затем проверяем объект через локальную БД или другие методы
            logger.info(f"[LPA] Starting day-by-day search (will check object via local DB if UF_OBJECT_LINK is empty)")
            log.info(f"[LPA] Starting day-by-day search (will check object via local DB if UF_OBJECT_LINK is empty)")
            
            # Увеличиваем диапазон поиска до 60 дней
            for days_ago in range(60):
                check_date = today - timedelta(days=days_ago)
                day_from = check_date.isoformat() + "T00:00:00"
                day_to = check_date.isoformat() + "T23:59:59"
                
                # Ищем все смены за день
                try:
                    shifts_res = await bx("crm.item.list", {
                        "entityTypeId": SHIFT_ETID,
                        "filter": {
                            f">={f_date_camel}": day_from,
                            f"<={f_date_camel}": day_to,
                        },
                        "select": ["id", f_date_camel, UF_OBJECT_LINK, f_status_camel, f_plan_camel, f_fact_camel, f_eff_camel, "*"],
                        "order": {"id": "desc"},
                        "limit": 100  # Увеличиваем лимит
                    })
                    
                    items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
                    items_count = len(items)
                    logger.info(f"[LPA] Found {items_count} shifts for {check_date}")
                    log.info(f"[LPA] Found {items_count} shifts for {check_date}")
                    
                    if items_count == 0:
                        continue  # Пропускаем дни без смен
                except Exception as e:
                    logger.error(f"Error fetching shifts for {check_date}: {e}", exc_info=True)
                    continue
                
                logger.debug(f"Processing {len(items)} shifts for {check_date}, looking for object {obj_id}")
                
                # Обрабатываем найденные смены
                for item in items:
                    bitrix_shift_id = item.get("id")
                    if not bitrix_shift_id:
                        continue
                    
                    # Если использовали поиск по дням, проверяем объект
                    if 'check_date' in locals():  # Значит использовали поиск по дням
                        obj_link = item.get(UF_OBJECT_LINK)
                        
                        # Если Bitrix24 вернул "Array" как строку, получаем реальное значение через crm.item.get
                        if obj_link == "Array" or (isinstance(obj_link, str) and obj_link == "Array"):
                            try:
                                # Получаем полные данные смены через crm.item.get
                                shift_full = await bx("crm.item.get", {
                                    "entityTypeId": SHIFT_ETID,
                                    "id": bitrix_shift_id
                                })
                                # Правильно обрабатываем ответ от Bitrix24
                                if isinstance(shift_full, dict):
                                    shift_item_full = shift_full.get("item", shift_full)
                                    # Пробуем получить через разные варианты имени поля
                                    obj_link = shift_item_full.get(UF_OBJECT_LINK) or shift_item_full.get(upper_to_camel(UF_OBJECT_LINK)) or shift_item_full.get("ufCrm7UfCrmObject")
                                    logger.info(f"[LPA] Day search: Shift {bitrix_shift_id} - got real UF_OBJECT_LINK via crm.item.get: {obj_link}")
                                    log.info(f"[LPA] Day search: Shift {bitrix_shift_id} - got real UF_OBJECT_LINK via crm.item.get: {obj_link}")
                                else:
                                    obj_link = None
                            except Exception as e:
                                logger.warning(f"[LPA] Day search: Shift {bitrix_shift_id} - failed to get via crm.item.get: {e}")
                                obj_link = None
                        
                        # Логируем первые несколько смен для диагностики
                        item_idx = items.index(item) if item in items else -1
                        if item_idx < 3:
                            logger.info(f"[LPA] Day search: Shift {bitrix_shift_id}, UF_OBJECT_LINK={obj_link} (type: {type(obj_link).__name__})")
                            log.info(f"[LPA] Day search: Shift {bitrix_shift_id}, UF_OBJECT_LINK={obj_link} (type: {type(obj_link).__name__})")
                        
                        obj_id_from_bitrix = None
                        
                        if obj_link:
                            # Извлекаем ID объекта (с обработкой "Array")
                            obj_str = None
                            if isinstance(obj_link, list) and len(obj_link) > 0:
                                obj_str = obj_link[0]
                            elif isinstance(obj_link, str) and obj_link != "Array":
                                obj_str = obj_link
                            else:
                                # Пробуем через camelCase
                                obj_link_camel = item.get(upper_to_camel(UF_OBJECT_LINK))
                                if obj_link_camel:
                                    if isinstance(obj_link_camel, list) and len(obj_link_camel) > 0:
                                        obj_str = obj_link_camel[0]
                                    elif isinstance(obj_link_camel, str) and obj_link_camel != "Array":
                                        obj_str = obj_link_camel
                            
                            if obj_str and obj_str != "Array":
                                # Парсим ID объекта
                                try:
                                    if isinstance(obj_str, str) and obj_str.startswith("D_"):
                                        obj_id_from_bitrix = int(obj_str[2:])
                                    else:
                                        obj_id_from_bitrix = int(obj_str)
                                    
                                    if item_idx < 3:
                                        logger.info(f"[LPA] Day search: Shift {bitrix_shift_id} - parsed object ID={obj_id_from_bitrix}, looking for {obj_id}")
                                except (ValueError, TypeError) as e:
                                    if item_idx < 3:
                                        logger.warning(f"[LPA] Day search: Shift {bitrix_shift_id} - Could not parse object ID from {obj_str}: {e}")
                        
                        # Если не удалось получить объект из Bitrix24, пробуем через локальную БД
                        if not obj_id_from_bitrix:
                            try:
                                from app.services.shift_repo import get_shift_by_bitrix_id
                                local_shift = get_shift_by_bitrix_id(bitrix_shift_id)
                                if local_shift:
                                    obj_id_from_bitrix = local_shift[1].get("object_id") if isinstance(local_shift[1], dict) else None
                                    if obj_id_from_bitrix:
                                        logger.info(f"[LPA] Day search: Shift {bitrix_shift_id} - got object ID from local DB: {obj_id_from_bitrix}")
                                        log.info(f"[LPA] Day search: Shift {bitrix_shift_id} - got object ID from local DB: {obj_id_from_bitrix}")
                            except Exception as e:
                                logger.debug(f"[LPA] Day search: Shift {bitrix_shift_id} - could not get object from local DB: {e}")
                        
                        # Если все еще не знаем объект, пропускаем смену
                        if not obj_id_from_bitrix:
                            if item_idx < 3:
                                logger.info(f"[LPA] Day search: Shift {bitrix_shift_id} - no object ID found (neither Bitrix24 nor local DB), skipping")
                            continue
                        
                        # Проверяем соответствие объекта
                        if obj_id_from_bitrix != obj_id:
                            if item_idx < 3:
                                logger.info(f"[LPA] Day search: Shift {bitrix_shift_id} - object mismatch ({obj_id_from_bitrix} != {obj_id}), skipping")
                            continue
                    
                    bitrix_shift_id = item.get("id")
                    if not bitrix_shift_id:
                        continue
                    
                    # Читаем значения полей (пробуем разные варианты)
                    plan_total = float(item.get(f_plan_camel) or item.get(f_plan_code) or item.get("ufCrm7UfCrmPlanTotal") or 0)
                    fact_total = float(item.get(f_fact_camel) or item.get(f_fact_code) or item.get("ufCrm7UfCrmFactTotal") or 0)
                    eff_final = float(item.get(f_eff_camel) or item.get(f_eff_code) or item.get("ufCrm7UfCrmEffFinal") or 0)
                    
                    # Проверяем статус смены
                    item_status = ""
                    try:
                        item_status = _get_field_value(item, f_status_camel) or _get_field_value(item, f_status_code) or ""
                        if isinstance(item_status, str):
                            item_status = item_status.lower().strip()
                    except Exception as e:
                        logger.debug(f"Could not get status for shift {bitrix_shift_id}: {e}")
                        item_status = ""
                    
                    # Получаем obj_id_from_bitrix для логирования (если еще не получен)
                    if 'obj_id_from_bitrix' not in locals():
                        obj_link = item.get(UF_OBJECT_LINK)
                        if obj_link:
                            if isinstance(obj_link, list) and len(obj_link) > 0:
                                obj_str = obj_link[0]
                            elif isinstance(obj_link, str):
                                obj_str = obj_link
                            else:
                                obj_str = str(obj_link)
                            
                            try:
                                if isinstance(obj_str, str) and obj_str.startswith("D_"):
                                    obj_id_from_bitrix = int(obj_str[2:])
                                else:
                                    obj_id_from_bitrix = int(obj_str)
                            except (ValueError, TypeError):
                                obj_id_from_bitrix = "unknown"
                        else:
                            obj_id_from_bitrix = "no_link"
                    
                    logger.info(f"Shift {bitrix_shift_id}: obj={obj_id_from_bitrix}, plan={plan_total}, fact={fact_total}, eff={eff_final}, status='{item_status}'")
                    log.info(f"[LPA] Shift {bitrix_shift_id}: obj={obj_id_from_bitrix}, plan={plan_total}, fact={fact_total}, eff={eff_final}, status='{item_status}'")
                    
                    # Пропускаем смены без фактических данных
                    if not fact_total or fact_total == 0:
                        logger.info(f"[LPA] ⚠️ Skipping shift {bitrix_shift_id} - no fact data (fact_total={fact_total})")
                        log.info(f"[LPA] ⚠️ Skipping shift {bitrix_shift_id} - no fact data (fact_total={fact_total})")
                        continue
                    
                    # Принимаем смену если:
                    # 1. Есть фактические данные (fact_total > 0) - это главный признак закрытой смены
                    # 2. Статус "closed"/"закрыта"/"закрыто" ИЛИ статус пустой/None ИЛИ статус не "open"
                    # Считаем смену закрытой, если есть факт, даже если статус не установлен или имеет другое значение
                    # Исключаем только явно открытые смены (status == "open")
                    is_closed = (
                        item_status in ("closed", "закрыта", "закрыто") or  # Явно закрыта
                        not item_status or  # Статус не установлен, но есть факт
                        item_status == "" or  # Пустой статус
                        (item_status != "open" and fact_total > 0)  # Не открыта и есть факт
                    )
                    
                    logger.info(f"[LPA] Shift {bitrix_shift_id}: is_closed={is_closed} (status='{item_status}', fact={fact_total})")
                    log.info(f"[LPA] Shift {bitrix_shift_id}: is_closed={is_closed} (status='{item_status}', fact={fact_total})")
                    
                    if not is_closed:
                        logger.info(f"[LPA] ⚠️ Skipping shift {bitrix_shift_id} - not closed (status='{item_status}', fact={fact_total})")
                        log.info(f"[LPA] ⚠️ Skipping shift {bitrix_shift_id} - not closed (status='{item_status}', fact={fact_total})")
                        continue
                    
                    # Получаем дату смены
                    shift_date_str = item.get(f_date_camel) or item.get(f_date)
                    if shift_date_str:
                        try:
                            from datetime import datetime
                            if isinstance(shift_date_str, str):
                                shift_date_obj = datetime.fromisoformat(shift_date_str.replace("Z", "+00:00")).date()
                            else:
                                shift_date_obj = shift_date_str
                            shift_date = shift_date_obj.strftime("%d.%m.%Y")
                        except:
                            shift_date = check_date.strftime("%d.%m.%Y") if 'check_date' in locals() else "Не указана"
                    else:
                        shift_date = check_date.strftime("%d.%m.%Y") if 'check_date' in locals() else "Не указана"
                    
                    logger.info(f"✅ Found closed shift in Bitrix24: {bitrix_shift_id} for object {obj_id} (fact={fact_total}, status='{item_status}', date={shift_date})")
                    log.info(f"[LPA] ✅ Found closed shift in Bitrix24: {bitrix_shift_id} for object {obj_id} (fact={fact_total}, status='{item_status}', date={shift_date})")
                    print(f"[LPA] ✅ Found closed shift: {bitrix_shift_id} for object {obj_id} (fact={fact_total}, status='{item_status}')")
                    
                    # Получаем дополнительные данные смены
                    from app.services.objects import fetch_all_objects
                    objs = await fetch_all_objects()
                    # objs это список кортежей (id, title)
                    obj_name = next((title for oid, title in objs if oid == obj_id), f"Объект #{obj_id}")
                    
                    # Пытаемся получить детальные данные из локальной БД
                    from app.services.shift_repo import get_shift_by_bitrix_id
                    from app.db import session_scope
                    from app.models import Shift
                    
                    local_shift = get_shift_by_bitrix_id(bitrix_shift_id)
                    
                    if local_shift:
                        # Если нашли в локальной БД, получаем полные данные
                        local_shift_id, _ = local_shift
                        with session_scope() as s:
                            sh = s.get(Shift, local_shift_id)
                            if sh and sh.object_id == obj_id:
                                # Получаем полные данные
                                object_name_local = sh.object.name if sh.object else obj_name
                                formatted_date_local = sh.date.strftime("%d.%m.%Y") if sh.date else shift_date
                                plan_data_full = sh.plan_json or {}
                                fact_data_full = sh.fact_json or {}
                                
                                shift_data = {
                                    "plan": {
                                        **plan_data_full,
                                        "object_name": object_name_local,
                                        "date": formatted_date_local,
                                        "section": plan_data_full.get("section", "Не указан"),
                                        "foreman": plan_data_full.get("foreman", "Не указан"),
                                        "shift_type": sh.type.value if sh.type else "day"
                                    },
                                    "fact": fact_data_full,
                                    "efficiency": sh.eff_final or eff_final,
                                    "date": formatted_date_local,
                                    "type": sh.type.value if sh.type else "day",
                                    "status": sh.status.value if sh.status else "closed"
                                }
                                shift_id = local_shift_id
                                logger.info(f"[LPA] ✅ Got detailed data from local DB for shift {bitrix_shift_id} -> local {local_shift_id}")
                                log.info(f"[LPA] ✅ Got detailed data from local DB for shift {bitrix_shift_id} -> local {local_shift_id}")
                            else:
                                # Объект не совпадает, используем данные из Bitrix24
                                shift_data = {
                                    "plan": {
                                        "plan_total": plan_total,
                                        "object_name": obj_name,
                                        "date": shift_date,
                                    },
                                    "fact": {"fact_total": fact_total},
                                    "efficiency": eff_final,
                                    "date": shift_date,
                                    "type": "day",
                                    "status": item_status if item_status else "closed"
                                }
                                shift_id = bitrix_shift_id
                    else:
                        # Не нашли в локальной БД, пробуем получить детальные данные из Bitrix24 (JSON)
                        logger.info(f"[LPA] Shift {bitrix_shift_id} not found in local DB, trying to get JSON from Bitrix24")
                        log.info(f"[LPA] Shift {bitrix_shift_id} not found in local DB, trying to get JSON from Bitrix24")
                        
                        # Пробуем получить JSON из Bitrix24
                        import json
                        f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
                        f_fact_json = resolve_code("Смена", "UF_FACT_JSON")
                        
                        plan_json_str = None
                        fact_json_str = None
                        
                        if f_plan_json:
                            f_plan_json_camel = upper_to_camel(f_plan_json)
                            plan_json_str = item.get(f_plan_json_camel) or item.get(f_plan_json)
                        
                        if f_fact_json:
                            f_fact_json_camel = upper_to_camel(f_fact_json)
                            fact_json_str = item.get(f_fact_json_camel) or item.get(f_fact_json)
                        
                        # Парсим JSON, если есть
                        plan_data_from_json = {}
                        fact_data_from_json = {}
                        
                        if plan_json_str:
                            try:
                                plan_data_from_json = json.loads(plan_json_str) if isinstance(plan_json_str, str) else plan_json_str
                                logger.info(f"[LPA] ✅ Loaded plan_json from Bitrix24: {len(plan_data_from_json)} items")
                                log.info(f"[LPA] ✅ Loaded plan_json from Bitrix24: {len(plan_data_from_json)} items")
                            except Exception as e:
                                logger.warning(f"[LPA] Could not parse plan_json from Bitrix24: {e}")
                        
                        if fact_json_str:
                            try:
                                fact_data_from_json = json.loads(fact_json_str) if isinstance(fact_json_str, str) else fact_json_str
                                logger.info(f"[LPA] ✅ Loaded fact_json from Bitrix24: {len(fact_data_from_json)} items")
                                log.info(f"[LPA] ✅ Loaded fact_json from Bitrix24: {len(fact_data_from_json)} items")
                            except Exception as e:
                                logger.warning(f"[LPA] Could not parse fact_json from Bitrix24: {e}")
                        
                        # Используем данные из JSON, если они есть, иначе только итоговые значения
                        if plan_data_from_json or fact_data_from_json:
                            shift_data = {
                                "plan": {
                                    **plan_data_from_json,
                                    "object_name": obj_name,  # Всегда используем актуальное название из выбранного объекта
                                    "date": plan_data_from_json.get("date") or shift_date,
                                    "section": plan_data_from_json.get("section", "Не указан"),
                                    "foreman": plan_data_from_json.get("foreman", "Не указан"),
                                    "shift_type": plan_data_from_json.get("shift_type", "day")
                                },
                                "fact": fact_data_from_json if fact_data_from_json else {"fact_total": fact_total},
                                "efficiency": eff_final,
                                "date": plan_data_from_json.get("date") or shift_date,
                                "type": "day",
                                "status": item_status if item_status else "closed"
                            }
                            logger.info(f"[LPA] ✅ Using detailed data from Bitrix24 JSON fields")
                            log.info(f"[LPA] ✅ Using detailed data from Bitrix24 JSON fields")
                        else:
                            # Используем только итоговые данные из Bitrix24
                            logger.warning(f"[LPA] Shift {bitrix_shift_id} not found in local DB and no JSON in Bitrix24, using summary data only")
                            log.warning(f"[LPA] Shift {bitrix_shift_id} not found in local DB and no JSON in Bitrix24, using summary data only")
                            shift_data = {
                                "plan": {
                                    "plan_total": plan_total,
                                    "object_name": obj_name,
                                    "date": shift_date,
                                },
                                "fact": {"fact_total": fact_total},
                                "efficiency": eff_final,
                                "date": shift_date,
                                "type": "day",
                                "status": item_status if item_status else "closed"
                            }
                        shift_id = bitrix_shift_id
                    break  # Выходим из цикла for item in items
                
                # Если нашли смену, выходим из цикла по дням
                if shift_data:
                    break  # Выходим из цикла for days_ago in range(60)
        
        except Exception as e:
            logger.error(f"[LPA] Error searching for closed shift in Bitrix24: {e}", exc_info=True)
            log.error(f"[LPA] Error searching for closed shift in Bitrix24: {e}", exc_info=True)
            print(f"[LPA] ERROR in Bitrix24 search: {e}")
    
    if not shift_data:
        logger.warning(f"[LPA] ❌ No closed shifts found for object {obj_id} after searching 60 days")
        log.warning(f"[LPA] ❌ No closed shifts found for object {obj_id} after searching 60 days")
        print(f"[LPA] ❌ No closed shifts found for object {obj_id}")
        await cq.message.answer(
            "❌ <b>Закрытых смен не найдено</b>\n\n"
            "Для генерации ЛПА нужна закрытая смена с фактическими данными.\n\n"
            "Сначала создайте план, затем отчёт, и закройте смену.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Логируем данные перед сохранением в state
    logger.info(f"[LPA] Saving shift_data to state: shift_id={shift_id}, obj_id={obj_id}")
    logger.info(f"[LPA] shift_data keys: {list(shift_data.keys()) if shift_data and isinstance(shift_data, dict) else 'None'}")
    plan_data_check = shift_data.get("plan", {}) if shift_data and isinstance(shift_data, dict) else {}
    fact_data_check = shift_data.get("fact", {}) if shift_data and isinstance(shift_data, dict) else {}
    
    # Проверяем тип перед вызовом .keys()
    if isinstance(plan_data_check, dict):
        logger.info(f"[LPA] plan_data keys: {list(plan_data_check.keys())}")
        logger.info(f"[LPA] plan_data content: {plan_data_check}")
        print(f"[LPA] Сохраняем shift_data: plan={list(plan_data_check.keys())}")
    else:
        logger.info(f"[LPA] plan_data type: {type(plan_data_check)}, value: {plan_data_check}")
        print(f"[LPA] Сохраняем shift_data: plan={type(plan_data_check)}")
    
    if isinstance(fact_data_check, dict):
        logger.info(f"[LPA] fact_data keys: {list(fact_data_check.keys())}")
        logger.info(f"[LPA] fact_data content: {fact_data_check}")
        print(f"[LPA] Сохраняем shift_data: fact={list(fact_data_check.keys())}")
    else:
        logger.info(f"[LPA] fact_data type: {type(fact_data_check)}, value: {fact_data_check}")
        print(f"[LPA] Сохраняем shift_data: fact={type(fact_data_check)}")
    
    resolved_bitrix_id = bitrix_shift_id
    if not resolved_bitrix_id and shift_id:
        try:
            shift_id_int = int(shift_id)
            if shift_id_int >= 100000:
                resolved_bitrix_id = shift_id_int
        except (TypeError, ValueError):
            resolved_bitrix_id = bitrix_shift_id

    # ВАЖНО: Собираем единый контекст для превью и PDF через collect_lpa_data
    # Это гарантирует, что превью и PDF используют одни и те же данные
    lpa_context = None
    if resolved_bitrix_id:
        try:
            from app.services.lpa_data import collect_lpa_data
            logger.info(f"[LPA] Collecting LPA context for preview: shift_bitrix_id={resolved_bitrix_id}")
            log.info(f"[LPA] Collecting LPA context for preview: shift_bitrix_id={resolved_bitrix_id}")
            
            # Подготавливаем fallback данные из shift_data
            plan_data_fallback = shift_data.get("plan", {}) if isinstance(shift_data.get("plan"), dict) else {}
            fact_data_fallback = shift_data.get("fact", {}) if isinstance(shift_data.get("fact"), dict) else {}
            meta_fallback = {
                "object_name": plan_data_fallback.get("object_name") or shift_data.get("object_name"),
                "date": plan_data_fallback.get("date") or shift_data.get("date"),
                "section": plan_data_fallback.get("section") or shift_data.get("section"),
                "foreman": plan_data_fallback.get("foreman") or shift_data.get("foreman"),
            }
            
            # Собираем единый контекст (тот же, что будет использован для PDF)
            lpa_context, _ = await collect_lpa_data(
                shift_bitrix_id=resolved_bitrix_id,
                fallback_plan=plan_data_fallback if plan_data_fallback else None,
                fallback_fact=fact_data_fallback if fact_data_fallback else None,
                meta=meta_fallback if meta_fallback else None,
            )
            
            logger.info(f"[LPA] LPA context collected: object_name={lpa_context.get('object_name')}, plan_total={lpa_context.get('plan_total')}, fact_total={lpa_context.get('fact_total')}")
            log.info(f"[LPA] LPA context collected: object_name={lpa_context.get('object_name')}, plan_total={lpa_context.get('plan_total')}, fact_total={lpa_context.get('fact_total')}")
        except Exception as e:
            logger.warning(f"[LPA] Could not collect LPA context for preview: {e}", exc_info=True)
            log.warning(f"[LPA] Could not collect LPA context for preview: {e}")
            # Продолжаем с fallback данными
    
    await state.update_data(
        object_id=obj_id,
        shift_id=shift_id,
        shift_data=shift_data,
        bitrix_shift_id=resolved_bitrix_id,
        lpa_context=lpa_context,  # Сохраняем контекст для использования при генерации
    )
    await state.set_state(LPAFlow.generate_pdf)
    
    # Показываем информацию о смене
    # Проверяем тип shift_data перед вызовом .get()
    if not isinstance(shift_data, dict):
        logger.error(f"[LPA] shift_data is not a dict: {type(shift_data)}")
        await cq.message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Данные смены имеют неверный формат. Попробуйте выбрать другой объект.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Используем единый контекст для превью (если собран), иначе fallback
    if lpa_context:
        # Используем данные из единого контекста
        object_name = lpa_context.get('object_name', 'Не указан')
        date_str = lpa_context.get('date', 'Не указана')
        shift_type = lpa_context.get('shift_type', 'Не указан')
        plan_sum = float(lpa_context.get('plan_total', 0) or 0)
        fact_sum = float(lpa_context.get('fact_total', 0) or 0)
        efficiency = float(lpa_context.get('efficiency', 0) or 0)
        logger.info(f"[LPA] Using unified context for preview: plan_total={plan_sum}, fact_total={fact_sum}")
        log.info(f"[LPA] Using unified context for preview: plan_total={plan_sum}, fact_total={fact_sum}")
    else:
        # Fallback: используем данные из shift_data (старый способ)
        plan_data = shift_data.get("plan", {}) if isinstance(shift_data.get("plan"), dict) else {}
        fact_data = shift_data.get("fact", {}) if isinstance(shift_data.get("fact"), dict) else {}
        efficiency = shift_data.get("efficiency", 0)
        
        # Вычисляем план и факт для отображения
        if isinstance(plan_data, dict) and plan_data.get("tasks"):
            plan_sum = sum(float(task.get("plan", 0) or 0) for task in plan_data["tasks"])
        elif isinstance(plan_data, dict):
            plan_sum = plan_data.get("plan_total") or plan_data.get("total_plan") or 0
            try:
                plan_sum = float(plan_sum or 0)
            except (ValueError, TypeError):
                plan_sum = 0
        else:
            plan_sum = 0
        
        if isinstance(fact_data, dict) and fact_data.get("tasks"):
            fact_sum = sum(float(task.get("fact", 0) or 0) for task in fact_data["tasks"])
        elif isinstance(fact_data, dict):
            fact_total_val = fact_data.get("fact_total")
            fact_sum = fact_total_val if isinstance(fact_total_val, (int, float, str)) else 0
            try:
                fact_sum = float(fact_sum or 0)
            except (ValueError, TypeError):
                fact_sum = 0
        else:
            fact_sum = 0
        
        # Безопасное получение метаданных
        object_name = plan_data.get('object_name', 'Не указан') if isinstance(plan_data, dict) else 'Не указан'
        date_str = plan_data.get('date', 'Не указана') if isinstance(plan_data, dict) else 'Не указана'
        shift_type = plan_data.get('type', 'Не указан') if isinstance(plan_data, dict) else 'Не указан'
        logger.info(f"[LPA] Using fallback data for preview: plan_total={plan_sum}, fact_total={fact_sum}")
        log.info(f"[LPA] Using fallback data for preview: plan_total={plan_sum}, fact_total={fact_sum}")
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Сгенерировать ЛПА", callback_data="generate_lpa")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_lpa")]
        ]
    )
    
    await cq.message.answer(
        f"📄 <b>Подготовка ЛПА</b>\n\n"
        f"<b>Объект:</b> {object_name}\n"
        f"<b>Дата:</b> {date_str}\n"
        f"<b>Тип смены:</b> {shift_type}\n"
        f"<b>Эффективность:</b> {efficiency:.1f}%\n\n"
        f"<b>План:</b> {plan_sum:.2f}\n"
        f"<b>Факт:</b> {fact_sum:.2f}\n\n"
        f"Нажмите кнопку ниже для генерации ЛПА:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    # Не генерируем автоматически, ждем нажатия кнопки


async def generate_lpa_pdf(message: Message, state: FSMContext):
    """Генерация ЛПА DOCX (с последующей попыткой конвертации в PDF)."""
    await message.answer("⏳ Генерируем ЛПА...")

    try:
        pass  # Импорты перенесены внутрь функции
    except ImportError as e:
        logger.error(f"Не удалось импортировать lpa_pdf: {e}")
        await message.answer(
            "❌ <b>Ошибка генерации ЛПА</b>\n\n"
            "Модуль генерации ЛПА недоступен. Обратитесь к администратору.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    try:
        data = await state.get_data()
        shift_id = data.get("shift_id")
        shift_data = data.get("shift_data", {})

        if not shift_data:
            await message.answer(
                "❌ <b>Ошибка генерации ЛПА</b>\n\n"
                "Данные смены не найдены. Попробуйте выбрать смену заново.",
                parse_mode="HTML",
            )
            await state.clear()
            return

        plan_data = shift_data.get("plan", {}) or {}
        fact_data = shift_data.get("fact", {}) or {}

        meta = {
            "object_name": plan_data.get("object_name") or shift_data.get("object_name"),
            "date": plan_data.get("date") or shift_data.get("date"),
            "section": plan_data.get("section") or shift_data.get("section"),
            "foreman": plan_data.get("foreman") or shift_data.get("foreman"),
            "downtime_reason": shift_data.get("downtime_reason"),
        }

        async def resolve_bitrix_id(raw_value: Any) -> Optional[int]:
            if data.get("bitrix_shift_id"):
                return data["bitrix_shift_id"]
            try:
                value_int = int(raw_value)
            except (TypeError, ValueError):
                return None
            if value_int >= 100000:
                return value_int
            try:
                from app.db import session_scope
                from app.models import Shift

                with session_scope() as s:
                    sh = s.get(Shift, value_int)
                    if sh and sh.bitrix_id:
                        return sh.bitrix_id
            except Exception as err:
                logger.debug(f"[LPA] Could not resolve bitrix_id for shift {raw_value}: {err}")
            return None

        bitrix_shift_id = data.get("bitrix_shift_id") or await resolve_bitrix_id(shift_id)
        object_name_for_log = meta.get("object_name") or shift_data.get("object_name") or "Unknown"
        logger.info(f"[LPA BOT] shift_id={shift_id}, bitrix_id={bitrix_shift_id}, object={object_name_for_log}")
        log.info(f"[LPA BOT] shift_id={shift_id}, bitrix_id={bitrix_shift_id}, object={object_name_for_log}")
        
        # ВАЖНО: Используем единую функцию генерации ЛПА
        from app.services.lpa_generator import generate_lpa_for_shift
        from app.services.http_client import bx
        from app.bitrix_field_map import resolve_code, upper_to_camel
        from app.services.bitrix_ids import UF_PDF_FILE
        
        logger.info(f"[LPA BOT] ===== START GENERATION =====")
        logger.info(f"[LPA BOT] shift_bitrix_id={bitrix_shift_id}, shift_id={shift_id}")
        
        # Проверяем, есть ли уже сгенерированный ЛПА в Bitrix
        try:
            f_pdf_file = resolve_code("Смена", "UF_PDF_FILE")
            f_pdf_file_camel = upper_to_camel(f_pdf_file) if f_pdf_file and f_pdf_file.startswith("UF_") else None
            
            shift_item = await bx("crm.item.get", {
                "entityTypeId": 1050,  # SHIFT_ETID
                "id": bitrix_shift_id,
            })
            
            shift_data_bitrix = shift_item.get("item", shift_item) if isinstance(shift_item, dict) else {}
            existing_pdf = shift_data_bitrix.get(f_pdf_file_camel) or shift_data_bitrix.get("ufCrm7UfCrmPdfFile")
            
            if existing_pdf:
                logger.info(f"[LPA BOT] Found existing PDF file in Bitrix: {existing_pdf}")
                # Сохраняем информацию о существующем файле в FSM для подтверждения
                await state.update_data(has_existing_pdf=True, existing_pdf_info=str(existing_pdf))
                
                # Спрашиваем у пользователя, перегенерировать ли
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                kb = InlineKeyboardBuilder()
                kb.button(text="✅ Да, перегенерировать", callback_data="lpa_regenerate_confirm")
                kb.button(text="❌ Нет, отмена", callback_data="lpa_regenerate_cancel")
                kb.adjust(1)
                
                await message.answer(
                    "⚠️ <b>ЛПА уже сгенерирован</b>\n\n"
                    f"Для этой смены уже существует файл ЛПА в Bitrix24.\n\n"
                    "Перегенерировать ЛПА?",
                    reply_markup=kb.as_markup(),
                    parse_mode="HTML"
                )
                return
        except Exception as e:
            logger.warning(f"[LPA BOT] Could not check existing PDF: {e}")
            # Продолжаем генерацию, если проверка не удалась
        
        # Проверяем, есть ли уже собранный контекст из превью
        lpa_context_preview = data.get("lpa_context")
        
        try:
            logger.info(f"[LPA BOT] Starting LPA generation for shift {bitrix_shift_id}")
            result = await generate_lpa_for_shift(
                shift_bitrix_id=bitrix_shift_id,
                fallback_plan=plan_data if plan_data else None,
                fallback_fact=fact_data if fact_data else None,
                meta=meta if meta else None,
            )
        except LPAPlaceholderError:
            logger.error(f"[LPA BOT] Placeholder error during LPA generation", exc_info=True)
            await message.answer(PLACEHOLDER_ERROR_TEXT, parse_mode="HTML")
            await state.clear()
            return
        except FileNotFoundError as e:
            logger.error(f"[LPA BOT] Template not found: {e}")
            await message.answer(
                "❌ <b>Ошибка генерации ЛПА</b>\n\n"
                "Шаблон не найден. Обратитесь к администратору.",
                parse_mode="HTML",
            )
            await state.clear()
            return
        except Exception as e:
            logger.error(f"[LPA BOT] Unexpected error while generating LPA", exc_info=True)
            await message.answer(GENERAL_ERROR_TEXT, parse_mode="HTML")
            await state.clear()
            return

        pdf_path = result.pdf_path
        lpa_context = result.context or {}

        if lpa_context_preview and lpa_context:
            preview_plan = lpa_context_preview.get("plan_total", 0)
            gen_plan = lpa_context.get("plan_total", 0)
            if abs(preview_plan - gen_plan) > 0.01:
                logger.warning(f"[LPA BOT] Context mismatch: preview plan_total={preview_plan}, generated plan_total={gen_plan}")
                log.warning(f"[LPA BOT] Context mismatch: preview plan_total={preview_plan}, generated plan_total={gen_plan}")
            else:
                logger.info(f"[LPA BOT] Context matches: plan_total={gen_plan} (preview and generated)")
                log.info(f"[LPA BOT] Context matches: plan_total={gen_plan} (preview and generated)")

        logger.info(f"[LPA BOT] LPA generated successfully: {pdf_path}")
        
        # Загружаем PDF файл в Bitrix
        try:
            from app.services.bitrix_files import upload_docx_to_bitrix_field
            uploaded = False
            for field_name in ["UF_PDF_FILE", "UF_LPA_FILE", "UF_FILE_PDF"]:
                if await upload_docx_to_bitrix_field(
                    file_path=str(pdf_path),
                    entity_type_id=1050,
                    item_id=bitrix_shift_id,
                    field_logical_name=field_name,
                    entity_ru_name="Смена",
                ):
                    uploaded = True
                    logger.info(f"[LPA BOT] PDF uploaded to Bitrix field: {field_name}")
                    break
            
            if not uploaded:
                logger.warning(f"[LPA BOT] Could not upload PDF to Bitrix (tried all fields)")
        except Exception as upload_err:
            logger.warning(f"[LPA BOT] Could not upload PDF to Bitrix: {upload_err}")
        
        # Обновляем агрегаты после успешной генерации и загрузки ЛПА
        try:
            await bitrix_update_shift_aggregates(
                shift_id=bitrix_shift_id,
                plan_total=lpa_context.get("plan_total", 0),
                fact_total=lpa_context.get("fact_total", 0),
                efficiency=lpa_context.get("efficiency"),
                status="closed",
            )
        except Exception as agg_err:
            logger.warning(f"[LPA BOT] Could not update shift aggregates: {agg_err}")
        
        # Формируем "человеческое" имя файла для отправки
        object_name_safe = lpa_context.get("object_name", "Не указан").replace("/", "_").replace("\\", "_")
        date_str_safe = lpa_context.get("date", "").replace("/", "_").replace(":", "_")
        nice_filename = f"LPA_{object_name_safe}_{date_str_safe}.pdf" if pdf_path and pdf_path.exists() else f"LPA_{object_name_safe}_{date_str_safe}.docx"
        
        caption = (
            f"📄 <b>ЛПА сформирован (<code>{'PDF' if pdf_path and pdf_path.exists() else 'DOCX'}</code>)</b>\n\n"
            f"Объект: {lpa_context.get('object_name', 'Не указан')}\n"
            f"Дата: {lpa_context.get('date', 'Не указана')}\n"
            f"План: {lpa_context.get('plan_total', 0)}\n"
            f"Факт: {lpa_context.get('fact_total', 0)}\n"
            f"Эффективность: {lpa_context.get('efficiency', 0)}%\n"
            f"Причина простоя: {lpa_context.get('downtime_reason', 'Не указана')}\n"
            f"Фото: {lpa_context.get('photos_attached', 'Нет')}"
        )

        final_path = pdf_path
        logger.info(f"[LPA BOT] Sending generated LPA to chat {message.chat.id}: {final_path}")
        
        logger.info(f"[LPA BOT] Sending file: {final_path.name} (nice_filename: {nice_filename})")
        log.info(f"[LPA] Sending file to user: {final_path}")
        
        with open(str(final_path), "rb") as f:
            file_content = f.read()
            input_file = BufferedInputFile(
                file_content,
                filename=nice_filename,  # Используем "человеческое" имя
            )
            await message.answer_document(document=input_file, caption=caption, parse_mode="HTML")

        await state.clear()
        logger.info(f"[LPA] ЛПА успешно отправлен пользователю. Файл: {final_path}")
    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"[LPA] Ошибка генерации ЛПА: {e}")
        logger.error(f"[LPA] Traceback:\n{error_trace}")
        log.error(f"[LPA] Ошибка генерации ЛПА: {e}")
        log.error(f"[LPA] Traceback:\n{error_trace}")
        await message.answer(GENERAL_ERROR_TEXT, parse_mode="HTML")
        await state.clear()


@router.callback_query(F.data == "generate_lpa")
async def generate_lpa_callback(cq: CallbackQuery, state: FSMContext):
    """Обработчик кнопки генерации ЛПА."""
    user_id = cq.from_user.id if cq.from_user else "unknown"
    logger.info(f"[LPA] User {user_id} clicked 'generate_lpa' button")
    log.info(f"[LPA] User {user_id} clicked 'generate_lpa' button")
    try:
        await cq.answer("⏳ Генерируем ЛПА...")
        logger.info(f"[LPA] Starting LPA generation for user {user_id}")
        log.info(f"[LPA] Starting LPA generation for user {user_id}")
        await generate_lpa_pdf(cq.message, state)
    except Exception as e:
        logger.error(f"Ошибка генерации ЛПА: {e}", exc_info=True)
        try:
            await cq.answer("❌ Ошибка генерации", show_alert=True)
        except:
            pass
        await cq.message.answer(GENERAL_ERROR_TEXT, parse_mode="HTML")
        await state.clear()


@router.callback_query(F.data == "lpa_regenerate_confirm")
async def lpa_regenerate_confirm(cq: CallbackQuery, state: FSMContext):
    """Подтверждение перегенерации ЛПА."""
    await cq.answer()
    
    try:
        data = await state.get_data()
        shift_id = data.get("shift_id")
        shift_data = data.get("shift_data", {})
        bitrix_shift_id = data.get("bitrix_shift_id")
        
        if not bitrix_shift_id:
            await cq.message.answer(
                "❌ <b>Ошибка</b>\n\n"
                "Не найден ID смены. Попробуйте выбрать смену заново.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Продолжаем генерацию ЛПА (код из generate_lpa_pdf)
        plan_data = shift_data.get("plan", {}) or {}
        fact_data = shift_data.get("fact", {}) or {}
        
        meta = {
            "object_name": plan_data.get("object_name") or shift_data.get("object_name"),
            "date": plan_data.get("date") or shift_data.get("date"),
            "section": plan_data.get("section") or shift_data.get("section"),
            "foreman": plan_data.get("foreman") or shift_data.get("foreman"),
            "downtime_reason": shift_data.get("downtime_reason"),
        }
        
        from app.services.lpa_generator import generate_lpa_for_shift
        
        lpa_context_preview = data.get("lpa_context")
        
        try:
            result = await generate_lpa_for_shift(
                shift_bitrix_id=bitrix_shift_id,
                fallback_plan=plan_data if plan_data else None,
                fallback_fact=fact_data if fact_data else None,
                meta=meta if meta else None,
            )
        except LPAPlaceholderError:
            logger.error(f"[LPA BOT] Placeholder error during LPA regeneration", exc_info=True)
            await cq.message.answer(PLACEHOLDER_ERROR_TEXT, parse_mode="HTML")
            await state.clear()
            return
        except FileNotFoundError as e:
            logger.error(f"[LPA BOT] Template not found: {e}")
            await cq.message.answer(
                "❌ <b>Ошибка генерации ЛПА</b>\n\n"
                "Шаблон не найден. Обратитесь к администратору.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        except Exception as e:
            logger.error(f"[LPA BOT] Error regenerating LPA: {e}", exc_info=True)
            await cq.message.answer(GENERAL_ERROR_TEXT, parse_mode="HTML")
            await state.clear()
            return

        pdf_path = result.pdf_path
        lpa_context = result.context or {}
        
        from app.services.bitrix_files import upload_docx_to_bitrix_field
        uploaded = False
        for field_name in ["UF_PDF_FILE", "UF_LPA_FILE", "UF_FILE_PDF"]:
            if await upload_docx_to_bitrix_field(
                file_path=str(pdf_path),
                entity_type_id=1050,
                item_id=bitrix_shift_id,
                field_logical_name=field_name,
                entity_ru_name="Смена"
            ):
                uploaded = True
                logger.info(f"[LPA BOT] PDF uploaded to Bitrix field: {field_name}")
                break
        
        if not uploaded:
            logger.warning(f"[LPA BOT] Could not upload PDF to Bitrix (tried all fields)")
        
        object_name = lpa_context.get("object_name", "Не указан")
        date_str = lpa_context.get("date", "")
        filename = f"LPA_{object_name}_{date_str}.pdf"
        
        logger.info(f"[LPA BOT] Sending generated LPA to chat {cq.message.chat.id}: {pdf_path}")
        await cq.message.answer_document(
            document=types.FSInputFile(pdf_path),
            caption=f"📄 <b>ЛПА перегенерирован</b>\n\n"
                   f"Объект: {object_name}\n"
                   f"Дата: {date_str}",
            parse_mode="HTML"
        )
        
        await state.clear()
            
    except Exception as e:
        logger.error(f"[LPA] Error in lpa_regenerate_confirm: {e}", exc_info=True)
        await cq.message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при перегенерации ЛПА.",
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "lpa_regenerate_cancel")
async def lpa_regenerate_cancel(cq: CallbackQuery, state: FSMContext):
    """Отмена перегенерации ЛПА."""
    await cq.answer("❌ Отменено")
    await state.clear()
    
    from app.telegram.keyboards import get_main_menu_keyboard
    
    await cq.message.answer(
        "❌ <b>Перегенерация отменена</b>\n\n"
        "Возвращаемся в главное меню:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("regen_lpa:"))
async def regen_lpa_button(cq: CallbackQuery, state: FSMContext):
    """Перегенерация ЛПА из отчётного флоу без повторного сценария."""
    await cq.answer("⏳ Генерируем ЛПА...", show_alert=False)
    from app.services.lpa_generator import generate_lpa_for_shift
    from app.services.lpa_pdf import LPAPlaceholderError

    try:
        _, shift_id_str = cq.data.split(":", 1)
        bitrix_shift_id = int(shift_id_str)
    except (ValueError, IndexError):
        logger.error(f"[LPA BOT] Invalid regen_lpa callback: {cq.data}")
        await cq.message.answer(GENERAL_ERROR_TEXT, parse_mode="HTML")
        return

    logger.info(f"[LPA BOT] Starting quick LPA regeneration for shift {bitrix_shift_id}")

    try:
        result = await generate_lpa_for_shift(shift_bitrix_id=bitrix_shift_id)
    except LPAPlaceholderError:
        logger.error(f"[LPA BOT] Placeholder error during quick regeneration", exc_info=True)
        await cq.message.answer(PLACEHOLDER_ERROR_TEXT, parse_mode="HTML")
        return
    except FileNotFoundError as e:
        logger.error(f"[LPA BOT] Template not found during quick regeneration: {e}")
        await cq.message.answer(
            "❌ <b>Ошибка генерации ЛПА</b>\n\n"
            "Шаблон не найден. Обратитесь к администратору.",
            parse_mode="HTML",
        )
        return
    except Exception as e:
        logger.error(f"[LPA BOT] Unexpected error during quick regeneration: {e}", exc_info=True)
        await cq.message.answer(GENERAL_ERROR_TEXT, parse_mode="HTML")
        return

    pdf_path = result.pdf_path
    lpa_context = result.context or {}

    from app.services.bitrix_files import upload_docx_to_bitrix_field
    uploaded = False
    for field_name in ["UF_PDF_FILE", "UF_LPA_FILE", "UF_FILE_PDF"]:
        if await upload_docx_to_bitrix_field(
            file_path=str(pdf_path),
            entity_type_id=1050,
            item_id=bitrix_shift_id,
            field_logical_name=field_name,
            entity_ru_name="Смена",
        ):
            uploaded = True
            logger.info(f"[LPA BOT] PDF uploaded to Bitrix field: {field_name}")
            break
    if not uploaded:
        logger.warning(f"[LPA BOT] Could not upload PDF to Bitrix (regen button) for shift {bitrix_shift_id}")

    object_name = lpa_context.get("object_name", "Не указан")
    date_str = lpa_context.get("date", "")

    logger.info(f"[LPA BOT] Sending generated LPA to chat {cq.message.chat.id}: {pdf_path}")
    await cq.message.answer_document(
        document=types.FSInputFile(pdf_path),
        caption=f"📄 <b>ЛПА перегенерирован</b>\n\n"
               f"Объект: {object_name}\n"
               f"Дата: {date_str}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel_lpa")
async def cancel_lpa_callback(cq: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отмены ЛПА."""
    user_id = cq.from_user.id if cq.from_user else "unknown"
    logger.info(f"[LPA] User {user_id} clicked 'cancel_lpa' button")
    log.info(f"[LPA] User {user_id} clicked 'cancel_lpa' button")
    try:
        await cq.answer("❌ Отменено")
        await state.clear()
        
        from app.telegram.keyboards import get_main_menu_keyboard
        
        await cq.message.answer(
            "❌ <b>Генерация ЛПА отменена</b>\n\n"
            "Возвращаемся в главное меню:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при отмене ЛПА: {e}", exc_info=True)
        try:
            await cq.answer("❌ Ошибка", show_alert=True)
        except:
            pass
        await state.clear()


@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(cq: CallbackQuery, state: FSMContext):
    """Возврат в главное меню."""
    await cq.answer()
    await state.clear()
    
    from app.telegram.keyboards import get_main_menu_keyboard
    
    await cq.message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
