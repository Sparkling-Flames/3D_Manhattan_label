"""Restore oversized v2.1 outputs from ordered, verified binary parts."""
from pathlib import Path
from contextlib import nullcontext
import hashlib
import json


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "LARGE_FILES.json"
CHUNK = 4 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def restore(root=None):
    root = Path(root).resolve() if root else HERE.parents[3]
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    results = []
    for entry in entries:
        target = root / entry["path"]
        temporary = target.with_name(target.name + ".restore.tmp")
        whole = hashlib.sha256()
        size = 0
        if target.exists():
            if target.stat().st_size != entry["bytes"] or digest(target) != entry["sha256"]:
                raise RuntimeError(f"Existing file differs; refusing to overwrite: {target}")
            check_only = True
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            check_only = False
        try:
            with (nullcontext(None) if check_only else temporary.open("xb")) as output:
                for part in entry["parts"]:
                    source = root / part["path"]
                    if source.stat().st_size != part["bytes"] or digest(source) != part["sha256"]:
                        raise RuntimeError(f"Part size/hash mismatch: {source}")
                    with source.open("rb") as stream:
                        for block in iter(lambda: stream.read(CHUNK), b""):
                            if output:
                                output.write(block)
                            whole.update(block)
                            size += len(block)
            if size != entry["bytes"] or whole.hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Reassembled file size/hash mismatch: {target}")
            if not check_only:
                temporary.replace(target)
            results.append({"path": entry["path"], "status": "verified" if check_only else "restored"})
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
    return results


if __name__ == "__main__":
    print(json.dumps(restore(), ensure_ascii=False, indent=2))
