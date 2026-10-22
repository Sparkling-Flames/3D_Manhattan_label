"""恢复两份按原 gzip 字节分块保存的大事件表；已有完整文件不覆盖。"""
import json
from pathlib import Path
import shutil


def main(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    manifest = json.loads((root / "LARGE_TABLE_STORAGE.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        target = root / item["path"]
        if target.exists():
            assert target.stat().st_size == item["bytes"], f"已有表大小不符：{target}"
            continue
        parts = [root / entry["path"] for entry in item["parts"]]
        assert all(p.stat().st_size == entry["bytes"] for p, entry in zip(parts, item["parts"]))
        temporary = target.with_name(target.name + ".restoring")
        with temporary.open("wb") as out:
            for part in parts:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, out)
        assert temporary.stat().st_size == item["bytes"]
        temporary.replace(target)
        print("已恢复", item["path"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='含 LARGE_TABLE_STORAGE.json 的研究包目录')
    main(parser.parse_args().root)
