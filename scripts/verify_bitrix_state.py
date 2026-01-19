"""Diagnostics: verify Bitrix state for a given shift."""

import argparse
import asyncio
import json
import logging
from typing import Any, Dict, List

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, TIMESHEET_ETID, RESOURCE_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.shift_meta import shift_type_display_label
from app.services.resource_meta import resource_type_display_label

log = logging.getLogger("gpo.verify_shift")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _camel(field: str | None) -> str | None:
    if field and field.startswith("UF_"):
        return upper_to_camel(field)
    return field


def _normalize_plan_json(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return first
        if isinstance(first, str):
            try:
                return json.loads(first)
            except json.JSONDecodeError:
                return {}
    return {}


async def main(shift_id: int) -> None:
    log.info("=== VERIFY BITRIX STATE: shift_id=%s ===", shift_id)

    f_plan_total = resolve_code("Смена", "UF_PLAN_TOTAL")
    f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
    f_fact_total = resolve_code("Смена", "UF_FACT_TOTAL")
    f_eff_raw = resolve_code("Смена", "UF_EFF_RAW")
    f_eff_final = resolve_code("Смена", "UF_EFF_FINAL")
    f_shift_type = resolve_code("Смена", "UF_SHIFT_TYPE")
    f_pdf_file = resolve_code("Смена", "UF_PDF_FILE")
    f_status = resolve_code("Смена", "UF_STATUS")
    f_object_link = resolve_code("Смена", "UF_OBJECT_LINK")

    f_plan_total_camel = _camel(f_plan_total)
    f_plan_json_camel = _camel(f_plan_json)
    f_fact_total_camel = _camel(f_fact_total)

    # Запрашиваем смену с полным select для получения всех полей
    shift_resp = await bx(
        "crm.item.get",
        {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id,
            "select": ["id", "*", "ufCrm%"],  # Полный select для получения всех полей
        },
    )
    shift_item = shift_resp.get("item", shift_resp)
    
    # Служебные поля
    shift_id_value = shift_item.get("id")
    created_by = shift_item.get("createdBy") or shift_item.get("CREATED_BY_ID")
    assigned_by = shift_item.get("assignedById") or shift_item.get("ASSIGNED_BY_ID")
    status_id = shift_item.get("statusId") or shift_item.get("STATUS_ID")
    date_value = shift_item.get("ufCrm7UfDate") or shift_item.get("UF_CRM_7_UF_DATE")
    plan_total_shift = float(
        shift_item.get(f_plan_total_camel)
        or shift_item.get(f_plan_total)
        or 0.0
    )
    fact_total_shift = float(
        shift_item.get(f_fact_total_camel)
        or shift_item.get(f_fact_total)
        or 0.0
    )
    eff_value = float(
        shift_item.get(_camel(f_eff_final)) or shift_item.get(_camel(f_eff_raw)) or 0.0
    )
    shift_type_value = shift_item.get(_camel(f_shift_type)) or shift_item.get(f_shift_type) or ""
    
    # Чтение PDF поля (может быть список ID, массив объектов, строка "Array" или None)
    pdf_value_raw = shift_item.get(_camel(f_pdf_file)) or shift_item.get(f_pdf_file) or shift_item.get("ufCrm7UfCrmPdfFile")
    pdf_value = pdf_value_raw
    pdf_attached = False
    
    # Если PDF не найден, делаем повторный запрос после небольшой задержки (Bitrix может обрабатывать файл)
    if not pdf_value_raw:
        import asyncio
        await asyncio.sleep(2)  # Задержка для обработки файла Bitrix
        shift_resp_retry = await bx(
            "crm.item.get",
            {
                "entityTypeId": SHIFT_ETID,
                "id": shift_id,
                "select": ["id", "*", "ufCrm%"],
            },
        )
        shift_item_retry = shift_resp_retry.get("item", shift_resp_retry)
        pdf_value_raw = shift_item_retry.get(_camel(f_pdf_file)) or shift_item_retry.get(f_pdf_file) or shift_item_retry.get("ufCrm7UfCrmPdfFile")
        pdf_value = pdf_value_raw  # Обновляем pdf_value после повторного запроса
    
    if pdf_value_raw:
        if isinstance(pdf_value_raw, list) and len(pdf_value_raw) > 0:
            pdf_attached = True
            pdf_value = pdf_value_raw
        elif isinstance(pdf_value_raw, (int, str)) and str(pdf_value_raw).strip() and str(pdf_value_raw) != "Array":
            pdf_attached = True
            pdf_value = pdf_value_raw
        elif str(pdf_value_raw).strip() == "Array":
            # Bitrix вернул "Array" - это означает, что файлы есть, но нужно запросить их отдельно
            pdf_attached = True
            pdf_value = "Array (файлы присутствуют)"
    
    status_value = shift_item.get(_camel(f_status)) or shift_item.get(f_status)
    plan_json_raw = (
        shift_item.get(f_plan_json_camel) or shift_item.get(f_plan_json)
    )
    plan_json = _normalize_plan_json(plan_json_raw)
    total_plan_json = float(plan_json.get("total_plan") or 0.0)
    meta = plan_json.get("meta", {})
    meta_obj_id = meta.get("object_bitrix_id")
    meta_obj_name = meta.get("object_name")

    # Извлекаем эффективность отдельно для raw и final
    eff_raw_value = float(
        shift_item.get(_camel(f_eff_raw)) or shift_item.get(f_eff_raw) or 0.0
    )
    eff_final_value = float(
        shift_item.get(_camel(f_eff_final)) or shift_item.get(f_eff_final) or 0.0
    )
    
    # Расшифровка типа смены через BitrixEnumHelper
    shift_type_display = ""
    shift_type_id = None
    
    if isinstance(shift_type_value, dict):
        shift_type_id = int(shift_type_value.get("ID") or shift_type_value.get("id") or 0)
        shift_type_display = shift_type_value.get("value") or shift_type_value.get("VALUE") or ""
    elif isinstance(shift_type_value, int):
        shift_type_id = shift_type_value
    elif shift_type_value:
        try:
            shift_type_id = int(shift_type_value)
        except (TypeError, ValueError):
            shift_type_display = str(shift_type_value)
    
    if shift_type_id:
        from app.services.bitrix_enums import get_shift_type_enum
        shift_type_enum = get_shift_type_enum()
        label = await shift_type_enum.get_label(shift_type_id)
        if label:
            shift_type_display = f"{label} (ID: {shift_type_id})"
        else:
            # Fallback: используем мета-данные
            meta_shift_type = plan_json.get("meta", {}).get("shift_type")
            if meta_shift_type:
                meta_label = shift_type_display_label(meta_shift_type)
                if meta_label:
                    shift_type_display = f"{meta_label} (ID: {shift_type_id})"
                else:
                    shift_type_display = f"ID: {shift_type_id}"
            else:
                shift_type_display = f"ID: {shift_type_id}"
    elif not shift_type_display:
        shift_type_display = "Не указан"
    
    # Расшифровка статуса через BitrixEnumHelper
    status_display = ""
    status_id = None
    
    if isinstance(status_value, dict):
        status_id = int(status_value.get("ID") or status_value.get("id") or 0)
        status_display = status_value.get("value") or status_value.get("VALUE") or ""
    elif isinstance(status_value, int):
        status_id = status_value
    elif status_value:
        try:
            status_id = int(status_value)
        except (TypeError, ValueError):
            status_display = str(status_value)
    
    if status_id:
        from app.services.bitrix_enums import get_shift_status_enum
        shift_status_enum = get_shift_status_enum()
        label = await shift_status_enum.get_label(status_id)
        if label:
            status_display = f"{label} (ID: {status_id})"
        else:
            # Fallback: используем значение по умолчанию
            status_display = f"Закрыта (ID: {status_id})"
    elif not status_display:
        status_display = "Не установлен"
    
    # Поле связи с объектом
    obj_link_camel = _camel(f_object_link) or "ufCrm7UfCrmObject"
    obj_link_raw = shift_item.get(obj_link_camel) or shift_item.get(f_object_link) or shift_item.get("ufCrm7UfCrmObject")
    
    log.info("=== СЛУЖЕБНЫЕ ПОЛЯ ===")
    log.info("id: %s", shift_id_value)
    log.info("createdBy: %s", created_by)
    log.info("assignedById: %s", assigned_by)
    log.info("statusId: %s", status_id)
    log.info("UF_OBJECT_LINK: %s (raw: %s)", obj_link_raw, type(obj_link_raw).__name__)
    
    log.info("=== ПЛАН/ФАКТ/ЭФФЕКТИВНОСТЬ ===")
    log.info("Shift date: %s", date_value)
    log.info("UF_PLAN_TOTAL: %.2f", plan_total_shift)
    log.info(
        "UF_PLAN_JSON: total_plan=%.2f, meta.object_bitrix_id=%s, meta.object_name=%s",
        total_plan_json,
        meta_obj_id,
        meta_obj_name,
    )
    log.info("UF_FACT_TOTAL: %.2f", fact_total_shift)
    log.info("UF_EFF_RAW: %.2f", eff_raw_value)
    log.info("UF_EFF_FINAL: %.2f", eff_final_value)
    
    log.info("=== ТИП СМЕНЫ И СТАТУС ===")
    log.info("UF_SHIFT_TYPE: %s (raw: %s)", shift_type_display, shift_type_value)
    log.info("UF_STATUS: %s (statusId: %s)", status_display, status_id)
    
    log.info("=== ФАЙЛ PDF ===")
    log.info("UF_PDF_FILE: %s (attached: %s)", pdf_value, pdf_attached)

    # Timesheets
    f_ts_shift = resolve_code("Табель", "UF_SHIFT_ID")
    f_ts_hours = resolve_code("Табель", "UF_HOURS")
    f_ts_worker = resolve_code("Табель", "UF_WORKER")

    f_ts_shift_camel = _camel(f_ts_shift) or "ufCrm11UfShiftId"
    f_ts_hours_camel = _camel(f_ts_hours) or "ufCrm11UfHours"
    f_ts_worker_camel = _camel(f_ts_worker) or "ufCrm11UfWorker"

    ts_resp = await bx(
        "crm.item.list",
        {
            "entityTypeId": TIMESHEET_ETID,
            "filter": {f_ts_shift_camel: shift_id},
            "select": ["id", f_ts_shift_camel, f_ts_hours_camel, f_ts_worker_camel],
            "order": {"id": "asc"},
        },
    )
    timesheet_items: List[Dict[str, Any]] = ts_resp.get("items", [])
    ts_ids = []
    ts_hours_sum = 0.0
    log.info("=== ТАБЕЛЬ ===")
    for item in timesheet_items:
        ts_id = item.get("id")
        ts_shift_id = item.get(f_ts_shift_camel)
        hours = float(item.get(f_ts_hours_camel) or 0.0)
        worker = item.get(f_ts_worker_camel) or ""
        ts_ids.append(ts_id)
        ts_hours_sum += hours
        log.info("  #%s | UF_SHIFT_ID=%s | worker=%s | UF_HOURS=%.2f", ts_id, ts_shift_id, worker, hours)
    log.info("Timesheet total hours: %.2f (records=%d)", ts_hours_sum, len(timesheet_items))

    # Resources
    f_res_shift = resolve_code("Ресурс", "UF_SHIFT_ID")
    f_res_type = resolve_code("Ресурс", "UF_RESOURCE_TYPE")
    f_res_mat = resolve_code("Ресурс", "UF_MAT_TYPE")
    f_res_qty = resolve_code("Ресурс", "UF_MAT_QTY")
    f_res_unit = resolve_code("Ресурс", "UF_MAT_UNIT")
    f_res_equip = resolve_code("Ресурс", "UF_EQUIP_TYPE")

    f_res_shift_camel = _camel(f_res_shift) or "ufCrm9UfShiftId"
    fields = ["id", f_res_shift_camel]
    for fld in [f_res_type, f_res_mat, f_res_qty, f_res_unit, f_res_equip]:
        if fld:
            fields.append(_camel(fld) or fld)

    res_resp = await bx(
        "crm.item.list",
        {
            "entityTypeId": RESOURCE_ETID,
            "filter": {f_res_shift_camel: shift_id},
            "select": fields,
            "order": {"id": "asc"},
        },
    )
    resource_items = res_resp.get("items", [])
    res_ids = []
    log.info("=== РЕСУРСЫ ===")
    for item in resource_items:
        res_id = item.get("id")
        res_shift_id = item.get(f_res_shift_camel)
        res_type_raw = item.get(_camel(f_res_type) or f_res_type)
        
        # Сначала получаем mat и equip для определения типа
        mat = item.get(_camel(f_res_mat) or f_res_mat)
        equip = item.get(_camel(f_res_equip) or f_res_equip)
        qty = item.get(_camel(f_res_qty) or f_res_qty)
        unit = item.get(_camel(f_res_unit) or f_res_unit)
        
        # Расшифровка типа ресурса через BitrixEnumHelper
        res_type_display = ""
        res_type_code = ""
        res_type_id = None
        
        if isinstance(res_type_raw, dict):
            res_type_id = int(res_type_raw.get("ID") or res_type_raw.get("id") or 0)
            res_type_code = res_type_raw.get("value") or res_type_raw.get("VALUE") or ""
        elif isinstance(res_type_raw, int):
            res_type_id = res_type_raw
        elif res_type_raw:
            try:
                res_type_id = int(res_type_raw)
            except (TypeError, ValueError):
                res_type_code = str(res_type_raw)
        
        # Определяем тип ресурса: сначала по контексту (mat_type/equip_type), затем по enum_id
        # Это важно, так как в Bitrix все ресурсы могут иметь один enum_id=1
        if equip and not mat:
            # Если есть equipment и нет material - это техника
            res_type_display = "Техника"
            if res_type_id:
                res_type_display = f"Техника (ID: {res_type_id})"
        elif mat:
            # Если есть material - это материал
            res_type_display = "Материалы"
            if res_type_id:
                res_type_display = f"Материалы (ID: {res_type_id})"
        elif res_type_id:
            # Если нет контекста, используем BitrixEnumHelper
            from app.services.bitrix_enums import get_resource_type_enum
            resource_type_enum = get_resource_type_enum()
            label = await resource_type_enum.get_label(res_type_id)
            if label:
                res_type_display = f"{label} (ID: {res_type_id})"
            else:
                res_type_display = f"ID: {res_type_id}"
        elif res_type_code:
            res_type_display = res_type_code or "Не указан"
        else:
            res_type_display = "Не указан"
        res_ids.append(res_id)
        log.info(
            "  #%s | UF_SHIFT_ID=%s | UF_RESOURCE_TYPE=%s | material=%s | equipment=%s | qty=%s %s",
            res_id,
            res_shift_id,
            res_type_display,
            mat,
            equip,
            qty,
            unit or "",
        )
    log.info("Resource records: %d", len(resource_items))

    # Summary
    eff_recalc = round(ts_hours_sum / plan_total_shift * 100, 2) if plan_total_shift > 0 else 0.0
    log.info("=== SUMMARY ===")
    # Расшифровка statusId (стадии смарт-процесса)
    status_id_display = ""
    if status_id:
        # Пытаемся получить название стадии через API
        try:
            # Для смарт-процессов можно попробовать получить стадии через crm.status.list
            # Но этот метод может не работать для всех типов сущностей
            status_id_display = f"ID: {status_id}"
            # TODO: Добавить получение названия стадии через API если доступно
        except Exception:
            status_id_display = f"ID: {status_id}"
    else:
        status_id_display = "Не установлен"
    
    log.info("--- Служебные поля ---")
    log.info("createdBy: %s (заполнено: %s)", created_by, bool(created_by))
    log.info("assignedById: %s (заполнено: %s)", assigned_by, bool(assigned_by))
    log.info("statusId: %s (заполнено: %s)", status_id_display, bool(status_id))
    log.info("UF_OBJECT_LINK: %s (заполнено: %s)", obj_link_raw, bool(obj_link_raw))
    
    log.info("--- План/Факт/Эффективность ---")
    log.info("plan_total_from_shift: %.2f", plan_total_shift)
    log.info("total_plan_from_plan_json: %.2f", total_plan_json)
    log.info("fact_total_from_shift_field: %.2f", fact_total_shift)
    log.info("fact_total_from_timesheet: %.2f", ts_hours_sum)
    log.info("UF_EFF_RAW: %.2f (заполнено: %s)", eff_raw_value, bool(eff_raw_value))
    log.info("UF_EFF_FINAL: %.2f (заполнено: %s)", eff_final_value, bool(eff_final_value))
    
    log.info("--- Тип смены и статус ---")
    log.info("UF_SHIFT_TYPE: %s (заполнено: %s)", shift_type_display, bool(shift_type_value))
    log.info("UF_STATUS: %s (заполнено: %s)", status_display, bool(status_value))
    
    log.info("--- Файл PDF ---")
    log.info("UF_PDF_FILE: %s (заполнено: %s)", pdf_value, pdf_attached)
    
    log.info("--- Связанные записи ---")
    log.info("timesheet_count: %d | ids=%s", len(timesheet_items), ts_ids[:10] if len(ts_ids) > 10 else ts_ids)
    log.info("resource_count: %d | ids=%s", len(resource_items), res_ids[:10] if len(res_ids) > 10 else res_ids)
    
    log.info("--- Проверки согласованности ---")
    plan_match = abs(plan_total_shift - total_plan_json) < 0.01
    fact_match = abs(fact_total_shift - ts_hours_sum) < 0.01
    eff_match = abs(eff_final_value - eff_recalc) < 0.01 if plan_total_shift > 0 else eff_final_value == 0
    # pdf_attached уже вычислен выше
    log.info(
        "plan_match=%s | fact_match=%s | eff_match=%s | pdf_attached=%s",
        plan_match,
        fact_match,
        eff_match,
        pdf_attached,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Bitrix shift state.")
    parser.add_argument("shift_id", type=int, help="Bitrix ID of the shift")
    args = parser.parse_args()
    asyncio.run(main(args.shift_id))

