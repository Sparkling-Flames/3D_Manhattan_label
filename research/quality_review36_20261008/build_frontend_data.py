#!/usr/bin/env python3
"""Rebuild review-36 browser data from the public frozen geometry.

No network access, metric recomputation, coordinate changes, or image downloads.
Optional --image-dir copies only the six hash-matching original PNG files.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

ROOT = Path(__file__).resolve().parent


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def build(geometry: dict) -> dict:
    images = geometry["images"]
    annotations = [record for image in images for record in image["annotations"]]
    references = [record for image in images for record in image["groundtruths"]]
    if len(images) != 6 or any(len(image["annotations"]) != 6 for image in images):
        raise ValueError("Expected six images with six annotations each")
    if len(annotations) != 36 or len(references) != 8:
        raise ValueError("Expected 36 annotations and eight versioned references")
    if len({record["id"] for record in annotations}) != 36:
        raise ValueError("Annotation IDs must be unique")
    if [record["reviewId"] for record in annotations] != [f"Q{i:02}" for i in range(1, 37)]:
        raise ValueError("Unexpected frozen review order")
    if any(record.get("userRating") is not None for record in annotations):
        raise ValueError("The initial data must not contain human scores")
    for image in images:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", image["code"]):
            raise ValueError("Unsafe image code")
        original = [r for r in image["groundtruths"] if r["version"] == "original"]
        if len(original) != 1 or image["defaultReferenceId"] != original[0]["id"]:
            raise ValueError("Original-reference binding mismatch")
        if image["defaultReferenceVersion"] != "original":
            raise ValueError("Initial reference must be original")
    fingerprint_payload = {"images": [
        {"code": image["code"], "imageSha256": image["imageSha256"],
         "annotations": [{"reviewId": r["reviewId"], "id": r["id"], "points": r["points"]}
                         for r in image["annotations"]],
         "groundtruths": [{"id": r["id"], "version": r["version"], "points": r["points"]}
                          for r in image["groundtruths"]]}
        for image in images]}
    if sha256(compact(fingerprint_payload)) != geometry["datasetFingerprintSha256"]:
        raise ValueError("Frozen geometry fingerprint mismatch")
    output = {
        "schema": "quality_review36_public_frontend_v1",
        "sourceInfo": {
            "dataset": "data/frozen_geometry.json",
            "referenceVersion": "original",
            "scales": copy.deepcopy(geometry["scales"]),
            "formulas": copy.deepcopy(geometry["formulas"]),
            "geometry": copy.deepcopy(geometry["geometryContract"]),
            "limitations": copy.deepcopy(geometry["limitations"]),
        },
        "selection36": {
            "recordCount": 36,
            "recordsPerImage": 6,
            "imageCount": 6,
            "reviewIds": [r["reviewId"] for r in annotations],
            "datasetId": geometry["datasetId"],
            "datasetFingerprintSha256": geometry["datasetFingerprintSha256"],
            "ratingsStartEmpty": True,
        },
        "images": copy.deepcopy(images),
    }
    for image in output["images"]:
        image["label"] = image["code"]
        image["imageFile"] = "images/" + image["code"] + ".png"
        image["reference"] = "original"
    return output


def validate_images(images: list[dict], image_dir: Path) -> list[tuple[Path, str]]:
    verified = []
    for image in images:
        name = image["code"] + ".png"
        source = image_dir / name
        data = source.read_bytes()
        if sha256(data) != image["imageSha256"]:
            raise ValueError(f"Original PNG hash mismatch: {name}")
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Not a PNG: {name}")
        if tuple(struct.unpack(">II", data[16:24])) != tuple(image["imageSize"]):
            raise ValueError(f"Original PNG size mismatch: {name}")
        verified.append((source, name))
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, default=ROOT / "data/frozen_geometry.json")
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/data36.js")
    parser.add_argument("--image-dir", type=Path,
                        help="Existing directory of authorized originals; copy only six verified PNGs")
    args = parser.parse_args()
    geometry = json.loads(args.geometry.read_text(encoding="utf-8"))
    data = build(geometry)
    # Verify all requested images before writing anything or copying any image.
    verified = validate_images(data["images"], args.image_dir) if args.image_dir else []
    js = b"window.REVIEW36_DATA = " + compact(data) + b";\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_bytes(js)
    temporary.replace(args.output)
    if verified:
        target = args.output.parent / "images"
        target.mkdir(exist_ok=True)
        for source, name in verified:
            destination = target / name
            if source.resolve() != destination.resolve():
                shutil.copyfile(source, destination)
    print(json.dumps({
        "generated_file": args.output.name,
        "generated_sha256": sha256(js),
        "datasetFingerprintSha256": data["selection36"]["datasetFingerprintSha256"],
        "annotations": 36,
        "references": 8,
        "images_copied": [name for _, name in verified],
        "network_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
