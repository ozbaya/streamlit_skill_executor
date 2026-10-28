#!/usr/bin/env python3
"""
Extract the text of a lecture-notes PDF, page by page, into a text file.

Usage:
    python extract_notes.py <input.pdf> [<output.txt>]

Prints a short report: page count, characters per page and a warning for
pages with little or no text (likely scanned images or diagrams that need to
be viewed with the Read tool instead).
"""

import sys
from pathlib import Path


def extract(pdf_path: Path) -> list[str]:
    try:
        import pdfplumber

        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return pages
    except ImportError:
        from pypdf import PdfReader

        return [(p.extract_text() or "") for p in PdfReader(str(pdf_path)).pages]


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python extract_notes.py <input.pdf> [<output.txt>]")

    pdf_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("work/notes.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pages = extract(pdf_path)
    chunks = [f"===== PAGE {i} =====\n{text.strip()}\n" for i, text in enumerate(pages, 1)]
    out_path.write_text("\n".join(chunks), encoding="utf-8")

    total = sum(len(t) for t in pages)
    print(f"Pages: {len(pages)}  Characters: {total}  Written to: {out_path}")
    sparse = [i for i, t in enumerate(pages, 1) if len(t.strip()) < 40]
    if sparse:
        print(
            "WARNING: little or no extractable text on pages "
            f"{sparse}. These may be scanned, handwritten or diagram pages. "
            "Open the PDF with the Read tool to view them."
        )


if __name__ == "__main__":
    main()
