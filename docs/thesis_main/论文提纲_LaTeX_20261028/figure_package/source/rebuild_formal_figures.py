"""Rebuild the current formal figure assets without editing any LaTeX file."""
from pathlib import Path
import hashlib
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]
MANUSCRIPT = PACKAGE.parent


def tex_snapshot():
    return {p.relative_to(MANUSCRIPT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in MANUSCRIPT.rglob("*.tex")}


def main():
    before = tex_snapshot()
    steps = [
        ["source/panel_cleanup/build_panels.py"],
        ["source/fig04/build_fig04.py", "--package-root", "."],
        ["source/compact/build_compact_panels.py"],
        ["source/result_layout/build_results.py"],
        ["source/consensus_actual/build_fig06.py"],
        ["dot_fig07/build.py"],
        ["source/height_control_layout/build_fig05.py"],
        ["source/formal_typography/build_other_panels.py"],
        ["source/doorway_layout/build_fig15.py"],
        ["source/embed_base14_resources.py"],
    ]
    for step in steps:
        print("Running", " ".join(step), flush=True)
        subprocess.run([sys.executable, *step], cwd=PACKAGE, check=True)
    if tex_snapshot() != before:
        raise RuntimeError("A figure build modified a LaTeX file")
    print(f"Completed {len(steps)} figure-build steps; {len(before)} LaTeX files unchanged.")


if __name__ == "__main__":
    main()
