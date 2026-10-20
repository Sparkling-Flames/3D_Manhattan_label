"""Losslessly restore the two split gzip research tables and verify every hash."""
from pathlib import Path
import argparse
import hashlib
import json


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = args.repo_root.resolve() if args.repo_root else here.parents[4]
    index = json.loads((here / "LARGE_TABLES.json").read_text())
    results = []
    for entry in index["tables"]:
        target = root / entry["target_path"]
        if target.exists():
            if target.stat().st_size != entry["target_bytes"] or digest(target) != entry["target_sha256"]:
                raise RuntimeError(f"Existing target differs; refusing to overwrite: {target}")
            results.append({"path": entry["target_path"], "status": "already_verified"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".reconstruction.tmp")
        with temporary.open("xb") as out:
            whole = hashlib.sha256()
            size = 0
            for part in entry["parts"]:
                source = root / part["path"]
                if source.stat().st_size != part["bytes"] or digest(source) != part["sha256"]:
                    raise RuntimeError(f"Part size/hash mismatch: {source}; temporary output retained.")
                with source.open("rb") as src:
                    for chunk in iter(lambda: src.read(4 * 1024 * 1024), b""):
                        out.write(chunk)
                        whole.update(chunk)
                        size += len(chunk)
        if size != entry["target_bytes"] or whole.hexdigest() != entry["target_sha256"]:
            raise RuntimeError(f"Final size/hash mismatch: {temporary}; temporary output retained.")
        temporary.replace(target)
        results.append({"path": entry["target_path"], "status": "restored_and_verified",
                        "bytes": size, "sha256": whole.hexdigest()})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
