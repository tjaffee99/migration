#!/usr/bin/env python3
"""Pull single pages out of a Perma.cc WARC (archive.org item perma_cc_<ID>/<ID>.warc.gz).

Usage:
  python3 -I warc_pages.py <file.warc.gz> --list
  python3 -I warc_pages.py <file.warc.gz> <url-substring> <out-file> [--text] [--pylib DIR]

Writes the HTTP body of the first 200 response whose target URI contains <url-substring>.
With --text, HTML is reduced to plain text (tables as ' | '-separated cells), which is what we
keep in data/raw/ as a small, reviewable page extract.
No external dependencies; the WARC is untrusted input and is only parsed, never executed.
"""
import gzip
import html
import re
import sys
import zlib


def records(path):
    with gzip.open(path, "rb") as fh:
        data = fh.read()
    pos, n = 0, len(data)
    while pos < n:
        m = data.find(b"WARC/1.", pos)
        if m < 0:
            return
        he = data.find(b"\r\n\r\n", m)
        if he < 0:
            return
        hdr = {}
        for line in data[m:he].decode("latin-1").split("\r\n")[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                hdr[k.strip().lower()] = v.strip()
        clen = int(hdr.get("content-length", "0"))
        yield hdr, data[he + 4: he + 4 + clen]
        pos = he + 4 + clen


def dechunk(body):
    out, pos = bytearray(), 0
    while True:
        e = body.find(b"\r\n", pos)
        if e < 0:
            break
        try:
            size = int(body[pos:e].split(b";")[0].strip(), 16)
        except ValueError:
            return bytes(body)
        if size == 0:
            break
        out += body[e + 2: e + 2 + size]
        pos = e + 2 + size + 2
    return bytes(out)


def http_body(block):
    he = block.find(b"\r\n\r\n")
    if he < 0:
        return "", {}, block
    lines = block[:he].decode("latin-1").split("\r\n")
    h = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip().lower()] = v.strip()
    body = block[he + 4:]
    if "chunked" in h.get("transfer-encoding", "").lower():
        body = dechunk(body)
    ce = h.get("content-encoding", "").lower()
    try:
        if ce == "gzip":
            body = gzip.decompress(body)
        elif ce == "deflate":
            body = zlib.decompress(body)
        elif ce == "br":
            body = _brotli().decompress(body)
    except Exception:
        pass
    return lines[0], h, body


def _brotli():
    """Brotli is not in the standard library: pass --pylib DIR (a folder with `pip install --target DIR brotli`)."""
    if "--pylib" in sys.argv:
        sys.path.append(sys.argv[sys.argv.index("--pylib") + 1])
    import brotli  # noqa: E402
    return brotli


def html_to_text(raw):
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<(br|p|tr|div|h\d|li|table|section|article)\b[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"</t[dh]>", " | ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip() + "\n"


def main():
    path = sys.argv[1]
    if "--list" in sys.argv:
        for hdr, block in records(path):
            if hdr.get("warc-type") == "response":
                status, h, body = http_body(block)
                print(f"{status[:15]:15s} {len(body):>9d} {h.get('content-type','')[:35]:35s} {hdr.get('warc-target-uri','')}")
        return
    sub, out = sys.argv[2], sys.argv[3]
    for hdr, block in records(path):
        if hdr.get("warc-type") != "response" or sub not in hdr.get("warc-target-uri", ""):
            continue
        status, h, body = http_body(block)
        if " 200" not in status:
            continue
        with open(out, "wb") as fo:
            fo.write(html_to_text(body).encode("utf-8") if "--text" in sys.argv else body)
        print(f"wrote {out} from {hdr.get('warc-target-uri')} ({hdr.get('warc-date')})")
        return
    sys.exit(f"no 200 response matching {sub!r}")


if __name__ == "__main__":
    main()
