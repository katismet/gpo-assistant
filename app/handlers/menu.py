# app/handlers/menu.py

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import logging
from app.services.authz import get_user  # роли берем из staff_map.json

log = logging.getLogger("gpo.menu")

router = Router(name="menu")

# Тестовый обработчик для проверки работы роутера
@router.message(F.text == "/test_menu")
async def test_menu(m: Message):
    """Тестовый обработчик для проверки работы menu router."""
    log.info(f"test_menu called from user {m.from_user.id}")
    await m.answer("✅ Menu router работает!")

# Универсальный обработчик для диагностики удален - может мешать другим роутерам

# маппинг кнопок → уже существующие команды/хэндлеры проекта
BUTTON_TO_CMD = {
    "🗓 План": "/act:plan",
    "✅ Отчёт": "/act:report",
    "🔄 Ресурс": "/act:resources",  # Изменено: было "/act:shift", теперь ведет в мастер ресурсов
    "👥 Табель": "/act:tab",
    "🧱 Объекты": "/act:objects",
    "🧾 ЛПА": "/act:lpa",
    # ещё…
    "📊 Сводка за сегодня": "/daily_report",
    "🔔 Подписаться на сводки": "/subscribe_alerts",
    "🔕 Отписаться": "/unsubscribe_alerts",
    "🛠 Статус системы": "/status",
    "🤖 Инсайты": "/insights",
}


def kb_main(role: str) -> ReplyKeyboardMarkup:
    """Главное меню с клавиатурой."""
    rows = [
        [KeyboardButton(text="🗓 План")],
        [KeyboardButton(text="✅ Отчёт")],
        [KeyboardButton(text="🔄 Ресурс"), KeyboardButton(text="👥 Табель")],  # Изменено: "Смена" → "Ресурс"
        [KeyboardButton(text="🧱 Объекты"), KeyboardButton(text="🧾 ЛПА")],
        [KeyboardButton(text="Ещё…")],
    ]
    
    if role in ("OWNER", "ADMIN"):
        # при желании можно вывести «Инсайты» в главный ряд:
        # rows[-1].insert(0, KeyboardButton(text="🤖 Инсайты"))
        pass
    
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def kb_more(role: str) -> ReplyKeyboardMarkup:
    """Дополнительное меню."""
    rows = [
        [KeyboardButton(text="📊 Сводка за сегодня")],
        [KeyboardButton(text="🔔 Подписаться на сводки"), KeyboardButton(text="🔕 Отписаться")],
        [KeyboardButton(text="🛠 Статус системы")],
        [KeyboardButton(text="◀︎ Назад")],
    ]
    
    if role in ("OWNER", "ADMIN"):
        rows.insert(0, [KeyboardButton(text="🤖 Инсайты")])
    
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def role_of(message: Message) -> str:
    """Получить роль пользователя из staff_map.json."""
    u = get_user(message.from_user.id)
    return (u and u.get("role")) or "FOREMAN"  # По умолчанию прораб


@router.message(CommandStart())
async def start(m: Message):
    """Обработчик команды /start."""
    user_id = m.from_user.id if m.from_user else "unknown"
    chat_id = m.chat.id if m.chat else "unknown"
    username = m.from_user.username if m.from_user else "unknown"
    
    # Логируем в консоль и файл
    print(f"[START] ✅ Command /start received from user {user_id} (@{username}), chat_id: {chat_id}")
    log.info(f"[START] ✅ Command /start received from user {user_id} (@{username}), chat_id: {chat_id}")
    
    try:
        # Получаем роль пользователя
        try:
            role = role_of(m)
            log.info(f"[START] User {user_id} role: {role}")
        except Exception as e:
            log.error(f"[START] Error getting role for user {user_id}: {e}", exc_info=True)
            role = "FOREMAN"  # Используем роль по умолчанию
        
        # Создаем клавиатуру
        try:
            keyboard = kb_main(role)
            log.info(f"[START] Keyboard created for user {user_id}")
        except Exception as e:
            log.error(f"[START] Error creating keyboard for user {user_id}: {e}", exc_info=True)
            # Создаем простую клавиатуру без роли
            keyboard = kb_main("FOREMAN")
        
        # Отправляем сообщение
        try:
            response = await m.answer(
                "ГПО-Помощник. Выберите действие:",
                reply_markup=keyboard
            )
            print(f"[START] ✅ Message sent successfully to user {user_id}")
            log.info(f"[START] ✅ Start command completed successfully for user {user_id}, role: {role}, message_id: {response.message_id if response else 'N/A'}")
        except Exception as e:
            log.error(f"[START] ❌ Error sending message to user {user_id}: {e}", exc_info=True)
            print(f"[START] ❌ Error sending message to user {user_id}: {e}")
            # Пробуем отправить без клавиатуры
            try:
                await m.answer("ГПО-Помощник. Выберите действие:")
                log.info(f"[START] ✅ Fallback message sent to user {user_id}")
            except Exception as e2:
                log.error(f"[START] ❌ Critical error sending message to user {user_id}: {e2}", exc_info=True)
                print(f"[START] ❌ Critical error: {e2}")
                raise
            
    except Exception as e:
        log.error(f"[START] ❌ Critical error in start handler for user {user_id}: {e}", exc_info=True)
        print(f"[START] ❌ Critical error in start handler: {e}")
        try:
            await m.answer(f"❌ Ошибка при запуске: {str(e)}\n\nПопробуйте еще раз или обратитесь к администратору.")
        except:
            log.error(f"[START] Could not send error message to user {user_id}")


