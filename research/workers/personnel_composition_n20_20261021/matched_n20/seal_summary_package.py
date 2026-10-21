#!/usr/bin/env python3
"""Freeze a compact summary and an exact index over the nine immutable batches.

No event values, labels, scoring, or geometry are changed. Wide event tables are
not concatenated or copied into this package. Run after all nine result batches
and the streaming summary have successful receipts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile

BASE = Path(__file__).resolve().parent
CP = BASE / "checkpointed_manual"
READY = CP / "ready"
OUT = BASE / "final_summary"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def info(path: Path) -> dict:
    return {"path": str(path.relative_to(BASE)), "bytes": path.stat().st_size,
            "sha256": sha(path)}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_bytes(path: Path, content: bytes) -> None:
    # Refuse to modify a previously frozen file, including an identical one.
    if path.exists():
        raise FileExistsError(f"Frozen output already exists: {path}")
    temp = path.with_name(path.name + f".pending.{os.getpid()}.{time.time_ns()}")
    with temp.open("xb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    if temp.read_bytes() != content:
        raise RuntimeError(f"Readback failed: {temp}")
    temp.replace(path)


def write_json(path: Path, value) -> None:
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def write_csv(path: Path, rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Empty required table")
    import io
    f = io.StringIO(newline="")
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    write_bytes(path, ("\ufeff" + f.getvalue()).encode("utf-8"))
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        back = list(r)
        assert len(back) == len(rows)
        assert r.fieldnames == list(rows[0])
        assert all(None not in row and None not in row.values() for row in back)
    return {**info(path), "rows": len(rows), "columns": len(rows[0])}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    if (OUT / "SUMMARY_PACKAGE_RECEIPT.json").exists():
        raise RuntimeError("Package is already sealed. Do not rewrite a saved artifact.")

    plan_receipt = read_json(CP / "PLAN_RECEIPT.json")
    summary = read_json(CP / "summary/SUMMARY_RECEIPT.json")
    design = read_json(BASE / "design_manual/DESIGN_RECEIPT.json")
    with (CP / "CHECKPOINT_PLAN.csv").open(encoding="utf-8-sig", newline="") as f:
        plan = {row["part"]: row for row in csv.DictReader(f)}
    summarized = {row["part"]: row for row in summary["input_parts"]}
    assert len(plan) == len(summarized) == 164
    assert summary["complete_event_id_equality"] is True
    assert summary["events_computed"] == summary["events_expected"] == 269814
    assert set(plan) == set(summarized)
    assert sha(BASE / "design_manual/MATCHED_ABC_EVENTS.csv.gz") == plan_receipt["design_sha256"]
    assert design["outcomes_accessed_for_design"] is False
    assert design["all_matched_triples_in_declared_registered_panel_enumerated"] is True

    batches, shards = [], []
    all_parts, all_buildings = set(), set()
    zip_receipts = sorted(READY.glob("BATCH_*_ZIP_RECEIPT.json"))
    assert len(zip_receipts) == 9
    for receipt_path in zip_receipts:
        zreceipt = read_json(receipt_path)
        batch_id = zreceipt["batch"]
        manifest_path = READY / f"{batch_id}_MANIFEST.json"
        manifest = read_json(manifest_path)
        # Retain portability when copied into another workspace.
        zpath = READY / Path(zreceipt["path"]).name
        assert zpath.stat().st_size == zreceipt["bytes"]
        assert sha(zpath) == zreceipt["sha256"]
        assert manifest["all_expected_ids_for_selected_buildings_verified"] is True
        assert manifest["immutable"] is True
        assert not (all_buildings & set(manifest["buildings"]))
        all_buildings.update(manifest["buildings"])
        assert manifest["events"] == zreceipt["events"]
        assert manifest["pools"] == len(manifest["part_results"])
        batch_events = batch_complete = 0
        for part in manifest["part_results"]:
            name = part["part"]
            assert name not in all_parts
            all_parts.add(name)
            p = plan[name]
            s = summarized[name]
            committed = read_json(CP / "shards" / f"{name}_RECEIPT.json")
            assert p["building"] == part["building"] == committed["building"]
            assert int(p["events"]) == part["events"] == s["events"] == committed["events"]
            assert part["sha256"] == s["sha256"] == committed["output"]["sha256"]
            assert part["columns"] == committed["output"]["columns"] == 697
            assert committed["input_sha256"] == p["input_sha256"]
            assert committed["fusion_calls"] == committed["score_calls"] == 0
            batch_events += part["events"]
            batch_complete += part["all_complete"]
            shards.append({
                "batch": batch_id, "zip_file": zpath.name, "part": name,
                "building": p["building"], "pool_id": p["pool_id"],
                "events": part["events"], "all_complete_events": part["all_complete"],
                "events_with_any_native_failure": part["events"] - part["all_complete"],
                "columns": 697, "event_file": committed["output"]["path"],
                "bytes": committed["output"]["bytes"], "sha256": part["sha256"],
                "design_input_sha256": committed["input_sha256"],
            })
        assert batch_events == manifest["events"]
        assert batch_complete == manifest["all_complete"]
        batches.append({
            "batch": batch_id, "zip_file": zpath.name,
            "events": batch_events, "all_complete_events": batch_complete,
            "events_with_any_native_failure": batch_events - batch_complete,
            "pools": manifest["pools"], "buildings": len(manifest["buildings"]),
            "building_ids": "|".join(manifest["buildings"]),
            "event_columns": 697, "zip_bytes": zreceipt["bytes"],
            "zip_sha256": zreceipt["sha256"],
            "manifest_sha256": sha(manifest_path),
            "zip_receipt_sha256": sha(receipt_path),
        })
    assert all_parts == set(plan) == set(summarized)
    assert all_buildings == {p["building"] for p in plan.values()}
    assert len(all_buildings) == 22
    assert sum(x["events"] for x in batches) == 269814
    assert sum(x["all_complete_events"] for x in batches) == 264867
    assert sum(x["events_with_any_native_failure"] for x in batches) == 4947

    outputs = [write_csv(OUT / "N20_MANUAL_RESULT_BATCH_INDEX.csv", batches),
               write_csv(OUT / "N20_MANUAL_RESULT_SHARD_INDEX.csv", shards)]
    coverage = {
        "condition": "manual", "n": 20, "minimum_matched_actual_m": 4,
        "batches": 9, "shards": 164, "pools": 164, "buildings": 22,
        "events": 269814, "all_complete_events": 264867,
        "events_with_any_native_failure": 4947, "columns_per_event_file": 697,
        "all_batch_zip_hashes_rechecked": True,
        "no_repeated_buildings_between_batches": True,
        "no_repeated_or_missing_shards_between_batches": True,
        "batch_shard_hashes_equal_streaming_summary_inputs": True,
        "event_id_union_equal_frozen_design": summary["complete_event_id_equality"],
        "event_id_verification_source": info(CP / "summary/SUMMARY_RECEIPT.json"),
        "event_id_verification_note": "Exact event ID equality was checked in the streaming summary; this index verifies the complete hash chain from those same immutable shards to all nine ZIPs, without copying or recomputing wide data.",
        "plan_receipt": info(CP / "PLAN_RECEIPT.json"),
        "frozen_design_sha256": plan_receipt["design_sha256"],
        "all_possible_population_member_sets_enumerated": False,
        "all_legal_events_within_method_registered_finite_panel_enumerated": True,
        "outputs": outputs,
    }
    write_json(OUT / "N20_MANUAL_RESULT_COVERAGE_RECEIPT.json", coverage)

    table = "\n".join(
        f"| {x['batch']} | {x['events']:,} | {x['pools']} | {x['buildings']} | {x['events_with_any_native_failure']:,} |"
        for x in batches
    )
    readme = f"""# n20 匹配对照：最终小包与分批结果索引

