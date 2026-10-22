"""Render stored case only, using verified atomic figure writes; no replay."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import uuid

os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_joint_case_mpl")
from PIL import Image
from matplotlib.figure import Figure

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
ROOT = STUDY.parents[2]
ADAPTER = ROOT / "research/workers/personnel_global_composition_20261021/evidence/render_evidence.py"
ORIGINAL_SAVEFIG = Figure.savefig


def atomic_savefig(self, filename, *args, **kwargs):
    if not isinstance(filename, (str, Path)):
        return ORIGINAL_SAVEFIG(self, filename, *args, **kwargs)
    path = Path(filename)
    fmt = kwargs.pop("format", None) or path.suffix.lstrip(".")
    buffer = io.BytesIO()
    ORIGINAL_SAVEFIG(self, buffer, *args, format=fmt, **kwargs)
    data = buffer.getvalue()
    if fmt.lower() == "png":
        with Image.open(io.BytesIO(data)) as image:
            image.load()
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".writing")
    with temporary.open("wb") as stream:
        assert stream.write(data) == len(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    actual = path.read_bytes()
    assert len(actual) == len(data) and hashlib.sha256(actual).digest() == hashlib.sha256(data).digest()
    if fmt.lower() == "png":
        with Image.open(path) as image:
            image.load()


def main():
    Figure.savefig = atomic_savefig
    spec = importlib.util.spec_from_file_location("frozen_evidence_renderer", ADAPTER)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    sys.argv = [str(ADAPTER), "--case", str(HERE / "case.json.gz"), "--photos", str(STUDY / "mechanisms/originals"), "--out", str(HERE / "figures")]
    adapter.main()
    images=[]
    for path in sorted((HERE / "figures").glob("*.png")):
        with Image.open(path) as image:
            image.load()
            images.append(dict(path=path.name,bytes=path.stat().st_size,dimensions=list(image.size),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),decoded_completely=True))
    (HERE / "figures/PNG_WRITE_VERIFICATION.json").write_text(json.dumps(dict(images=images, metadata_replays=0,score_calls=0,atomic_bytesio_write=True),ensure_ascii=False,indent=2),encoding="utf8")


if __name__ == "__main__":
    main()
