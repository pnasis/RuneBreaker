#!/usr/bin/env python3
"""
build_corpora.py

Build training corpora for rune_decryptor.py.

Creates:
    corpora/de.txt
    corpora/en.txt
    corpora/es.txt
    corpora/fr.txt
    corpora/grc.txt
    corpora/it.txt
    corpora/la.txt
    corpora/nl.txt
    corpora/ru.txt
    corpora/sv.txt

Sources:
- Project Gutenberg, selected through the Gutendex metadata API, for
  de/en/es/fr/it/la/nl/ru/sv.
- PerseusDL canonical Ancient Greek TEI XML for grc.

The goal is not a linguistically perfect corpus. It is a practical literary
character n-gram corpus for monoalphabetic substitution solving, with a mix
of public-domain authors and historical spellings.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


GUTENDEX = "https://gutendex.com/books"

# Gutendex uses two-letter Gutenberg language codes.
GUTENBERG_LANGS = {
    "de": "de",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "la": "la",
    "nl": "nl",
    "ru": "ru",
    "sv": "sv",
}

LANGUAGE_NAMES = {
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "grc": "Ancient Greek",
    "it": "Italian",
    "la": "Latin",
    "nl": "Dutch",
    "ru": "Russian",
    "sv": "Swedish",
}

# Ancient Greek originals from PerseusDL/canonical-greekLit.
# If one URL has moved, the builder will skip it and continue.
GREEK_SOURCES = [
    # Homer
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0012/tlg001/tlg0012.tlg001.perseus-grc2.xml",
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0012/tlg002/tlg0012.tlg002.perseus-grc2.xml",

    # Herodotus
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0016/tlg001/tlg0016.tlg001.perseus-grc2.xml",

    # Thucydides
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0003/tlg001/tlg0003.tlg001.perseus-grc2.xml",

    # Xenophon, Anabasis
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0032/tlg006/tlg0032.tlg006.perseus-grc2.xml",

    # Plato, Apology
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0059/tlg002/tlg0059.tlg002.perseus-grc2.xml",
]

USER_AGENT = (
    "RuneDecryptorCorpusBuilder/1.0 "
    "(educational monoalphabetic substitution analysis)"
)


def fetch(url: str, timeout: int = 45, retries: int = 3) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Could not fetch {url}: {error}")


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url).decode("utf-8"))


def decode_text(raw: bytes) -> str:
    """
    Gutenberg text is usually UTF-8 now, but older items can still have
    legacy encodings. Try a few safe fallbacks.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


START_MARKERS = (
    "*** START OF THE PROJECT GUTENBERG EBOOK",
    "***START OF THE PROJECT GUTENBERG EBOOK",
    "*** START OF THIS PROJECT GUTENBERG EBOOK",
    "***START OF THIS PROJECT GUTENBERG EBOOK",
)

END_MARKERS = (
    "*** END OF THE PROJECT GUTENBERG EBOOK",
    "***END OF THE PROJECT GUTENBERG EBOOK",
    "*** END OF THIS PROJECT GUTENBERG EBOOK",
    "***END OF THIS PROJECT GUTENBERG EBOOK",
)


def strip_gutenberg_boilerplate(text: str) -> str:
    """
    Remove the most common Gutenberg header/footer markers.
    If markers are not found, keep the text rather than accidentally deleting
    genuine content.
    """
    upper = text.upper()

    start = None
    for marker in START_MARKERS:
        pos = upper.find(marker)
        if pos != -1:
            nl = text.find("\n", pos)
            start = nl + 1 if nl != -1 else pos + len(marker)
            break

    end = None
    for marker in END_MARKERS:
        pos = upper.find(marker)
        if pos != -1:
            end = pos
            break

    if start is None:
        start = 0
    if end is None or end <= start:
        end = len(text)

    body = text[start:end]

    # Normalize line endings and remove obvious Gutenberg metadata remnants.
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"\n{4,}", "\n\n\n", body)

    return body.strip()


