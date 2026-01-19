#!/usr/bin/env python3
"""
Тест импорта модулей бота без ошибок libgobject
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Тестируем импорт всех модулей бота"""
    
    print("🧪 Тестируем импорт модулей бота...")
    
    try:
        print("📦 Импортируем основные модули...")
        from app.telegram.bot import gpo_bot, dp
        print("✅ app.telegram.bot - OK")
        
        from app.telegram.flow_plan import router as plan_router
        print("✅ app.telegram.flow_plan - OK")
        
        from app.telegram.flow_report import router as report_router
        print("✅ app.telegram.flow_report - OK")
        
        from app.telegram.flow_lpa import router as lpa_router
        print("✅ app.telegram.flow_lpa - OK")
        
        from app.telegram.router_root import router as root_router
        print("✅ app.telegram.router_root - OK")
        
        print("\n🔧 Тестируем импорт сервисов...")
        from app.services.objects import fetch_all_objects
        print("✅ app.services.objects - OK")
        
        from app.services.shift_repo import get_last_closed_shift
        print("✅ app.services.shift_repo - OK")
        
        from app.services.lpa_pdf import render_lpa_docx
        print("✅ app.services.lpa_pdf - OK")
        
        print("\n🎉 Все модули импортированы успешно!")
        print("✅ Ошибка libgobject-2.0-0 больше не возникает!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Проверка импорта модулей бота")
    print("=" * 50)
    
    success = test_imports()
    
    print("=" * 50)
    if success:
        print("🎉 Тест пройден успешно!")
        print("✅ Бот готов к запуску без ошибок libgobject!")
    else:
        print("💥 Тест не пройден")
        sys.exit(1)

