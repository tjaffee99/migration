#!/usr/bin/env python3
"""Lenient ZIP extractor for AHCB downloads.

Some Newberry AHCB zips (e.g. US_AtlasHCB_Counties_Gen01.zip) have ~19 KB of junk
between the last local file record and the central directory, so `unzip` refuses
them ("overlapped components / possible zip bomb"). This walks the *local* file
headers sequentially, inflates each member and verifies its CRC-32.

Usage: python3 -I unzip_lenient.py ARCHIVE.zip OUT_DIR
"""
import os
import struct
import sys
import zlib


def main(archive, out_dir):
    data = open(archive, "rb").read()
    off = 0
    n = 0
    out_root = os.path.realpath(out_dir)
    while data[off:off + 4] == b"PK\x03\x04":
        (_ver, flag, meth, _mt, _md, crc, csize, usize, fnlen, exlen) = struct.unpack(
            "<HHHHHIIIHH", data[off + 4:off + 30])
        if flag & 8:
            raise SystemExit("data-descriptor entries not supported")
        name = data[off + 30:off + 30 + fnlen].decode("cp437")
        start = off + 30 + fnlen + exlen
        payload = data[start:start + csize]
        off = start + csize
        dest = os.path.realpath(os.path.join(out_root, name))
        if not dest.startswith(out_root + os.sep):
            raise SystemExit(f"unsafe path in archive: {name!r}")
        if name.endswith("/"):
            os.makedirs(dest, exist_ok=True)
            continue
        if meth == 0:
            raw = payload
        elif meth == 8:
            raw = zlib.decompress(payload, -15)
        else:
            raise SystemExit(f"unsupported compression method {meth} for {name}")
        if len(raw) != usize or (zlib.crc32(raw) & 0xFFFFFFFF) != crc:
            raise SystemExit(f"CRC/size mismatch for {name}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(raw)
        n += 1
    print(f"extracted {n} files from {archive} -> {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
