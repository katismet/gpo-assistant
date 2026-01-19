from pathlib import Path
from app.services.lpa_pdf import docx_has_placeholders
print(docx_has_placeholders(Path('output/pdf/test_simple.docx')))
