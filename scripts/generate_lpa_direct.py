#!/usr/bin/env python3
"""Прямая генерация ЛПА для конкретной смены из Bitrix24.

Использует единую функцию generate_lpa_for_shift из app/services/lpa_generator.py.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.lpa_generator import generate_lpa_for_shift


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/generate_lpa_direct.py <SHIFT_BITRIX_ID>")
        print()
        print("Пример:")
        print("  python scripts/generate_lpa_direct.py 285")
        sys.exit(1)
    
    try:
        shift_bitrix_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом (Bitrix ID смены)")
        sys.exit(1)
    
    print(f"📄 Генерация ЛПА для смены (Bitrix ID: {shift_bitrix_id})...")
    print()
    
    try:
        result = await generate_lpa_for_shift(shift_bitrix_id)
    except Exception as e:
        print(f"❌ Ошибка генерации ЛПА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    pdf_path = result.pdf_path
    context = result.context
    if pdf_path and pdf_path.exists():
        print()
        print("=" * 60)
        print(f"✅ ЛПА успешно сгенерирован!")
        print(f"📁 Файл: {pdf_path}")
        print(f"📊 Размер: {pdf_path.stat().st_size} байт")
        print(f"📄 Формат: {pdf_path.suffix.upper()}")
        if context:
            print(f"📋 Объект: {context.get('object_name', 'Не указан')}")
            print(f"📅 Дата: {context.get('date', 'Не указана')}")
            print(f"📊 План: {context.get('plan_total', 0)}")
            print(f"📊 Факт: {context.get('fact_total', 0)}")
        print("=" * 60)
        print()
        print("Проверьте файл на наличие плейсхолдеров {{...}}")
        print("Если плейсхолдеры есть - проверьте логи генерации.")
    else:
        print()
        print("❌ Не удалось сгенерировать ЛПА")
        print("   Проверьте логи для деталей ошибки.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