本包保存已完成研究的总结、小表、代码、输入引用和覆盖收据。Manual 的 **269,814 个完整事件、697 个字段** 已分九批交付；本包不再重复复制。Semi 的 **1,517 个完整事件** 已在独立完整结果包交付，条件保持分开。

## 优先阅读

1. `MANUAL_N20_FINDINGS_ZH.md`：采用判断、质量／形状／时间／失败与反例。
2. `checkpointed_manual/summary/N20_MANUAL_KEY_FINDINGS.csv`：方法与父类内关键结果；同目录另有 m、难度、来源匹配响应表。
3. `checkpointed_manual/time_analysis/N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_EVENTS.csv`：875 个方向事件；A/B 和 A/C 的匹配 m 与 B/C 的实际净换人数分开。
4. `results_semi/RESULTS_ZH.md`：Semi 独立结果和机会限制。
5. `N20_MATCHED_EVENT_FIELD_DICTIONARY.csv`：完整 697 字段定义。

时间是原来源记录时长之和，单位秒；新批标记为 `user_processed_reported_not_raw_log_replayed`，本分支没有重放原始日志验证主动时长。统计以建筑为单位描述，质量无效不补零，原生失败留在失败及联合稳定分母。

## 九批 Manual 结果

| 批次 | 事件数 | 池数 | 建筑数 | 至少一队原生失败事件 |
|---|---:|---:|---:|---:|
{table}
| 合计 | 269,814 | 164 | 22 | 4,947 |

