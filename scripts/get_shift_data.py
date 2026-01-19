"""Получение данных смены из Bitrix24 для проверки."""

import asyncio
import json
import sys
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel

async def get_shift_data(shift_id: int):
    f_plan_total = resolve_code('Смена', 'UF_PLAN_TOTAL')
    f_fact_total = resolve_code('Смена', 'UF_FACT_TOTAL')
    f_plan_json = resolve_code('Смена', 'UF_PLAN_JSON')
    f_fact_json = resolve_code('Смена', 'UF_FACT_JSON')
    f_date = resolve_code('Смена', 'UF_DATE')
    f_object_link = resolve_code('Смена', 'UF_OBJECT_LINK')
    
    f_plan_total_camel = upper_to_camel(f_plan_total) if f_plan_total else None
    f_fact_total_camel = upper_to_camel(f_fact_total) if f_fact_total else None
    f_plan_json_camel = upper_to_camel(f_plan_json) if f_plan_json else None
    f_fact_json_camel = upper_to_camel(f_fact_json) if f_fact_json else None
    f_date_camel = upper_to_camel(f_date) if f_date else None
    f_object_link_camel = upper_to_camel(f_object_link) if f_object_link else None
    
    result = await bx('crm.item.get', {
        'entityTypeId': SHIFT_ETID,
        'id': shift_id,
        'select': ['id', '*', 'ufCrm%']
    })
    
    if result:
        item = result.get('item', result) if isinstance(result, dict) else result
        print('=== Данные смены из Bitrix24 ===')
        print(f'ID: {item.get("id")}')
        print(f'Дата смены: {item.get(f_date_camel) or item.get(f_date) or "Не указана"}')
        print(f'UF_PLAN_TOTAL: {item.get(f_plan_total_camel) or item.get("ufCrm7UfCrmPlanTotal") or 0}')
        print(f'UF_FACT_TOTAL: {item.get(f_fact_total_camel) or item.get("ufCrm7UfCrmFactTotal") or 0}')
        obj_link = item.get(f_object_link_camel) or item.get("ufCrm7UfCrmObject") or "Не указана"
        print(f'UF_OBJECT_LINK: {obj_link}')
        
        plan_json_raw = item.get(f_plan_json_camel) or item.get('ufCrm7UfPlanJson') or ''
        fact_json_raw = item.get(f_fact_json_camel) or item.get('ufCrm7UfFactJson') or ''
        
        # Обрабатываем случай, когда Bitrix возвращает список
        if isinstance(plan_json_raw, list):
            if plan_json_raw and isinstance(plan_json_raw[0], str):
                plan_json_raw = plan_json_raw[0]
            elif plan_json_raw and isinstance(plan_json_raw[0], dict):
                plan_json_raw = plan_json_raw[0]
            else:
                plan_json_raw = ''
        
        print(f'UF_PLAN_JSON (length): {len(plan_json_raw) if isinstance(plan_json_raw, str) and plan_json_raw else 0} chars')
        if plan_json_raw:
            try:
                if isinstance(plan_json_raw, str):
                    plan_json = json.loads(plan_json_raw)
                elif isinstance(plan_json_raw, dict):
                    plan_json = plan_json_raw
                else:
                    plan_json = {}
                
                if plan_json:
                    print(f'UF_PLAN_JSON (parsed): total_plan={plan_json.get("total_plan")}, tasks={len(plan_json.get("tasks", []))}')
                    if plan_json.get('meta'):
                        meta = plan_json.get('meta')
                        print(f'UF_PLAN_JSON.meta: object_bitrix_id={meta.get("object_bitrix_id")}, object_name={meta.get("object_name")}')
            except Exception as e:
                print(f'UF_PLAN_JSON: не удалось распарсить: {e}')
        
        print(f'UF_FACT_JSON (length): {len(fact_json_raw) if fact_json_raw else 0} chars')
        if fact_json_raw:
            try:
                fact_json = json.loads(fact_json_raw) if isinstance(fact_json_raw, str) else fact_json_raw
                print(f'UF_FACT_JSON (parsed): total_fact={fact_json.get("total_fact")}, tasks={len(fact_json.get("tasks", []))}')
            except Exception as e:
                print(f'UF_FACT_JSON: не удалось распарсить: {e}')
    else:
        print('Ошибка: не удалось получить данные смены из Bitrix24')

if __name__ == '__main__':
    shift_id = int(sys.argv[1]) if len(sys.argv) > 1 else 397
    asyncio.run(get_shift_data(shift_id))

