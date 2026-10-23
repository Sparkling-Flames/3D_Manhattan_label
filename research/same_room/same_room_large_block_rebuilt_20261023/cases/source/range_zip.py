#!/usr/bin/env python3
"""Inspect/download selected public GitHub Release ZIP members using HTTP Range.

Only Python's standard library is required. This tool never downloads a full ZIP
as fallback. Non-206 responses to a ZIP Range request are closed without reading
their response body. Selected extraction validates ZIP CRC and indexed SHA-256
when the release index supplies one.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import pathlib
import struct
import urllib.parse
import urllib.request
import zlib


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    pathlib.Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_url(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def fetch(url, size, log, byte_range=None):
    headers = {"User-Agent": "personnel-composition-image-inspection/1.0", "Accept-Encoding": "identity"}
    if byte_range:
        start, end = byte_range
        headers["Range"] = f"bytes={start}-{end}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        record = {
            "url": safe_url(url), "final_url": safe_url(response.url), "status": response.status,
            "requested_range": headers.get("Range"),
            "headers": {k: response.headers.get(k) for k in (
                "Content-Length", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified", "Content-Type"
            )},
        }
        log.append(record)
        if byte_range:
            if response.status != 206:
                raise RuntimeError(f"Range unsupported: HTTP {response.status}; ZIP body was not read")
            expected_range = f"bytes {start}-{end}/{size}"
            if response.headers.get("Content-Range") != expected_range:
                raise RuntimeError(f"Unexpected Content-Range: {response.headers.get('Content-Range')!r}")
            expected = end - start + 1
        else:
            expected = size
        data = response.read(expected + 1)
        record["body_bytes_read"] = len(data)
        if len(data) != expected:
            raise RuntimeError(f"Unexpected body size {len(data)} != {expected}")
        return data


def remote_directory(asset, log):
    total = asset["size"]
    start = max(0, total - 65557)
    tail = fetch(asset["browser_download_url"], total, log, (start, total - 1))
    eocd_at = tail.rfind(b"PK\x05\x06")
    if eocd_at < 0 or len(tail) - eocd_at < 22:
        raise RuntimeError("ZIP end-of-central-directory not found")
    _, disk, cd_disk, disk_entries, entries, cd_size, cd_offset, comment_len = struct.unpack_from("<4sHHHHIIH", tail, eocd_at)
    if disk or cd_disk or disk_entries != entries:
        raise RuntimeError("Split ZIPs are unsupported")
    if entries == 65535 or cd_size == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF:
        raise RuntimeError("ZIP64 is unsupported by this lightweight extractor")
    if eocd_at + 22 + comment_len != len(tail):
        raise RuntimeError("EOCD comment length does not end at asset boundary")
    if cd_offset >= start and cd_offset + cd_size <= total:
        directory = tail[cd_offset - start:cd_offset - start + cd_size]
    else:
        directory = fetch(asset["browser_download_url"], total, log, (cd_offset, cd_offset + cd_size - 1))
    result = []
    pos = 0
    for _ in range(entries):
        fields = struct.unpack_from("<4sHHHHHHIIIHHHHHII", directory, pos)
        sig, _, _, flags, method, _, _, crc, csize, usize, nlen, elen, clen, dstart, _, _, offset = fields
        if sig != b"PK\x01\x02" or dstart:
            raise RuntimeError("Invalid central directory entry")
        raw_name = directory[pos + 46:pos + 46 + nlen]
        name = raw_name.decode("utf-8" if flags & 0x800 else "cp437")
        result.append({
            "archive": asset["name"], "archive_path": name,
            "compression_type": method, "flags": flags, "crc32": f"{crc:08x}",
            "compressed_size": csize, "uncompressed_size": usize, "local_header_offset": offset,
        })
        pos += 46 + nlen + elen + clen
    if pos != cd_size:
        raise RuntimeError(f"Central directory trailing data: parsed {pos} of {cd_size}")
    internal_manifest = None
    for member in result:
        if member["archive_path"] != "MANIFEST.json":
            continue
        local = member["local_header_offset"] - start
        if local < 0 or local + 30 > len(tail):
            continue
        local_fields = struct.unpack_from("<4sHHHHHIIIHH", tail, local)
        if local_fields[0] != b"PK\x03\x04":
            raise RuntimeError("Internal manifest local header missing")
        payload_at = local + 30 + local_fields[-2] + local_fields[-1]
        payload_end = payload_at + member["compressed_size"]
        if payload_end > len(tail):
            continue
        payload = tail[payload_at:payload_end]
        if member["compression_type"] == 8:
            payload = zlib.decompress(payload, -15)
        elif member["compression_type"] != 0:
            continue
        if len(payload) != member["uncompressed_size"] or f"{zlib.crc32(payload):08x}" != member["crc32"]:
            raise RuntimeError("Internal manifest CRC mismatch")
        internal_manifest = json.loads(payload.decode("utf-8-sig"))
    return {"archive": asset["name"], "archive_size": total, "entries": entries,
            "central_directory_size": cd_size, "central_directory_offset": cd_offset,
            "members": result, "internal_manifest": internal_manifest}


def inspect(meta, out):
    log = []
    index = []
    try:
        for asset in meta["assets"]:
            if asset["name"] in ("IMAGE_INDEX.csv", "MANIFEST.json"):
                payload = fetch(asset["browser_download_url"], asset["size"], log)
                expected = asset.get("digest", "")
                if expected and "sha256:" + hashlib.sha256(payload).hexdigest() != expected:
                    raise RuntimeError(f"Asset SHA mismatch: {asset['name']}")
                (out / ("release_" + asset["name"])).write_bytes(payload)
                print(json.dumps({"downloaded": asset["name"], "bytes": len(payload), "sha256_verified": bool(expected)}), flush=True)
            elif asset["name"].endswith(".zip"):
                directory = remote_directory(asset, log)
                internal_manifest = directory.pop("internal_manifest")
                if internal_manifest is not None:
                    write_json(out / (asset["name"].removesuffix(".zip") + "_MANIFEST.json"), internal_manifest)
                index.append(directory)
                print(json.dumps({k: v for k, v in directory.items() if k != "members"}), flush=True)
        write_json(out / "zip_directories.json", index)
    finally:
        write_json(out / "http_inspection.json", log)


def extract(meta, directory_path, index_path, image_ids, out):
    assets = {a["name"]: a for a in meta["assets"]}
    members = {(d["archive"], m["archive_path"]): m for d in read_json(directory_path) for m in d["members"]}
    with open(index_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    lookup = {r["image_id"]: r for r in rows}
    lookup.update({r["image_code"]: r for r in rows if r.get("image_code")})
    log = []
    results = []
    try:
        for image_id in image_ids:
            row = lookup[image_id]
            key = (row["archive"], row["archive_path"])
            member = members[key]
            asset = assets[row["archive"]]
            offset = member["local_header_offset"]
            header = fetch(asset["browser_download_url"], asset["size"], log, (offset, offset + 29))
            sig, _, flags, method, _, _, _, _, _, nlen, elen = struct.unpack("<4sHHHHHIIIHH", header)
            if sig != b"PK\x03\x04" or flags & 1 or method != member["compression_type"]:
                raise RuntimeError("Invalid/encrypted local file header")
            end_header = offset + 30 + nlen + elen
            encoded_name = fetch(asset["browser_download_url"], asset["size"], log, (offset + 30, offset + 30 + nlen - 1))
            name = encoded_name.decode("utf-8" if flags & 0x800 else "cp437")
            if name != row["archive_path"]:
                raise RuntimeError("Local and central member names differ")
            csize = member["compressed_size"]
            compressed = fetch(asset["browser_download_url"], asset["size"], log, (end_header, end_header + csize - 1))
            if method == 0:
                payload = compressed
            elif method == 8:
                payload = zlib.decompress(compressed, -15)
            else:
                raise RuntimeError(f"Unsupported compression method: {method}")
            if len(payload) != member["uncompressed_size"] or f"{zlib.crc32(payload):08x}" != member["crc32"]:
                raise RuntimeError("Decompressed member size or CRC mismatch")
            if row.get("bytes") and len(payload) != int(row["bytes"]):
                raise RuntimeError("Release index and extracted member size differ")
            png_dimensions = None
            if payload.startswith(b"\x89PNG\r\n\x1a\n"):
                png_dimensions = struct.unpack_from(">II", payload, 16)
                if row.get("width") and row.get("height") and png_dimensions != (int(row["width"]), int(row["height"])):
                    raise RuntimeError("Release index and PNG dimensions differ")
            sha = hashlib.sha256(payload).hexdigest()
            expected_sha = row.get("sha256", "").removeprefix("sha256:")
            if expected_sha and sha != expected_sha:
                raise RuntimeError("Indexed member SHA-256 mismatch")
            filename = pathlib.PurePosixPath(name).name
            target = out / filename
            target.write_bytes(payload)
            result = {"image_id": row["image_id"], "image_code": row.get("image_code"),
                      "archive": row["archive"], "archive_path": name, "file": str(target),
                      "bytes": len(payload), "crc32": member["crc32"], "sha256": sha,
                      "indexed_sha256_verified": bool(expected_sha), "png_dimensions": png_dimensions}
            results.append(result)
            print(json.dumps(result), flush=True)
        write_json(out / "extraction_manifest.json", results)
    finally:
        write_json(out / "http_extraction.json", log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "extract"))
    parser.add_argument("--metadata", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--directories", type=pathlib.Path)
    parser.add_argument("--index", type=pathlib.Path)
    parser.add_argument("--image-id", action="append", default=[])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    meta = read_json(args.metadata)
    if args.mode == "inspect":
        inspect(meta, args.out)
    else:
        if not args.directories or not args.index or not args.image_id:
            parser.error("extract requires --directories, --index, and at least one --image-id")
        extract(meta, args.directories, args.index, args.image_id, args.out)


if __name__ == "__main__":
    main()
