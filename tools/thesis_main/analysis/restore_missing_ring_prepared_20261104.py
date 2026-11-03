"""Verify and restore the sharded prepared cache for the 2026-11-04 review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "research/fusion/missing_ring_review_20261104"
ARCHIVE = PACKAGE / "prepared_shards"


def verify(archive: Path = ARCHIVE) -> dict:
    manifest = json.loads((archive / "PREPARED_SHARDS_MANIFEST.json").read_text(encoding="utf-8"))
    files = 0
    size = 0
    for part in manifest["parts"]:
        path = archive / part["file"]
        if path.parent != archive or path.stat().st_size != part["bytes"]:
            raise ValueError(f"分片路径或大小不匹配: {part['file']}")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != part["sha256"]:
            raise ValueError(f"分片 SHA-256 不匹配: {part['file']}")
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if len(names) != part["files"] or zf.testzip() is not None:
                raise ValueError(f"ZIP 条目数或 CRC 校验失败: {part['file']}")
            if len(names) != len(set(names)) or any(
                PurePosixPath(name).name != name or not name.endswith(".json.gz") for name in names
            ):
                raise ValueError(f"ZIP 含非法或重复条目: {part['file']}")
            part_size = sum(info.file_size for info in zf.infolist())
            if part_size != part["content_bytes"]:
                raise ValueError(f"ZIP 内容大小不匹配: {part['file']}")
            files += len(names)
            size += part_size
    if files != manifest["total_files"] or size != manifest["total_content_bytes"]:
        raise ValueError("分片总文件数或总内容大小不匹配")
    return {"files": files, "content_bytes": size, "parts": len(manifest["parts"])}


def restore(destination: Path, archive: Path = ARCHIVE) -> dict:
    verified = verify(archive)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"目标目录已存在，不覆盖: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    try:
        for part in json.loads((archive / "PREPARED_SHARDS_MANIFEST.json").read_text(encoding="utf-8"))["parts"]:
            with zipfile.ZipFile(archive / part["file"]) as zf:
                for info in zf.infolist():
                    output = destination / info.filename
                    with zf.open(info) as source, output.open("xb") as target:
                        while chunk := source.read(1024 * 1024):
                            target.write(chunk)
        if sum(1 for _ in destination.iterdir()) != verified["files"]:
            raise ValueError("恢复后的文件数不匹配")
    except Exception:
        for path in destination.iterdir():
            path.unlink()
        destination.rmdir()
        raise
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore-to", type=Path, help="恢复目录；不指定时只验证归档")
    args = parser.parse_args()
    result = restore(args.restore_to) if args.restore_to else verify()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
