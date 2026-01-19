from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE = 8

def page_kb(objects, page:int, prefix:str):
    """
    Создает клавиатуру с объектами для выбора.
    
    Args:
        objects: Список кортежей (bitrix_id, title, code) или (bitrix_id, title)
        page: Номер страницы (0-based)
        prefix: Префикс для callback_data (например, "obj", "repobj", "lpaobj")
    
    Returns:
        InlineKeyboardMarkup с кнопками объектов
    """
    start = page * PAGE_SIZE
    chunk = objects[start:start+PAGE_SIZE]
    kb = InlineKeyboardBuilder()
    
    for obj_data in chunk:
        # Поддерживаем старый формат (bitrix_id, title) и новый (bitrix_id, title, code)
        if len(obj_data) == 3:
            oid, title, code = obj_data
        else:
            oid, title = obj_data
            code = ""
        
        # Формируем текст кнопки: "{code} · {title}" или просто "{title}" если код пустой
        if code:
            button_text = f"{code} · {title}"
        else:
            button_text = title
        
        # Ограничиваем длину текста кнопки (Telegram ограничение ~64 символа)
        if len(button_text) > 60:
            button_text = button_text[:57] + "..."
        
        kb.button(text=button_text, callback_data=f"{prefix}:{oid}")
    
    # пагинация
    rows = []
    if page > 0:
        kb.button(text="⬅️ Назад", callback_data=f"{prefix}:page:{page-1}")
        rows.append(1)
    if start + PAGE_SIZE < len(objects):
        kb.button(text="Вперёд ➡️", callback_data=f"{prefix}:page:{page+1}")
        rows.append(1)
    kb.adjust(2,2,2,*rows)  # по 2 в ряд
    return kb.as_markup()

