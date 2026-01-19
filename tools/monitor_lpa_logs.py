"""Скрипт для мониторинга логов ЛПА в реальном времени."""

import time
from pathlib import Path
import sys

def monitor_logs():
    """Мониторинг логов ЛПА."""
    log_file = Path("logs/app.log")
    bot_log_file = Path("bot.log")
    
    print("=" * 60)
    print("Мониторинг логов ЛПА")
    print("=" * 60)
    print(f"\nОтслеживаемые файлы:")
    print(f"  - {log_file}")
    print(f"  - {bot_log_file}")
    print("\nНажмите Ctrl+C для остановки\n")
    print("=" * 60)
    
    # Открываем файлы для чтения
    positions = {}
    
    if log_file.exists():
        positions[str(log_file)] = log_file.stat().st_size
    if bot_log_file.exists():
        positions[str(bot_log_file)] = bot_log_file.stat().st_size
    
    try:
        while True:
            # Проверяем logs/app.log
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(positions.get(str(log_file), 0))
                        new_lines = f.readlines()
                        if new_lines:
                            positions[str(log_file)] = f.tell()
                            for line in new_lines:
                                if "[LPA]" in line:
                                    print(f"[APP.LOG] {line.strip()}")
                except Exception as e:
                    print(f"Ошибка чтения {log_file}: {e}")
            
            # Проверяем bot.log
            if bot_log_file.exists():
                try:
                    with open(bot_log_file, "r", encoding="utf-8") as f:
                        f.seek(positions.get(str(bot_log_file), 0))
                        new_lines = f.readlines()
                        if new_lines:
                            positions[str(bot_log_file)] = f.tell()
                            for line in new_lines:
                                if "LPA" in line.upper() or "lpa" in line.lower():
                                    print(f"[BOT.LOG] {line.strip()}")
                except Exception as e:
                    print(f"Ошибка чтения {bot_log_file}: {e}")
            
            time.sleep(0.5)  # Проверяем каждые 0.5 секунды
            
    except KeyboardInterrupt:
        print("\n\nМониторинг остановлен.")


if __name__ == "__main__":
    try:
        monitor_logs()
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)







