#!/usr/bin/env python3
"""
Проверка статуса бота
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_bot_status():
    """Проверяем статус бота"""
    
    print("🤖 Проверка статуса бота...")
    
    try:
        from app.config import get_settings
        settings = get_settings()
        
        print(f"📱 Bot Token: {settings.bot_token[:10]}...")
        print("✅ Конфигурация загружена")
        
        # Проверяем импорт модулей
        from app.telegram.bot import gpo_bot, dp
        print("✅ Бот импортирован")
        
        from app.telegram.flow_lpa import router as lpa_router
        print("✅ LPA роутер импортирован")
        
        print("\n🎉 Бот готов к работе!")
        print("📱 Откройте Telegram и найдите @GPO_Helper2_bot")
        print("🚀 Нажмите /start для активации")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Проверка статуса бота")
    print("=" * 50)
    
    success = check_bot_status()
    
    print("=" * 50)
    if success:
        print("🎉 Бот готов к работе!")
    else:
        print("💥 Есть проблемы с ботом")
        sys.exit(1)

