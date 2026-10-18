#!/usr/bin/env python3
"""OCR helper for scanned census tables (state rows x country columns).

  python3 -I scripts/stock/ocr_census_table.py <pdf> <page_no(1-based)> <out_json> [dpi]

Renders one PDF page with pdftoppm, runs RapidOCR (rapidocr_onnxruntime) and writes the raw
token list [[box, text, conf], ...] to <out_json>.  Grid reconstruction, validation by row
and column sums and manual corrections are done by the per-table builders
(e.g. build_hist_1950_t71.py); OCR output is never used without those checks.
"""
import json, os, subprocess, sys, tempfile


def ocr_page(pdf, page, out_json, dpi=300):
    from rapidocr_onnxruntime import RapidOCR
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, 'p')
        subprocess.run(['pdftoppm', '-r', str(dpi), '-f', str(page), '-l', str(page), '-png', pdf, base],
                       check=True)
        png = [os.path.join(td, f) for f in os.listdir(td) if f.endswith('.png')][0]
        eng = RapidOCR()
        from PIL import Image
        im = Image.open(png)
        W, H = im.size
        # OCR in overlapping horizontal strips (whole-page OCR silently dropped the top of
        # the page); keep a token only from the strip whose core contains its centre.
        step, pad = 600, 60
        xstep, xpad = 800, 160
        toks = []
        for y0 in range(0, H, step):
            top, bot = max(0, y0 - pad), min(H, y0 + step + pad)
            for x0 in range(0, W, xstep):
                left, right = max(0, x0 - xpad), min(W, x0 + xstep + xpad)
                tile = os.path.join(td, 'tile.png')
                im.crop((left, top, right, bot)).save(tile)
                res, _ = eng(tile, use_cls=False)
                for box, txt, conf in (res or []):
                    yc = sum(p[1] for p in box) / 4 + top
                    xc = sum(p[0] for p in box) / 4 + left
                    if y0 <= yc < y0 + step and x0 <= xc < x0 + xstep:
                        toks.append([[[float(x) + left, float(y) + top] for x, y in box], txt, float(conf)])
    json.dump(toks, open(out_json, 'w'))
    return toks


def tokens(path):
    out = []
    for box, txt, conf in json.load(open(path)):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append(dict(xl=min(xs), xr=max(xs), yt=min(ys), yb=max(ys), y=sum(ys) / 4, x=sum(xs) / 4,
                        text=txt, conf=conf))
    return out


SEPARATORS = set(" ,.'+$#\u03bc/*`:;_-")


def parse_int(txt):
    t = ''.join(ch for ch in txt if ch not in SEPARATORS)
    t = t.replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1').replace('S', '5')
    if t.isdigit():
        return int(t)
    return None


if __name__ == '__main__':
    pdf, page, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 300
    toks = ocr_page(pdf, page, out, dpi)
    print(len(toks), 'tokens ->', out)
