#!/usr/bin/env python3
"""Альтернативный тест загрузки фото через Bitrix24 Disk."""

import sys
import asyncio
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx


async def test_photo_upload_via_disk(shift_id: int, field_name: str):
    """Тестирует загрузку фото через Disk API."""
    print(f"🧪 Тест загрузки фото через Disk API")
    print(f"   Смена: {shift_id}, Поле: {field_name}")
    print()
    
    # Создаем тестовое изображение (1x1 пиксель PNG)
    test_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    test_png_bytes = base64.b64decode(test_png_base64)
    
    print(f"📦 Тестовое изображение: {len(test_png_bytes)} байт")
    print()
    
    try:
        # Метод 1: Попробуем загрузить через disk.file.uploadfile
        print("📤 Метод 1: Загрузка через disk.file.uploadfile...")
        
        # Получаем корневую папку
        storage_result = await bx("disk.storage.getlist", {})
        print(f"   Storage result: {type(storage_result)}")
        
        # Пробуем загрузить файл
        upload_result = await bx("disk.file.uploadfile", {
            "id": "0",  # Корневая папка
            "data": {
                "NAME": "test_photo.jpg",
                "fileData": ["test_photo.jpg", test_png_base64]
            }
        })
        
        print(f"   Upload result: {upload_result}")
        
        if isinstance(upload_result, dict) and "ID" in upload_result:
            file_id = upload_result["ID"]
            print(f"   ✓ Файл загружен, ID: {file_id}")
            
            # Привязываем к полю
            print()
            print("📎 Привязываю файл к полю смены...")
            update_result = await bx("crm.item.update", {
                "entityTypeId": 1050,
                "id": shift_id,
                "fields": {
                    field_name: [{"id": file_id}]
                }
            })
            
            print(f"   Update result: {update_result}")
            
            # Проверяем результат
            await asyncio.sleep(2)
            get_result = await bx("crm.item.get", {
                "entityTypeId": 1050,
                "id": shift_id
            })
            
            item = (get_result or {}).get("item", get_result) if isinstance(get_result, dict) else get_result
            photos_uf = item.get(field_name) if item else None
            
            print()
            print(f"📋 Результат:")
            print(f"   {field_name}: {photos_uf}")
            
            if photos_uf:
                print(f"   ✓ Фото привязано!")
                return True
            else:
                print(f"   ❌ Фото не привязано")
                return False
        else:
            print(f"   ❌ Не удалось загрузить файл")
            print(f"   Попробуем метод 2...")
            print()
            
            # Метод 2: Прямая загрузка через crm.item.update с одним файлом
            print("📤 Метод 2: Прямая загрузка одного файла...")
            update_result = await bx("crm.item.update", {
                "entityTypeId": 1050,
                "id": shift_id,
                "fields": {
                    field_name: {"fileData": ["test_photo.jpg", test_png_base64]}
                }
            })
            
            print(f"   Update result: {update_result}")
            
            await asyncio.sleep(2)
            get_result = await bx("crm.item.get", {
                "entityTypeId": 1050,
                "id": shift_id
            })
            
            item = (get_result or {}).get("item", get_result) if isinstance(get_result, dict) else get_result
            photos_uf = item.get(field_name) if item else None
            
            print()
            print(f"📋 Результат:")
            print(f"   {field_name}: {photos_uf}")
            
            if photos_uf:
                print(f"   ✓ Фото загружено!")
                return True
            else:
                print(f"   ❌ Фото не загружено")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция."""
    if len(sys.argv) < 3:
        print("Использование: python scripts/test_photo_upload_disk.py <SHIFT_ID> <FIELD_NAME>")
        print()
        print("Пример:")
        print("  python scripts/test_photo_upload_disk.py 285 ufCrm7UfShiftPhotos")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
        field_name = sys.argv[2]
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    success = await test_photo_upload_via_disk(shift_id, field_name)
    
    if success:
        print()
        print("✅ Тест пройден успешно!")
    else:
        print()
        print("❌ Тест не пройден.")


if __name__ == "__main__":
    asyncio.run(main())





