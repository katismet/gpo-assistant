"""Сбор данных для генерации ЛПА из Bitrix24."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.http_client import bx
from app.services.bitrix_ids import (
    SHIFT_ETID,
    RESOURCE_ETID,
    TIMESHEET_ETID,
    OBJECT_ETID,
)
from app.bitrix_field_map import upper_to_camel
from app.services.shift_meta import shift_type_display_label
from datetime import datetime

logger = logging.getLogger("gpo.lpa_builder")


async def _extract_shift_photos(item: dict, shift_bitrix_id: int) -> List[Dict[str, Any]]:
    """Извлекает фото из поля ufCrm7UfShiftPhotos.
    
    Поле single (multiple=False), но Bitrix может возвращать строку "Array".
    Возвращает список словарей с ключами id и url.
    """
    v = item.get("ufCrm7UfShiftPhotos") or item.get("UF_CRM_7_UF_SHIFT_PHOTOS")
    
    if not v:
        return []
    
    # Если поле вернулось как строка "Array", делаем повторный запрос с полным select
    if v == "Array" or (isinstance(v, str) and v.lower() == "array"):
        logger.info(f"[LPA] Photo field returned as 'Array', fetching directly")
        try:
            result = await bx("crm.item.get", {
                "entityTypeId": SHIFT_ETID,
                "id": shift_bitrix_id,
                "select": ["id", "*", "ufCrm%"]
            })
            if result:
                item_full = result.get("item", result) if isinstance(result, dict) else result
                v = item_full.get("ufCrm7UfShiftPhotos") or item_full.get("UF_CRM_7_UF_SHIFT_PHOTOS")
        except Exception as e:
            logger.warning(f"[LPA] Could not fetch photos directly: {e}")
    
    if not v or v == "Array":
        return []
    
    # Обрабатываем разные форматы: список ID, список объектов, один объект
    file_ids = []
    if isinstance(v, list):
        for f in v:
            if isinstance(f, int):
                file_ids.append(f)
            elif isinstance(f, dict):
                file_id = f.get("id") or f.get("ID")
                if file_id:
                    file_ids.append(file_id)
    elif isinstance(v, (int, str)):
        try:
            file_ids.append(int(v))
        except (ValueError, TypeError):
            pass
    
    # Для каждого ID получаем downloadUrl через disk.file.get
    out = []
    for fid in file_ids:
        try:
            file_data = await bx("disk.file.get", {"id": fid})
            if file_data:
                download_url = (
                    file_data.get("downloadUrl") or 
                    file_data.get("DOWNLOAD_URL") or
                    file_data.get("downloadUrlDirect") or
                    file_data.get("DOWNLOAD_URL_DIRECT") or
                    file_data.get("detailUrl") or
                    file_data.get("DETAIL_URL")
                )
                if download_url:
                    out.append({
                        "id": fid,
                        "url": download_url
                    })
        except Exception as e:
            logger.warning(f"[LPA] Could not get file info for {fid}: {e}")
    
    return out


def read_field(item: Dict[str, Any], field_name: str) -> Any:
    """Читает поле из item, проверяя UPPER, camelCase и list варианты."""
    if not isinstance(item, dict):
        return None
    
    # Пробуем разные варианты имени поля
    variants = [
        field_name,  # Оригинальное имя
        upper_to_camel(field_name),  # camelCase
        field_name.upper(),  # UPPER
    ]
    
    for variant in variants:
        if variant in item:
            value = item[variant]
            # Если это список с одним элементом - возвращаем элемент
            if isinstance(value, list) and len(value) == 1:
                return value[0]
            return value
    
    return None


async def _fetch_shift_item(shift_id: int) -> Dict[str, Any]:
    """Получает смену из Bitrix24 с полным select для избежания проблемы "Array"."""
    if not shift_id:
        return {}
    try:
        # ВАЖНО: используем select с ["id", "*", "ufCrm%"] чтобы поле привязки не схлопывалось в "Array"
        result = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id,
            "select": ["id", "*", "ufCrm%"]  # Получаем все поля, включая пользовательские
        })
        logger.info(f"[LPA] Bitrix shift get: {shift_id}")
        if isinstance(result, dict):
            item = result.get("item", result) or {}
            return item
        else:
            logger.warning(f"[LPA] Bitrix shift get: {shift_id} - unexpected type: {type(result)}")
    except Exception as e:
        logger.warning(f"[LPA] Bitrix shift get: {shift_id} - Failed: {e}")
    return {}


async def _fetch_resources(shift_id: int) -> List[Dict[str, Any]]:
    """Получает ресурсы (технику и материалы) для смены."""
    resources: List[Dict[str, Any]] = []
    if not shift_id:
        return resources
    
    try:
        result = await bx("crm.item.list", {
            "entityTypeId": RESOURCE_ETID,
            "filter": {"ufCrm9UfShiftId": shift_id},
            "select": ["id", "*", "ufCrm%"]
        })
        
        items = result.get("items", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
        resources = items if isinstance(items, list) else []
        logger.info(f"[LPA] Loaded {len(resources)} resources for shift {shift_id}")
    except Exception as e:
        logger.warning(f"[LPA] Failed to fetch resources: {e}")
    
    return resources


async def _fetch_timesheet(shift_id: int) -> List[Dict[str, Any]]:
    """Получает табель для смены."""
    timesheets: List[Dict[str, Any]] = []
    if not shift_id:
        return timesheets
    
    try:
        result = await bx("crm.item.list", {
            "entityTypeId": TIMESHEET_ETID,
            "filter": {"ufCrm11UfShiftId": shift_id},
            "select": ["id", "*", "ufCrm%"]
        })
        
        items = result.get("items", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
        timesheets = items if isinstance(items, list) else []
        logger.info(f"[LPA] Loaded {len(timesheets)} timesheet entries for shift {shift_id}")
    except Exception as e:
        logger.warning(f"[LPA] Failed to fetch timesheet: {e}")
    
    return timesheets


def _parse_json_field(raw: Any) -> Dict[str, Any]:
    """Парсит JSON поле из Bitrix24.
    
    Поддерживает форматы:
    - [] (пустой список)
    - ['{"tasks": [...], ...}'] (список с JSON-строкой)
    - '{"tasks": [...], ...}' (просто строка JSON)
    - {"tasks": [...], ...} (уже dict)
    """
    if not raw:
        return {}
    
    try:
        # Если это уже dict
        if isinstance(raw, dict):
            return raw
        
        # Если это список
        if isinstance(raw, list):
            if not raw:
                return {}
            # Берем первый элемент
            first = raw[0]
            if isinstance(first, str):
                # Это JSON-строка
                return json.loads(first)
            elif isinstance(first, dict):
                # Уже dict
                return first
            else:
                return {}
        
        # Если это строка
        if isinstance(raw, str):
            # Пробуем распарсить как JSON
            return json.loads(raw)
        
        return {}
    except Exception as e:
        logger.warning(f"[LPA] JSON parse failed for {raw!r}: {e}")
        return {}


async def get_object_name_for_shift(shift_item: Dict[str, Any], shift_bitrix_id: int, plan_json: Optional[Dict[str, Any]] = None) -> str:
    """Получает название объекта для смены.
    
    Приоритет:
    1. plan_json.meta.object_name (данные из бота)
    2. Локальная БД (если есть связь)
    3. Поле привязки из Bitrix24 (формат "T1046_51" или ["T1046_51"])
    4. "Не указан"
    """
    # 1. Пробуем получить из plan_json.meta (данные из бота)
    if plan_json and isinstance(plan_json, dict):
        meta = plan_json.get("meta", {})
        if isinstance(meta, dict):
            object_name_from_meta = meta.get("object_name")
            if object_name_from_meta:
                logger.info(f"[LPA] Got object name from plan_json.meta: {object_name_from_meta}")
                return str(object_name_from_meta).strip()
            # Если есть object_bitrix_id, можем получить название из Bitrix24
            object_bitrix_id = meta.get("object_bitrix_id")
            if object_bitrix_id:
                try:
                    obj_data = await bx("crm.item.get", {
                        "entityTypeId": OBJECT_ETID,
                        "id": int(object_bitrix_id)
                    })
                    if obj_data:
                        obj_item = obj_data.get("item", obj_data)
                        obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{object_bitrix_id}"
                        logger.info(f"[LPA] Got object name from Bitrix24 via plan_json.meta: {obj_title}")
                        return obj_title
                except Exception as e:
                    logger.warning(f"[LPA] Could not get object name from Bitrix24 via meta: {e}")
    
    # 2. Пробуем получить из локальной БД
    try:
        from app.db import session_scope
        from app.models import Shift, Object
        
        with session_scope() as s:
            shift = s.query(Shift).filter(Shift.bitrix_id == shift_bitrix_id).first()
            logger.info(f"[LPA] Local DB shift lookup: shift={shift}, bitrix_id={shift_bitrix_id}")
            if shift:
                logger.info(f"[LPA] Local shift found: id={shift.id}, object_id={shift.object_id}")
                if shift.object_id:
                    obj = s.query(Object).filter(Object.id == shift.object_id).first()
                    logger.info(f"[LPA] Local object lookup: obj={obj}, object_id={shift.object_id}")
                    if obj:
                        # Если есть название в локальной БД
                        if obj.name:
                            logger.info(f"[LPA] Got object name from local DB: {obj.name}")
                            return obj.name
                        # Если есть bitrix_id, получаем название из Bitrix24
                        if obj.bitrix_id:
                            try:
                                obj_data = await bx("crm.item.get", {
                                    "entityTypeId": OBJECT_ETID,
                                    "id": obj.bitrix_id
                                })
                                if obj_data:
                                    obj_item = obj_data.get("item", obj_data)
                                    obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{obj.bitrix_id}"
                                    logger.info(f"[LPA] Got object name from Bitrix24 via local DB: {obj_title}")
                                    return obj_title
                            except Exception as e:
                                logger.warning(f"[LPA] Could not get object name from Bitrix24: {e}")
                    else:
                        # Объект не найден в локальной БД, но object_id есть
                        # Пробуем получить объект из Bitrix24 напрямую, используя известные ID
                        logger.info(f"[LPA] Object {shift.object_id} not found in local DB, trying Bitrix24 directly")
                        # Пробуем получить через поле привязки из Bitrix24 (будет обработано ниже)
                else:
                    logger.info(f"[LPA] Local shift has no object_id")
            else:
                logger.info(f"[LPA] No local shift found for bitrix_id={shift_bitrix_id}")
    except Exception as e:
        logger.warning(f"[LPA] Could not get object from local DB: {e}", exc_info=True)
    
    # 3. Пробуем получить из поля привязки Bitrix24
    object_field = (
        shift_item.get("ufCrm7UfCrmObject") or
        shift_item.get("UF_CRM_7_UF_CRM_OBJECT") or
        read_field(shift_item, "UF_CRM_7_UF_CRM_OBJECT")
    )
    
    # Если поле вернулось как "Array", делаем повторный запрос
    if object_field == "Array" or (isinstance(object_field, str) and object_field.lower() == "array"):
        logger.info(f"[LPA] Object field returned as 'Array', fetching with full select")
        try:
            result = await bx("crm.item.get", {
                "entityTypeId": SHIFT_ETID,
                "id": shift_bitrix_id,
                "select": ["id", "*", "ufCrm%"]
            })
            if result:
                item_full = result.get("item", result) if isinstance(result, dict) else result
                object_field = (
                    item_full.get("ufCrm7UfCrmObject") or
                    item_full.get("UF_CRM_7_UF_CRM_OBJECT")
                )
        except Exception as e:
            logger.warning(f"[LPA] Could not fetch object field directly: {e}")
    
    # Парсим поле привязки (формат "T1046_51" или ["T1046_51"] или "D_51")
    if object_field and object_field != "Array":
        try:
            logger.info(f"[LPA] Parsing object_field: {object_field} (type: {type(object_field)})")
            # Нормализуем в список
            links = []
            if isinstance(object_field, list):
                links = object_field
            elif isinstance(object_field, str):
                links = [object_field]
            
            if links:
                # Берем первую запись
                raw = links[0]
                logger.info(f"[LPA] Parsing raw link: {raw} (type: {type(raw)})")
                
                if isinstance(raw, str):
                    # Формат "T1046_51": T - префикс, 1046 - entityTypeId, 51 - itemId
                    if raw.startswith("T"):
                        parts = raw[1:].split("_", 1)  # Убираем 'T' и разбиваем по '_'
                        if len(parts) == 2:
                            entity_type_id = int(parts[0])
                            item_id = int(parts[1])
                            
                            logger.info(f"[LPA] Extracted: entityTypeId={entity_type_id}, itemId={item_id}")
                            
                            # Получаем название объекта
                            obj_data = await bx("crm.item.get", {
                                "entityTypeId": entity_type_id,
                                "id": item_id
                            })
                            if obj_data:
                                obj_item = obj_data.get("item", obj_data)
                                obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{item_id}"
                                logger.info(f"[LPA] Got object name from Bitrix24 link: {obj_title}")
                                return obj_title
                    # Формат "D_51": D - префикс для динамических сущностей, 51 - itemId
                    elif raw.startswith("D_"):
                        item_id = int(raw[2:])  # Убираем 'D_'
                        logger.info(f"[LPA] Extracted from D_ format: itemId={item_id}")
                        
                        # Пробуем получить объект с entityTypeId=OBJECT_ETID
                        obj_data = await bx("crm.item.get", {
                            "entityTypeId": OBJECT_ETID,
                            "id": item_id
                        })
                        if obj_data:
                            obj_item = obj_data.get("item", obj_data)
                            obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{item_id}"
                            logger.info(f"[LPA] Got object name from Bitrix24 link (D_ format): {obj_title}")
                            return obj_title
        except Exception as e:
            logger.warning(f"[LPA] Could not parse object link field: {e}", exc_info=True)
    
    # 3. Fallback
    logger.warning(f"[LPA] Could not get object name, using fallback")
    return "Не указан"


async def collect_lpa_data(
    shift_bitrix_id: Optional[int],
    *,
    fallback_plan: Optional[Dict[str, Any]] = None,
    fallback_fact: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Собирает данные для генерации ЛПА из Bitrix24.
    Возвращает контекст для docxtpl и список фото.
    """
    meta = meta or {}
    
    # Загружаем смену из Bitrix24
    shift_item = await _fetch_shift_item(shift_bitrix_id) if shift_bitrix_id else {}
    
    if not shift_item:
        logger.warning(f"[LPA] Shift {shift_bitrix_id} not found in Bitrix24")
    
    # Читаем план и факт из Bitrix24 (только JSON поля)
    plan_raw = (
        read_field(shift_item, "UF_CRM_7_UF_PLAN_JSON") or 
        read_field(shift_item, "ufCrm7UfPlanJson") or
        None
    )
    fact_raw = (
        read_field(shift_item, "UF_CRM_7_UF_FACT_JSON") or 
        read_field(shift_item, "ufCrm7UfFactJson") or
        None
    )
    
    # Логируем сырые данные
    logger.info(f"[LPA] ===== DATA SOURCE TRACE =====")
    logger.info(f"[LPA] shift_bitrix_id={shift_bitrix_id}")
    logger.info(f"[LPA] plan_raw type: {type(plan_raw)}, is_empty: {not plan_raw}")
    logger.info(f"[LPA] fact_raw type: {type(fact_raw)}, is_empty: {not fact_raw}")
    logger.info(f"[LPA] fallback_plan provided: {fallback_plan is not None}")
    logger.info(f"[LPA] fallback_fact provided: {fallback_fact is not None}")
    
    # Парсим JSON поля через универсальный парсер
    plan_json = _parse_json_field(plan_raw) if plan_raw else {}
    fact_json = _parse_json_field(fact_raw) if fact_raw else {}
    
    # Диагностика plan_json (только ключевая информация)
    plan_from_bitrix = bool(plan_json)
    fact_from_bitrix = bool(fact_json)
    
    if isinstance(plan_json, dict):
        if "meta" in plan_json:
            meta_in_plan = plan_json.get("meta", {})
            object_bitrix_id_meta = meta_in_plan.get("object_bitrix_id")
            object_name_meta = meta_in_plan.get("object_name")
            logger.info(f"[LPA] ⚠️ PLAN FROM BITRIX24: plan_json.meta: object_bitrix_id={object_bitrix_id_meta}, object_name={object_name_meta}")
        if "total_plan" in plan_json:
            logger.info(f"[LPA] ⚠️ PLAN FROM BITRIX24: plan_json.total_plan={plan_json.get('total_plan')}")
        if "tasks" in plan_json:
            logger.info(f"[LPA] ⚠️ PLAN FROM BITRIX24: plan_json.tasks count={len(plan_json.get('tasks', []))}")
            # Логируем первые 3 задачи для диагностики
            tasks_list = plan_json.get('tasks', [])[:3]
            for i, task in enumerate(tasks_list, 1):
                logger.info(f"[LPA] ⚠️ PLAN FROM BITRIX24: task{i}: name={task.get('name')}, plan={task.get('plan')}")
    
    if isinstance(fact_json, dict):
        if "total_fact" in fact_json:
            logger.info(f"[LPA] ⚠️ FACT FROM BITRIX24: fact_json.total_fact={fact_json.get('total_fact')}")
        if "tasks" in fact_json:
            logger.info(f"[LPA] ⚠️ FACT FROM BITRIX24: fact_json.tasks count={len(fact_json.get('tasks', []))}")
            # Логируем первые 3 задачи для диагностики
            tasks_list = fact_json.get('tasks', [])[:3]
            for i, task in enumerate(tasks_list, 1):
                logger.info(f"[LPA] ⚠️ FACT FROM BITRIX24: task{i}: name={task.get('name')}, fact={task.get('fact')}")
    
    # Fallback на локальные данные, если JSON пустые
    if not plan_json and fallback_plan:
        plan_json = fallback_plan
        logger.info(f"[LPA] ✅ USING FALLBACK PLAN DATA (Bitrix24 plan was empty)")
        logger.info(f"[LPA] fallback_plan keys: {list(fallback_plan.keys())[:10] if isinstance(fallback_plan, dict) else 'not dict'}")
        if isinstance(fallback_plan, dict) and "meta" in fallback_plan:
            logger.info(f"[LPA] fallback_plan.meta: {fallback_plan.get('meta')}")
        if isinstance(fallback_plan, dict) and "tasks" in fallback_plan:
            tasks_list = fallback_plan.get('tasks', [])[:3]
            for i, task in enumerate(tasks_list, 1):
                logger.info(f"[LPA] ✅ FALLBACK PLAN: task{i}: name={task.get('name')}, plan={task.get('plan')}")
    elif plan_from_bitrix:
        logger.info(f"[LPA] ⚠️ WARNING: Using plan from Bitrix24 (may contain old data), fallback_plan was ignored!")
    
    if not fact_json and fallback_fact:
        fact_json = fallback_fact
        logger.info(f"[LPA] ✅ USING FALLBACK FACT DATA (Bitrix24 fact was empty)")
        if isinstance(fallback_fact, dict) and "tasks" in fallback_fact:
            tasks_list = fallback_fact.get('tasks', [])[:3]
            for i, task in enumerate(tasks_list, 1):
                logger.info(f"[LPA] ✅ FALLBACK FACT: task{i}: name={task.get('name')}, fact={task.get('fact')}")
    elif fact_from_bitrix:
        logger.info(f"[LPA] ⚠️ WARNING: Using fact from Bitrix24 (may contain old data), fallback_fact was ignored!")
    
    logger.info(f"[LPA] ===== END DATA SOURCE TRACE =====")
    
    # Нормализуем структуру: всегда должны быть tasks, total_plan, total_fact
    if isinstance(plan_json, dict) and "tasks" not in plan_json:
        # Старый формат: {"земляные": 110, ...}
        logger.info(f"[LPA] Normalizing old plan format")
        plan_tasks_list = []
        for k, v in plan_json.items():
            # Фильтруем служебные ключи
            if k.lower() in {"tasks", "total_plan", "total_fact", "object_name", "date", 
                             "section", "foreman", "shift_type", "type", "plan_total", 
                             "fact_total", "downtime_reason", "photos"}:
                continue
            if not isinstance(v, (int, float, str)):
                continue
            try:
                num_val = float(v)
                if num_val > 0:
                    plan_tasks_list.append({
                        "name": str(k).strip(),
                        "unit": "ед.",
                        "plan": num_val,
                        "executor": "Бригада",
                    })
            except (ValueError, TypeError):
                continue
        if plan_tasks_list:
            plan_json = {"tasks": plan_tasks_list, "total_plan": sum(t["plan"] for t in plan_tasks_list)}
            logger.info(f"[LPA] Normalized plan: {len(plan_tasks_list)} tasks")
    
    if isinstance(fact_json, dict) and "tasks" not in fact_json:
        # Старый формат для факта
        logger.info(f"[LPA] Normalizing old fact format")
        fact_tasks_list = []
        for k, v in fact_json.items():
            if k.lower() in {"tasks", "total_plan", "total_fact", "object_name", "date", 
                             "section", "foreman", "shift_type", "type", "plan_total", 
                             "fact_total", "downtime_reason", "photos"}:
                continue
            if not isinstance(v, (int, float, str)):
                continue
            try:
                num_val = float(v)
                if num_val > 0:
                    fact_tasks_list.append({
                        "name": str(k).strip(),
                        "unit": "ед.",
                        "fact": num_val,
                        "executor": "Бригада",
                    })
            except (ValueError, TypeError):
                continue
        if fact_tasks_list:
            fact_json = {"tasks": fact_tasks_list, "total_fact": sum(t["fact"] for t in fact_tasks_list)}
            logger.info(f"[LPA] Normalized fact: {len(fact_tasks_list)} tasks")
    
    # Загружаем ресурсы и табель
    logger.info(f"[LPA] ===== LOADING RESOURCES AND TIMESHEET =====")
    resources = await _fetch_resources(shift_bitrix_id) if shift_bitrix_id else []
    timesheets = await _fetch_timesheet(shift_bitrix_id) if shift_bitrix_id else []
    logger.info(f"[LPA] ⚠️ RESOURCES FROM BITRIX24: count={len(resources)}")
    if resources:
        for i, r in enumerate(resources[:3], 1):
            mat_type = r.get("ufCrm9UfMatType") or r.get("UF_CRM_9_UF_MAT_TYPE") or ""
            equip_type = r.get("ufCrm9UfEquipType") or r.get("UF_CRM_9_UF_EQUIP_TYPE") or ""
            logger.info(f"[LPA] ⚠️ RESOURCE {i}: mat_type={mat_type}, equip_type={equip_type}")
    logger.info(f"[LPA] ⚠️ TIMESHEET FROM BITRIX24: count={len(timesheets)}")
    if timesheets:
        for i, t in enumerate(timesheets[:3], 1):
            worker = t.get("ufCrm11UfWorker") or t.get("UF_CRM_11_UF_WORKER") or ""
            hours = t.get("ufCrm11UfHours") or t.get("UF_CRM_11_UF_HOURS") or 0
            logger.info(f"[LPA] ⚠️ TIMESHEET {i}: worker={worker}, hours={hours}")
    logger.info(f"[LPA] ===== END LOADING RESOURCES AND TIMESHEET =====")
    
    # Загружаем фото из Bitrix24 поля
    photos_uf = await _extract_shift_photos(shift_item, shift_bitrix_id) if shift_bitrix_id else []
    
    # Fallback к fact_json.photos (telegram file_id), если UF пусто
    photos = photos_uf
    if not photos:
        ph = fact_json.get("photos") or [] if isinstance(fact_json, dict) else []
        photos = [{"tg_file_id": x} for x in ph if isinstance(x, str)]
        if photos:
            logger.info(f"[LPA] Found {len(photos)} Telegram photo IDs in fact_json.photos (fallback)")
    
    logger.info(f"[LPA] Loaded {len(photos)} photos for shift {shift_bitrix_id} (UF: {len(photos_uf)}, TG: {len(photos) - len(photos_uf)})")
    
    # Получаем название объекта с приоритетом plan_json.meta
    object_name = "Не указан"
    object_bitrix_id_from_meta = None
    
    # 1. ПРИОРИТЕТ: plan_json.meta (данные из сохраненного плана в Bitrix)
    if isinstance(plan_json, dict) and "meta" in plan_json:
        meta_in_plan = plan_json.get("meta", {})
        if isinstance(meta_in_plan, dict):
            # Сначала пробуем object_name из meta
            object_name_from_meta = meta_in_plan.get("object_name")
            if object_name_from_meta:
                object_name = str(object_name_from_meta).strip()
                logger.info(f"[LPA] Got object_name from plan_json.meta: {object_name}")
            
            # Сохраняем object_bitrix_id из meta для дальнейшего использования
            object_bitrix_id_from_meta = meta_in_plan.get("object_bitrix_id")
            if object_bitrix_id_from_meta:
                logger.info(f"[LPA] Got object_bitrix_id from plan_json.meta: {object_bitrix_id_from_meta}")
    
    # 2. Fallback: если object_name не найден в meta, но есть object_bitrix_id - получаем из Bitrix
    if object_name == "Не указан" and object_bitrix_id_from_meta:
        try:
            obj_data = await bx("crm.item.get", {
                "entityTypeId": OBJECT_ETID,
                "id": int(object_bitrix_id_from_meta)
            })
            if obj_data:
                obj_item = obj_data.get("item", obj_data) if isinstance(obj_data, dict) else obj_data
                obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{object_bitrix_id_from_meta}"
                object_name = obj_title
                logger.info(f"[LPA] Got object_name from Bitrix24 via plan_json.meta.object_bitrix_id: {object_name}")
        except Exception as e:
            logger.warning(f"[LPA] Could not get object name from Bitrix24 via meta: {e}")
    
    # 3. Fallback: get_object_name_for_shift (локальная БД, Bitrix24) - только если meta не помогло
    if object_name == "Не указан" and shift_bitrix_id:
        object_name_fallback = await get_object_name_for_shift(shift_item, shift_bitrix_id, plan_json)
        if object_name_fallback and object_name_fallback != "Не указан":
            object_name = object_name_fallback
            logger.info(f"[LPA] Got object_name from fallback (local DB/Bitrix): {object_name}")
    
    # 4. Fallback: meta параметр функции
    if object_name == "Не указан":
        object_name = meta.get("object_name") or "Не указан"
        if object_name != "Не указан":
            logger.info(f"[LPA] Got object_name from meta parameter: {object_name}")
    
    logger.info(f"[LPA] Final object_name={object_name}, object_bitrix_id={object_bitrix_id_from_meta}")
    
    # Читаем метаданные
    date_field = read_field(shift_item, "UF_CRM_7_UF_CRM_DATE")
    
    # Форматируем дату
    date_str = meta.get("date") or ""
    if date_field:
        try:
            if isinstance(date_field, str):
                dt = datetime.fromisoformat(date_field.replace("Z", "+00:00"))
                date_str = dt.strftime("%d.%m.%Y")
        except:
            pass
    
    section = meta.get("section") or plan_json.get("section") or "Строительство"
    foreman = meta.get("foreman") or plan_json.get("foreman") or "Прораб"
    shift_type_code = (
        meta.get("shift_type")
        or plan_json.get("shift_type")
        or fact_json.get("shift_type")
        or read_field(shift_item, "UF_CRM_7_UF_SHIFT_TYPE")
        or "Не указана"
    )
    shift_type = shift_type_display_label(shift_type_code)
    
    # Формируем структурированный объект для lpa_pdf.py
    # 1. Задачи (объединяем план и факт)
    tasks = []
    
    # Обрабатываем задачи из плана
    if isinstance(plan_json, dict) and "tasks" in plan_json:
        for t in plan_json["tasks"]:
            name = t.get("name") or ""
            if not name:
                continue
            # Фильтруем служебные поля
            name_lower = name.lower().strip()
            if name_lower in {"tasks", "total_plan", "total_fact", "object_name", "date", 
                             "section", "foreman", "shift_type", "type", "plan_total", 
                             "fact_total", "downtime_reason", "photos"}:
                continue
            plan = float(t.get("plan") or 0)
            fact = 0.0
            unit = t.get("unit", "ед.")
            executor = t.get("executor", "Бригада")
            reason = ""
            
            # Ищем соответствующий факт
            if isinstance(fact_json, dict) and "tasks" in fact_json:
                for f in fact_json["tasks"]:
                    if f.get("name") == name:
                        fact = float(f.get("fact", 0))
                        reason = f.get("reason", "")
                        if f.get("unit"):
                            unit = f.get("unit")
                        if f.get("executor"):
                            executor = f.get("executor")
                        break
            
            # Определяем причину отклонения
            if not reason and abs(plan - fact) > 0.01:
                if plan == 0:
                    reason = "Работа вне плана"
                else:
                    reason = "Отклонение от плана"
            
            tasks.append({
                "name": name,
                "unit": unit,
                "plan": plan,
                "fact": fact,
                "executor": executor,
                "reason": reason,
            })
    
    # Добавляем задачи из факта, которых нет в плане
    if isinstance(fact_json, dict) and "tasks" in fact_json:
        plan_task_names = {t["name"] for t in tasks}
        for f in fact_json["tasks"]:
            name = f.get("name") or ""
            if not name:
                continue
            # Фильтруем служебные поля
            name_lower = name.lower().strip()
            if name_lower in {"tasks", "total_plan", "total_fact", "object_name", "date", 
                             "section", "foreman", "shift_type", "type", "plan_total", 
                             "fact_total", "downtime_reason", "photos"}:
                continue
            if name and name not in plan_task_names:
                fact = float(f.get("fact", 0))
                if fact > 0:
                    tasks.append({
                        "name": name,
                        "unit": f.get("unit", "ед."),
                        "plan": 0.0,
                        "fact": fact,
                        "executor": f.get("executor", "Бригада"),
                        "reason": "Работа вне плана",
                    })
    
    # 2. Ресурсы → техника / материалы
    from app.services.resource_meta import resource_type_display_label
    tech = []
    materials = []
    for r in resources:
        rtype_raw = r.get("ufCrm9UfResourceType") or r.get("UF_CRM_9_UF_RESOURCE_TYPE")
        rtype_str = ""
        if isinstance(rtype_raw, str):
            rtype_str = rtype_raw
        elif isinstance(rtype_raw, dict):
            value = rtype_raw.get("value") or rtype_raw.get("VALUE")
            rtype_str = str(value or "")
        elif rtype_raw is not None:
            rtype_str = str(rtype_raw)
        
        # Определяем тип ресурса: если есть equip_type - это техника, иначе - материал
        # Также проверяем по человекочитаемому значению из Bitrix
        is_equipment = (
            bool(r.get("ufCrm9UfEquipType") or r.get("UF_CRM_9_UF_EQUIP_TYPE"))
            or "техника" in rtype_str.lower()
            or "equip" in rtype_str.lower()
            or "tech" in rtype_str.lower()
        )

        if is_equipment:
            tech.append({
                "name": r.get("ufCrm9UfEquipType") or r.get("UF_CRM_9_UF_EQUIP_TYPE") or "",
                "hours": r.get("ufCrm9UfEquipHours") or r.get("UF_CRM_9_UF_EQUIP_HOURS") or "",
                "comment": r.get("ufCrm9UfResComment") or r.get("UF_CRM_9_UF_RES_COMMENT") or "",
            })
        else:
            qty = float(r.get("ufCrm9UfMatQty") or r.get("UF_CRM_9_UF_MAT_QTY") or 0)
            price = float(r.get("ufCrm9UfMatPrice") or r.get("UF_CRM_9_UF_MAT_PRICE") or 0)
            materials.append({
                "name": r.get("ufCrm9UfMatType") or r.get("UF_CRM_9_UF_MAT_TYPE") or "",
                "unit": r.get("ufCrm9UfMatUnit") or r.get("UF_CRM_9_UF_MAT_UNIT") or "",
                "qty": qty,
                "price": price,
                "sum": qty * price,
            })
    
    # 3. Табель
    timesheet_data = []
    for t in timesheets:
        h = float(t.get("ufCrm11UfHours") or t.get("UF_CRM_11_UF_HOURS") or 0)
        r = float(t.get("ufCrm11UfRate") or t.get("UF_CRM_11_UF_RATE") or 0)
        timesheet_data.append({
            "name": t.get("ufCrm11UfWorker") or t.get("UF_CRM_11_UF_WORKER") or "",
            "hours": h,
            "rate": r,
            "sum": h * r,
        })
    
    # 4. Итоги
    # Приоритет: plan_json.total_plan, но если отсутствует или ≤ 0, пересчитываем из задач
    plan_total = None
    if isinstance(plan_json, dict) and "total_plan" in plan_json:
        try:
            plan_total_raw = plan_json.get("total_plan")
            if plan_total_raw is not None:
                plan_total = float(plan_total_raw)
                logger.info(f"[LPA] Got plan_total from plan_json.total_plan: {plan_total}")
                # Если total_plan ≤ 0, считаем это как "не заполнено" и пересчитываем
                if plan_total <= 0:
                    logger.info(f"[LPA] plan_json.total_plan={plan_total} <= 0, will recalculate from tasks")
                    plan_total = None
        except (TypeError, ValueError) as e:
            logger.warning(f"[LPA] Could not parse plan_json.total_plan: {e}")
            plan_total = None
    
    # Если total_plan отсутствует или ≤ 0, считаем из задач
    if plan_total is None:
        if tasks:
            calculated_from_tasks = sum(float(t.get("plan", 0) or 0) for t in tasks)
            plan_total = calculated_from_tasks
            logger.info(f"[LPA] Calculated plan_total from tasks: {plan_total}")
        else:
            plan_total = 0.0
            logger.warning(f"[LPA] plan_total is None and no tasks, using 0.0")
    
    # Считаем fact_total из реальных записей табеля
    fact_total = None
    
    # ПРИОРИТЕТ 1: Сумма часов из табеля
    if timesheets:
        fact_total_from_timesheet = sum(
            float(t.get("ufCrm11UfHours") or t.get("UF_CRM_11_UF_HOURS") or 0)
            for t in timesheets
        )
        if fact_total_from_timesheet > 0:
            fact_total = fact_total_from_timesheet
            logger.info(f"[LPA] fact_total from timesheet: {fact_total} (items={len(timesheets)})")
    
    # ПРИОРИТЕТ 2: fact_json.total_fact (если табель пустой)
    if fact_total is None or fact_total == 0:
        if isinstance(fact_json, dict) and "total_fact" in fact_json:
            try:
                fact_total = float(fact_json.get("total_fact", 0) or 0)
                logger.info(f"[LPA] Got fact_total from fact_json.total_fact: {fact_total}")
            except (TypeError, ValueError):
                pass
    
    # ПРИОРИТЕТ 3: Считаем из задач (fallback)
    if fact_total is None or fact_total == 0:
        fact_total = sum(float(t.get("fact", 0)) for t in tasks)
        if fact_total > 0:
            logger.info(f"[LPA] Calculated fact_total from tasks: {fact_total}")
        else:
            fact_total = 0.0
    
    logger.info(f"[LPA] Final plan_total={plan_total}, fact_total={fact_total}")
    
    efficiency = round((fact_total / plan_total * 100), 2) if plan_total > 0 else 0.0
    downtime_reason = fact_json.get("downtime_reason", "") or ""
    downtime_minutes = (
        fact_json.get("downtime_minutes")
        or fact_json.get("downtime_min")
        or fact_json.get("downtime_duration")
        or 0
    )
    try:
        downtime_minutes = float(downtime_minutes) if downtime_minutes else 0
    except (TypeError, ValueError):
        downtime_minutes = 0

    report_status = (
        fact_json.get("status")
        or shift_item.get("stageId")
        or shift_item.get("statusId")
        or "Не указан"
    )

    reasons = [
        f"{t['name']}: {t['reason']}"
        for t in tasks
        if t.get("name") and t.get("reason")
    ]
    reasons_text = "\n".join(reasons) if reasons else "Отклонений не выявлено"
    
    # Логируем итоги
    logger.info(f"[LPA] Merged: tasks={len(tasks)}, plan_total={plan_total}, fact_total={fact_total}")
    
    # Получаем адрес объекта (если есть)
    object_address = ""
    try:
        # Пробуем получить из Bitrix24 через object_bitrix_id
        if isinstance(plan_json, dict) and "meta" in plan_json:
            meta_in_plan = plan_json.get("meta", {})
            if isinstance(meta_in_plan, dict):
                object_bitrix_id = meta_in_plan.get("object_bitrix_id")
                if object_bitrix_id:
                    try:
                        obj_data = await bx("crm.item.get", {
                            "entityTypeId": OBJECT_ETID,
                            "id": int(object_bitrix_id),
                            "select": ["id", "title", "*", "ufCrm%"]
                        })
                        if obj_data:
                            obj_item = obj_data.get("item", obj_data) if isinstance(obj_data, dict) else obj_data
                            # Пробуем разные варианты названий поля адреса
                            object_address = (
                                read_field(obj_item, "UF_ADDRESS") or
                                read_field(obj_item, "UF_CRM_ADDRESS") or
                                read_field(obj_item, "address") or
                                ""
                            )
                    except Exception as e:
                        logger.warning(f"[LPA] Could not get object address: {e}")
    except Exception as e:
        logger.warning(f"[LPA] Error getting object address: {e}")
    
    # Формируем итоговый контекст
    context = {
        "object_name": object_name,
        "object_address": object_address or "",
        "section": section,
        "date": date_str or datetime.now().strftime("%d.%m.%Y"),
        "foreman": foreman,
        "shift_type": shift_type,
        "tasks": tasks,
        "tech": tech,
        "materials": materials,
        "timesheet": timesheet_data,
        "plan_total": plan_total,
        "fact_total": fact_total,
        "efficiency": efficiency,
        "downtime_reason": downtime_reason,
        "downtime_min": downtime_minutes,
        "report_status": report_status,
        "reasons_text": reasons_text,
        "photos": photos,  # Добавляем фото в контекст
        "photos_attached": "Да" if photos else "Нет",  # Флаг наличия фото для шаблона
    }
    
    logger.info(f"[LPA] ===== FINAL CONTEXT SUMMARY =====")
    logger.info(f"[LPA] Context built: tasks={len(tasks)}, tech={len(tech)}, materials={len(materials)}, timesheet={len(timesheet_data)}, plan_total={plan_total}, fact_total={fact_total}")
    logger.info(f"[LPA] object_name={context.get('object_name')}")
    logger.info(f"[LPA] date={context.get('date')}")
    logger.info(f"[LPA] shift_type={context.get('shift_type')}")
    if tasks:
        logger.info(f"[LPA] First 3 tasks in final context:")
        for i, task in enumerate(tasks[:3], 1):
            logger.info(f"[LPA]   task{i}: name={task.get('name')}, plan={task.get('plan')}, fact={task.get('fact')}")
    if timesheet_data:
        logger.info(f"[LPA] First 3 workers in final context:")
        for i, worker in enumerate(timesheet_data[:3], 1):
            logger.info(f"[LPA]   worker{i}: name={worker.get('name')}, hours={worker.get('hours')}")
    logger.info(f"[LPA] ===== END FINAL CONTEXT SUMMARY =====")
    
    return context, photos
