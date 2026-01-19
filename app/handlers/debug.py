# app/handlers/debug.py

import os
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.bitrix_field_map import resolve_code
from app.services.http_client import bx, BitrixError
from app.config import get_settings
from dotenv import load_dotenv

router = Router(name="debug")
log = logging.getLogger("gpo.debug")

# Явно загружаем .env для переменных, которых нет в Settings
load_dotenv()

# Используем Settings для загрузки переменных из .env
_settings = get_settings()

ENTITY_RESOURCE = _settings.ENTITY_RESOURCE if _settings.ENTITY_RESOURCE is not None else int(os.getenv("ENTITY_RESOURCE", "0"))
ENTITY_TIMESHEET = int(os.getenv("ENTITY_TIMESHEET", "0"))  # Нет в Settings, используем env
DEBUG_SHIFT_ID = int(os.getenv("DEBUG_SHIFT_ID", "98765"))

log.debug(f"Загружены переменные: ENTITY_RESOURCE={ENTITY_RESOURCE}, ENTITY_TIMESHEET={ENTITY_TIMESHEET}, DEBUG_SHIFT_ID={DEBUG_SHIFT_ID}")


async def bx_add(entity_type_id: int, fields: dict) -> dict:
    """Добавить элемент в Bitrix24 через надёжный клиент с ретраями."""
    payload = {"entityTypeId": entity_type_id, "fields": fields}
    log.debug(f"Отправка в Bitrix: {payload}")
    try:
        result = await bx("crm.item.add", payload)
        log.debug(f"Успешный ответ от Bitrix: {result}")
        return result
    except BitrixError as e:
        log.error(f"Ошибка Bitrix: {e}")
        raise


def res_fields_equip(shift_id: int) -> dict:
    """Создает поля для техники. Если UF поля не найдены, возвращает только базовые."""
    from app.bitrix_field_map import resolve_code, upper_to_camel
    e = "Ресурс"
    fields = {}
    
    # Пробуем разрешить UF коды
    uf_shift_id = resolve_code(e, "UF_SHIFT_ID")
    uf_resource_type = resolve_code(e, "UF_RESOURCE_TYPE")
    uf_equip_type = resolve_code(e, "UF_EQUIP_TYPE")
    uf_equip_hours = resolve_code(e, "UF_EQUIP_HOURS")
    uf_equip_rate_type = resolve_code(e, "UF_EQUIP_RATE_TYPE")
    uf_equip_rate = resolve_code(e, "UF_EQUIP_RATE")
    
    # Конвертируем в camelCase для Bitrix24 API
    if uf_shift_id and uf_shift_id.startswith("UF_"):
        fields[upper_to_camel(uf_shift_id)] = shift_id
    if uf_resource_type and uf_resource_type.startswith("UF_"):
        fields[upper_to_camel(uf_resource_type)] = "EQUIP"
    if uf_equip_type and uf_equip_type.startswith("UF_"):
        fields[upper_to_camel(uf_equip_type)] = "Экскаватор JCB"
    if uf_equip_hours and uf_equip_hours.startswith("UF_"):
        fields[upper_to_camel(uf_equip_hours)] = 6.0
    if uf_equip_rate_type and uf_equip_rate_type.startswith("UF_"):
        fields[upper_to_camel(uf_equip_rate_type)] = "HOUR"
    if uf_equip_rate and uf_equip_rate.startswith("UF_"):
        fields[upper_to_camel(uf_equip_rate)] = 3500.0
    
    return fields


def res_fields_mat(shift_id: int) -> dict:
    """Создает поля для материала. Если UF поля не найдены, возвращает только базовые."""
    from app.bitrix_field_map import resolve_code, upper_to_camel
    e = "Ресурс"
    fields = {}
    
    # Пробуем разрешить UF коды
    uf_shift_id = resolve_code(e, "UF_SHIFT_ID")
    uf_resource_type = resolve_code(e, "UF_RESOURCE_TYPE")
    uf_mat_type = resolve_code(e, "UF_MAT_TYPE")
    uf_mat_qty = resolve_code(e, "UF_MAT_QTY")
    uf_mat_unit = resolve_code(e, "UF_MAT_UNIT")
    uf_mat_price = resolve_code(e, "UF_MAT_PRICE")
    
    # Конвертируем в camelCase для Bitrix24 API
    if uf_shift_id and uf_shift_id.startswith("UF_"):
        fields[upper_to_camel(uf_shift_id)] = shift_id
    if uf_resource_type and uf_resource_type.startswith("UF_"):
        fields[upper_to_camel(uf_resource_type)] = "MAT"
    if uf_mat_type and uf_mat_type.startswith("UF_"):
        fields[upper_to_camel(uf_mat_type)] = "Щебень 20–40"
    if uf_mat_qty and uf_mat_qty.startswith("UF_"):
        fields[upper_to_camel(uf_mat_qty)] = 18.0
    if uf_mat_unit and uf_mat_unit.startswith("UF_"):
        fields[upper_to_camel(uf_mat_unit)] = "т"
    if uf_mat_price and uf_mat_price.startswith("UF_"):
        fields[upper_to_camel(uf_mat_price)] = 1200.0
    
    return fields


