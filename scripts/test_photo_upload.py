#!/usr/bin/env python3
"""Тестовый скрипт для загрузки фото в Bitrix24."""

import sys
import asyncio
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def test_photo_upload(shift_id: int, field_name: str):
    """Тестирует загрузку фото в указанное поле."""
    print(f"🧪 Тест загрузки фото в смену {shift_id}")
    print(f"   Поле: {field_name}")
    print()
    
    # Создаем тестовое изображение (1x1 пиксель PNG в base64)
    # Это минимальный валидный PNG
    test_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    # Декодируем для проверки
    test_png_bytes = base64.b64decode(test_png_base64)
    print(f"📦 Тестовое изображение: {len(test_png_bytes)} байт")
    print()
    
    # Пробуем разные форматы
    print("📤 Тестирую разные форматы загрузки...")
    print()
    
    # Формат 1: Один файл (не массив)
    print("🔹 Формат 1: Один файл (не массив)")
    try:
        result1 = await bx("crm.item.update", {
            "entityTypeId": 1050,
            "id": shift_id,
            "fields": {
                field_name: {"fileData": ["test_photo_1.jpg", test_png_base64]}
            }
        })
        print(f"   Результат: {result1}")
        
        await asyncio.sleep(2)
        get_result1 = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
        item1 = (get_result1 or {}).get("item", get_result1) if isinstance(get_result1, dict) else get_result1
        photos1 = item1.get(field_name) if item1 else None
        print(f"   Проверка: {photos1}")
        if photos1:
            print(f"   ✅ Успешно! Формат 1 работает")
            return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print()
    
    # Формат 2: Массив с одним файлом
    print("🔹 Формат 2: Массив с одним файлом")
    try:
        result2 = await bx("crm.item.update", {
            "entityTypeId": 1050,
            "id": shift_id,
            "fields": {
                field_name: [{"fileData": ["test_photo_2.jpg", test_png_base64]}]
            }
        })
        print(f"   Результат: {result2}")
        
        await asyncio.sleep(2)
        get_result2 = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
        item2 = (get_result2 or {}).get("item", get_result2) if isinstance(get_result2, dict) else get_result2
        photos2 = item2.get(field_name) if item2 else None
        print(f"   Проверка: {photos2}")
        if photos2:
            print(f"   ✅ Успешно! Формат 2 работает")
            return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print()
    
    # Формат 3: Массив с несколькими файлами
    print("🔹 Формат 3: Массив с несколькими файлами")
    try:
        files_payload = [
            {"fileData": ["test_photo_3.jpg", test_png_base64]},
            {"fileData": ["test_photo_4.jpg", test_png_base64]},
        ]
        result3 = await bx("crm.item.update", {
            "entityTypeId": 1050,
            "id": shift_id,
            "fields": {
                field_name: files_payload
            }
        })
        print(f"   Результат: {result3}")
        
        await asyncio.sleep(2)
        get_result3 = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
        item3 = (get_result3 or {}).get("item", get_result3) if isinstance(get_result3, dict) else get_result3
        photos3 = item3.get(field_name) if item3 else None
        print(f"   Проверка: {photos3}")
        if photos3:
            print(f"   ✅ Успешно! Формат 3 работает")
            return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print()
    
    # Если ничего не сработало, возвращаем False
    try:
        
        print(f"✅ Обновление выполнено")
        
        # Проверяем ошибки
        if isinstance(result, dict):
            if "error" in result:
                print(f"❌ Ошибка: {result.get('error')}")
                print(f"   Описание: {result.get('error_description', 'N/A')}")
                return False
            elif "result" in result and result.get("result") is False:
                print(f"⚠️  result = False")
                return False
        
        print("❌ Ни один формат не сработал")
        return False
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция."""
    if len(sys.argv) < 3:
        print("Использование: python scripts/test_photo_upload.py <SHIFT_ID> <FIELD_NAME>")
        print()
        print("Пример:")
        print("  python scripts/test_photo_upload.py 285 ufCrm7UfShiftPhotos")
        print()
        print("Сначала проверьте поля через:")
        print("  python scripts/check_shift_fields.py")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
        field_name = sys.argv[2]
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    success = await test_photo_upload(shift_id, field_name)
    
    if success:
        print()
        print("✅ Тест пройден успешно!")
    else:
        print()
        print("❌ Тест не пройден. Проверьте:")
        print("   1. Существует ли поле в Bitrix24")
        print("   2. Правильный ли код поля (camelCase)")
        print("   3. Тип поля (должен быть file/file_multiple)")


if __name__ == "__main__":
    asyncio.run(main())

