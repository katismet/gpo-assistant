"""Справочники для W3 Resource Management."""

from typing import List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Справочники по умолчанию
EQUIP_TYPES = [
    "Экскаватор JCB",
    "Погрузчик", 
    "Самосвал 20т",
    "Каток",
    "Бульдозер",
    "Кран"
]

RATE_TYPES = [
    ("HOUR", "час"),
    ("SHIFT", "смена"), 
    ("TRIP", "рейс")
]

MAT_TYPES = [
    "Щебень 20–40",
    "Песок",
    "Цемент", 
    "Арматура",
    "Бетон",
    "Кирпич"
]

UNITS = [
    "т",
    "м³", 
    "шт",
    "кг",
    "л"
]

def create_inline_keyboard(items: List[str], prefix: str, page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Создает inline-клавиатуру из списка элементов с пагинацией."""
    kb = InlineKeyboardBuilder()
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(items))
    page_items = items[start_idx:end_idx]
    
    # Добавляем кнопки элементов
    for item in page_items:
        kb.button(text=item, callback_data=f"{prefix}:{item}")
    
    # Добавляем кнопки пагинации
    if page > 0:
        kb.button(text="◀️", callback_data=f"{prefix}:page:{page-1}")
    
    if end_idx < len(items):
        kb.button(text="▶️", callback_data=f"{prefix}:page:{page+1}")
    
    # Кнопка отмены
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    
    # Настройка расположения кнопок
    kb.adjust(2, 2, 1, 1)  # 2 в ряд, затем 2 в ряд, затем по 1
    
    return kb.as_markup()

def create_rate_type_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора типа тарифа."""
    kb = InlineKeyboardBuilder()
    
    for rate_code, rate_name in RATE_TYPES:
        kb.button(text=rate_name, callback_data=f"{prefix}:{rate_code}")
    
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(1, 1, 1, 1)  # По одной кнопке в ряд
    
    return kb.as_markup()

def create_unit_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора единицы измерения."""
    kb = InlineKeyboardBuilder()
    
    for unit in UNITS:
        kb.button(text=unit, callback_data=f"{prefix}:{unit}")
    
    kb.button(text="❌ Отмена", callback_data="cancel_resource")
    kb.adjust(3, 2, 1)  # 3 в ряд, затем 2 в ряд, затем 1
    
    return kb.as_markup()

def get_equip_type_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Получить клавиатуру для выбора типа техники."""
    return create_inline_keyboard(EQUIP_TYPES, "equip_type", page)

def get_mat_type_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Получить клавиатуру для выбора типа материала."""
    return create_inline_keyboard(MAT_TYPES, "mat_type", page)

def get_rate_type_keyboard() -> InlineKeyboardMarkup:
    """Получить клавиатуру для выбора типа тарифа."""
    return create_rate_type_keyboard("rate_type")

def get_unit_keyboard() -> InlineKeyboardMarkup:
    """Получить клавиатуру для выбора единицы измерения."""
    return create_unit_keyboard("unit")