`N20_MANUAL_RESULT_BATCH_INDEX.csv` 保存每个 ZIP 的精确名称、字节数、SHA256、建筑和失败分母；`N20_MANUAL_RESULT_SHARD_INDEX.csv` 保存全部 164 分片的位置、池、行数和哈希。九批之间没有重复建筑或分片，分片并集与冻结计划一致。流式汇总已逐事件验证完整 ID 并集等于 269,814 个设计事件；此处通过不可变分片哈希及九个 ZIP 哈希衔接该校验，不重新复制宽表。

全部事件仅穷举于各方法自己的预登记有限成员面板；没有穷举全人口所有具体成员集合或所有加入顺序。三团队 A/B/C 是对照臂，不限制人员类别数。所有选择先只用人员和楼外标签，结果阶段再读取质量、几何和时间。

## 恢复与解包顺序

将设计包、九批 Manual 结果包、Semi 设计／结果包分别解压到研究的 `continuation_20261021/n20_abc/` 目录，最后解压本小包，使最终加固的写入及恢复代码生效。早期批内保存的是当时的代码快照，不应改写它们的 manifest 或哈希；最终脚本在本包根目录。

原终点标量、精简几何、冻结类别及输入引用仍由研究主包和 n20 全配置阶段提供，具体 SHA256 见 `REPRODUCE_MATCHED_N20_ZH.md`、`INDEX_RECEIPT.json` 及设计收据。SQLite 查询索引、分片设计输入、原图、虚拟环境、`.pending` 文件均不随本包复制。完成分片的恢复以成功 receipt 为准。

`checkpointed_manual/time_analysis/N20_MATCHED_TIME_EVENT_VALUES.csv.gz` 是可由既有宽表重建的 269,814×32 派生时间表，未重复打入本小包；`TIME_RECEIPT.json` 保留其当时生成哈希。执行 `analyze_n20_time.py` 可以重建它及已交付的小型时间表。主要结果宽表已经包含相应原始终点值。

`N20_M_FINE_ILLUSTRATION_CASES.csv` 的三个案例按明确结果条件后选，仅解释 M 细类正例、D10 门槛敏感性和反例，不估计频率。`PREVIOUS_EVENT_PHYSICAL_OVERLAP.json` 另验证本轮 Manual／Semi 三团队物理集合与旧事件均无重叠，不能据此将本次探索称为全新盲测。

