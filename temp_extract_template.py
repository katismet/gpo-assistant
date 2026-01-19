import zipfile
import shutil
from pathlib import Path
zip_path = Path('app/templates/pdf/lpa_template.docx')
out_dir = Path('app/templates/pdf/tmp_docx')
if out_dir.exists():
    shutil.rmtree(out_dir)
out_dir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(out_dir)
print('Extracted to', out_dir)
