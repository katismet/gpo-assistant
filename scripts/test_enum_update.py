"""Тест обновления enum значений."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.resource_meta import resource_type_bitrix_label
from app.services.bitrix_enums import enum_payload

async def main():
    # Получаем существующий ресурс
    res_list = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType', 'ufCrm9UfEquipType'],
        'limit': 5
    })
    
    f_res_type = resolve_code("Ресурс", "UF_RESOURCE_TYPE")
    f_res_type_camel = upper_to_camel(f_res_type) if f_res_type and f_res_type.startswith("UF_") else None
    
    print(f"Поле: {f_res_type} -> {f_res_type_camel}\n")
    
    # Находим ресурс с материалом
    mat_res = None
    equip_res = None
    
    for item in res_list.get('items', []):
        if item.get('ufCrm9UfMatType') and not item.get('ufCrm9UfEquipType'):
            mat_res = item
        elif item.get('ufCrm9UfEquipType') and not item.get('ufCrm9UfMatType'):
            equip_res = item
        if mat_res and equip_res:
            break
    
    # Обновляем ресурс с материалом
    if mat_res:
        res_id = mat_res['id']
        print(f"Обновляем ресурс с материалом (ID={res_id})")
        print(f"Текущее значение: {mat_res.get('ufCrm9UfResourceType')}")
        
        # Обновляем с "Материал"
        label_mat = resource_type_bitrix_label("MAT")
        payload_mat = enum_payload(label_mat)
        print(f"Отправляем: {payload_mat}")
        
        result = await bx('crm.item.update', {
            'entityTypeId': RESOURCE_ETID,
            'id': res_id,
            'fields': {f_res_type_camel: payload_mat}
        })
        
        check = await bx('crm.item.get', {
            'entityTypeId': RESOURCE_ETID,
            'id': res_id,
            'select': ['id', f_res_type_camel]
        })
        print(f"После обновления: {check.get('item', {}).get(f_res_type_camel)}\n")
    
    # Обновляем ресурс с техникой
    if equip_res:
        res_id = equip_res['id']
        print(f"Обновляем ресурс с техникой (ID={res_id})")
        print(f"Текущее значение: {equip_res.get('ufCrm9UfResourceType')}")
        
        # Обновляем с "Техника"
        label_equip = resource_type_bitrix_label("EQUIP")
        payload_equip = enum_payload(label_equip)
        print(f"Отправляем: {payload_equip}")
        
        result = await bx('crm.item.update', {
            'entityTypeId': RESOURCE_ETID,
            'id': res_id,
            'fields': {f_res_type_camel: payload_equip}
        })
        
        check = await bx('crm.item.get', {
            'entityTypeId': RESOURCE_ETID,
            'id': res_id,
            'select': ['id', f_res_type_camel]
        })
        print(f"После обновления: {check.get('item', {}).get(f_res_type_camel)}")

if __name__ == "__main__":
    asyncio.run(main())