全部实验已经完成；此包的封存不新增融合、评分或分型搜索。
"""
    write_bytes(OUT / "FINAL_PACKAGE_GUIDE_ZH.md", readme.encode("utf-8"))

    relpaths = [
        "MANUAL_N20_FINDINGS_ZH.md", "REPRODUCE_MATCHED_N20_ZH.md",
        "N20_MATCHED_EVENT_FIELD_DICTIONARY.csv", "PREVIOUS_EVENT_PHYSICAL_OVERLAP.json",
        "KERNEL_EQUIVALENCE_CHECK.json", "MANUAL_DESIGN_PACKAGE_MANIFEST.json",
        "SEMI_DESIGN_PACKAGE_MANIFEST.json", "SEMI_RESULTS_PACKAGE_MANIFEST.json",
        "discover_n20_abc.py", "evaluate_n20_abc.py", "event_kernel.py",
        "evaluate_n20_checkpointed.py", "atomic_checkpoint_io.py",
        "freeze_n20_results.py", "summarize_n20_checkpointed.py", "analyze_n20_time.py",
        "seal_summary_package.py", "checkpointed_manual/CHECKPOINT_PLAN.csv",
        "checkpointed_manual/POOL_PAIR_SCALE.csv", "checkpointed_manual/PLAN_RECEIPT.json",
        "checkpointed_manual/INDEX_RECEIPT.json",
        "checkpointed_manual/FIXED_FOUR_PARTITION_ASSIGNMENT.csv",
        "checkpointed_manual/CHECKPOINT_EXCEPTION_AND_RECOVERY.json",
        "checkpointed_manual/time_analysis/N20_QTD_TRAINING_TIME_DIRECTION_CHECK.csv",
        "final_summary/N20_MANUAL_RESULT_BATCH_INDEX.csv",
        "final_summary/N20_MANUAL_RESULT_SHARD_INDEX.csv",
        "final_summary/N20_MANUAL_RESULT_COVERAGE_RECEIPT.json",
        "final_summary/FINAL_PACKAGE_GUIDE_ZH.md",
    ]
    paths = [BASE / x for x in relpaths]
    for condition in ["manual", "semi"]:
        paths += [BASE / f"design_{condition}/{name}" for name in
                  ["DESIGN_RECEIPT.json", "DESIGN_SCOPE_ZH.md", "MATCHED_ABC_POOL_SCALE.csv", "MATCHED_ABC_M_SCALE.csv"]]
    paths += sorted(p for p in (CP / "summary").iterdir()
                    if p.name.endswith((".csv", ".csv.gz", ".json")))
    paths += sorted(p for p in (CP / "time_analysis").iterdir()
                    if p.name.endswith((".csv", ".csv.gz", ".json"))
                    and p.name != "N20_MATCHED_TIME_EVENT_VALUES.csv.gz")
    paths += sorted(p for p in (BASE / "results_semi").iterdir()
                    if p.name.endswith((".csv", ".csv.gz", ".json", ".md"))
                    and p.name != "N20_ABC_ALL_COMPONENT_EVENTS.csv.gz")
    paths += sorted(READY.glob("BATCH_*_MANIFEST.json"))
    paths += sorted(READY.glob("BATCH_*_ZIP_RECEIPT.json"))
    paths += sorted(READY.glob("BATCH_*_ZH.md"))
    paths += sorted(READY.glob("BATCH_*_INDEX_RECEIPT_SNAPSHOT.json"))
    paths = sorted(set(paths))
    assert all(p.is_file() for p in paths)
    assert not any(".pending" in p.name or p.suffix in {".sqlite", ".zip"} for p in paths)
    manifest = {
        "scope": "Immutable summary, key tables, exact nine-batch index, final code and reproducibility; wide event batches are referenced, not copied.",
        "manual_events": 269814, "semi_events": 1517,
        "files": [info(p) for p in paths],
        "excluded_reproducible_derived_time_table": "checkpointed_manual/time_analysis/N20_MATCHED_TIME_EVENT_VALUES.csv.gz",
        "raw_wide_event_tables_included": False,
    }
    mpath = OUT / "SUMMARY_PACKAGE_MANIFEST.json"
    write_json(mpath, manifest)
    paths.append(mpath)
    zip_path = BASE / "HOHONET_n20_同构成改构成匹配对照_总结代码与九批索引_20261021.zip"
    if zip_path.exists():
        raise FileExistsError(zip_path)
    temp_zip = zip_path.with_name(zip_path.name + f".pending.{os.getpid()}.{time.time_ns()}")
    with zipfile.ZipFile(temp_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in paths:
            z.write(path, path.relative_to(BASE).as_posix())
    expected = {str(p.relative_to(BASE)): sha(p) for p in paths}
    with zipfile.ZipFile(temp_zip) as z:
        assert len(z.namelist()) == len(expected)
        assert set(z.namelist()) == set(expected)
        assert z.testzip() is None
        for name, digest in expected.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest, name
    temp_zip.replace(zip_path)
    receipt = {
        **info(zip_path), "files": len(paths), "manual_events": 269814, "semi_events": 1517,
        "zip_readback_all_member_hashes_verified": True, "all_nine_manual_zip_hashes_verified": True,
        "manual_full_event_table_not_duplicated": True, "immutable_after_handoff": True,
        "manifest": info(mpath), "coverage_receipt": info(OUT / "N20_MANUAL_RESULT_COVERAGE_RECEIPT.json"),
    }
    write_json(OUT / "SUMMARY_PACKAGE_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