def timesheet_fields(shift_id: int) -> dict:
    """Создает поля для табеля. Если UF поля не найдены, возвращает только базовые."""
    from app.bitrix_field_map import resolve_code, upper_to_camel
    e = "Табель"
    fields = {}
    
    # Пробуем разрешить UF коды
    uf_shift_id = resolve_code(e, "UF_SHIFT_ID")
    uf_worker = resolve_code(e, "UF_WORKER")
    uf_hours = resolve_code(e, "UF_HOURS")
    uf_rate = resolve_code(e, "UF_RATE")
    
    # Конвертируем в camelCase для Bitrix24 API
    if uf_shift_id and uf_shift_id.startswith("UF_"):
        fields[upper_to_camel(uf_shift_id)] = shift_id
    if uf_worker and uf_worker.startswith("UF_"):
        fields[upper_to_camel(uf_worker)] = "Бригада №2"
    if uf_hours and uf_hours.startswith("UF_"):
        fields[upper_to_camel(uf_hours)] = 8.0
    if uf_rate and uf_rate.startswith("UF_"):
        fields[upper_to_camel(uf_rate)] = 600.0
    
    return fields


@router.message(Command("debug_w3"))
async def debug_w3(m: Message, state: FSMContext = None):
    """Debug команда - доступна только в режиме DEBUG."""
    from app.config import get_settings
    settings = get_settings()
    
    if not settings.DEBUG:
        log.warning(f"User {m.from_user.id} tried to use debug_w3 in production")
        await m.answer("❌ Команда недоступна в продакшене.")
        return
    
    log.info(f"/debug_w3 вызвана пользователем {m.from_user.id}")
    try:
        # Очищаем FSM состояние если есть
        if state:
            await state.clear()
            log.debug("FSM состояние очищено")
        
        if not ENTITY_RESOURCE:
            log.warning("ENTITY_RESOURCE не задан")
            await m.answer("ENTITY_RESOURCE не задан в .env")
            return
        
        log.info(f"Создание ресурсов для смены {DEBUG_SHIFT_ID}")
        fields_equip = res_fields_equip(DEBUG_SHIFT_ID)
        fields_mat = res_fields_mat(DEBUG_SHIFT_ID)
        log.debug(f"Поля техники: {fields_equip}")
        log.debug(f"Поля материала: {fields_mat}")
        
        log.info("Отправка запроса на создание техники...")
        r1 = await bx_add(ENTITY_RESOURCE, {"TITLE": "Экскаватор JCB / 6 ч", **fields_equip})
        log.info(f"Ответ от Bitrix (техника): {r1}")
        
        log.info("Отправка запроса на создание материала...")
        r2 = await bx_add(ENTITY_RESOURCE, {"TITLE": "Щебень 20–40 / 18 т", **fields_mat})
        log.info(f"Ответ от Bitrix (материал): {r2}")
        
        id1 = r1.get("item", {}).get("id") or r1.get("id")
        id2 = r2.get("item", {}).get("id") or r2.get("id")
        
        log.info(f"Ресурсы созданы: техника={id1}, материал={id2}")
        
        response_text = f"✅ Ресурсы созданы:\n— техника id={id1}\n— материал id={id2}"
        log.info(f"Отправка ответа пользователю: {response_text}")
        await m.answer(response_text)
        log.info("Ответ отправлен успешно")
        
    except Exception as e:
        log.error(f"Ошибка в /debug_w3: {e}", exc_info=True)
        error_text = f"❌ /debug_w3: {e}"
        log.info(f"Отправка сообщения об ошибке: {error_text}")
        try:
            await m.answer(error_text)
            log.info("Сообщение об ошибке отправлено")
        except Exception as send_error:
            log.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)


@router.message(Command("debug_w4"))
async def debug_w4(m: Message, state: FSMContext = None):
    """Debug команда - доступна только в режиме DEBUG."""
    from app.config import get_settings
    settings = get_settings()
    
    if not settings.DEBUG:
        log.warning(f"User {m.from_user.id} tried to use debug_w4 in production")
        await m.answer("❌ Команда недоступна в продакшене.")
        return
    
    log.info(f"/debug_w4 вызвана пользователем {m.from_user.id}")
    try:
        # Очищаем FSM состояние если есть
        if state:
            await state.clear()
            log.debug("FSM состояние очищено")
        
        if not ENTITY_TIMESHEET:
            log.warning("ENTITY_TIMESHEET не задан")
            await m.answer("ENTITY_TIMESHEET не задан в .env")
            return
        
        log.info(f"Создание табеля для смены {DEBUG_SHIFT_ID}")
        fields = timesheet_fields(DEBUG_SHIFT_ID)
        log.debug(f"Поля табеля: {fields}")
        
        log.info("Отправка запроса на создание табеля...")
        r = await bx_add(ENTITY_TIMESHEET, {"TITLE": "Бригада №2 / 8 ч", **fields})
        log.info(f"Ответ от Bitrix (табель): {r}")
        
        tid = r.get("item", {}).get("id") or r.get("id")
        
        log.info(f"Табель создан: id={tid}")
        
        response_text = f"✅ Табель создан: id={tid}"
        log.info(f"Отправка ответа пользователю: {response_text}")
        await m.answer(response_text)
        log.info("Ответ отправлен успешно")
        
    except Exception as e:
        log.error(f"Ошибка в /debug_w4: {e}", exc_info=True)
        error_text = f"❌ /debug_w4: {e}"
        log.info(f"Отправка сообщения об ошибке: {error_text}")
        try:
            await m.answer(error_text)
            log.info("Сообщение об ошибке отправлено")
        except Exception as send_error:
            log.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)


# Временный отладочный хэндлер удалён - может конфликтовать с FSM состояниями
# Используйте команды напрямую: /start /debug_w3 /debug_w4

