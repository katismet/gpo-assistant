"""Тест загрузки PDF через disk.file.upload."""
import asyncio
import base64
from pathlib import Path
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel

async def main():
    # Находим PDF файл
    pdf_dir = Path("output/pdf")
    pdf_files = list(pdf_dir.glob("LPA_491_*.pdf"))
    if not pdf_files:
        print("PDF файл не найден")
        return
    
    pdf_path = pdf_files[0]
    print(f"Найден PDF: {pdf_path}")
    
    # Читаем файл
    with open(pdf_path, 'rb') as f:
        file_bytes = f.read()
    
    file_name = pdf_path.name
    file_base64 = base64.b64encode(file_bytes).decode('utf-8')
    
    # Вариант 1: disk.file.upload
    print("\n=== Вариант 1: disk.file.upload ===")
    try:
        upload_result = await bx('disk.file.upload', {
            'id': 'shared_files_s1',  # ID папки для загрузки
            'data': {
                'NAME': file_name,
                'fileContent': file_base64
            }
        })
        print(f"Результат upload: {upload_result}")
        
        if isinstance(upload_result, dict) and 'result' in upload_result:
            file_id = upload_result['result'].get('ID')
            if file_id:
                print(f"Файл загружен, ID: {file_id}")
                
                # Привязываем файл к смене
                f_pdf_file = resolve_code("Смена", "UF_PDF_FILE")
                f_pdf_file_camel = upper_to_camel(f_pdf_file) if f_pdf_file and f_pdf_file.startswith("UF_") else None
                
                if f_pdf_file_camel:
                    # Пробуем разные форматы для привязки файла
                    # Формат 1: массив с ID
                    result1 = await bx('crm.item.update', {
                        'entityTypeId': SHIFT_ETID,
                        'id': 491,
                        'fields': {f_pdf_file_camel: [file_id]}
                    })
                    print(f"Результат привязки (массив): {result1}")
                    
                    # Проверяем результат
                    check = await bx('crm.item.get', {
                        'entityTypeId': SHIFT_ETID,
                        'id': 491,
                        'select': ['id', f_pdf_file_camel]
                    })
                    print(f"Поле после привязки: {check.get('item', {}).get(f_pdf_file_camel)}")
    except Exception as e:
        print(f"Ошибка варианта 1: {e}")
    
    # Вариант 2: прямое обновление через fileData
    print("\n=== Вариант 2: прямое обновление через fileData ===")
    try:
        f_pdf_file = resolve_code("Смена", "UF_PDF_FILE")
        f_pdf_file_camel = upper_to_camel(f_pdf_file) if f_pdf_file and f_pdf_file.startswith("UF_") else None
        
        if f_pdf_file_camel:
            file_data = {
                "fileData": [file_name, file_base64]
            }
            
            result2 = await bx('crm.item.update', {
                'entityTypeId': SHIFT_ETID,
                'id': 491,
                'fields': {f_pdf_file_camel: file_data}
            })
            print(f"Результат обновления: {result2}")
            
            # Проверяем результат
            await asyncio.sleep(2)
            check = await bx('crm.item.get', {
                'entityTypeId': SHIFT_ETID,
                'id': 491,
                'select': ['id', f_pdf_file_camel]
            })
            print(f"Поле после обновления: {check.get('item', {}).get(f_pdf_file_camel)}")
    except Exception as e:
        print(f"Ошибка варианта 2: {e}")

if __name__ == "__main__":
    asyncio.run(main())



