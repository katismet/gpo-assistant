#!/usr/bin/env python3
"""
Тест отправки файла в Telegram
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_file_sending():
    """Тестируем создание InputFile"""
    
    print("🧪 Тестируем создание InputFile...")
    
    try:
        from aiogram.types import InputFile
        
        # Проверяем существование тестового файла
        test_file_path = Path("output/pdf/LPA_Не указан_Не указана.docx")
        if not test_file_path.exists():
            print(f"❌ Тестовый файл не найден: {test_file_path}")
            return False
        
        print(f"✅ Тестовый файл найден: {test_file_path}")
        
        # Тестируем создание InputFile
        with open(test_file_path, 'rb') as f:
            input_file = InputFile(f, filename="test_lpa.docx")
            print(f"✅ InputFile создан успешно: {input_file}")
        
        print("🎉 Тест пройден успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Тест создания InputFile")
    print("=" * 50)
    
    success = test_file_sending()
    
    print("=" * 50)
    if success:
        print("🎉 Тест пройден успешно!")
    else:
        print("💥 Тест не пройден")
        sys.exit(1)

