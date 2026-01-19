"""Обработчики callback'ов для Telegram бота."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.models import User as DBUser
from app.telegram.fsm_states import WorkflowState
from app.telegram.keyboards import (
    get_back_keyboard,
    get_confirmation_keyboard,
    get_main_menu_keyboard,
    get_objects_menu_keyboard,
    get_plan_menu_keyboard,
    get_report_menu_keyboard,
    get_resources_menu_keyboard,
)

router = Router()


@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню."""
    await callback.message.edit_text(
        "🏠 Главное меню",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "back_to_plan")
async def back_to_plan(callback: CallbackQuery):
    """Возврат к планированию."""
    await callback.message.edit_text(
        "📋 Планирование смены",
        reply_markup=get_plan_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cancel")
async def cancel_action(callback: CallbackQuery):
    """Отмена действия."""
    await callback.message.edit_text(
        "❌ Действие отменено",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_action(callback: CallbackQuery):
    """Подтверждение действия."""
    action = callback.data.replace("confirm_", "")
    
    if action == "plan":
        await callback.message.edit_text(
            "✅ План смены подтверждён и сохранён в Bitrix24",
            reply_markup=get_back_keyboard(),
        )
    elif action == "report":
        await callback.message.edit_text(
            "✅ Отчёт подтверждён и сохранён в Bitrix24",
            reply_markup=get_back_keyboard(),
        )
    else:
        await callback.message.edit_text(
            f"✅ Действие '{action}' подтверждено",
            reply_markup=get_back_keyboard(),
        )
    
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_action_with_data(callback: CallbackQuery):
    """Отмена действия с данными."""
    action = callback.data.replace("cancel_", "")
    await callback.message.edit_text(
        f"❌ Действие '{action}' отменено",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


# Планирование
@router.callback_query(lambda c: c.data == "plan_object")
async def plan_object_selection(callback: CallbackQuery):
    """Выбор объекта для планирования."""
    await callback.message.edit_text(
        "🏗️ Выберите объект для планирования:",
        reply_markup=get_objects_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "plan_shift")
async def plan_shift_selection(callback: CallbackQuery):
    """Выбор смены для планирования."""
    await callback.message.edit_text(
        "📅 Выберите тип смены:",
        reply_markup=get_plan_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "plan_resources")
async def plan_resources_selection(callback: CallbackQuery):
    """Выбор ресурсов для планирования."""
    await callback.message.edit_text(
        "🔧 Выберите тип ресурсов:",
        reply_markup=get_resources_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "plan_confirm")
async def plan_confirm(callback: CallbackQuery):
    """Подтверждение плана."""
    await callback.message.edit_text(
        "❓ Подтвердить план смены?",
        reply_markup=get_confirmation_keyboard("plan"),
    )
    await callback.answer()


# Отчёты
@router.callback_query(lambda c: c.data == "report_plan_fact")
async def report_plan_fact(callback: CallbackQuery):
    """Отчёт план-факт."""
    await callback.message.edit_text(
        "📊 Введите данные план-факт:\n\n"
        "Формат: план:факт\n"
        "Пример: 100:95",
        reply_markup=get_back_keyboard("back_to_menu"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "report_incidents")
async def report_incidents(callback: CallbackQuery):
    """Отчёт об инцидентах."""
    await callback.message.edit_text(
        "⚠️ Опишите инциденты:\n\n"
        "Формат: время - описание\n"
        "Пример: 14:30 - Поломка экскаватора",
        reply_markup=get_back_keyboard("back_to_menu"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "report_downtime")
async def report_downtime(callback: CallbackQuery):
    """Отчёт о простоях."""
    await callback.message.edit_text(
        "⏸️ Опишите простои:\n\n"
        "Формат: время - причина\n"
        "Пример: 15:00 - Ожидание материалов",
        reply_markup=get_back_keyboard("back_to_menu"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "report_confirm")
async def report_confirm(callback: CallbackQuery):
    """Подтверждение отчёта."""
    await callback.message.edit_text(
        "❓ Подтвердить отчёт?",
        reply_markup=get_confirmation_keyboard("report"),
    )
    await callback.answer()


# Ресурсы
@router.callback_query(lambda c: c.data == "resources_technique")
async def resources_technique(callback: CallbackQuery):
    """Ресурсы - техника."""
    await callback.message.edit_text(
        "🚜 Введите данные о технике:\n\n"
        "Формат: название - количество - единица\n"
        "Пример: Экскаватор - 1 - шт",
        reply_markup=get_back_keyboard("back_to_menu"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "resources_materials")
async def resources_materials(callback: CallbackQuery):
    """Ресурсы - материалы."""
    await callback.message.edit_text(
        "📦 Введите данные о материалах:\n\n"
        "Формат: название - количество - единица\n"
        "Пример: Цемент - 50 - т",
        reply_markup=get_back_keyboard("back_to_menu"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "resources_timesheet")
async def resources_timesheet(callback: CallbackQuery):
    """Ресурсы - табель."""
    await callback.message.edit_text(
        "👥 Введите данные табеля:\n\n"
        "Формат: бригада - часы - ставка\n"
        "Пример: Бригада 1 - 8 - 1000",
        reply_markup=get_back_keyboard("back_to_menu"),
    )
    await callback.answer()


# Объекты
@router.callback_query(lambda c: c.data == "objects_list")
async def objects_list(callback: CallbackQuery):
    """Список объектов."""
    await callback.message.edit_text(
        "🏗️ Список объектов:\n\n"
        "1. Объект А - Строительство дома\n"
        "2. Объект Б - Ремонт дороги\n"
        "3. Объект В - Установка забора",
        reply_markup=get_objects_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "objects_add")
async def objects_add(callback: CallbackQuery):
    """Добавление объекта."""
    await callback.message.edit_text(
        "➕ Введите данные нового объекта:\n\n"
        "Формат: название - описание\n"
        "Пример: Объект Г - Строительство моста",
        reply_markup=get_back_keyboard("objects_list"),
    )
    await callback.answer()


# Типы смен
@router.callback_query(lambda c: c.data == "shift_day")
async def shift_day(callback: CallbackQuery):
    """Дневная смена."""
    await callback.message.edit_text(
        "☀️ Выбрана дневная смена\n\n"
        "Время: 08:00 - 20:00",
        reply_markup=get_plan_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "shift_night")
async def shift_night(callback: CallbackQuery):
    """Ночная смена."""
    await callback.message.edit_text(
        "🌙 Выбрана ночная смена\n\n"
        "Время: 20:00 - 08:00",
        reply_markup=get_plan_menu_keyboard(),
    )
    await callback.answer()


# Эффективность
@router.callback_query(lambda c: c.data == "efficiency_raw")
async def efficiency_raw(callback: CallbackQuery):
    """Эффективность Raw."""
    await callback.message.edit_text(
        "📊 Эффективность Raw: 85%\n\n"
        "Расчёт основан на автоматических данных",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "efficiency_user")
async def efficiency_user(callback: CallbackQuery):
    """Эффективность User."""
    await callback.message.edit_text(
        "👤 Эффективность User: 90%\n\n"
        "Расчёт основан на пользовательских данных",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "efficiency_final")
async def efficiency_final(callback: CallbackQuery):
    """Эффективность Final."""
    await callback.message.edit_text(
        "🎯 Эффективность Final: 87.5%\n\n"
        "Итоговый расчёт эффективности",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


# Обработчики команд
# ПРИМЕЧАНИЕ: Обработчик /start перенесен в app/handlers/menu.py
# Этот обработчик отключен, чтобы избежать конфликтов
# @router.message(Command("start"))
# async def start_command(message: Message, db_user: DBUser):
#     """Обработчик команды /start."""
#     await message.answer(
#         f"👋 Добро пожаловать, {db_user.role.value}!\n\n"
#         "Я помогу вам планировать смены и вести отчёты.\n"
#         "Выберите действие в меню ниже:",
#         reply_markup=get_main_menu_keyboard(),
#     )


@router.message(Command("help"))
async def help_command(message: Message):
    """Обработчик команды /help."""
    help_text = """
🤖 ГПО-Помощник - бот для прорабов

📋 Основные функции:
• Планирование смен
• Ведение отчётов
• Управление ресурсами
• Работа с объектами

🔧 Команды:
/start - Начать работу
/help - Показать справку
/menu - Главное меню

📞 Поддержка: @support
    """
    await message.answer(help_text)


@router.message(Command("menu"))
async def menu_command(message: Message):
    """Обработчик команды /menu."""
    await message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_menu_keyboard(),
    )
