"""Utility: extract readable text from PDFs for literature review.

Usage:
    python tools/extract_pdf_text.py --pages 2 <pdf1> <pdf2> ...

Tips:
    - Use --out-dir to write full extracted text to files (recommended).
    - Use --max-chars to control how much preview is printed to the terminal.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # PyMuPDF


def extract_text(pdf_path: Path, max_pages: int) -> str:
    doc = fitz.open(pdf_path)
    pages = min(len(doc), max_pages)
    chunks: list[str] = []
    for page_index in range(pages):
        page = doc.load_page(page_index)
        text = page.get_text("text")
        # normalize whitespace
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        chunks.append("\n".join(lines))
    doc.close()
    return "\n\n---PAGE---\n\n".join(chunks)


def extract_pdf_to_text(pdf_path: str | Path, max_pages: int = 2) -> str:
    """Backward-compatible alias for earlier helper name."""
    return extract_text(Path(pdf_path), max_pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=2, help="How many pages to extract from start")
    parser.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Optional output directory to write full extracted text as .txt files",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=12000,
        help="How many characters to preview in the terminal (full text still written if --out-dir is set)",
    )
    parser.add_argument("pdfs", nargs="+", help="PDF paths")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    for p in args.pdfs:
        path = Path(p)
        print("=" * 100)
        print(path)
        if not path.exists():
            print("[MISSING]")
            continue
        try:
            text = extract_text(path, args.pages)
        except Exception as e:
            print(f"[ERROR] {e}")
            continue

        if out_dir is not None:
            out_path = out_dir / f"{path.stem}.txt"
            out_path.write_text(text, encoding="utf-8")
            print(f"[WROTE] {out_path}")

        # Print a bounded amount to avoid flooding terminal
        max_chars = max(0, int(args.max_chars))
        print(text[:max_chars])
        if len(text) > max_chars:
            print("\n...[TRUNCATED]...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
