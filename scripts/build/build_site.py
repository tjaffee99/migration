"""Inline the app, data and geometry into self-contained HTML pages.

Inputs:  web/src/{index.html,app.css,app.js}, web/data/data.json, web/geo/*.json
Outputs: docs/index.html            full standalone page (GitHub Pages / open locally)
         <fragment path> (optional) the same page without <html>/<head>/<body>, for hosts
                                    that wrap the page in their own document skeleton

Usage: python3 -I scripts/build/build_site.py [--fragment PATH]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "web" / "src"
GEO = ROOT / "web" / "geo"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def geo_bundle():
    us = load(GEO / "us_historical.topo.json")
    years = load(GEO / "us_historical_years.json")
    nation = load(GEO / "us_nation.topo.json")
    world = load(GEO / "world.topo.json")
    geoms = us["objects"]["jurisdictions"]["geometries"]
    index = {g["properties"]["id"]: i for i, g in enumerate(geoms)}
    us_years = {}
    for y, ids in years.items():
        us_years[y] = [index[i] for i in ids if i in index]
    return {"us": us, "usYears": us_years, "nation": nation, "world": world}


def compact_json(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", help="also write a skeleton-free page to this path")
    args = ap.parse_args()

    html = (SRC / "index.html").read_text(encoding="utf-8")
    css = (SRC / "app.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")
    data = load(ROOT / "web" / "data" / "data.json")
    geo = geo_bundle()

    data_tag = (
        "<script>window.__DATA__=" + compact_json(data) + ";\n"
        "window.__GEO__=" + compact_json(geo) + ";</script>"
    )
    body = (
        html.replace("<!--CSS-->", "<style>\n" + css + "\n</style>")
        .replace("<!--DATA-->", data_tag)
        .replace("<!--JS-->", "<script>\n" + js + "\n</script>")
    )

    # Full document: move the head-ish lines (title/meta/link/style) into <head>.
    lines = body.split("\n")
    head, rest, in_head = [], [], True
    for line in lines:
        s = line.strip()
        if in_head and (s.startswith(("<title", "<meta", "<link")) or s == ""):
            head.append(line)
            continue
        in_head = False
        rest.append(line)
    full = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        + "\n".join(head)
        + "\n<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
        "body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n"
        "</head>\n<body>\n" + "\n".join(rest) + "\n</body>\n</html>\n"
    )
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(full, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.2f} MB)")
    if args.fragment:
        fp = Path(args.fragment)
        fp.write_text(body, encoding="utf-8")
        print(f"wrote {fp} ({fp.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
