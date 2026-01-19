"""Единый клиент для работы со сменами в Bitrix24."""

import json
import logging
from datetime import date, datetime
from typing import Optional, Tuple, Dict, Any
from app.services.bitrix import bx_post
from app.services.http_client import bx as bx_http
from app.services.bitrix_ids import SHIFT_ETID, UF_DATE, UF_TYPE, UF_PLAN_TOTAL
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.objects import fetch_all_objects
from app.services.shift_meta import (
    shift_type_bitrix_label,
    shift_status_bitrix_label,
)
# enum_payload больше не используется - используем BitrixEnumHelper

log = logging.getLogger("gpo.shift_client")


def _shift_field_camel(logical_code: str) -> Optional[str]:
    """Возвращает camelCase код поля смены."""
    field_code = resolve_code("Смена", logical_code)
    if not field_code:
        return None
    return upper_to_camel(field_code) if field_code.startswith("UF_") else field_code


def _normalize_date(value: Any) -> Optional[date]:
    """Нормализует дату из различных форматов Bitrix.
    
    Варианты: "2025-11-16", "2025-11-16T08:00:00+03:00"
    """
    if not value:
        return None
    
    if isinstance(value, date):
        return value
    
    if not isinstance(value, str):
        return None
    
    # Берём кусок до 'T'
    base = value.split("T", 1)[0]
    try:
        return datetime.strptime(base, "%Y-%m-%d").date()
    except ValueError:
        return None


def _score_shift(item: Dict[str, Any], f_plan_json_camel: str, f_plan_total_camel: Optional[str]) -> Tuple[int, int]:
    """Вычисляет приоритет смены для выбора лучшей.
    
    Returns:
        (priority, id): priority=0 если есть план, 1 если нет; id для сортировки
    """
    shift_id = int(item.get("id", 0))
    
    # Проверяем наличие плана
    plan_json_raw = item.get(f_plan_json_camel) or ""
    plan_total = item.get(f_plan_total_camel) or 0
    
    has_plan = False
    if plan_json_raw and isinstance(plan_json_raw, str) and plan_json_raw.strip():
        try:
            plan_json = json.loads(plan_json_raw)
            if plan_json.get("total_plan") or plan_json.get("tasks"):
                has_plan = True
        except:
            pass
    
    if not has_plan and plan_total and isinstance(plan_total, (int, float)) and float(plan_total) > 0:
        has_plan = True
    
    priority = 0 if has_plan else 1
    return (priority, shift_id)


