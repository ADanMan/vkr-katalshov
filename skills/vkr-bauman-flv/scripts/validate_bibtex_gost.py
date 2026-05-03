#!/usr/bin/env python3
"""
validate_bibtex_gost.py — проверка BibTeX-файла на минимальные поля под ГОСТ 7.0.5-2008.

Usage: python validate_bibtex_gost.py BIBLIO.bib

Выход 0 — все ОК, выход 1 — есть проблемы.
Печатает пред problèmes по entry'ям.

Зависимости: bibtexparser. `pip install bibtexparser==1.4.0`.
"""

import sys
from collections import defaultdict

try:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
except ImportError:
    sys.exit("Установи: pip install bibtexparser==1.4.0")


REQUIRED_FIELDS = {
    "article": ["author", "title", "journal", "year"],
    "book": ["author", "title", "publisher", "year"],
    "inproceedings": ["author", "title", "booktitle", "year"],
    "incollection": ["author", "title", "booktitle", "publisher", "year"],
    "manual": ["title", "year"],
    "techreport": ["author", "title", "institution", "year"],
    "phdthesis": ["author", "title", "school", "year"],
    "mastersthesis": ["author", "title", "school", "year"],
    "misc": ["title"],  # для электронных ресурсов; URL/note желательны
}

RECOMMENDED_FIELDS = {
    "article": ["volume", "pages"],
    "book": ["address"],
    "inproceedings": ["pages"],
    "misc": ["url", "note"],
}


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: validate_bibtex_gost.py BIBLIO.bib")

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    with open(sys.argv[1], encoding="utf-8") as f:
        db = bibtexparser.load(f, parser=parser)

    errors = 0
    warnings = 0
    seen_keys = set()

    for entry in db.entries:
        key = entry.get("ID", "?")
        type_ = entry.get("ENTRYTYPE", "?").lower()

        # Дубли ключей
        if key in seen_keys:
            print(f"[ERR] Дублирующийся ключ: {key}")
            errors += 1
        seen_keys.add(key)

        # Required fields
        required = REQUIRED_FIELDS.get(type_, [])
        for field in required:
            if field not in entry or not entry[field].strip():
                print(f"[ERR] {key} ({type_}): пропущено обязательное поле '{field}'")
                errors += 1

        # Recommended
        recommended = RECOMMENDED_FIELDS.get(type_, [])
        for field in recommended:
            if field not in entry or not entry[field].strip():
                print(f"[WARN] {key} ({type_}): желательно заполнить '{field}'")
                warnings += 1

        # Год — 4 цифры
        if "year" in entry:
            year = entry["year"].strip()
            if not (year.isdigit() and 1800 <= int(year) <= 2100):
                print(f"[ERR] {key}: подозрительный год '{year}'")
                errors += 1

        # Кириллица в авторе + латиница в названии — может быть OK, но предупредим
        author = entry.get("author", "")
        title = entry.get("title", "")
        has_cyr = lambda s: any('а' <= c <= 'я' or 'А' <= c <= 'Я' for c in s)
        if author and title:
            if has_cyr(author) != has_cyr(title):
                print(f"[INFO] {key}: смешанные алфавиты в author/title — проверь оформление")

    print(f"\n— Итого: {len(db.entries)} записей, {errors} ошибок, {warnings} предупреждений.")
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
