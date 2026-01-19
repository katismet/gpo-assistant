"""Маппинг логических имён полей Bitrix24 к реальным UF_* кодам."""

import json
from functools import lru_cache
from pathlib import Path


# Соответствия «логических имён» нашему проекту → реальным кодам UF_* в Bitrix
LOGICAL_TO_LABEL = {
    # Объект
    "UF_ADDRESS": "Адрес",
    "UF_CODE": "Код/ID",
    # Смена
    "UF_DATE": "Дата",
    "UF_OBJECT_LINK": "Объект",  # Поле связи с объектом (может быть "Объект" или "Ссылка на объект")
    "UF_PLAN_TOTAL": "Плановый объем",  # В Bitrix24 есть пробел, но .strip() уберёт его при сравнении
    "UF_FACT_TOTAL": "Фактический объём",
    "UF_EFF_RAW": "Коэффициент эффективности",
    "UF_EFF_FINAL": "Итоговая эффективность",
    "UF_SHIFT_TYPE": "Тип Смены",
    "UF_STATUS": "Статус",
    "UF_DOWNTIME_REASON": "Причина простоя",
    "UF_SHIFT_PHOTOS": "Фото смены",
    "UF_PLAN_JSON": "План работ (JSON)",
    "UF_FACT_JSON": "Факт работ (JSON)",
    "UF_LPA_FILE": "Файл PDF",  # Поле для загрузки ЛПА
    "UF_PDF_FILE": "Файл PDF",  # Альтернативное название
    # Ресурс
    "UF_SHIFT_ID": "Смена (ID)",
    "UF_RESOURCE_TYPE": "Тип ресурса",
    "UF_EQUIP_TYPE": "Тип техники",
    "UF_EQUIP_HOURS": "Машино-часы",
    "UF_EQUIP_RATE_TYPE": "Тип тарифа",
    "UF_EQUIP_RATE": "Ставка",
    "UF_MAT_TYPE": "Материал",
    "UF_MAT_QTY": "Кол-во",
    "UF_MAT_UNIT": "Ед. изм.",
    "UF_MAT_PRICE": "Цена за ед.",
    "UF_RES_COMMENT": "Комментарий к ресурсу",
    "UF_RES_PHOTOS": "Фото ресурса",
    # Табель
    "UF_SHIFT_ID": "Смена (ID)",  # Для табеля тоже нужен shift_id
    "UF_WORKER": "Сотрудник/бригада",
    "UF_HOURS": "Часы",
    "UF_RATE": "Ставка",
    "UF_TS_COMMENT": "Комментарий к табелю",
    "UF_TS_PHOTOS": "Фото табеля",
}


@lru_cache(maxsize=1)
def _load_map() -> dict:
    path = Path("bitrix_field_map.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def upper_to_camel(uf_name: str) -> str:
    """Конвертирует UF_CRM_9_UF_SHIFT_ID в ufCrm9UfShiftId (формат для Bitrix24 API).
    
    Bitrix24 API принимает поля в camelCase формате при создании/обновлении записей,
    хотя возвращает их в UPPER_CASE в некоторых методах.
    """
    if not uf_name.startswith("UF_"):
        return uf_name
    
    parts = uf_name.split("_")
    result = parts[0].lower()  # uf
    for part in parts[1:]:
        if part:
            if part.isdigit():
                result += part
            else:
                result += part.capitalize()
    return result


def resolve_code(spa_ru_name: str, logical_code: str) -> str:
    """Возвращает реальный UF_* код по названию СПА и логическому имени поля.

    Логика:
    1) пробуем точное совпадение метки (label) из карты
    2) если не нашли — пробуем совпадение по «хвосту» кода (endswith)
    3) иначе возвращаем логическое имя (для стандартных полей)
    
    Возвращает код в UPPER_CASE формате (например, UF_CRM_9_UF_SHIFT_ID).
    Для отправки в Bitrix24 API используйте upper_to_camel() для конвертации в camelCase.
    """
    import logging
    log = logging.getLogger("gpo.field_map")
    
    field_map = _load_map()
    uf = (field_map.get(spa_ru_name) or {}).get("userfields") or {}
    
    log.debug(f"resolve_code('{spa_ru_name}', '{logical_code}') - найдено UF полей: {len(uf)}")

    label = LOGICAL_TO_LABEL.get(logical_code)

    if label:
        for real_code, meta in uf.items():
            if (meta.get("label") or "").strip() == label:
                log.debug(f"Найдено по label '{label}': {logical_code} -> {real_code}")
                return real_code

    for real_code in uf.keys():
        if real_code.endswith(logical_code):
            log.debug(f"Найдено по endswith: {logical_code} -> {real_code}")
            return real_code

    log.warning(f"Не найдено реального кода для '{logical_code}' в '{spa_ru_name}', возвращаем логический код")
    return logical_code

