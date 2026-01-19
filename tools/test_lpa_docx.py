#!/usr/bin/env python3
"""
Тест генерации ЛПА DOCX (без PDF конвертации)
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.lpa_pdf import render_lpa_docx

def test_lpa_docx_generation():
    """Тестируем генерацию ЛПА DOCX"""
    
    # Тестовые данные для ЛПА
    test_data = {
        "object_name": "Объект №1 - Строительство дома",
        "section": "Строительный участок №1",
        "date": "23.10.2025",
        "foreman": "Иванов И.И.",
        
        # Производственные задания (до 10)
        "tasks": [
            {
                "name": "Земляные работы",
                "unit": "м³",
                "plan": "100",
                "fact": "95",
                "executor": "Бригада №1",
                "reason": "Неблагоприятные погодные условия"
            },
            {
                "name": "Бетонные работы",
                "unit": "м³",
                "plan": "50",
                "fact": "52",
                "executor": "Бригада №2",
                "reason": ""
            },
            {
                "name": "Кладка стен",
                "unit": "м²",
                "plan": "200",
                "fact": "180",
                "executor": "Бригада №3",
                "reason": "Недостаток материалов"
            }
        ],
        
        # Техника (до 7)
        "equipment": [
            {
                "name": "Экскаватор CAT 320",
                "hours": "8",
                "comment": "Работал без перебоев"
            },
            {
                "name": "Бетономешалка",
                "hours": "6",
                "comment": "Технический перерыв 2 часа"
            },
            {
                "name": "Кран КБ-405",
                "hours": "7",
                "comment": ""
            }
        ],
        
        # Табель (до 7)
        "timesheet": [
            {
                "name": "Иванов И.И.",
                "hours": "8",
                "rate": "500",
                "sum": "4000"
            },
            {
                "name": "Петров П.П.",
                "hours": "8",
                "rate": "450",
                "sum": "3600"
            },
            {
                "name": "Сидоров С.С.",
                "hours": "8",
                "rate": "400",
                "sum": "3200"
            }
        ],
        
        # Материалы (до 7)
        "materials": [
            {
                "name": "Цемент М400",
                "unit": "т",
                "qty": "5",
                "price": "8000",
                "sum": "40000"
            },
            {
                "name": "Песок",
                "unit": "м³",
                "qty": "10",
                "price": "500",
                "sum": "5000"
            },
            {
                "name": "Щебень",
                "unit": "м³",
                "qty": "8",
                "price": "800",
                "sum": "6400"
            }
        ],
        
        # Итоговые показатели
        "plan_total": "150000",
        "fact_total": "142000",
        "downtime_min": "120",
        "downtime_reason": "Ожидание поставки материалов",
        "efficiency": "94.7",
        "report_status": "Сформирован",
        "reasons_text": "Основные причины недовыполнения: недостаток материалов, неблагоприятные погодные условия",
        "photos_attached": "Да"
    }
    
    print("🧪 Тестируем генерацию ЛПА DOCX...")
    print(f"📊 Данные: {len(test_data['tasks'])} задач, {len(test_data['equipment'])} единиц техники")
    
    try:
        # Проверяем наличие шаблона
        template_path = Path("app/templates/pdf/lpa_template.docx")
        if not template_path.exists():
            print(f"❌ Шаблон ЛПА не найден: {template_path}")
            return False
        
        print(f"✅ Шаблон найден: {template_path}")
        
        # Создаем директорию для вывода
        output_dir = Path("output/pdf")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерируем DOCX
        docx_path = render_lpa_docx(
            template_path=str(template_path),
            out_dir=str(output_dir),
            data=test_data,
            filename_prefix="LPA"
        )
        
        if os.path.exists(docx_path):
            file_size = os.path.getsize(docx_path)
            print(f"✅ ЛПА DOCX успешно создан!")
            print(f"📄 Файл: {docx_path}")
            print(f"📏 Размер: {file_size:,} байт")
            return True
        else:
            print(f"❌ DOCX файл не создан: {docx_path}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка генерации ЛПА: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Запуск теста генерации ЛПА DOCX")
    print("=" * 50)
    
    success = test_lpa_docx_generation()
    
    print("=" * 50)
    if success:
        print("🎉 Тест пройден успешно!")
    else:
        print("💥 Тест не пройден")
        sys.exit(1)

