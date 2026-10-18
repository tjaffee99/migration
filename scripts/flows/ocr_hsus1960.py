#!/usr/bin/env python3
"""Re-OCR HSUS 1960 series C 88-114 (pages 18-21 of hist_stats_colonial-1957-chC.pdf)
column by column with Tesseract, because the PDF's own text layer is too noisy.

  python3 -I scripts/flows/ocr_hsus1960.py
Needs: pdftoppm (poppler), tesseract (apt-get install tesseract-ocr), Pillow, numpy.
Writes data/raw/hsus1960_chC/C88_114_tesseract_ocr.csv  (page,row,year_text,col1..colN = raw OCR strings).
The validated numbers are produced later by build_flows.py / hsus1960.py.
"""
import csv
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PDF = os.path.join(ROOT, "data", "raw", "hsus1960_chC", "hist_stats_colonial-1957-chC.pdf")
OUT = os.path.join(ROOT, "data", "raw", "hsus1960_chC", "C88_114_tesseract_ocr.csv")
DPI = 400
NCOLS = {18: 13, 19: 13, 20: 14, 21: 14}


def groups(idx, gap=6):
    g = []
    for i in idx:
        if g and i - g[-1][-1] <= gap:
            g[-1].append(i)
        else:
            g.append([i])
    return [(x[0], x[-1]) for x in g]


def find_layout(gray, ncols):
    dark = gray < 190
    H, W = dark.shape
    rows = dark.mean(axis=1)
    hrules = groups([y for y in range(H) if rows[y] > 0.45])
    # body top: last horizontal rule in the top 25% of the page (below the column-number row)
    tops = [b for a, b in hrules if b < H * 0.25]
    top = max(tops) + 4
    bots = [a for a, b in hrules if a > H * 0.6]
    bot = min(bots) - 4 if bots else int(H * 0.93)
    body = gray[top:bot] < 225
    # a ruling line is a long *continuous* vertical dark run; digits never are
    longest = np.zeros(W, dtype=int)
    for x in range(W):
        col = body[:, x].astype(np.int8)
        if not col.any():
            continue
        d = np.diff(np.concatenate(([0], col, [0])))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        longest[x] = (ends - starts).max()
    vr = groups([x for x in range(W) if longest[x] > 0.3 * (bot - top)], gap=25)  # merge double rules
    edges = [(a + b) // 2 for a, b in vr]
    # keep edges that leave reasonable column widths
    return top, bot, edges


def ocr_strip(img, whitelist):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "s.png")
        img.save(p)
        res = subprocess.run(["tesseract", p, "stdout", "--psm", "6", "-c", f"tessedit_char_whitelist={whitelist}",
                              "tsv"], capture_output=True, text=True)
    words = []
    for line in res.stdout.splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        left, top, w, h, conf = int(f[6]), int(f[7]), int(f[8]), int(f[9]), float(f[10])
        words.append((top + h / 2, left, f[11].strip(), conf))
    return words


def main():
    rows_out = []
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", "18", "-l", "21", "-r", str(DPI), "-gray", "-png", PDF,
                        os.path.join(td, "p")], check=True)
        for p in (18, 19, 20, 21):
            im = Image.open(os.path.join(td, f"p-{p}.png")).convert("L")
            g = np.array(im)
            top, bot, edges = find_layout(g, NCOLS[p])
            print(f"page {p}: body y {top}-{bot}, {len(edges)} vertical rules at {edges}", file=sys.stderr)
            # year column = left of first rule; value columns between rules (ignore very narrow gaps)
            bounds = [0] + edges + [g.shape[1]]
            strips = [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if b - a > 60]
            year_strip, val_strips = strips[0], strips[1:]
            if len(val_strips) != NCOLS[p]:
                print(f"  WARNING page {p}: {len(val_strips)} value strips (expected {NCOLS[p]})", file=sys.stderr)
            ycrop = im.crop((year_strip[0], top, year_strip[1], bot))
            ywords = ocr_strip(ycrop, "0123456789.-")
            yrows = [(y, t) for y, x, t, c in ywords if re.match(r"^1[89]\d\d", t)]
            cols = []
            for a, b in val_strips:
                cols.append(ocr_strip(im.crop((a + 6, top, b - 6, bot)), "0123456789,."))
            # row anchors: y-centres of the words in a column that has a value in every year
            # (C 88 "All countries" on pp. 18-19, C 106 "America, total" on pp. 20-21)
            anchor_col = 0 if p in (18, 19) else 5
            anchors = sorted(y for y, x, t, cf in cols[anchor_col])
            expected = 72 if p in (18, 20) else 66
            if len(anchors) != expected:   # fall back: clusters of word centres seen in >= 3 columns
                ys = sorted((y, j) for j, c in enumerate(cols) for y, x, t, cf in c)
                cl = []
                for y, j in ys:
                    if cl and y - cl[-1][-1][0] <= 12:
                        cl[-1].append((y, j))
                    else:
                        cl.append([(y, j)])
                anchors = [sum(y for y, _ in c) / len(c) for c in cl if len({j for _, j in c}) >= 3]
            if len(anchors) != expected:
                print(f"  WARNING page {p}: {len(anchors)} anchor rows (expected {expected})", file=sys.stderr)
            for i, ay in enumerate(anchors):
                cells = []
                for c in cols:
                    near = [t for y, x, t, cf in c if abs(y - ay) < 14]
                    cells.append(" ".join(near))
                yt = next((t for y, t in yrows if abs(y - ay) < 16), "")
                rows_out.append([p, i, yt] + cells)
            print(f"  page {p}: {len(anchors)} rows", file=sys.stderr)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["page", "row", "year_text"] + [f"c{i+1}" for i in range(14)])
        for r in rows_out:
            w.writerow(r + [""] * (17 - len(r)))
    print("wrote", OUT, file=sys.stderr)


def _cluster(ys, tol):
    out = []
    for y in ys:
        if out and y - out[-1][-1] <= tol:
            out[-1].append(y)
        else:
            out.append([y])
    return out


if __name__ == "__main__":
    main()
