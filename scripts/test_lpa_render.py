#!/usr/bin/env python3
"""Тестовый скрипт для проверки рендеринга ЛПА без Telegram и Bitrix."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.lpa_pdf import render_lpa_docx, debug_extract_placeholders


async def test_lpa_render():
    """Тест рендеринга ЛПА с фиктивными данными."""
    print("=" * 60)
    print("ТЕСТ РЕНДЕРИНГА ЛПА")
    print("=" * 60)
    print()
    
    # Путь к шаблону
    template_path = Path("app/templates/pdf/lpa_template.docx")
    if not template_path.exists():
        print(f"❌ Шаблон не найден: {template_path}")
        return False
    
    print(f"✅ Шаблон найден: {template_path}")
    print()
    
    # Извлекаем плейсхолдеры из шаблона
    print("📋 Извлечение плейсхолдеров из шаблона...")
    template_vars = debug_extract_placeholders(str(template_path))
    print(f"   Найдено плейсхолдеров: {len(template_vars)}")
    print(f"   Примеры: {sorted(list(template_vars))[:20]}")
    print()
    
    # Создаем фиктивный контекст
    print("📝 Создание тестового контекста...")
    test_context = {
        "object_name": "Тестовый объект",
        "object_address": "г. Москва, ул. Тестовая, д. 1",
        "date": "13.11.2025",
        "shift_type": "Дневная",
        "section": "Строительство",
        "foreman": "Иванов И.И.",
        "tasks": [
            {"name": "Тестовая работа 1", "unit": "м³", "plan": 100.0, "fact": 95.0, "executor": "Бригада 1", "reason": ""},
            {"name": "Тестовая работа 2", "unit": "м²", "plan": 50.0, "fact": 52.0, "executor": "Бригада 2", "reason": ""},
        ],
        "tech": [
            {"name": "Экскаватор", "hours": 8.0, "comment": "Работал нормально"},
        ],
        "materials": [
            {"name": "Бетон", "unit": "м³", "qty": 10.0, "price": 5000.0, "sum": 50000.0},
        ],
        "timesheet": [
            {"name": "Бригада 1", "hours": 8.0, "rate": 2000.0, "sum": 16000.0},
        ],
        "plan_total": 150.0,
        "fact_total": 147.0,
        "efficiency": 98.0,
        "downtime_reason": "",
        "downtime_min": 0,
        "report_status": "Закрыт",
        "reasons_text": "Отклонений не выявлено",
        "photos": [],
    }
    
    print(f"   Задач: {len(test_context['tasks'])}")
    print(f"   Техники: {len(test_context['tech'])}")
    print(f"   Материалов: {len(test_context['materials'])}")
    print(f"   Табель: {len(test_context['timesheet'])}")
    print()
    
    # Рендерим DOCX
    print("🔄 Рендеринг DOCX...")
    output_dir = Path("output/test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        docx_path = render_lpa_docx(
            template_path=template_path,
            data=test_context,
            out_dir=output_dir,
            filename_prefix="TEST_LPA",
            photos=[],
            max_photos_in_doc=5,
        )
        
        if not docx_path.exists():
            print(f"❌ Файл не был создан: {docx_path}")
            return False
        
        print(f"✅ DOCX создан: {docx_path}")
        print(f"   Размер: {docx_path.stat().st_size} байт")
        print()
        
        # Проверяем наличие плейсхолдеров
        print("🔍 Проверка на наличие плейсхолдеров...")
        import zipfile
        with zipfile.ZipFile(docx_path, 'r') as z:
            doc_xml = z.read('word/document.xml').decode('utf-8')
            has_placeholders = '{{' in doc_xml or '}}' in doc_xml
        
        if has_placeholders:
            import re
            placeholder_matches = re.findall(r'\{\{[^}]+\}\}', doc_xml)
            print(f"❌ Найдено {len(placeholder_matches)} плейсхолдеров в файле!")
            print(f"   Примеры: {list(set(placeholder_matches))[:10]}")
            return False
        else:
            print("✅ Плейсхолдеры не найдены - рендеринг успешен!")
            print()
            print("=" * 60)
            print("✅ ТЕСТ ПРОЙДЕН")
            print(f"📁 Файл: {docx_path}")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при рендеринге: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_lpa_render())
    sys.exit(0 if success else 1)




