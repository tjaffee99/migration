#!/usr/bin/env python3
"""Minimal WARC extractor (no external deps).

Usage: python3 -I warc_extract.py <file.warc.gz> <out_dir> [--list]

Writes the HTTP response body of each `response` record whose content type
looks like a PDF / HTML / spreadsheet into <out_dir>, named after the target
URI basename.  Handles chunked transfer-encoding and gzip content-encoding.
"""
import gzip
import os
import re
import sys
import zlib


def iter_records(path):
    with gzip.open(path, "rb") as fh:
        data = fh.read()
    pos = 0
    n = len(data)
    while pos < n:
        m = data.find(b"WARC/1.", pos)
        if m < 0:
            break
        hdr_end = data.find(b"\r\n\r\n", m)
        if hdr_end < 0:
            break
        hdr = data[m:hdr_end].decode("latin-1")
        headers = {}
        for line in hdr.split("\r\n")[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        clen = int(headers.get("content-length", "0"))
        block = data[hdr_end + 4: hdr_end + 4 + clen]
        pos = hdr_end + 4 + clen
        yield headers, block


def dechunk(body):
    out = bytearray()
    pos = 0
    while True:
        e = body.find(b"\r\n", pos)
        if e < 0:
            break
        size_s = body[pos:e].split(b";")[0].strip()
        try:
            size = int(size_s, 16)
        except ValueError:
            return bytes(body)  # not actually chunked
        if size == 0:
            break
        out += body[e + 2: e + 2 + size]
        pos = e + 2 + size + 2
    return bytes(out)


def parse_http(block):
    he = block.find(b"\r\n\r\n")
    if he < 0:
        return {}, block, ""
    head = block[:he].decode("latin-1")
    body = block[he + 4:]
    lines = head.split("\r\n")
    status = lines[0]
    h = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip().lower()] = v.strip()
    if "chunked" in h.get("transfer-encoding", "").lower():
        body = dechunk(body)
    ce = h.get("content-encoding", "").lower()
    if ce == "gzip":
        try:
            body = gzip.decompress(body)
        except Exception:
            pass
    elif ce == "deflate":
        try:
            body = zlib.decompress(body)
        except Exception:
            pass
    return h, body, status


def main():
    path, out_dir = sys.argv[1], sys.argv[2]
    list_only = "--list" in sys.argv
    os.makedirs(out_dir, exist_ok=True)
    for headers, block in iter_records(path):
        if headers.get("warc-type") != "response":
            continue
        uri = headers.get("warc-target-uri", "")
        h, body, status = parse_http(block)
        ctype = h.get("content-type", "")
        print(f"{status[:15]:15s} {len(body):>10d} {ctype[:40]:40s} {uri}")
        if list_only:
            continue
        keep = any(t in ctype for t in ("pdf", "html", "spreadsheet", "excel", "csv"))
        if not keep or not status.split(" ")[1:2] == ["200"]:
            continue
        if "dhs.gov" not in uri:
            continue
        base = re.sub(r"[^A-Za-z0-9._-]", "_", uri.split("?")[0].rstrip("/").split("/")[-1]) or "index"
        if "html" in ctype and not base.endswith(".html"):
            base += ".html"
        with open(os.path.join(out_dir, base), "wb") as fo:
            fo.write(body)


if __name__ == "__main__":
    main()