async def bitrix_get_shift_for_object_and_date(
    object_bitrix_id: int,
    target_date: date,
    *,
    create_if_not_exists: bool = False,
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """
    Возвращает Bitrix ID смены для пары (object_bitrix_id, target_date).
    
    Поиск выполняется по plan_json.meta.object_bitrix_id и дате смены.
    UF_OBJECT_LINK больше не используется.
    
    Если create_if_not_exists=True и смена не найдена – создаёт новую и возвращает её ID.
    Если create_if_not_exists=False и смена не найдена – возвращает (None, None).
    
    При наличии нескольких смен выбирает ту, у которой есть план (UF_PLAN_JSON или UF_PLAN_TOTAL > 0).
    Если таких несколько – выбирает самую старую по ID.
    Если ни у одной нет плана – выбирает самую старую по ID.
    
    Args:
        object_bitrix_id: Bitrix ID объекта
        target_date: Дата смены
        create_if_not_exists: Создавать смену, если не найдена
        
    Returns:
        Tuple[Optional[int], Optional[Dict]]: (Bitrix ID смены, метаданные) или (None, None)
    """
    log.info(f"[SHIFT] search object={object_bitrix_id} date={target_date} create_if_not_exists={create_if_not_exists}")
    
    try:
        # Получаем коды полей через маппинг
        f_date = resolve_code("Смена", "UF_DATE")
        f_date_camel = upper_to_camel(f_date) if f_date and f_date.startswith("UF_") else None
        f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
        f_plan_json_camel = upper_to_camel(f_plan_json) if f_plan_json and f_plan_json.startswith("UF_") else None
        f_plan_total = resolve_code("Смена", "UF_PLAN_TOTAL")
        f_plan_total_camel = upper_to_camel(f_plan_total) if f_plan_total and f_plan_total.startswith("UF_") else None
        
        if not f_date_camel or not f_plan_json_camel:
            log.error(f"[SHIFT] Required fields not found: UF_DATE={f_date}, UF_PLAN_JSON={f_plan_json}")
            return None, None
        
        # Получаем последние смены для фильтрации
        log.info(f"[SHIFT] Fetching last 200 shifts for filtering by plan_json.meta")
        
        select_fields = ["id", f_date_camel, f_plan_json_camel]
        if f_plan_total_camel:
            select_fields.append(f_plan_total_camel)
        
        try:
            shifts_resp = await bx_http("crm.item.list", {
                "entityTypeId": SHIFT_ETID,
                "order": {"id": "desc"},
                "limit": 200,
                "select": select_fields,
            })
            
            items = shifts_resp.get("items", shifts_resp) if isinstance(shifts_resp, dict) else (shifts_resp if isinstance(shifts_resp, list) else [])
            
            log.info(f"[SHIFT] raw items: {len(items)}")
            
            # Логируем первые несколько смен для отладки
            if items:
                sample_ids = [it.get("id") for it in items[:5]]
                log.info(f"[SHIFT] sample item ids: {sample_ids}")
                # Проверяем, есть ли среди них смена с plan_json
                for sample in items[:5]:
                    sid = sample.get("id")
                    pj = sample.get(f_plan_json_camel)
                    if pj:
                        try:
                            # Обрабатываем разные форматы
                            if isinstance(pj, str):
                                p = json.loads(pj)
                            elif isinstance(pj, dict):
                                p = pj
                            elif isinstance(pj, list) and pj and isinstance(pj[0], dict):
                                p = pj[0]
                            else:
                                continue
                            m = p.get("meta", {})
                            log.info(f"[SHIFT] sample id={sid} has plan_json, meta keys: {list(m.keys())}, plan keys: {list(p.keys())}")
                        except Exception as e:
                            log.debug(f"[SHIFT] error parsing sample id={sid}: {e}")
                            pass
            
            # Фильтруем смены по plan_json.meta.object_bitrix_id и дате
            candidates = []
            items_with_plan = 0
            items_with_meta = 0
            
            for it in items:
                shift_id = it.get("id")
                if not shift_id:
                    continue
                
                raw_date = it.get(f_date_camel)
                norm_date = _normalize_date(raw_date)
                
                plan_json_raw = it.get(f_plan_json_camel)
                if not plan_json_raw:
                    log.debug(f"[SHIFT] skip id={shift_id} no plan_json")
                    continue
                
                items_with_plan += 1
                
                # Обрабатываем разные форматы: строка или уже распарсенный объект
                plan = None
                try:
                    if isinstance(plan_json_raw, str):
                        plan = json.loads(plan_json_raw)
                    elif isinstance(plan_json_raw, dict):
                        # Bitrix уже вернул распарсенный JSON как словарь
                        plan = plan_json_raw
                    elif isinstance(plan_json_raw, list):
                        # Bitrix вернул список - возможно, это массив с одним элементом-словарём
                        # Пробуем взять первый элемент, если он словарь
                        if plan_json_raw and len(plan_json_raw) > 0:
                            first_elem = plan_json_raw[0]
                            if isinstance(first_elem, dict):
                                plan = first_elem
                                log.debug(f"[SHIFT] id={shift_id} plan_json was list, using first element (keys: {list(plan.keys())[:5]})")
                            elif isinstance(first_elem, str):
                                # Возможно, это список строк - пробуем распарсить первую
                                try:
                                    plan = json.loads(first_elem)
                                    log.debug(f"[SHIFT] id={shift_id} plan_json was list of strings, parsed first")
                                except:
                                    log.debug(f"[SHIFT] skip id={shift_id} plan_json is list but first element is not parseable: {type(first_elem)}")
                                    continue
                            else:
                                log.debug(f"[SHIFT] skip id={shift_id} plan_json is list but first element is not dict/string: {type(first_elem)}")
                                continue
                        else:
                            log.debug(f"[SHIFT] skip id={shift_id} plan_json is empty list")
                            continue
                    else:
                        log.debug(f"[SHIFT] skip id={shift_id} plan_json has unexpected type: {type(plan_json_raw)}")
                        continue
                except Exception as e:
                    log.debug(f"[SHIFT] bad plan_json id={shift_id}: {e}")
                    continue
                
                # Проверяем, что plan - это словарь (не список)
                if not plan or not isinstance(plan, dict):
                    log.debug(f"[SHIFT] skip id={shift_id} plan is not dict after parsing: {type(plan)}")
                    continue
                
                meta = plan.get("meta") or {}
                meta_object_id = meta.get("object_bitrix_id")
                
                if not meta_object_id:
                    items_with_meta += 1
                    # Логируем первые несколько для отладки
                    if items_with_meta <= 5:
                        log.info(f"[SHIFT] skip id={shift_id} no meta.object_bitrix_id (meta keys: {list(meta.keys())}, plan keys: {list(plan.keys())})")
                        # Для отладки: показываем структуру plan
                        if items_with_meta == 1 and shift_id:
                            log.info(f"[SHIFT] DEBUG: plan structure for id={shift_id}: {list(plan.keys())[:10]}")
                            if meta:
                                log.info(f"[SHIFT] DEBUG: meta structure for id={shift_id}: {meta}")
                            else:
                                log.info(f"[SHIFT] DEBUG: meta is empty for id={shift_id}")
                    else:
                        log.debug(f"[SHIFT] skip id={shift_id} no meta.object_bitrix_id (meta keys: {list(meta.keys())})")
                    continue
                
                # Сравниваем по объекту и дате
                try:
                    meta_obj_int = int(meta_object_id)
                    target_obj_int = int(object_bitrix_id)
                    if meta_obj_int != target_obj_int:
                        log.debug(f"[SHIFT] skip id={shift_id} meta.object_id={meta_obj_int}!={target_obj_int}")
                        continue
                except (ValueError, TypeError) as e:
                    log.debug(f"[SHIFT] skip id={shift_id} invalid meta.object_bitrix_id: {meta_object_id} ({e})")
                    continue
                
                if norm_date != target_date:
                    log.debug(f"[SHIFT] skip id={shift_id} date={norm_date}!={target_date}")
                    continue
                
                log.info(f"[SHIFT] MATCH id={shift_id} object={meta_object_id} date={norm_date}")
                
                candidates.append(it)
            
            log.info(f"[SHIFT] Filtering stats: items_with_plan={items_with_plan}, items_with_meta={items_with_meta}, candidates={len(candidates)}")
            log.info(f"[SHIFT] candidates for object={object_bitrix_id} date={target_date}: {[c.get('id') for c in candidates]}")
            
            # Если кандидатов нет
            if not candidates:
                log.info(f"[SHIFT] no shift found for object={object_bitrix_id} date={target_date}")
                
                if not create_if_not_exists:
                    return None, None
                
                # Создаем новую смену
                log.info(f"[SHIFT] create new shift for object={object_bitrix_id} date={target_date}")
                
                # Получаем название объекта
                objects = await fetch_all_objects()
                object_name = f"Объект #{object_bitrix_id}"
                for obj in objects:
                    obj_id = obj[0] if isinstance(obj, (list, tuple)) else obj
                    if obj_id == object_bitrix_id:
                        object_name = obj[1] if len(obj) > 1 else f"Объект #{object_bitrix_id}"
                        break
                
                # Формируем поля для новой смены
                date_str = target_date.isoformat()  # "2025-11-16"
                date_value = date_str + "T08:00:00"  # "2025-11-16T08:00:00"
                
                fields = {
                    "TITLE": f"Смена для {object_name}",
                    UF_DATE: date_value,
                    UF_TYPE: "day",
                    UF_PLAN_TOTAL: 0,
                }
                
                # Создаем смену в Bitrix24
                result = await bx_post("crm.item.add", {
                    "entityTypeId": SHIFT_ETID,
                    "fields": fields
                })
                
                new_shift_id = result.get("result", {}).get("item", {}).get("id") if isinstance(result, dict) else None
                if new_shift_id:
                    log.info(f"[SHIFT] create new shift_id={new_shift_id} for object={object_bitrix_id} date={target_date}")
                    return new_shift_id, None
                else:
                    log.error(f"[SHIFT] failed to create shift: {result}")
                    return None, None
            
            # Выбираем лучшую смену из кандидатов
            # Сортируем: сначала по приоритету (есть план или нет), затем по ID (самая старая)
            sorted_candidates = sorted(candidates, key=lambda x: _score_shift(x, f_plan_json_camel, f_plan_total_camel))
            best = sorted_candidates[0]
            best_id = int(best.get("id"))
            best_plan_json = best.get(f_plan_json_camel)
            
            # Логируем информацию о выборе
            best_score = _score_shift(best, f_plan_json_camel, f_plan_total_camel)
            log.info(f"[SHIFT] pick existing shift_id={best_id} from {len(candidates)} candidates (priority={best_score[0]}, has_plan={best_score[0]==0})")
            
            meta = {}
            if best_plan_json:
                try:
                    plan_data = json.loads(best_plan_json)
                    meta = plan_data.get("meta", {})
                except:
                    pass
            
            return best_id, {"plan_json": best_plan_json}
            
        except Exception as e:
            log.error(f"[SHIFT] error searching shifts: {e}", exc_info=True)
            if create_if_not_exists:
                # Пробуем создать смену даже при ошибке поиска
                log.warning(f"[SHIFT] search failed, trying to create shift anyway")
                objects = await fetch_all_objects()
                object_name = f"Объект #{object_bitrix_id}"
                for obj in objects:
                    obj_id = obj[0] if isinstance(obj, (list, tuple)) else obj
                    if obj_id == object_bitrix_id:
                        object_name = obj[1] if len(obj) > 1 else f"Объект #{object_bitrix_id}"
                        break
                
                date_str = target_date.isoformat()
                date_value = date_str + "T08:00:00"
                
                fields = {
                    "TITLE": f"Смена для {object_name}",
                    UF_DATE: date_value,
                    UF_TYPE: "day",
                    UF_PLAN_TOTAL: 0,
                }
                
                try:
                    result = await bx_post("crm.item.add", {
                        "entityTypeId": SHIFT_ETID,
                        "fields": fields
                    })
                    new_shift_id = result.get("result", {}).get("item", {}).get("id") if isinstance(result, dict) else None
                    if new_shift_id:
                        log.info(f"[SHIFT] create new shift_id={new_shift_id} for object={object_bitrix_id} date={target_date} (after search error)")
                        return new_shift_id, None
                except Exception as create_err:
                    log.error(f"[SHIFT] failed to create shift after search error: {create_err}", exc_info=True)
            
            return None, None
            
    except Exception as e:
        log.error(f"[SHIFT] error in bitrix_get_shift_for_object_and_date: {e}", exc_info=True)
        return None, None


async def bitrix_update_shift_aggregates(
    shift_id: int,
    plan_total: float,
    fact_total: float,
    *,
    efficiency: Optional[float] = None,
    status: Optional[str] = None,
) -> None:
    """Обновляет агрегированные показатели смены (план, факт, эффективность, статус)."""
    if not shift_id:
        return

    plan_total_val = float(plan_total or 0.0)
    fact_total_val = float(fact_total or 0.0)
    if efficiency is None:
        efficiency = round(fact_total_val / plan_total_val * 100, 2) if plan_total_val > 0 else 0.0

    fields: Dict[str, Any] = {}

    for logical, value in (
        ("UF_PLAN_TOTAL", plan_total_val),
        ("UF_FACT_TOTAL", fact_total_val),
    ):
        camel = _shift_field_camel(logical)
        if camel is not None:
            fields[camel] = value

    for logical in ("UF_EFF_RAW", "UF_EFF_FINAL"):
        camel = _shift_field_camel(logical)
        if camel is not None:
            fields[camel] = efficiency

    status_field = _shift_field_camel("UF_STATUS")
    status_label = shift_status_bitrix_label(status or "closed")
    if status_field and status_label:
        # Используем BitrixEnumHelper для получения числового ID
        from app.services.bitrix_enums import get_shift_status_enum
        shift_status_enum = get_shift_status_enum()
        enum_id = await shift_status_enum.get_id(status_label)
        
        # Если enum_id не найден, но есть другие значения с ID, используем первый доступный
        if enum_id is None and shift_status_enum._id_to_label:
            enum_id = list(shift_status_enum._id_to_label.keys())[0]
            log.warning(
                f"[SHIFT] Enum ID not found for status label '{status_label}', "
                f"using available ID {enum_id} (Bitrix may have only one enum value)"
            )
        
        if enum_id is not None:
            # Отправляем только числовой ID, а не {"value": "..."}
            fields[status_field] = enum_id
            log.debug("[SHIFT] Mapped status '%s' -> enum_id %s", status_label, enum_id)
        else:
            log.warning("[SHIFT] No enum ID available for status label '%s'", status_label)
    
    # Устанавливаем statusId (стадию смарт-процесса) при закрытии смены
    # Обычно для закрытых смен используется stageId = 1 или другой ID
    # Можно попробовать установить через statusId поле
    if status and status.lower() in ("closed", "закрыта"):
        # Пробуем установить statusId для стадии "Закрыта"
        # Обычно это 1 для первой стадии закрытия, но может быть разным
        # В Bitrix смарт-процессах statusId обычно устанавливается автоматически
        # при изменении стадии, но можно попробовать установить явно
        try:
            # Пробуем установить statusId = 1 (типичное значение для закрытых сделок)
            # Если это не работает, нужно будет получить список стадий через API
            fields["statusId"] = 1
            log.debug("[SHIFT] Setting statusId=1 for closed shift")
        except Exception:
            # Если не получается, пропускаем - Bitrix может установить автоматически
            pass

    if not fields:
        log.warning("[SHIFT] No aggregate fields resolved for update (shift_id=%s)", shift_id)
        return

    try:
        await bx_post(
            "crm.item.update",
            {
                "entityTypeId": SHIFT_ETID,
                "id": int(shift_id),
                "fields": fields,
            },
        )
        log.info(
            "[SHIFT] Aggregates updated: shift_id=%s plan=%.2f fact=%.2f eff=%.2f status=%s",
            shift_id,
            plan_total_val,
            fact_total_val,
            efficiency,
            status_label or "",
        )
    except Exception as err:
        log.error("[SHIFT] Failed to update aggregates for shift %s: %s", shift_id, err, exc_info=True)


async def bitrix_update_shift_type(shift_id: int, shift_type_code: Optional[str]) -> None:
    """Записывает человекочитаемый тип смены в Bitrix."""
    if not shift_id or not shift_type_code:
        return

    label = shift_type_bitrix_label(shift_type_code)
    if not label:
        return

    field_camel = _shift_field_camel("UF_SHIFT_TYPE")
    if not field_camel:
        log.warning("[SHIFT] UF_SHIFT_TYPE not resolved, skipping update")
        return

    try:
        # Используем BitrixEnumHelper для получения числового ID
        from app.services.bitrix_enums import get_shift_type_enum
        shift_type_enum = get_shift_type_enum()
        enum_id = await shift_type_enum.get_id(label)
        
        # Если enum_id не найден, но есть другие значения с ID, используем первый доступный
        if enum_id is None and shift_type_enum._id_to_label:
            enum_id = list(shift_type_enum._id_to_label.keys())[0]
            log.warning(
                f"[SHIFT] Enum ID not found for label '{label}', "
                f"using available ID {enum_id} (Bitrix may have only one enum value)"
            )
        
        if enum_id is not None:
            # Отправляем только числовой ID, а не {"value": "..."}
            await bx_post(
                "crm.item.update",
                {
                    "entityTypeId": SHIFT_ETID,
                    "id": int(shift_id),
                    "fields": {field_camel: enum_id},
                },
            )
            log.info("[SHIFT] Shift type updated: shift_id=%s type=%s (enum_id=%s)", shift_id, label, enum_id)
        else:
            log.warning("[SHIFT] No enum ID available for shift type label '%s', skipping update", label)
    except Exception as err:
        log.error("[SHIFT] Failed to update shift type for %s: %s", shift_id, err, exc_info=True)
