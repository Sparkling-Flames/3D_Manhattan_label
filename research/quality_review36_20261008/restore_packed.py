#!/usr/bin/env python3
"""Restore exact archived bytes from small gzip+base64 chunks (stdlib only).
Run from any working directory. No network or image downloads are performed.
Existing different output files are preserved and cause an error.
"""
from pathlib import Path, PurePosixPath
import base64
import gzip
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parent


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ("..", ".") for p in path.parts):
        raise ValueError("Unsafe archive path: " + name)
    resolved = (ROOT / path).resolve()
    if ROOT not in resolved.parents:
        raise ValueError("Archive path escapes root: " + name)
    return resolved


def check(data, entry):
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Size/SHA-256 mismatch: " + entry["path"])


def main():
    manifest = json.loads((ROOT / "packed/manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "review36-packed-v1" or manifest["encoding"] != "gzip+base64":
        raise ValueError("Unsupported packed format")
    ready = []
    seen = set()
    for entry in manifest["files"]:
        target = safe_path(entry["path"])
        if target in seen:
            raise ValueError("Duplicate output path")
        seen.add(target)
        chunks = []
        for part in entry["parts"]:
            data = safe_path(part["path"]).read_bytes()
            check(data, part)
            if len(data) > manifest["chunk_max_bytes"]:
                raise ValueError("Oversized chunk")
            chunks.append(data)
        encoded = b"".join(chunks)
        if len(encoded) != entry["encoded_bytes"]:
            raise ValueError("Encoded size mismatch")
        compressed = base64.b64decode(encoded, validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            data = stream.read(entry["bytes"] + 1)
        check(data, entry)
        if target.exists():
            check(target.read_bytes(), entry)
        ready.append((target, data, entry))
    # Validate every payload and existing output before writing any output.
    for target, data, entry in ready:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(data)
    print(json.dumps({"passed": True, "files_verified": len(ready),
                      "bytes_verified": sum(e["bytes"] for _, _, e in ready),
                      "restored_paths": [e["path"] for _, _, e in ready]}, indent=2))


if __name__ == "__main__":
    main()
