"""Parse the DOLE Labor Code (2022) PDF into one record per Article.

Pipeline: PDF -> body-text lines (footnotes dropped by font size)
          -> cleaned text -> list of article records -> JSONL file.
"""
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]     # labor_code_parser.py -> shared -> src -> project root

# Font sizes found in the PDF: body 9.5 (some 9.0), headings 10-16,
# footnote text 5.5, footnote numbers 3.5, in-text footnote marks 6.0, page numbers 8.0.
MIN_BODY_SIZE = 8.5

BOOK    = re.compile(r"^Book\s+(\w+)\s+[–-]\s+(.+)$", re.IGNORECASE)
TITLE   = re.compile(r"^Title\s+([IVX]+(?:-[A-Z])?)\s+[–-]\s+(.+)$", re.IGNORECASE)
CHAPTER = re.compile(r"^Chapter\s+([IVX]+)\s+[–-]\s+(.+)$", re.IGNORECASE)
ARTICLE = re.compile(r"^ART\.\s+(\d+)\.\s*(?:\[(\d+)\]\s*)?(.*)$")
DASH    = re.compile(r"\s+–\s*")               # separates an article heading from its text
LEADING_DASH = re.compile(r"^–\s*")


def lines_from_page_dict(page_dict: dict, min_size: float = MIN_BODY_SIZE) -> list[str]:
    """Return the body-text lines of one page, skipping small text (footnotes, marks)."""
    lines = []
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"] if s["size"] >= min_size).strip()
            if text:
                lines.append(text)
    return lines


def read_pdf_text(pdf_path, min_size: float = MIN_BODY_SIZE) -> str:
    """Read every page and join the body-text lines into one string."""
    all_lines = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            all_lines.extend(lines_from_page_dict(page.get_text("dict"), min_size))
    return "\n".join(all_lines)


def clean_text(raw: str) -> str:
    """Start at Article 1 and drop leftover lone page numbers."""
    start = re.search(r"^ART\.\s+1\.", raw, re.MULTILINE).start()
    kept = []
    for line in raw[start:].splitlines():
        line = line.strip()
        if not line or re.fullmatch(r"\d{1,3}", line):
            continue
        kept.append(line)
    return "\n".join(kept)


CAPS_CONT = re.compile(r"^[A-Z0-9 ,\-–&'’/().]+$")   # an ALL-CAPS line = wrapped part of a heading


def tidy_label(label: str) -> str:
    """Remove a footnote/page number glued to the end of a heading ('WAGES82' -> 'WAGES')."""
    return re.sub(r"(?<=[A-Za-z])\d{1,3}$", "", label).strip()


def split_articles(clean: str) -> list[dict]:
    """Split cleaned text into article records labelled with Book/Title/Chapter."""
    records, seen = [], {}
    labels = {"book": "PRELIMINARY TITLE", "title": "", "chapter": "Chapter I - GENERAL PROVISIONS"}
    pending = None          # which label's heading may continue on the next line
    current = None

    for line in clean.splitlines():
        if BOOK.match(line):
            labels.update(book=tidy_label(line), title="", chapter="")
            pending = "book"
            continue
        if TITLE.match(line):
            labels.update(title=tidy_label(line), chapter="")
            pending = "title"
            continue
        if CHAPTER.match(line):
            labels["chapter"] = tidy_label(line)
            pending = "chapter"
            continue

        m = ARTICLE.match(line)
        if m:
            pending = None
            no, old, rest = m.group(1), m.group(2), m.group(3)
            parts = DASH.split(rest, maxsplit=1)
            heading = parts[0].strip(" .")
            first_text = parts[1].strip() if len(parts) > 1 else ""
            seen[no] = seen.get(no, 0) + 1
            art_id = f"art_{no}" if seen[no] == 1 else f"art_{no}_{chr(96 + seen[no])}"
            current = {"id": art_id, "article": no, "old_article": old or "",
                       "heading": heading, "book": labels["book"], "title": labels["title"],
                       "chapter": labels["chapter"], "lines": [first_text] if first_text else []}
            records.append(current)
        elif pending and CAPS_CONT.match(line):
            labels[pending] = tidy_label(f"{labels[pending]} {line}")   # heading wrapped onto this line
        elif current is not None:
            if not current["lines"]:
                line = LEADING_DASH.sub("", line)   # text continues the heading line after its dash
            current["lines"].append(line)

    for r in records:
        r["text"] = "\n".join(r.pop("lines"))
    return records


def save_jsonl(records: list[dict], out_path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_jsonl(path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> None:
    pdf = ROOT / "data" / "raw" / "labor_code_2022.pdf"
    out = ROOT / "data" / "processed" / "labor_code_articles.jsonl"
    articles = split_articles(clean_text(read_pdf_text(pdf)))
    save_jsonl(articles, out)
    print(len(articles), "articles saved to", out)


if __name__ == "__main__":
    main()