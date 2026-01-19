# -*- coding: utf-8 -*-
from pathlib import Path
from PyPDF2 import PdfReader
pdf_path = Path(r'C:/ГПО Помощник/output/pdf/LPA_501_20251118_Объект_№1_-_Строительство_жилого_дома_Объект №1 - Строительство жилого дома_18.11.2025.pdf')
reader = PdfReader(str(pdf_path))
text = ''
for page in reader.pages:
    text += page.extract_text() or ''
    if len(text) > 1000:
        break
text = text.strip().replace('\n', ' ')
print(text[:500])