def choose_plain_text_url(formats: Dict[str, str]) -> Optional[str]:
    """
    Prefer UTF-8 text/plain, then any text/plain variant.
    """
    candidates = []
    for mime, url in formats.items():
        if not url:
            continue
        if mime.startswith("text/plain"):
            score = 0
            ml = mime.lower()
            ul = url.lower()

            if "utf-8" in ml or "utf8" in ml:
                score += 100
            if ".utf-8" in ul or "utf-8" in ul:
                score += 50
            if ul.endswith(".txt"):
                score += 10

            candidates.append((score, url))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def gutenberg_candidates(
    language: str,
    pages: int = 5,
    public_domain_only: bool = True,
) -> List[dict]:
    """
    Pull several pages of popular Gutenberg records for one language.
    """
    gut_lang = GUTENBERG_LANGS[language]

    params = {
        "languages": gut_lang,
        "mime_type": "text/plain",
        "sort": "popular",
    }
    if public_domain_only:
        params["copyright"] = "false"

    url = GUTENDEX + "?" + urllib.parse.urlencode(params)

    results: List[dict] = []

    for _ in range(pages):
        data = fetch_json(url)
        results.extend(data.get("results", []))
        next_url = data.get("next")
        if not next_url:
            break
        url = next_url

    return results


def book_is_useful(book: dict, language: str) -> bool:
    """
    Avoid dictionaries, word lists, catalogues, scores and similar material
    where possible. This is intentionally heuristic.
    """
    title = (book.get("title") or "").lower()
    subjects = " ".join(book.get("subjects") or []).lower()
    shelves = " ".join(book.get("bookshelves") or []).lower()

    bad_terms = (
        "dictionary", "dictionnaire", "wörterbuch", "woordenboek",
        "diccionario", "dizionario", "lexicon", "vocabulary",
        "catalog", "catalogue", "bibliography", "index",
        "music", "score", "scores", "sheet music",
    )

    haystack = " ".join((title, subjects, shelves))
    return not any(term in haystack for term in bad_terms)


def author_signature(book: dict) -> str:
    authors = book.get("authors") or []
    if not authors:
        return ""
    return authors[0].get("name") or ""


def build_gutenberg_language(
    language: str,
    out_path: Path,
    *,
    books: int,
    max_chars_per_book: int,
    pages: int,
) -> Tuple[int, int]:
    candidates = gutenberg_candidates(language, pages=pages)

    # Diversity: prefer different authors.
    selected: List[dict] = []
    seen_authors = set()

    for book in candidates:
        if not book_is_useful(book, language):
            continue

        url = choose_plain_text_url(book.get("formats", {}))
        if not url:
            continue

        author = author_signature(book)
        if author and author in seen_authors:
            continue

        selected.append(book)
        if author:
            seen_authors.add(author)

        if len(selected) >= books:
            break

    # If author diversity prevented reaching target, fill from remaining.
    if len(selected) < books:
        selected_ids = {b.get("id") for b in selected}
        for book in candidates:
            if book.get("id") in selected_ids:
                continue
            if not book_is_useful(book, language):
                continue
            if not choose_plain_text_url(book.get("formats", {})):
                continue
            selected.append(book)
            if len(selected) >= books:
                break

    chunks: List[str] = []
    successful = 0

    print(f"\n[{language}] {LANGUAGE_NAMES[language]}")

    for index, book in enumerate(selected, 1):
        url = choose_plain_text_url(book.get("formats", {}))
        title = book.get("title") or "(untitled)"
        author = author_signature(book) or "(unknown author)"

        print(f"  {index:02d}. {title} — {author}")

        try:
            raw = fetch(url)
            text = decode_text(raw)
            text = strip_gutenberg_boilerplate(text)

            # Skip tiny/non-prose downloads.
            if len(text) < 10_000:
                print("      skipped: too little usable text")
                continue

            # We don't need entire giant works. Taking a large prefix from
            # several different books gives better author/style diversity.
            if max_chars_per_book and len(text) > max_chars_per_book:
                text = text[:max_chars_per_book]

            chunks.append(
                f"\n\n"
                f"===== GUTENBERG BOOK {book.get('id')} =====\n"
                f"{text}\n"
            )
            successful += 1

        except Exception as exc:
            print(f"      download failed: {exc}")

    joined = "\n".join(chunks).strip() + "\n"
    out_path.write_text(joined, encoding="utf-8")

    return successful, len(joined)


