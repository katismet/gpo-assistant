from .bitrix import bx_get
from app.services.bitrix_ids import OBJECT_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel
import logging

log = logging.getLogger("gpo.objects")

async def fetch_all_objects():
    """
    Получает список объектов из Bitrix24 с кодами.
    
    Returns:
        List[tuple]: Список кортежей (bitrix_id, title, code)
        где code - это код объекта (OBJ-001) или пустая строка, если не указан
    """
    # Получаем код поля для кода объекта
    uf_code = resolve_code("Объект", "UF_CODE")
    uf_code_camel = upper_to_camel(uf_code) if uf_code and uf_code.startswith("UF_") else None
    
    # Формируем список полей для выборки
    select_fields = ["id", "title"]
    if uf_code_camel:
        select_fields.append(uf_code_camel)
    
    data = await bx_get("crm.item.list", entityTypeId=OBJECT_ETID, **{"select[]": select_fields}, start=0)
    items = data["result"]["items"]
    
    objs = []
    for i in items:
        bitrix_id = int(i["id"])
        title = i.get("title", f"Объект #{bitrix_id}")
        # Получаем код объекта (может быть в разных форматах)
        code = ""
        if uf_code_camel:
            code = i.get(uf_code_camel) or i.get(uf_code) or ""
        if not code:
            # Пробуем найти код в других возможных полях
            code = i.get("ufCrm5UfCrmObjectCode") or i.get("UF_CRM_5_UF_CRM_OBJECT_CODE") or ""
        
        # Если код не найден, используем пустую строку (будет показан только title)
        code = str(code).strip() if code else ""
        
        objs.append((bitrix_id, title, code))
    
    log.debug("fetch_all_objects count=%d", len(objs))
    return objs
