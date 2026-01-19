"""Bitrix клиент для W3 Resource Management."""

import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from app.services.bitrix import bx_post
from app.services.http_client import bx as bx_http
from app.services.bitrix_ids import RESOURCE_ETID, SHIFT_ETID, OBJECT_ETID
from app.services.bitrix_ids import (
    UF_SHIFT_ID, UF_RESOURCE_TYPE,
    UF_EQUIP_TYPE, UF_EQUIP_HOURS, UF_EQUIP_RATE_TYPE, UF_EQUIP_RATE,
    UF_MAT_TYPE, UF_MAT_QTY, UF_MAT_UNIT, UF_MAT_PRICE
)
from app.services.resource_meta import (
    resource_type_bitrix_label,
    rate_type_bitrix_label,
)
from app.services.bitrix_enums import get_resource_type_enum

log = logging.getLogger("resource_client")

async def build_resource_fields(data: dict, entity_type_name="Ресурс") -> dict:
    """Строит поля для Bitrix24 на основе данных ресурса с динамическим маппингом.
    
    Args:
        data: Словарь с данными ресурса (equip_type, equip_hours, mat_type, mat_qty и т.д.)
        entity_type_name: Название сущности в Bitrix (по умолчанию "Ресурс")
    
    Returns:
        Словарь полей для Bitrix24 API
    """
    from app.bitrix_field_map import resolve_code, upper_to_camel
    
    fields = {}
    
    # Маппинг полей
    field_mapping = {
        "shift_id": ("UF_SHIFT_ID", "Смена (ID)"),
        "resource_type": ("UF_RESOURCE_TYPE", "Тип ресурса"),
        "equip_type": ("UF_EQUIP_TYPE", "Тип техники"),
        "equip_hours": ("UF_EQUIP_HOURS", "Машино-часы"),
        "equip_rate_type": ("UF_EQUIP_RATE_TYPE", "Тип тарифа"),
        "equip_rate": ("UF_EQUIP_RATE", "Ставка"),
        "mat_type": ("UF_MAT_TYPE", "Материал"),
        "mat_qty": ("UF_MAT_QTY", "Кол-во"),
        "mat_unit": ("UF_MAT_UNIT", "Ед. изм."),
        "mat_price": ("UF_MAT_PRICE", "Цена за ед."),
    }
    
    for key, (logical_code, label) in field_mapping.items():
        value = data.get(key)
        if value is not None:
            # Получаем реальный код поля через маппинг
            real_code = resolve_code(entity_type_name, logical_code)
            if real_code and real_code.startswith("UF_"):
                camel_code = upper_to_camel(real_code)
                transformed_value = value
                if key == "resource_type":
                    label = resource_type_bitrix_label(value)
                    if label:
                        # Используем BitrixEnumHelper для получения числового ID
                        resource_type_enum = get_resource_type_enum()
                        enum_id = await resource_type_enum.get_id(label)
                        
                        # Если enum_id не найден для конкретного label, но есть другие значения с ID,
                        # используем первый доступный ID (так как в Bitrix может быть только один вариант enum)
                        if enum_id is None:
                            # Пытаемся найти любой доступный ID
                            if resource_type_enum._id_to_label:
                                enum_id = list(resource_type_enum._id_to_label.keys())[0]
                                log.warning(
                                    f"[RESOURCE] Enum ID not found for label '{label}', "
                                    f"using available ID {enum_id} (Bitrix may have only one enum value)"
                                )
                        
                        if enum_id is not None:
                            # Отправляем только числовой ID, а не {"value": "..."}
                            transformed_value = enum_id
                            log.debug(f"[RESOURCE] Mapped resource_type '{value}' -> label '{label}' -> enum_id {enum_id}")
                        else:
                            log.warning(f"[RESOURCE] No enum ID available for resource_type, skipping field")
                            # Не устанавливаем поле, если ID не найден
                            continue
                    else:
                        transformed_value = value
                elif key == "equip_rate_type":
                    # Для equip_rate_type пока оставляем старую логику, если это не enum поле
                    # Или можно создать отдельный helper если нужно
                    label = rate_type_bitrix_label(value)
                    if label:
                        transformed_value = label
                    else:
                        transformed_value = value
                fields[camel_code] = transformed_value
                log.debug(f"Mapped {key} -> {camel_code} = {transformed_value}")
            else:
                log.warning(f"Could not resolve field code for {logical_code} in {entity_type_name}")
    
    return fields