def greek_xml_to_text(raw: bytes) -> str:
    """
    Extract textual content from Perseus TEI XML without needing lxml.
    """
    root = ET.fromstring(raw)

    pieces: List[str] = []
    for node in root.iter():
        if node.text:
            pieces.append(node.text)
        if node.tail:
            pieces.append(node.tail)

    text = " ".join(pieces)
    text = html.unescape(text)

    # Normalize whitespace while preserving Unicode polytonic Greek.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def greek_letter_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0

    greek = 0
    for c in letters:
        name = unicodedata.name(c, "")
        if "GREEK" in name:
            greek += 1

    return greek / len(letters)


def build_ancient_greek(out_path: Path, max_chars_per_source: int) -> Tuple[int, int]:
    chunks: List[str] = []
    successful = 0

    print("\n[grc] Ancient Greek (Perseus originals)")

    for index, url in enumerate(GREEK_SOURCES, 1):
        print(f"  {index:02d}. {url.rsplit('/', 1)[-1]}")

        try:
            raw = fetch(url)
            text = greek_xml_to_text(raw)

            ratio = greek_letter_ratio(text)
            if len(text) < 5_000 or ratio < 0.70:
                print(
                    f"      skipped: text does not look sufficiently Greek "
                    f"(ratio={ratio:.2%})"
                )
                continue

            if max_chars_per_source and len(text) > max_chars_per_source:
                text = text[:max_chars_per_source]

            chunks.append(
                f"\n\n"
                f"===== PERSEUS GREEK SOURCE {index} =====\n"
                f"{text}\n"
            )
            successful += 1

        except Exception as exc:
            print(f"      download failed: {exc}")

    joined = "\n".join(chunks).strip() + "\n"
    out_path.write_text(joined, encoding="utf-8")
    return successful, len(joined)


def human_size(n: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build literary corpora for rune_decryptor.py."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("corpora"),
        help="Output directory (default: corpora).",
    )
    parser.add_argument(
        "--books",
        type=int,
        default=12,
        help="Gutenberg books per modern/Latin language (default: 12).",
    )
    parser.add_argument(
        "--chars-per-book",
        type=int,
        default=750_000,
        help="Max characters taken from each Gutenberg book (default: 750000).",
    )
    parser.add_argument(
        "--greek-chars-per-source",
        type=int,
        default=1_200_000,
        help="Max chars per Ancient Greek source (default: 1200000).",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=8,
        help="Gutendex result pages to inspect per language (default: 8).",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=(
            "de", "en", "es", "fr", "grc",
            "it", "la", "nl", "ru", "sv",
        ),
        default=[
            "de", "en", "es", "fr", "grc",
            "it", "la", "nl", "ru", "sv",
        ],
        help="Only build selected languages.",
    )

    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)

    summary = []

    for language in args.languages:
        path = args.output / f"{language}.txt"

        try:
            if language == "grc":
                count, size = build_ancient_greek(
                    path,
                    max_chars_per_source=args.greek_chars_per_source,
                )
            else:
                count, size = build_gutenberg_language(
                    language,
                    path,
                    books=args.books,
                    max_chars_per_book=args.chars_per_book,
                    pages=args.pages,
                )

            summary.append((language, count, size, path))
        except Exception as exc:
            print(f"\n[{language}] FAILED: {exc}", file=sys.stderr)
            summary.append((language, 0, 0, path))

    print("\n" + "=" * 72)
    print("CORPUS BUILD SUMMARY")
    print("=" * 72)

    for language, count, size, path in summary:
        print(
            f"{language:>3}  {LANGUAGE_NAMES[language]:<15} "
            f"sources={count:<3} size={human_size(size):>9}  {path}"
        )

    print(
        "\nDone. You can now run:\n\n"
        "  python rune_decryptor.py solve cipher.txt --corpora corpora\n"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
