"""Optional, bounded-size CSV.gz downloads of complete event tables.

Streaming, CSV-record-aware sharding.  It never splits a quoted CSV record,
never drops failure rows, preserves field strings/order, and verifies both the
whole record sequence and the event_id sequence against the complete source.
The independent complete source tables are retained unchanged.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULTS = {
    "manual_joint_A": ROOT / "manual_joint/EVENTS_COMPLETE.csv.gz",
    "manual_joint_B": ROOT / "manual_joint/phase_b_highq_slower/EVENTS_COMPLETE.csv.gz",
    "manual_structure": ROOT / "structure/EVENTS_COMPLETE.csv.gz",
}
FIELDS = ["theme", "part", "rows", "bytes", "sha256", "source_complete_table", "source_sha256",
          "row_start", "row_end", "columns", "row_sequence_sha256", "event_id_sequence_sha256"]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def encoded_record(row):
    return (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf8")


def save_json(path, value):
    tmp = path.with_name(path.name + ".writing")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    tmp.replace(path)


def save_manifest(path, rows):
    tmp = path.with_name(path.name + ".writing")
    with tmp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def write_piece(path, header, iterator, limit, event_column, source_hashes=None):
    rh, eh, count = hashlib.sha256(), hashlib.sha256(), 0
    with path.open("wb") as binary:
        with gzip.GzipFile(filename="", fileobj=binary, mode="wb", compresslevel=5, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8-sig", newline="") as text:
                writer = csv.writer(text)
                writer.writerow(header)
                for row in itertools.islice(iterator, limit):
                    assert len(row) == len(header), (path, len(row), len(header))
                    record = encoded_record(row)
                    eid = encoded_record([row[event_column]])
                    rh.update(record); eh.update(eid)
                    if source_hashes:
                        source_hashes[0].update(record); source_hashes[1].update(eid)
                    writer.writerow(row)
                    count += 1
    return dict(path=path, rows=count, row_sequence_sha256=rh.hexdigest(), event_id_sequence_sha256=eh.hexdigest())


def bounded_pieces(piece, header, event_column, maximum):
    if piece["path"].stat().st_size <= maximum:
        return [piece]
    assert piece["rows"] > 1, "A single CSV record exceeds the requested compressed size bound."
    sizes = [piece["rows"] // 2, piece["rows"] - piece["rows"] // 2]
    children = []
    with gzip.open(piece["path"], "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        assert next(reader) == header
        for idx, count in enumerate(sizes):
            child = piece["path"].with_name(piece["path"].stem + f"_split{idx}.csv.gz")
            written = write_piece(child, header, reader, count, event_column)
            assert written["rows"] == count
            children.extend(bounded_pieces(written, header, event_column, maximum))
        assert next(reader, None) is None
    piece["path"].unlink()
    return children


def verify_parts(folder, manifest, header, expected_rows, expected_rh, expected_eh, maximum):
    rh, eh, total = hashlib.sha256(), hashlib.sha256(), 0
    event_column = header.index("event_id")
    for entry in manifest:
        path = folder / entry["part"]
        assert path.stat().st_size == entry["bytes"] <= maximum
        assert digest(path) == entry["sha256"]
        local_rh, local_eh, count = hashlib.sha256(), hashlib.sha256(), 0
        assert entry["row_start"] == total + 1
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            assert next(reader) == header
            for row in reader:
                assert len(row) == len(header)
                rec, eid = encoded_record(row), encoded_record([row[event_column]])
                rh.update(rec); eh.update(eid); local_rh.update(rec); local_eh.update(eid)
                count += 1
        assert count == entry["rows"]
        assert local_rh.hexdigest() == entry["row_sequence_sha256"]
        assert local_eh.hexdigest() == entry["event_id_sequence_sha256"]
        total += count
        assert entry["row_end"] == total
    assert total == expected_rows
    assert rh.hexdigest() == expected_rh
    assert eh.hexdigest() == expected_eh
    return dict(rows=total, parts=len(manifest), row_sequence_sha256=rh.hexdigest(), event_id_sequence_sha256=eh.hexdigest(),
                source_and_parts_record_order_identical=True, source_and_parts_event_id_sequence_identical=True,
                every_header_identical=True, every_part_under_size_limit=True)


def shard(theme, source, output, chunk_rows, maximum):
    folder = output / theme
    folder.mkdir(parents=True, exist_ok=True)
    source_sha = digest(source)
    final_receipt = folder / "VERIFICATION.json"
    if final_receipt.exists():
        old = json.loads(final_receipt.read_text())
        if old["source_sha256"] == source_sha and old["max_part_bytes"] == maximum and old["initial_chunk_rows"] == chunk_rows:
            with (folder / "MANIFEST.csv").open(encoding="utf-8-sig", newline="") as stream:
                old_parts = list(csv.DictReader(stream))
            if all((folder / r["part"]).stat().st_size == int(r["bytes"]) and digest(folder / r["part"]) == r["sha256"] for r in old_parts):
                print(json.dumps(dict(theme=theme, resumed_completed=True, parts=old["parts"], rows=old["rows"])), flush=True)
                return old
    manifest, total, chunk = [], 0, 0
    rh, eh = hashlib.sha256(), hashlib.sha256()
    with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        event_column = header.index("event_id")
        while True:
            chunk += 1
            temp = folder / f"working_chunk_{chunk:04d}.csv.gz"
            piece = write_piece(temp, header, reader, chunk_rows, event_column, (rh, eh))
            if not piece["rows"]:
                temp.unlink()
                break
            for part in bounded_pieces(piece, header, event_column, maximum):
                dest = folder / f"EVENTS_PART_{len(manifest)+1:03d}.csv.gz"
                part["path"].replace(dest)
                start = total + 1
                total += part["rows"]
                manifest.append(dict(theme=theme, part=dest.name, rows=part["rows"], bytes=dest.stat().st_size, sha256=digest(dest),
                    source_complete_table=str(source.relative_to(ROOT)), source_sha256=source_sha, row_start=start, row_end=total,
                    columns=len(header), row_sequence_sha256=part["row_sequence_sha256"], event_id_sequence_sha256=part["event_id_sequence_sha256"]))
            save_manifest(folder / "MANIFEST.incomplete.csv", manifest)
            save_json(folder / "PROGRESS.json", dict(theme=theme, saved_rows=total, saved_parts=len(manifest), complete=False,
                source_sha256=source_sha, maximum_part_bytes=maximum, initial_chunk_rows=chunk_rows))
            print(json.dumps(dict(theme=theme, saved_rows=total, saved_parts=len(manifest))), flush=True)
    checked = verify_parts(folder, manifest, header, total, rh.hexdigest(), eh.hexdigest(), maximum)
    assert digest(source) == source_sha, "Complete source changed during sharding."
    save_manifest(folder / "MANIFEST.csv", manifest)
    (folder / "MANIFEST.incomplete.csv").unlink(missing_ok=True)
    receipt = dict(theme=theme, **checked, source_complete_table=str(source.relative_to(ROOT)), source_sha256=source_sha,
                   max_part_bytes=maximum, initial_chunk_rows=chunk_rows, source_retained_unchanged=True,
                   bytes=sum(r["bytes"] for r in manifest), complete=True, included_in_core_zip=False)
    save_json(final_receipt, receipt)
    save_json(folder / "PROGRESS.json", receipt)
    print(json.dumps(receipt), flush=True)
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", action="append", help="theme=complete_events.csv.gz; repeat as needed")
    ap.add_argument("--output-dir", type=Path, default=ROOT / "delivery/event_parts")
    ap.add_argument("--rows", type=int, default=8000)
    ap.add_argument("--max-mib", type=float, default=25)
    args = ap.parse_args()
    sources = dict((s.split("=", 1)[0], Path(s.split("=", 1)[1]).resolve()) for s in args.source) if args.source else DEFAULTS
    maximum = int(args.max_mib * 1024**2)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipts = [shard(theme, source, args.output_dir, args.rows, maximum) for theme, source in sources.items()]
    save_json(args.output_dir / "DELIVERY_VERIFICATION.json", dict(complete=True, themes=receipts,
        total_parts=sum(r["parts"] for r in receipts), total_rows=sum(r["rows"] for r in receipts),
        total_bytes=sum(r["bytes"] for r in receipts), optional_downloads=True, core_zip_excludes_parts=True,
        native_fusion_or_scoring_calls=0, semi_not_sharded_because_under_25_mib=True))
    (args.output_dir / "README.md").write_text("""# 完整事件表的可选分片下载

