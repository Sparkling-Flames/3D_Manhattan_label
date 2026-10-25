"""Restore only the exact frozen runtime files, without cloning the repository."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent


def restore(row, manifest, verify_only):
    target = HERE / "frozen_repo" / row["path"]
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == row["sha256"]:
        return "already_valid"
    if verify_only:
        raise ValueError("Missing or changed frozen source: " + row["path"])
    url = f"https://raw.githubusercontent.com/{manifest['repository']}/{manifest['commit']}/{row['path']}"
    with urllib.request.urlopen(url, timeout=90) as response:
        body = response.read()
    if len(body) != row["bytes"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
        raise ValueError("Downloaded input differs: " + row["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(target)
    return "restored"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE / "RUNTIME_SOURCE_MANIFEST.json").read_text())
    with ThreadPoolExecutor(max_workers=6) as executor:
        result = list(executor.map(lambda r: restore(r, manifest, args.verify_only), manifest["files"]))
    print(json.dumps(dict(files=len(result), restored=result.count("restored"),
                         already_valid=result.count("already_valid"), commit=manifest["commit"])))


if __name__ == "__main__":
    main()