@router.message(F.text == "Ещё…")
async def more_menu(m: Message):
    """Показать дополнительное меню."""
    log.info(f"more_menu called from user {m.from_user.id}")
    role = role_of(m)
    await m.answer("Дополнительно:", reply_markup=kb_more(role))


@router.message(F.text == "◀︎ Назад")
async def back_menu(m: Message):
    """Вернуться в главное меню."""
    log.info(f"back_menu called from user {m.from_user.id}")
    role = role_of(m)
    await m.answer("ГПО-Помощник. Выберите действие:", reply_markup=kb_main(role))

# Единый «мост»: любая кнопка из словаря дергает соответствующую команду
button_texts = list(BUTTON_TO_CMD.keys())

@router.message(F.text.in_(button_texts))
async def bridge(m: Message, state: FSMContext):
    """Мост от кнопок к командам."""
    log.info(f"bridge called for button: '{m.text}' from user {m.from_user.id}, chat_id: {m.chat.id}")
    if m.text not in BUTTON_TO_CMD:
        log.warning(f"Button text '{m.text}' not found in BUTTON_TO_CMD")
        await m.answer(f"❌ Кнопка '{m.text}' не найдена в словаре команд.")
        return
    cmd = BUTTON_TO_CMD[m.text]
    log.info(f"command mapped: {cmd}")
    
    # Для команд вида /act:plan, /act:report, /act:lpa используем прямое обращение через Message
    if cmd.startswith("/act:"):
        # Вызываем соответствующий обработчик напрямую через Message (более надежно)
        if cmd == "/act:plan":
            from app.services.objects import fetch_all_objects
            from app.telegram.objects_ui import page_kb
            from app.telegram.fsm_states import PlanFlow
            await state.clear()
            await state.set_state(PlanFlow.pick_object)
            objs = await fetch_all_objects()
            await state.update_data(objects_cache=objs, page=0)
            await m.answer("Выберите объект:", reply_markup=page_kb(objs, 0, "obj"))
        elif cmd == "/act:report":
            from app.services.objects import fetch_all_objects
            from app.telegram.objects_ui import page_kb
            await state.clear()
            objs = await fetch_all_objects()
            await state.update_data(objects_cache=objs, page=0)
            # НЕ устанавливаем состояние FSM, чтобы обработчик repobj_pick сработал без фильтра
            await m.answer("Выберите объект:", reply_markup=page_kb(objs, 0, "repobj"))
        elif cmd == "/act:lpa":
            from app.services.objects import fetch_all_objects
            from app.telegram.objects_ui import page_kb
            from app.telegram.flow_lpa import LPAFlow
            await state.clear()
            objs = await fetch_all_objects()
            await state.update_data(objects_cache=objs, page=0)
            await state.set_state(LPAFlow.select_object)
            await m.answer(
                "📄 <b>Генерация ЛПА (Лист производственного анализа)</b>\n\n"
                "Выберите объект для которого нужно сформировать ЛПА:",
                reply_markup=page_kb(objs, 0, "lpaobj"),
                parse_mode="HTML"
            )
        
        # Обработка остальных команд /act:
        if cmd == "/act:resources":
            # Запускаем flow для добавления ресурса
            from app.telegram.flow_resources import start_resource_flow
            # Создаем fake CallbackQuery для совместимости
            class FakeCQ:
                def __init__(self, msg):
                    self.message = msg
                    self.data = "act:resources"
                async def answer(self):
                    pass
            fake_cq = FakeCQ(m)
            await start_resource_flow(fake_cq, state)
        elif cmd == "/act:shift":
            # Старая команда, перенаправляем на ресурсы
            await m.answer("Раздел «Смена» объединен с «Ресурс». Используйте кнопку «🔄 Ресурс».")
        elif cmd == "/act:tab":
            # Запускаем flow для добавления табеля
            from app.telegram.flow_timesheet import start_timesheet_flow
            # Создаем fake CallbackQuery для совместимости
            class FakeCQ:
                def __init__(self, msg):
                    self.message = msg
                    self.data = "act:timesheet"
                async def answer(self):
                    pass
            fake_cq = FakeCQ(m)
            await start_timesheet_flow(fake_cq, state)
        elif cmd == "/act:objects":
            # Простой ответ для объектов
            await m.answer("Список объектов берётся из Bitrix. Для работы используйте «ПЛАН»/«ОТЧЁТ».")
    else:
        # Для остальных команд вызываем обработчики напрямую
        if cmd == "/daily_report":
            from app.handlers.w6_handlers import daily_report_command
            from aiogram.filters.command import CommandObject
            fake_command = CommandObject(
                prefix="/",
                command="daily_report",
                args=None,
                mention=None,
                regexp_match=None,
                magic_result=None
            )
            await daily_report_command(m, fake_command)
        elif cmd == "/subscribe_alerts":
            from app.handlers.w6_handlers import sub_alerts
            await sub_alerts(m)
        elif cmd == "/unsubscribe_alerts":
            from app.handlers.w6_handlers import unsub_alerts
            await unsub_alerts(m)
        elif cmd == "/status":
            from app.handlers.w6_handlers import status
            await status(m)
        elif cmd == "/insights":
            from app.handlers.insights_handler import insights_command
            await insights_command(m)
        else:
            # Для команд, которых еще нет - заглушка
            await m.answer(f"Команда {cmd} в разработке.")
