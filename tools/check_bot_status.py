"""Проверка статуса бота и диагностика проблем."""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv

load_dotenv()

def check_bot_status():
    """Проверка статуса бота."""
    print("=" * 60)
    print("Диагностика бота")
    print("=" * 60)
    
    # 1. Проверка токена
    print("\n1. Проверка конфигурации...")
    bot_token = os.getenv("BOT_TOKEN")
    if bot_token:
        print(f"   ✅ BOT_TOKEN найден: {bot_token[:10]}...")
    else:
        print("   ❌ BOT_TOKEN не найден в .env!")
        print("   Добавьте BOT_TOKEN=ваш_токен в файл .env")
        return False
    
    # 2. Проверка файлов логов
    print("\n2. Проверка логов...")
    log_files = {
        "logs/app.log": "Основные логи (loguru)",
        "bot.log": "Логи из bot.py",
        "logs/errors.log": "Логи ошибок"
    }
    
    for log_file, description in log_files.items():
        if Path(log_file).exists():
            size = Path(log_file).stat().st_size
            print(f"   ✅ {log_file} существует ({size} байт) - {description}")
        else:
            print(f"   ⚠️  {log_file} не найден - {description}")
    
    # 3. Проверка последних логов
    print("\n3. Последние записи в логах...")
    if Path("bot.log").exists():
        try:
            with open("bot.log", "r", encoding="utf-8") as f:
                lines = f.readlines()
                bot_lines = [l for l in lines[-20:] if any(x in l.lower() for x in ["bot", "start", "polling", "error", "gpo"])]
                if bot_lines:
                    print("   Последние записи о боте:")
                    for line in bot_lines[-5:]:
                        print(f"      {line.strip()[:100]}")
                else:
                    print("   ⚠️  Нет записей о боте в логах")
        except Exception as e:
            print(f"   ❌ Ошибка чтения bot.log: {e}")
    
    # 4. Проверка процессов Python
    print("\n4. Проверка запущенных процессов...")
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command", "Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, ProcessName"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            print("   ✅ Найдены процессы Python:")
            print(result.stdout)
        else:
            print("   ❌ Процессы Python не найдены - бот не запущен!")
            print("\n   Для запуска бота выполните:")
            print("   python app/telegram/bot.py")
    except Exception as e:
        print(f"   ⚠️  Не удалось проверить процессы: {e}")
    
    # 5. Рекомендации
    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИИ")
    print("=" * 60)
    
    if not bot_token:
        print("\n❌ КРИТИЧНО: BOT_TOKEN не найден!")
        print("   Добавьте BOT_TOKEN в файл .env")
        return False
    
    if not Path("bot.log").exists() or Path("bot.log").stat().st_size == 0:
        print("\n⚠️  Бот не запускался или логи пусты")
        print("   Запустите бота:")
        print("   python app/telegram/bot.py")
        return False
    
    print("\n✅ Конфигурация выглядит правильно")
    print("\n📝 Следующие шаги:")
    print("   1. Убедитесь, что бот запущен: python app/telegram/bot.py")
    print("   2. Отправьте /start в боте")
    print("   3. Проверьте логи: Get-Content logs\\app.log -Tail 50")
    
    return True


if __name__ == "__main__":
    try:
        check_bot_status()
    except Exception as e:
        print(f"\n❌ Ошибка диагностики: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
