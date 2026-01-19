"""Авто-синхронизация Bitrix24 → .env и bitrix_field_map.json"""

import os
import sys
import json
import re
from pathlib import Path
import httpx
from dotenv import dotenv_values, load_dotenv

# Загружаем .env
load_dotenv()

BITRIX = os.getenv("BITRIX_WEBHOOK_URL")
if not BITRIX:
    print("ERROR: .env must contain BITRIX_WEBHOOK_URL")
    sys.exit(1)

# Какие названия ищем в Bitrix → какие переменные записывать в .env
TYPE_NAME_TO_ENV = {
    "Объект": "ENTITY_OBJECT",
    "Смена": "ENTITY_SHIFT",
    "Ресурс": "ENTITY_RESOURCE",
    "Табель": "ENTITY_TIMESHEET",
}


def bx(method: str, payload=None, method_http="POST"):
    """Вызов Bitrix REST API."""
    url = f"{BITRIX}/{method}"
    if method_http == "GET":
        r = httpx.get(url, params=payload, timeout=30)
    else:
        r = httpx.post(url, json=payload or {}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"{method} error: {data.get('error_description')}")
    return data.get("result")


def list_types():
    """Получить список смарт-процессов (crm.type.list)."""
    res = bx("crm.type.list", {"filter": {}, "select": ["id", "title", "entityTypeId"]})
    # result: {"types":[{id, title, entityTypeId, ...}], "total": ...}
    types = res.get("types", []) if isinstance(res, dict) else res
    return [
        {
            "id": t.get("id"),
            "title": t.get("title"),
            "entityTypeId": t.get("entityTypeId") or t.get("id"),
        }
        for t in types or []
    ]


def list_userfields(entity_type_id: int):
    """Получить коды пользовательских UF_* полей."""
    try:
        res = bx("crm.item.userfield.list", {"entityTypeId": entity_type_id})
        items = res.get("userFields", []) if isinstance(res, dict) else res
        out = {}
        for uf in items or []:
            code = uf.get("FIELD_NAME")
            label = uf.get("EDIT_FORM_LABEL") or uf.get("LIST_COLUMN_LABEL")
            out[code] = {"label": label, "type": uf.get("USER_TYPE_ID")}
        return out
    except Exception as e:
        print(f"⚠ Не удалось получить user fields для {entity_type_id}: {e}")
        return {}

def list_uf_from_fields(entity_type_id: int):
    """Получить UF_* поля из crm.item.fields или crm.item.userfield.list как резерв."""
    uf = {}
    
    # Пробуем через crm.item.fields
    try:
        result = bx("crm.item.fields", {"entityTypeId": entity_type_id}) or {}
        # Поля могут быть в result["fields"] или напрямую в result
        fields = result.get("fields", result) if isinstance(result, dict) else {}
        
        for k, v in fields.items():
            if not isinstance(v, dict):
                continue
            
            # Проверяем, является ли поле UF полем
            # Может быть в camelCase (ufCrm9UfShiftId) или в верхнем регистре (UF_CRM_9_UF_SHIFT_ID)
            upper_name = v.get("upperName") or k.upper()
            
            if upper_name.startswith("UF_"):
                # Используем upperName как реальный код поля
                uf[upper_name] = {
                    "label": v.get("title") or v.get("formLabel") or v.get("listLabel") or upper_name,
                    "type": v.get("type")
                }
    except Exception as e:
        print(f"⚠ crm.item.fields не сработал: {e}")
    
    # Если не нашлись, пробуем через crm.item.userfield.list
    if not uf:
        try:
            print(f"   Пробуем crm.item.userfield.list для {entity_type_id}...")
            res = bx("crm.item.userfield.list", {"entityTypeId": entity_type_id})
            items = res.get("userFields", []) if isinstance(res, dict) else res
            for uf_item in items or []:
                code = uf_item.get("FIELD_NAME")
                if code and code.startswith("UF_"):
                    uf[code] = {
                        "label": uf_item.get("EDIT_FORM_LABEL") or uf_item.get("LIST_COLUMN_LABEL") or code,
                        "type": uf_item.get("USER_TYPE_ID")
                    }
            if uf:
                print(f"   ✅ Найдено {len(uf)} UF полей через userfield.list")
        except Exception as e:
            print(f"   ⚠ crm.item.userfield.list тоже не сработал: {e}")
    
    return uf


def list_all_fields(entity_type_id: int):
    """Получить все поля (стандартные + UF)."""
    res = bx("crm.item.fields", {"entityTypeId": entity_type_id})
    # res -> dict of fields
    fields = res or {}
    return fields


def update_env(pairs: dict):
    """Обновить .env файл, добавив/изменив указанные переменные."""
    env_path = Path(".env")
    existing = {}
    if env_path.exists():
        existing = dotenv_values(".env")
    
    # Обновляем строки (без разрушения остального)
    lines = []
    seen = set()
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
                if m:
                    k, v = m.group(1), m.group(2)
                    if k in pairs:
                        lines.append(f"{k}={pairs[k]}\n")
                        seen.add(k)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
    
    # Добавляем недостающие
    for k, v in pairs.items():
        if k not in seen and (not existing or k not in existing):
            lines.append(f"{k}={v}\n")
    
    with env_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    print(f"🔍 Подключение к Bitrix24: {BITRIX}")
    
    types = list_types()
    if not types:
        print("Не получен список смарт-процессов (crm.type.list). Проверь BITRIX_WEBHOOK_URL и права.")
        sys.exit(2)

    # Сопоставляем по названию
    name_to_type = {t["title"]: t for t in types}
    env_updates = {}
    field_map = {}

    for ru_name, env_var in TYPE_NAME_TO_ENV.items():
        t = name_to_type.get(ru_name)
        if not t:
            print(f"⚠ Не найден тип «{ru_name}»")
            continue
        
        etid = t["entityTypeId"]
        env_updates[env_var] = str(etid)

        # Тянем поля
        print(f"Получаю поля для {ru_name} (entityTypeId={etid})...")
        uf = list_uf_from_fields(etid)  # Используем функцию с резервом через userfield.list
        all_fields = bx("crm.item.fields", {"entityTypeId": etid}) or {}
        std = list(all_fields.keys()) if isinstance(all_fields, dict) else []
        
        field_map[ru_name] = {
            "entityTypeId": etid,
            "title": t["title"],
            "userfields": uf,            # Только UF_* (то, что ты видишь в списке)
            "std_fields": std  # std уже список
        }

        # Короткая сводка в консоль
        first_ufs = ", ".join(list(uf.keys())[:10]) if uf else "-"
        print(f"✔ {ru_name}: entityTypeId={etid} | UF: {first_ufs}")

    # Пишем .env
    if env_updates:
        update_env(env_updates)
        print("✅ .env обновлён:", " ".join([f"{k}={v}" for k, v in env_updates.items()]))

    # Сохраняем карту полей
    with open("bitrix_field_map.json", "w", encoding="utf-8") as f:
        json.dump(field_map, f, ensure_ascii=False, indent=2)
    print("✅ bitrix_field_map.json создан/обновлён")


if __name__ == "__main__":
    main()