async def bitrix_add_resource(resource_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Добавляет ресурс в Bitrix24.
    
    Args:
        resource_data: Словарь с данными ресурса
        
    Returns:
        Ответ от Bitrix24 API
    """
    try:
        fields = await build_resource_fields(resource_data)
        
        # Добавляем заголовок
        resource_type = resource_data.get("resource_type", "UNKNOWN")
        if resource_type == "EQUIP":
            title = f"Техника: {resource_data.get('equip_type', 'Не указано')}"
        else:
            title = f"Материал: {resource_data.get('mat_type', 'Не указано')}"
        
        fields["TITLE"] = title
        
        log.info(f"[RESOURCE] Adding resource to Bitrix24: {title}")
        
        # Проверяем формат enum-поля (должен быть числовой ID, а не {"value": "..."})
        from app.bitrix_field_map import resolve_code, upper_to_camel
        f_res_type = resolve_code("Ресурс", "UF_RESOURCE_TYPE")
        f_res_type_camel = upper_to_camel(f_res_type) if f_res_type and f_res_type.startswith("UF_") else None
        if f_res_type_camel and f_res_type_camel in fields:
            enum_value = fields[f_res_type_camel]
            if isinstance(enum_value, int):
                log.info(f"[RESOURCE] UF_RESOURCE_TYPE sent as numeric ID: {enum_value} (correct format)")
            elif isinstance(enum_value, dict):
                log.warning(f"[RESOURCE] UF_RESOURCE_TYPE sent as dict: {enum_value} (should be numeric ID!)")
            else:
                log.warning(f"[RESOURCE] UF_RESOURCE_TYPE sent as: {enum_value} (type: {type(enum_value)})")
        
        log.debug(f"[RESOURCE] Fields: {fields}")
        
        result = await bx_post("crm.item.add", {
            "entityTypeId": RESOURCE_ETID,
            "fields": fields
        })
        
        resource_id = result.get("result", {}).get("item", {}).get("id") if isinstance(result, dict) else None
        shift_id = resource_data.get("shift_id")
        
        if resource_id:
            log.info(f"[RESOURCE] Resource created in Bitrix24: resource_id={resource_id}, shift_id={shift_id}, type={resource_data.get('resource_type')}")
        
        return result
        
    except Exception as e:
        log.error(f"Error creating resource in Bitrix24: {e}")
        raise

async def bitrix_get_shifts_by_object_date(object_bitrix_id: int, shift_date: date) -> Optional[int]:
    """
    DEPRECATED: Используйте app.services.shift_client.bitrix_get_shift_for_object_and_date вместо этой функции.
    
    Находит или создает смену для объекта и даты.
    
    Args:
        object_bitrix_id: Bitrix ID объекта (не локальный ID!)
        shift_date: Дата смены
        
    Returns:
        Bitrix ID смены в Bitrix24 или None
    """
    log.warning("[RESOURCE] bitrix_get_shifts_by_object_date is deprecated, use shift_client.bitrix_get_shift_for_object_and_date instead")
    from app.services.shift_client import bitrix_get_shift_for_object_and_date
    shift_id, _ = await bitrix_get_shift_for_object_and_date(
        object_bitrix_id=object_bitrix_id,
        target_date=shift_date,
        create_if_not_exists=True,  # Старая функция всегда создавала смену
    )
    return shift_id

def validate_resource_data(resource_data: Dict[str, Any]) -> List[str]:
    """
    Валидирует данные ресурса перед отправкой в Bitrix24.
    
    Args:
        resource_data: Словарь с данными ресурса
        
    Returns:
        Список ошибок (пустой список, если все ОК)
    """
    errors = []
    
    resource_type = resource_data.get("resource_type")
    if not resource_type:
        errors.append("Не указан тип ресурса")
        return errors
    
    if resource_type == "EQUIP":
        if not resource_data.get("equip_type"):
            errors.append("Не указан тип техники")
        if not resource_data.get("equip_hours"):
            errors.append("Не указаны машино-часы")
        if not resource_data.get("equip_rate"):
            errors.append("Не указана ставка")
    elif resource_type == "MAT":
        if not resource_data.get("mat_type"):
            errors.append("Не указан тип материала")
        if not resource_data.get("mat_qty"):
            errors.append("Не указано количество")
        if not resource_data.get("mat_unit"):
            errors.append("Не указана единица измерения")
        if not resource_data.get("mat_price"):
            errors.append("Не указана цена")
    else:
        errors.append(f"Неизвестный тип ресурса: {resource_type}")
    
    return errors

def _is_numeric(value: str) -> bool:
    """Проверяет, является ли строка числом."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def format_resource_summary(resource_data: Dict[str, Any]) -> str:
    """
    Форматирует краткую сводку ресурса для отображения пользователю.
    
    Args:
        resource_data: Словарь с данными ресурса
        
    Returns:
        Отформатированная строка
    """
    resource_type = resource_data.get("resource_type", "UNKNOWN")
    
    if resource_type == "EQUIP":
        equip_type = resource_data.get("equip_type", "Не указано")
        hours = resource_data.get("equip_hours", 0)
        rate = resource_data.get("equip_rate", 0)
        rate_type = resource_data.get("equip_rate_type", "")
        return f"Техника: {equip_type}\nЧасы: {hours}\nСтавка: {rate} {rate_type}"
    elif resource_type == "MAT":
        mat_type = resource_data.get("mat_type", "Не указано")
        qty = resource_data.get("mat_qty", 0)
        unit = resource_data.get("mat_unit", "")
        price = resource_data.get("mat_price", 0)
        return f"Материал: {mat_type}\nКол-во: {qty} {unit}\nЦена: {price}"
    else:
        return "Неизвестный тип ресурса"
