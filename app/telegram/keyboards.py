"""Клавиатуры для Telegram бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ПЛАН на день", callback_data="act:plan"),
             InlineKeyboardButton(text="ОТЧЁТ за смену", callback_data="act:report")],
            [InlineKeyboardButton(text="Техника/Материалы", callback_data="act:resources"),
             InlineKeyboardButton(text="Табель", callback_data="act:tab")],
            [InlineKeyboardButton(text="📄 ЛПА", callback_data="act:lpa")],
            [InlineKeyboardButton(text="Мои объекты", callback_data="act:objects")],
        ]
    )
    return keyboard


def get_plan_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню планирования."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏗️ Выбрать объект", callback_data="plan_object")],
            [InlineKeyboardButton(text="📅 Выбрать смену", callback_data="plan_shift")],
            [InlineKeyboardButton(text="🔧 Ресурсы", callback_data="plan_resources")],
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="plan_confirm")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )
    return keyboard


def get_report_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню отчётов."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 План-факт", callback_data="report_plan_fact")],
            [InlineKeyboardButton(text="⚠️ Инциденты", callback_data="report_incidents")],
            [InlineKeyboardButton(text="⏸️ Простои", callback_data="report_downtime")],
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="report_confirm")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )
    return keyboard


def get_resources_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню ресурсов."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚜 Техника", callback_data="resources_technique")],
            [InlineKeyboardButton(text="📦 Материалы", callback_data="resources_materials")],
            [InlineKeyboardButton(text="👥 Табель", callback_data="resources_timesheet")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )
    return keyboard


def get_objects_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню объектов."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список объектов", callback_data="objects_list")],
            [InlineKeyboardButton(text="➕ Добавить объект", callback_data="objects_add")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )
    return keyboard


def get_shift_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа смены."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="☀️ Дневная", callback_data="shift_day")],
            [InlineKeyboardButton(text="🌙 Ночная", callback_data="shift_night")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_plan")],
        ]
    )
    return keyboard


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}"),
            ]
        ]
    )
    return keyboard


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )
    return keyboard


def get_back_keyboard(callback_data: str = "back_to_menu") -> InlineKeyboardMarkup:
    """Клавиатура возврата."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]
        ]
    )
    return keyboard


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str,
    extra_buttons: list = None,
) -> InlineKeyboardMarkup:
    """Клавиатура пагинации."""
    keyboard = []
    
    # Кнопки пагинации
    pagination_buttons = []
    if current_page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_page_{current_page - 1}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="current_page")
    )
    
    if current_page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_page_{current_page + 1}")
        )
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    # Дополнительные кнопки
    if extra_buttons:
        keyboard.extend(extra_buttons)
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_object_keyboard(object_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для объекта."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Детали", callback_data=f"object_details_{object_id}")],
            [InlineKeyboardButton(text="📅 Смены", callback_data=f"object_shifts_{object_id}")],
            [InlineKeyboardButton(text="📊 Отчёты", callback_data=f"object_reports_{object_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="objects_list")],
        ]
    )
    return keyboard


def get_shift_keyboard(shift_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для смены."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Детали", callback_data=f"shift_details_{shift_id}")],
            [InlineKeyboardButton(text="🔧 Ресурсы", callback_data=f"shift_resources_{shift_id}")],
            [InlineKeyboardButton(text="📊 Отчёт", callback_data=f"shift_report_{shift_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_plan")],
        ]
    )
    return keyboard


def get_efficiency_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для эффективности."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Raw", callback_data="efficiency_raw")],
            [InlineKeyboardButton(text="👤 User", callback_data="efficiency_user")],
            [InlineKeyboardButton(text="🎯 Final", callback_data="efficiency_final")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
        ]
    )
    return keyboard
