#!/usr/bin/env python3
"""
doi_to_bibtex.py — DOI/arXiv ID → BibTeX через CrossRef + Semantic Scholar.

Usage:
    python doi_to_bibtex.py 10.1007/978-3-540-30206-3_12
    python doi_to_bibtex.py arXiv:1505.01093
    python doi_to_bibtex.py 10.1007/978-3-540-30206-3_12 --key maler2004monitoring
    cat dois.txt | xargs -I{} python doi_to_bibtex.py {}

Stdout — BibTeX-запись. Stderr — diagnostics.

Зависимости: requests. Если нет — `pip install requests`.
"""

import argparse
import re
import sys
import json
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("Установи requests: pip install requests")


CROSSREF_URL = "https://api.crossref.org/works/{}"
SEMSCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/{}"
ARXIV_URL = "http://export.arxiv.org/api/query?id_list={}"


def normalize_id(input_id: str) -> tuple[str, str]:
    """Возвращает (kind, normalized_id), где kind ∈ {'doi', 'arxiv', 'unknown'}."""
    s = input_id.strip()
    if s.startswith("arXiv:"):
        return "arxiv", s[6:]
    if re.match(r"^\d{4}\.\d{4,5}", s):
        return "arxiv", s
    if s.startswith("10."):
        return "doi", s
    return "unknown", s


def make_bibkey(authors: list[str], year: str, title: str) -> str:
    """Сгенерировать ключ вида 'maler2004monitoring'."""
    if not authors:
        first = "anon"
    else:
        first = re.sub(r"[^a-zA-Z]", "", authors[0].split()[-1].lower())
    title_word = re.sub(r"[^a-zA-Z]", "", title.split()[0].lower()) if title else "x"
    return f"{first}{year}{title_word[:10]}"


def fetch_crossref(doi: str) -> Optional[dict]:
    try:
        r = requests.get(CROSSREF_URL.format(doi), timeout=10,
                         headers={"User-Agent": "vkr-bauman-flv/1.0 (mailto:adanman386@gmail.com)"})
        if r.status_code == 200:
            return r.json()["message"]
    except Exception as e:
        print(f"[CrossRef] {e}", file=sys.stderr)
    return None


def fetch_semscholar(ident: str) -> Optional[dict]:
    try:
        r = requests.get(SEMSCHOLAR_URL.format(ident),
                         params={"fields": "title,authors,year,venue,journal,abstract,externalIds"},
                         timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[SemanticScholar] {e}", file=sys.stderr)
    return None


def crossref_to_bibtex(meta: dict, key: Optional[str] = None) -> str:
    authors = []
    for a in meta.get("author", []):
        family = a.get("family", "")
        given = a.get("given", "")
        if family:
            authors.append(f"{family}, {given}".strip(", "))
    title = " ".join(meta.get("title") or ["[no title]"])
    year = ""
    if "issued" in meta:
        parts = meta["issued"].get("date-parts", [[None]])
        year = str(parts[0][0]) if parts and parts[0][0] else ""
    container = " ".join(meta.get("container-title") or [""])
    volume = meta.get("volume", "")
    issue = meta.get("issue", "")
    page = meta.get("page", "")
    publisher = meta.get("publisher", "")
    doi = meta.get("DOI", "")
    type_ = meta.get("type", "article")
    bibtype = {
        "journal-article": "article",
        "book-chapter": "incollection",
        "book": "book",
        "proceedings-article": "inproceedings",
        "monograph": "book",
        "report": "techreport",
    }.get(type_, "article")

    if not key:
        key = make_bibkey(authors, year, title)

    fields = {
        "author": " and ".join(authors),
        "title": title,
        "journal" if bibtype == "article" else "booktitle": container,
        "year": year,
        "volume": volume,
        "number": issue,
        "pages": page,
        "publisher": publisher,
        "doi": doi,
    }
    fields = {k: v for k, v in fields.items() if v}
    body = ",\n  ".join(f"{k} = {{{v}}}" for k, v in fields.items())
    return f"@{bibtype}{{{key},\n  {body}\n}}"


def main():
    p = argparse.ArgumentParser(description="DOI/arXiv → BibTeX")
    p.add_argument("ident", help="DOI или arXiv ID")
    p.add_argument("--key", help="Custom BibTeX key", default=None)
    args = p.parse_args()

    kind, ident = normalize_id(args.ident)
    if kind == "unknown":
        sys.exit(f"Не распознан идентификатор: {args.ident}")

    if kind == "doi":
        meta = fetch_crossref(ident)
        if meta:
            print(crossref_to_bibtex(meta, args.key))
            return
    if kind == "arxiv":
        # Для arXiv используем Semantic Scholar
        ss = fetch_semscholar(f"ARXIV:{ident}")
        if ss:
            authors = [a["name"] for a in ss.get("authors", [])]
            year = str(ss.get("year", ""))
            title = ss.get("title", "")
            key = args.key or make_bibkey(authors, year, title)
            arxiv_id = ss.get("externalIds", {}).get("ArXiv", ident)
            print(f"@misc{{{key},\n"
                  f"  author = {{{' and '.join(authors)}}},\n"
                  f"  title = {{{title}}},\n"
                  f"  year = {{{year}}},\n"
                  f"  eprint = {{{arxiv_id}}},\n"
                  f"  archivePrefix = {{arXiv}},\n"
                  f"  url = {{https://arxiv.org/abs/{arxiv_id}}}\n"
                  f"}}")
            return

    sys.exit("Не удалось извлечь метаданные ни через CrossRef, ни через Semantic Scholar")


if __name__ == "__main__":
    main()
