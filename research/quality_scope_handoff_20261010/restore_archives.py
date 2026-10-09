"""Restore original evidence archives and verify every SHA256. Python 3, standard library only."""
from pathlib import Path
import hashlib
import json

def restore(root=None):
    root = Path(root) if root else Path(__file__).resolve().parent
    manifest = json.loads((root / "archive_manifest.json").read_text(encoding="utf-8"))
    for archive in manifest:
        blocks = []
        for part in archive["parts"]:
            data = (root / part["file"]).read_bytes()
            if len(data) != part["bytes"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError("Invalid part: " + part["file"])
            blocks.append(data)
        data = b"".join(blocks)
        if len(data) != archive["bytes"] or hashlib.sha256(data).hexdigest() != archive["sha256"]:
            raise ValueError("Invalid archive: " + archive["file"])
        target = root / archive["file"]
        target.write_bytes(data)
        print("Verified:", target.name)
if __name__ == "__main__":
    restore()
