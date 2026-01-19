# app/services/authz.py
"""Сервис авторизации и получения ролей пользователей из staff_map.json"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Literal

log = logging.getLogger("gpo.authz")

# Тип роли
ROLE = Literal["OWNER", "FOREMAN", "ADMIN", "VIEW"]

# Путь к файлу staff_map.json
STAFF_MAP_FILE = Path("staff_map.json")


def _load() -> dict:
    """Загрузить данные из staff_map.json."""
    if not STAFF_MAP_FILE.exists():
        return {"staff": {}}
    try:
        with open(STAFF_MAP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Поддержка старого формата {"staff": {...}} и нового {"users": [...]}
            if "users" in data:
                return data
            elif "staff" in data:
                # Конвертируем старый формат в новый для совместимости
                users = []
                for user_id, user_data in data["staff"].items():
                    users.append({
                        "tg_id": int(user_id),
                        "chat_id": int(user_id),  # По умолчанию chat_id = tg_id
                        "role": user_data.get("role", "FOREMAN").upper(),
                        "name": user_data.get("name", f"User {user_id}"),
                        "objects": user_data.get("objects", [])
                    })
                return {"users": users}
            return {"users": []}
    except Exception as e:
        log.error(f"Error loading staff_map.json: {e}", exc_info=True)
        return {"users": []}


def _save(data: dict):
    """Сохранить данные в staff_map.json."""
    try:
        STAFF_MAP_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        log.error(f"Error saving staff_map.json: {e}", exc_info=True)
        raise


def load_staff_map() -> Dict[str, Dict]:
    """Загрузить карту сотрудников из staff_map.json (старый формат для совместимости)."""
    data = _load()
    users = data.get("users", [])
    staff_map = {}
    for u in users:
        user_str = str(u.get("tg_id", 0))
        staff_map[user_str] = {
            "role": u.get("role", "FOREMAN").upper(),
            "name": u.get("name", f"User {user_str}"),
            "objects": u.get("objects", [])
        }
    return staff_map


def get_user(tg_id: int) -> Optional[dict]:
    """Получить информацию о пользователе по Telegram ID."""
    data = _load()
    for u in data.get("users", []):
        if int(u.get("tg_id", 0)) == int(tg_id):
            # Нормализуем роль
            user_data = u.copy()
            if "role" in user_data:
                user_data["role"] = user_data["role"].upper()
            return user_data
    return None


def upsert_user(tg_id: int, role: str, chat_id: int, objects: List[int] | None = None):
    """Создать или обновить пользователя."""
    data = _load()
    users = data.get("users", [])
    
    # Нормализуем роль
    role = role.upper()
    if role not in ("OWNER", "FOREMAN", "ADMIN", "VIEW"):
        raise ValueError(f"Invalid role: {role}")
    
    # Ищем существующего пользователя
    u = get_user(tg_id)
    if u:
        # Обновляем существующего
        for user in users:
            if int(user.get("tg_id", 0)) == int(tg_id):
                user["role"] = role
                user["chat_id"] = int(chat_id)
                user["objects"] = objects if objects is not None else user.get("objects", [])
                break
    else:
        # Создаем нового
        users.append({
            "tg_id": int(tg_id),
            "chat_id": int(chat_id),
            "role": role,
            "name": f"User {tg_id}",
            "objects": objects or []
        })
    
    data["users"] = users
    _save(data)
    log.info(f"Upserted user: tg_id={tg_id}, role={role}, chat_id={chat_id}, objects={objects}")


def list_by_role(role: str) -> List[dict]:
    """Получить список пользователей по роли."""
    data = _load()
    role = role.upper()
    return [u for u in data.get("users", []) if u.get("role", "").upper() == role]


def list_all() -> List[dict]:
    """Получить список всех пользователей."""
    data = _load()
    return list(data.get("users", []))


def allowed_for_object(tg_id: int, object_id: int) -> bool:
    """Проверить, имеет ли пользователь доступ к объекту."""
    u = get_user(tg_id)
    if not u:
        return False
    
    role = u.get("role", "").upper()
    # OWNER и ADMIN имеют доступ ко всем объектам
    if role in ("OWNER", "ADMIN"):
        return True
    
    # FOREMAN и другие - только к своим объектам
    objs = u.get("objects", [])
    return int(object_id) in [int(x) for x in objs]


def save_staff_map(staff_map: Dict[str, Dict]) -> bool:
    """Сохранить карту сотрудников в staff_map.json (старый формат для совместимости)."""
    try:
        # Конвертируем старый формат в новый
        users = []
        for user_id, user_data in staff_map.items():
            users.append({
                "tg_id": int(user_id),
                "chat_id": int(user_id),
                "role": user_data.get("role", "FOREMAN").upper(),
                "name": user_data.get("name", f"User {user_id}"),
                "objects": user_data.get("objects", [])
            })
        data = {"users": users}
        _save(data)
        return True
    except Exception as e:
        log.error(f"Error saving staff_map.json: {e}", exc_info=True)
        return False


def bind_user(user_id: int, role: str, name: str = None) -> bool:
    """Привязать пользователя к роли в staff_map.json (старый формат для совместимости)."""
    try:
        upsert_user(int(user_id), role, int(user_id), None)
        # Обновляем имя если указано
        if name:
            data = _load()
            for u in data.get("users", []):
                if int(u.get("tg_id", 0)) == int(user_id):
                    u["name"] = name
                    _save(data)
                    break
        return True
    except Exception as e:
        log.error(f"Error in bind_user: {e}", exc_info=True)
        return False


def get_all_users() -> Dict[str, Dict]:
    """Получить всех пользователей из staff_map.json (старый формат для совместимости)."""
    return load_staff_map()

