#!/usr/bin/env python3
"""
md_to_docx_gost.py — конвертация Markdown главы в .docx по стилю ГОСТ 7.32.

Usage:
    python md_to_docx_gost.py 06_ПЗ/draft/02_Глава1.md \
        --output 06_ПЗ/Глава1.docx \
        --bib BIBLIO.bib \
        --csl assets/gost-r-7-0-5-2008.csl \
        --reference-doc assets/reference_gost.docx

Требует pandoc (>= 2.x). Установка:
    macOS: brew install pandoc
    Linux: apt install pandoc

Опционально: для русских формул через MathJax — pandoc сам справится.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path, help="Markdown-файл")
    p.add_argument("--output", "-o", type=Path, required=True, help="Выходной .docx")
    p.add_argument("--bib", type=Path, default=None, help="BibTeX-файл")
    p.add_argument("--csl", type=Path, default=None, help="CSL-стиль (по умолчанию ГОСТ 7.0.5)")
    p.add_argument("--reference-doc", type=Path, default=None, help="DOCX-шаблон со стилями")
    p.add_argument("--toc", action="store_true", help="Добавить оглавление")
    args = p.parse_args()

    if shutil.which("pandoc") is None:
        sys.exit("pandoc не найден. Установи: brew install pandoc / apt install pandoc")

    cmd = ["pandoc", str(args.input), "-o", str(args.output)]
    if args.bib:
        cmd += ["--bibliography", str(args.bib)]
    if args.csl:
        cmd += ["--csl", str(args.csl)]
    if args.reference_doc:
        cmd += ["--reference-doc", str(args.reference_doc)]
    if args.toc:
        cmd += ["--toc", "--toc-depth=3"]
    cmd += [
        "--standalone",
        "--from", "markdown+yaml_metadata_block+pipe_tables+raw_attribute",
        "--to", "docx",
        "--citeproc",
    ]

    print(" ".join(cmd))
    r = subprocess.run(cmd)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
