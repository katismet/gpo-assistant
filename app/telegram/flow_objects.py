"""W5 Flow - Объекты."""

from typing import List, Dict, Any

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.models import User as DBUser, Object
from app.telegram.fsm_states import WorkflowState
from app.telegram.keyboards import (
    get_back_keyboard,
    get_confirmation_keyboard,
    get_main_menu_keyboard,
    get_objects_menu_keyboard,
    get_pagination_keyboard,
)
from app.services.bitrix import BitrixService

router = Router()


@router.message(StateFilter(WorkflowState.OBJECTS_LIST))
async def objects_list(message: Message, state: FSMContext, db_user: DBUser):
    """Список объектов."""
    # Здесь должна быть логика получения объектов из базы данных
    # Пока используем заглушку
    objects = get_mock_objects()
    
    if objects:
        objects_text = format_objects_list(objects)
        await message.answer(
            f"🏗️ Список объектов:\n\n{objects_text}",
            reply_markup=get_objects_menu_keyboard(),
        )
    else:
        await message.answer(
            "📭 Объекты не найдены",
            reply_markup=get_objects_menu_keyboard(),
        )
    
    logger.info(f"User {db_user.tg_id} viewed objects list")


@router.message(StateFilter(WorkflowState.OBJECTS_DETAILS))
async def objects_details(message: Message, state: FSMContext, db_user: DBUser):
    """Детали объекта."""
    text = message.text
    
    # Парсинг ID объекта из текста
    object_id = parse_object_id_from_text(text)
    
    if object_id:
        # Здесь должна быть логика получения объекта из базы данных
        object_data = get_mock_object_details(object_id)
        
        if object_data:
            details_text = format_object_details(object_data)
            await message.answer(
                f"🏗️ Детали объекта:\n\n{details_text}",
                reply_markup=get_objects_menu_keyboard(),
            )
        else:
            await message.answer(
                "❌ Объект не найден",
                reply_markup=get_back_keyboard(),
            )
    else:
        await message.answer(
            "❌ Неверный формат. Укажите ID объекта:",
            reply_markup=get_back_keyboard(),
        )


def get_mock_objects() -> List[Dict[str, Any]]:
    """Получение заглушки объектов."""
    return [
        {
            "id": 1,
            "name": "Объект А",
            "description": "Строительство жилого дома",
            "address": "ул. Строительная, 1",
            "status": "active",
            "shifts_count": 5,
            "last_shift": "2024-01-15",
        },
        {
            "id": 2,
            "name": "Объект Б",
            "description": "Ремонт дороги",
            "address": "пр. Дорожный, 10",
            "status": "active",
            "shifts_count": 3,
            "last_shift": "2024-01-14",
        },
        {
            "id": 3,
            "name": "Объект В",
            "description": "Установка забора",
            "address": "ул. Заборная, 5",
            "status": "completed",
            "shifts_count": 2,
            "last_shift": "2024-01-10",
        },
    ]


def get_mock_object_details(object_id: int) -> Dict[str, Any]:
    """Получение заглушки деталей объекта."""
    objects = get_mock_objects()
    for obj in objects:
        if obj["id"] == object_id:
            return {
                **obj,
                "bitrix_id": 1000 + object_id,
                "created_at": "2024-01-01",
                "manager": "Иванов И.И.",
                "budget": 1000000,
                "progress": 75,
                "shifts": [
                    {
                        "id": 1,
                        "date": "2024-01-15",
                        "type": "day",
                        "status": "completed",
                        "efficiency": 85,
                    },
                    {
                        "id": 2,
                        "date": "2024-01-16",
                        "type": "night",
                        "status": "open",
                        "efficiency": None,
                    },
                ],
            }
    return None


def format_objects_list(objects: List[Dict[str, Any]]) -> str:
    """Форматирование списка объектов."""
    if not objects:
        return "Объекты не найдены"
    
    lines = []
    for obj in objects:
        status_emoji = "🟢" if obj["status"] == "active" else "🔴"
        lines.append(
            f"{status_emoji} {obj['name']} (ID: {obj['id']})\n"
            f"   📍 {obj['address']}\n"
            f"   📅 Смен: {obj['shifts_count']}, последняя: {obj['last_shift']}\n"
        )
    
    return "\n".join(lines)


def format_object_details(object_data: Dict[str, Any]) -> str:
    """Форматирование деталей объекта."""
    lines = [
        f"🏗️ {object_data['name']}",
        f"📝 {object_data['description']}",
        f"📍 {object_data['address']}",
        f"👤 Менеджер: {object_data['manager']}",
        f"💰 Бюджет: {object_data['budget']:,} руб.",
        f"📊 Прогресс: {object_data['progress']}%",
        f"🆔 Bitrix ID: {object_data['bitrix_id']}",
        "",
        "📅 Смены:",
    ]
    
    for shift in object_data["shifts"]:
        status_emoji = "✅" if shift["status"] == "completed" else "🔄"
        type_emoji = "☀️" if shift["type"] == "day" else "🌙"
        efficiency_text = f" ({shift['efficiency']}%)" if shift["efficiency"] else ""
        
        lines.append(
            f"   {status_emoji} {type_emoji} {shift['date']}{efficiency_text}"
        )
    
    return "\n".join(lines)


def parse_object_id_from_text(text: str) -> int:
    """Парсинг ID объекта из текста."""
    try:
        # Ищем ID в формате "ID: 123" или просто число
        import re
        
        # Ищем "ID: число"
        id_match = re.search(r'ID:\s*(\d+)', text)
        if id_match:
            return int(id_match.group(1))
        
        # Ищем просто число
        number_match = re.search(r'\b(\d+)\b', text)
        if number_match:
            return int(number_match.group(1))
        
        return None
    except (ValueError, AttributeError):
        return None


async def create_object_in_bitrix(name: str, description: str = "") -> int:
    """Создание объекта в Bitrix24."""
    try:
        async with BitrixService() as bitrix:
            bitrix_id = await bitrix.create_object(name)
            logger.info(f"Object created in Bitrix24 with ID: {bitrix_id}")
            return bitrix_id
    except Exception as e:
        logger.error(f"Failed to create object in Bitrix24: {e}")
        raise


async def sync_objects_with_bitrix():
    """Синхронизация объектов с Bitrix24."""
    try:
        async with BitrixService() as bitrix:
            # Получаем объекты из Bitrix24
            deals = await bitrix.list_deals(
                filter_data={"STAGE_ID": "NEW"},  # Фильтр по стадии
                select=["ID", "TITLE", "OPPORTUNITY", "UF_CRM_OBJECT_ID"],
            )
            
            logger.info(f"Synced {len(deals)} objects from Bitrix24")
            return deals
            
    except Exception as e:
        logger.error(f"Failed to sync objects with Bitrix24: {e}")
        return []
