#!/usr/bin/env python3
"""Проверка наличия плейсхолдеров {{...}} в DOCX."""

import sys
from pathlib import Path
from zipfile import ZipFile


def check_doc(path: Path) -> int:
    """Проверяет, остались ли в документе шаблонные плейсхолдеры."""
    if not path.exists():
        print(f"❌ Файл не найден: {path}")
        return 1

    with ZipFile(path) as zf:
        data = zf.read("word/document.xml").decode("utf-8", errors="ignore")

    if "{{" in data:
        idx = data.index("{{")
        snippet = data[max(0, idx - 80): idx + 80]
        print("⚠️  Найдены плейсхолдеры {{...}} в документе")
        print("Фрагмент:")
        print(snippet)
        return 1

    print("✅ Плейсхолдеры {{...}} не найдены")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: python scripts/check_doc_placeholders.py <path_to_docx>")
        return 1

    path = Path(sys.argv[1])
    return check_doc(path)


if __name__ == "__main__":
    sys.exit(main())





