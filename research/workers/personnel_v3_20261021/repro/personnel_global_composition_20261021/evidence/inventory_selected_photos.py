#!/usr/bin/env python3
"""Inventory locally retrieved selected photos against the frozen Release index.

This does not download or edit images. Per-call HTTP receipts remain separate;
the inventory joins all selected photos and checks original member CRC/length.
"""
import csv
import hashlib
import json
import struct
import zlib
from pathlib import Path
from fetch_selected_photos import HERE,ROOT,SOURCES


def main():
    meta=json.loads((SOURCES/"release_metadata.json").read_text())
    member={(d["archive"],m["archive_path"]):m for d in json.loads((SOURCES/"zip_directories.json").read_text()) for m in d["members"]}
    with (SOURCES/"release_IMAGE_INDEX.csv").open(encoding="utf-8-sig") as f:index={r["image_id"]:r for r in csv.DictReader(f)}
    rows=[]
    for path in sorted((HERE/"originals").glob("*.png")):
        r=index[path.stem];m=member[r["archive"],r["archive_path"]];data=path.read_bytes()
        crc=f"{zlib.crc32(data):08x}";sha=hashlib.sha256(data).hexdigest()
        assert len(data)==m["uncompressed_size"] and crc==m["crc32"]
        assert not r.get("bytes") or len(data)==int(r["bytes"])
        dims=struct.unpack_from(">II",data,16)
        assert dims==(int(r["width"]),int(r["height"]))
        expected=r.get("sha256","").removeprefix("sha256:")
        assert not expected or sha==expected
        rows.append(dict(image_id=path.stem,image_code=r["image_code"],file=str(path.relative_to(ROOT)),
                         archive=r["archive"],archive_path=r["archive_path"],bytes=len(data),crc32=crc,sha256=sha,
                         dimensions=dims,indexed_sha256_verified=bool(expected)))
    receipt=dict(schema="selected_release_photo_inventory_v1",release_tag=meta["tag_name"],release_url=meta["html_url"],
                 index_sha256=hashlib.sha256((SOURCES/"release_IMAGE_INDEX.csv").read_bytes()).hexdigest(),
                 photos=rows,no_download_or_edit_in_this_step=True,
                 verification="Local bytes match frozen ZIP-member CRC, length and PNG dimensions; local SHA is not an independent publisher SHA unless indexed_sha256_verified")
    (HERE/"originals/PHOTO_INVENTORY.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"photos":len(rows),"image_codes":[r["image_code"] for r in rows]},ensure_ascii=False))


if __name__=="__main__":main()
