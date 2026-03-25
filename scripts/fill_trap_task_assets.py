import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRAP_ROOT = REPO_ROOT / "trap集"
IMPORT_JSON = REPO_ROOT / "import_json" / "label_studio_import_docker.json"
IMG_ROOT = REPO_ROOT / "data" / "mp3d_layout" / "test" / "img"
TXT_ROOT = REPO_ROOT / "data" / "mp3d_layout" / "test" / "label_cor"

TASK_ID_OFFSET = 458
MAX_IMPORT_INDEX = 259
TASK_DIR_RE = re.compile(r"^task(\d+)")


@dataclass
class FillResult:
    task_dir: Path
    task_id: int
    import_index: int
    base_name: str
    copied_png: bool
    copied_txt: bool
    skipped_reason: str = ""


def load_import_entries() -> list[dict]:
    with IMPORT_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_base_name(entry: dict) -> str:
    data = entry.get("data") or {}
    title = str(data.get("title") or "").strip()
    image = str(data.get("image") or "").strip()
    source = title or image
    if not source:
        raise ValueError("missing title/image in import entry")
    return Path(source).stem


def fill_task_dir(task_dir: Path, import_entries: list[dict]) -> FillResult:
    match = TASK_DIR_RE.match(task_dir.name)
    if not match:
        return FillResult(task_dir, -1, -1, "", False, False, "invalid_task_dir")

    task_id = int(match.group(1))
    import_index = task_id - TASK_ID_OFFSET
    if import_index < 1 or import_index > MAX_IMPORT_INDEX:
        return FillResult(task_dir, task_id, import_index, "", False, False, "out_of_supported_range")

    entry = import_entries[import_index - 1]
    base_name = get_base_name(entry)
    src_png = IMG_ROOT / f"{base_name}.png"
    src_txt = TXT_ROOT / f"{base_name}.txt"

    if not src_png.exists() and not src_txt.exists():
        return FillResult(task_dir, task_id, import_index, base_name, False, False, "missing_png_and_txt")
    if not src_png.exists():
        return FillResult(task_dir, task_id, import_index, base_name, False, False, "missing_png")
    if not src_txt.exists():
        return FillResult(task_dir, task_id, import_index, base_name, False, False, "missing_txt")

    dst_png = task_dir / src_png.name
    dst_txt = task_dir / src_txt.name

    copied_png = False
    copied_txt = False

    if not dst_png.exists():
        shutil.copy2(src_png, dst_png)
        copied_png = True

    if not dst_txt.exists():
        shutil.copy2(src_txt, dst_txt)
        copied_txt = True

    return FillResult(task_dir, task_id, import_index, base_name, copied_png, copied_txt)


def main() -> None:
    import_entries = load_import_entries()
    task_dirs = sorted(
        p for p in TRAP_ROOT.rglob("*") if p.is_dir() and TASK_DIR_RE.match(p.name)
    )

    results: list[FillResult] = [fill_task_dir(task_dir, import_entries) for task_dir in task_dirs]

    copied = [r for r in results if r.copied_png or r.copied_txt]
    skipped = [r for r in results if r.skipped_reason]

    print(f"task_dirs={len(task_dirs)}")
    print(f"copied={len(copied)}")
    print(f"skipped={len(skipped)}")

    if copied:
        print("copied_details:")
        for r in copied:
            print(
                f"- task{r.task_id} idx={r.import_index} base={r.base_name} "
                f"png={'Y' if r.copied_png else 'N'} txt={'Y' if r.copied_txt else 'N'} "
                f"path={r.task_dir}"
            )

    if skipped:
        print("skipped_details:")
        for r in skipped:
            print(
                f"- task{r.task_id} idx={r.import_index} reason={r.skipped_reason} path={r.task_dir}"
            )


if __name__ == "__main__":
    main()
