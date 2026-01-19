# app/handlers/authz.py
"""Авторизация и базовые обработчики."""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import logging

from app.services.authz import bind_user, get_user, get_all_users

router = Router(name="authz")
log = logging.getLogger("gpo.authz")


@router.message(Command("help"))
async def help_command(m: Message):
    """Обработчик команды /help."""
    await m.answer(
        "ГПО-Помощник\n\n"
        "Основные команды:\n"
        "/start - Главное меню\n"
        "/help - Справка\n"
        "/menu - Показать меню\n"
        "/who - Список пользователей\n\n"
        "Используйте кнопки меню для навигации."
    )


@router.message(Command("menu"))
async def menu_command(m: Message):
    """Обработчик команды /menu - показать главное меню."""
    from app.handlers.menu import kb_main, role_of
    role = role_of(m)
    await m.answer("ГПО-Помощник. Выберите действие:", reply_markup=kb_main(role))


@router.message(Command("bind_user"))
async def bind_user_command(m: Message):
    """Привязать пользователя к роли: /bind_user <tg_id> <ROLE> [objects_csv]
    
    Примеры:
    /bind_user 123456789 OWNER
    /bind_user 987654321 FOREMAN 21,23
    /bind_user 111222333 FOREMAN 19,21,25
    """
    try:
        from app.services.authz import upsert_user
        
        parts = m.text.split(maxsplit=3)
        if len(parts) < 3:
            await m.answer(
                "Формат: /bind_user <tg_id> <ROLE> [object_ids_csv]\n\n"
                "Примеры:\n"
                "/bind_user 123456789 OWNER\n"
                "/bind_user 987654321 FOREMAN 21,23\n"
                "/bind_user 111222333 FOREMAN 19,21,25"
            )
            return
        
        user_id = int(parts[1])
        role = parts[2].upper()
        objects_str = parts[3] if len(parts) > 3 else ""
        
        if role not in ("OWNER", "FOREMAN", "ADMIN", "VIEW"):
            await m.answer("Роль должна быть: OWNER, FOREMAN, ADMIN или VIEW")
            return
        
        # Парсим объекты
        objects = []
        if objects_str:
            try:
                objects = [int(x.strip()) for x in objects_str.split(",") if x.strip()]
            except ValueError:
                await m.answer("❌ Неверный формат объектов. Используйте: 21,23,25")
                return
        
        # Используем chat_id = tg_id (можно расширить позже)
        upsert_user(user_id, role, m.chat.id, objects if objects else None)
        
        objects_info = f", объекты: {objects}" if objects else ""
        await m.answer(f"✅ Пользователь {user_id} привязан к роли {role}{objects_info}")
        log.info(f"User {m.from_user.id} bound user {user_id} to role {role}, objects={objects}")
        
    except ValueError as e:
        await m.answer(f"❌ Неверный формат. tg_id должен быть числом: {e}")
    except Exception as e:
        log.error(f"Error in bind_user_command: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка: {e}")


@router.message(Command("who"))
async def who_command(m: Message):
    """Показать список всех пользователей из staff_map.json."""
    try:
        from app.services.authz import list_all
        
        users = list_all()
        if not users:
            await m.answer("Список пользователей пуст.")
            return
        
        lines = ["📋 Список пользователей:\n"]
        for u in users:
            tg_id = u.get("tg_id", "?")
            chat_id = u.get("chat_id", "?")
            role = u.get("role", "FOREMAN")
            name = u.get("name", f"User {tg_id}")
            objects = u.get("objects", [])
            objects_str = f", объекты: {objects}" if objects else ""
            lines.append(f"• {name} (tg_id={tg_id}, chat_id={chat_id}) - {role}{objects_str}")
        
        await m.answer("\n".join(lines))
    except Exception as e:
        log.error(f"Error in who_command: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка: {e}")

