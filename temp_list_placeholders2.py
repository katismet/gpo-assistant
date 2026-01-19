from app.services.lpa_pdf import debug_extract_placeholders
placeholders = sorted(debug_extract_placeholders('шаблон лпа.docx'))
print(len(placeholders))
for ph in placeholders:
    print(ph)
