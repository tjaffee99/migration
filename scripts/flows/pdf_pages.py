#!/usr/bin/env python3
"""Copy a page range of a PDF into a new, de-duplicated (small) PDF.
Usage: python3 -I pdf_pages.py in.pdf first_page last_page out.pdf   (1-based, inclusive)"""
import sys
from pypdf import PdfReader, PdfWriter

src, first, last, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
r = PdfReader(src)
w = PdfWriter()
for i in range(first - 1, last):
    w.add_page(r.pages[i])
w.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
for p in w.pages:
    p.compress_content_streams()
with open(out, "wb") as f:
    w.write(f)