每个主题中的 `EVENTS_PART_*.csv.gz` 保留完整表头，按 `MANIFEST.csv` 的顺序拼接数据行即可恢复该主题完整事件表。不要把多份表头作为数据行拼入；CSV中的引号和字段内容须按CSV解析。`row_start`/`row_end` 是源表数据行的1起始序号，不包括表头。

每片压缩文件不超过25 MiB。清单提供每片行数、字节数、SHA256、源完整表SHA256和行区间。`VERIFICATION.json` 已验证所有字段字符串的完整记录顺序及 `event_id` 序列与源表一致，失败行完整保留。重复压缩可能改变gzip字节，但不会改变记录内容；源表自身未被修改。

三个主题：`manual_joint_A`（主阶段），`manual_joint_B`（最高Q较慢目标的新背景阶段），`manual_structure`（结构类别实验）。Semi完整事件表小于25 MiB，直接下载原表。这些分片作为独立可选下载文件，不放入核心ZIP。

通用生成脚本位于上层研究目录 `shard_event_delivery.py`，默认按8,000完整CSV记录尝试，压缩超限则递归细分；完成一批即保存进度。各主题独立验证，总计见 `DELIVERY_VERIFICATION.json`。
""", encoding="utf8")


if __name__ == "__main__":
    main()
