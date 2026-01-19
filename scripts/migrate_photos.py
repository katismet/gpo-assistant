#!/usr/bin/env python3
"""Миграция фото из fact_json.photos (Telegram file_id) в Bitrix24 ufCrm7UfShiftPhotos."""

import base64
import sys
import asyncio
import json
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем токен бота из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")


async def tg_download(file_id: str) -> bytes:
    """Скачивает фото из Telegram по file_id."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set in .env file")
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Получаем путь к файлу
        r = await client.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id}
        )
        r.raise_for_status()
        result = r.json()
        
        path = (result.get("result") or {}).get("file_path")
        if not path:
            return None
        
        # Скачиваем файл
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
        data_r = await client.get(url, timeout=60)
        data_r.raise_for_status()
        return data_r.content


async def migrate_photos(shift_id: int):
    """Переносит фото из fact_json.photos в Bitrix24."""
    print(f"📸 Миграция фото для смены {shift_id}...")
    print()
    
    # Получаем смену из Bitrix24
    g = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
    item = (g or {}).get("item", g) if isinstance(g, dict) else g
    
    if not item:
        print(f"❌ Смена {shift_id} не найдена в Bitrix24")
        return
    
    # Извлекаем fact_json
    fact_raw = item.get("ufCrm7UfFactJson")
    if isinstance(fact_raw, list):
        fact_raw = fact_raw[0] if fact_raw else None
    
    photos = []
    if isinstance(fact_raw, str) and fact_raw.strip().startswith("{"):
        try:
            fjson = json.loads(fact_raw)
            photos = fjson.get("photos") or []
        except json.JSONDecodeError:
            print(f"⚠️  Не удалось распарсить fact_json")
            return
    
    if not photos:
        print("❌ Нет Telegram фото в fact_json.photos")
        return
    
    print(f"📋 Найдено {len(photos)} фото в fact_json.photos")
    print(f"   Скачиваю и загружаю в Bitrix24...")
    print()
    
    # Скачиваем и загружаем фото по одному
    # ВАЖНО: Поле имеет multiple=False, поэтому загружаем по одному файлу
    # Bitrix24 вернет массив с объектами {id, url}
    uploaded_count = 0
    
    for i, file_id in enumerate(photos[:5]):  # Максимум 5 фото
        try:
            print(f"   [{i+1}/{min(len(photos), 5)}] Скачиваю {file_id[:20]}...")
            data = await tg_download(file_id)
            if not data:
                print(f"      ⚠️  Не удалось скачать")
                continue
            
            b64 = base64.b64encode(data).decode("ascii")
            print(f"      ✓ Скачано ({len(data)} байт)")
            
            # Загружаем по одному файлу (не массив!)
            print(f"      📤 Загружаю в Bitrix24...")
            r = await bx("crm.item.update", {
                "entityTypeId": 1050,
                "id": shift_id,
                "fields": {
                    "ufCrm7UfShiftPhotos": {"fileData": [f"shift_{shift_id}_{i+1}.jpg", b64]}
                }
            })
            
            if r and not (isinstance(r, dict) and ("error" in r or (r.get("result") is False))):
                uploaded_count += 1
                print(f"      ✅ Загружено")
            else:
                print(f"      ⚠️  Ошибка при загрузке: {r}")
            
            # Небольшая задержка между загрузками
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
            continue
    
    if uploaded_count == 0:
        print("❌ Не удалось загрузить ни одного фото")
        return
    
    print()
    print(f"✅ Загружено {uploaded_count} из {min(len(photos), 5)} фото")
    print()
    
    # Проверяем результат
    try:
        await asyncio.sleep(2)
        g2 = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
        item2 = (g2 or {}).get("item", g2) if isinstance(g2, dict) else g2
        
        print(f"✅ Обновление: {r}")
        
        # Проверяем, есть ли ошибки в ответе
        if isinstance(r, dict):
            if "error" in r or "error_description" in r:
                print(f"   ⚠️  Ошибка в ответе: {r.get('error', r.get('error_description', 'Unknown'))}")
            elif "result" in r and r.get("result") is False:
                print(f"   ⚠️  result = False")
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Ждем немного, чтобы Bitrix24 обработал обновление
    import asyncio
    await asyncio.sleep(2)
    
    # Проверяем результат
    g2 = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
    item2 = (g2 or {}).get("item", g2) if isinstance(g2, dict) else g2
    
    if not item2:
        print(f"❌ Не удалось получить смену после обновления")
        return
    
    # Проверяем оба варианта имени поля
    photos_uf = item2.get("ufCrm7UfShiftPhotos") or item2.get("UF_CRM_7_UF_SHIFT_PHOTOS")
    
    print(f"📋 Проверка результата:")
    print(f"   photosUF = {photos_uf}")
    print(f"   Тип: {type(photos_uf)}")
    
    if photos_uf:
        if isinstance(photos_uf, list):
            print(f"   ✓ Фото загружены: {len(photos_uf)} файлов")
            if len(photos_uf) > 0:
                print(f"   Первый элемент: {type(photos_uf[0])}")
                if isinstance(photos_uf[0], dict):
                    print(f"   Ключи: {list(photos_uf[0].keys())}")
        else:
            print(f"   ⚠️  Неожиданный формат: {type(photos_uf)}")
    else:
        print(f"   ❌ Фото не загрузились")
        print(f"   ⚠️  Возможно, поле не существует или имеет другой тип")


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/migrate_photos.py <SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/migrate_photos.py 285")
        print()
        print("Требования:")
        print("  - BOT_TOKEN должен быть установлен в .env")
        sys.exit(1)
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не установлен в .env файле")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом")
        sys.exit(1)
    
    await migrate_photos(shift_id)


if __name__ == "__main__":
    asyncio.run(main())

