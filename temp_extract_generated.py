import zipfile
import shutil
from pathlib import Path
zip_path = Path('output/pdf/LPA_501_20251118_Объект_№1_-_Строительство_жилого_дома_Объект №1 - Строительство жилого дома_18.11.2025.docx')
out_dir = Path('output/pdf/tmp_docx_rendered')
if out_dir.exists():
    shutil.rmtree(out_dir)
out_dir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(out_dir)
print('Extracted to', out_dir)
