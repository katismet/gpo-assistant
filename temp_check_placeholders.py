import zipfile
import re
from pathlib import Path
path = Path('C:/ГПО Помощник/output/pdf/LPA_501_20251118_Объект_№1_-_Строительство_жилого_дома_Объект №1 - Строительство жилого дома_18.11.2025.docx')
with zipfile.ZipFile(path) as z:
    for name in z.namelist():
        if not name.startswith('word/') or not name.endswith('.xml'):
            continue
        xml = z.read(name).decode('utf-8', errors='ignore')
        matches = re.findall(r'\{\{([^}]+)\}\}', xml)
        if matches:
            print(name, len(matches))
