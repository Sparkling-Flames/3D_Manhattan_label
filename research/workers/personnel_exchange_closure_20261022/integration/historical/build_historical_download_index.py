"""Locate recovered historical deliverables without recomputing research.

Large complete event CSVs are never decompressed by this script.  Archived
completion manifests supply rows/columns; compressed bytes are hashed directly.
All generated download links refer to files that exist in this workspace.
"""
from pathlib import Path
import hashlib
import json
import zipfile
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
WORK = ROOT.parent
OLD = ROOT / "research/workers/personnel_effective_exchange_conditions_20261022"
V3 = ROOT / "research/workers/personnel_useful_taxonomy_v3_20261021"
RECOVERED = WORK / "source_recovery/previous_complete_events"
LIB_FILES = WORK / "source_recovery/library"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def link(path, text=None):
    path = Path(path).resolve()
    assert path.is_file(), path
    assert " " not in str(path), path
    return f"[{text or path.name}](sandbox:{path})"


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    rows = []

    def add(path, category, stage, scientific_identity, use_status,
            row_count=None, columns=None, rows_source=None, expected_sha=None, expected_bytes=None,
            note="", alternate_paths=None):
        path = Path(path).resolve()
        assert path.is_file(), path
        actual_sha, size = sha(path), path.stat().st_size
        row = dict(category=category, historical_stage=stage, file_name=path.name,
                   scientific_identity=scientific_identity, use_status_this_round=use_status,
                   local_path=str(path), download_link=f"sandbox:{path}", bytes=size, sha256=actual_sha,
                   rows=row_count, columns=columns, rows_source=str(Path(rows_source).resolve()) if rows_source else "",
                   rows_method="inherited_archived_manifest_or_index" if rows_source else "not_applicable_or_not_in_manifest",
                   archived_sha256=expected_sha or "", archived_bytes=expected_bytes,
                   archived_sha_match=actual_sha == expected_sha if expected_sha else "not_provided",
                   archived_size_match=size == int(expected_bytes) if expected_bytes is not None else "not_provided",
                   alternate_existing_paths=" || ".join(str(Path(x).resolve()) for x in alternate_paths or [] if Path(x).is_file()),
                   note=note)
        rows.append(row)
        return row

    # 25 prior expanded full-event shards: rows and identity from archived receipts.
    expanded = []
    for receipt_path in sorted((OLD / "delivery/expanded_events").glob("*_COMPLETION.json")):
        d = json.loads(receipt_path.read_text())
        name = d["chunk_id"] + "_EVENTS_COMPLETE.csv.gz"
        rec = add(RECOVERED / name, "01_complete_expanded_events", "prior_effective_exchange_20261022_expanded",
                  f"{d['method_id']} / Manual / n{d['n']} / m{d['m']}；旧扩大登记的完整有向事件分片",
                  "recovered_complete_not_recomputed", d["rows"], d.get("columns"), receipt_path,
                  d["sha256"], d["bytes"],
                  "本轮仅恢复下载与登记字节身份；不重复重聚合全事件、不新增融合评分。镜像和复用端点不作为独立图片。")
        expanded.append(rec)
    assert len(expanded) == 25

    # Four cached/cross files and two native files retain their distinct identities.
    manifest_path = OLD / "joint_exchange/DELIVERY_MANIFEST.csv"
    jm = pd.read_csv(manifest_path, keep_default_na=False).set_index("file")
    joint = []
    for family in ["CACHED", "CROSS", "NATIVE"]:
        for condition in ["MANUAL", "SEMI"]:
            name = f"{family}_{condition}_EVENTS_COMPLETE.csv.gz"
            path = OLD / "joint_exchange" / name if family == "NATIVE" else RECOVERED / name
            m = jm.loc[name]
            scientific = {"CACHED": "原单条件联合类别、既有端点匹配事件",
                          "CROSS": "新双条件历史分类、分别在 Manual 或 Semi 评价的匹配事件",
                          "NATIVE": "原单条件联合类别、纯块匹配的新增／复用原生端点事件"}[family]
            status = "actual_inheritance_of_prior_baseline" if family == "NATIVE" else "recovered_complete_not_recomputed"
            rec = add(path, "02_complete_joint_events", f"prior_effective_exchange_20261022_{family.lower()}",
                      scientific + f"；评价条件 {condition}", status,
                      int(float(m["rows"])), int(float(m["columns"])), manifest_path, m["sha256"], int(m["bytes"]),
                      "保留此前实验身份；本轮新实验在 personnel_exchange_closure_20261022，不能累计成同一次独立试验。",
                      [LIB_FILES / name] if family == "NATIVE" else [])
            joint.append(rec)

    # Previously delivered packages, linked directly rather than repackaged.
    packages = [
        ("CORE_RESEARCH_CODE_AND_SMALL_EVIDENCE.zip", "prior_effective_exchange_20261022", "关键代码、楼外／全数据标签、正式汇总及机制小证据", None),
        ("SMALL_ANALYSIS_INPUTS.zip", "prior_effective_exchange_20261022", "253 格冻结请求、小面板摘要／完成回执、25 大事件分片小回执", None),
        ("HOHONET_v3_复现代码与必要小输入_20261021.zip", "prior_useful_taxonomy_v3_20261021", "此前三阶段复现代码与必要小输入；v3 是研究轮次，底层真实 v2", "f4c1912f5163dfd3342adbaaeae658d4c90bf93b506038a31dd8b6e8d2b5c34d"),
    ]
    for name, stage, meaning, expected in packages:
        path = LIB_FILES / name
        with zipfile.ZipFile(path) as z:
            entries = len([i for i in z.infolist() if not i.is_dir()])
        add(path, "03_existing_code_small_packages", stage, meaning, "restored_and_used_for_code_input_recovery",
            expected_sha=expected, note=f"现有 ZIP，中央目录含 {entries} 个文件；此处不重新打包、不重新解压或全包复审。rows 不适用于 ZIP。")

    # Necessary compact endpoints that are actually restored and directly downloadable.
    for kind in ["SCALARS", "GEOMETRY"]:
        name = f"ALL_USED_ENDPOINT_{kind}.csv.gz"
        m = jm.loc[name]
        add(OLD / "joint_exchange" / name, "04_available_compact_endpoints", "prior_effective_exchange_20261022_joint",
            "旧联合专题 44,328 个去重团队的标量或几何；两文件按 team_key 联接", "actually_reused_as_current_cache_input",
            int(float(m["rows"])), int(float(m["columns"])), manifest_path, m["sha256"], int(m["bytes"]),
            "不是全部 25 expanded 分片的端点全集；本轮按实际集合键复用。", [LIB_FILES / name])

    # The old lightweight endpoint index has row-level export membership. Reading
    # its file-name column avoids opening any large scalar/geometry/event table.
    key_index_path = LIB_FILES / "ENDPOINT_KEY_INDEX.csv.gz"
    ki = pd.read_csv(key_index_path, usecols=["scalar_file"])
    counts = ki.scalar_file.map(lambda s: Path(s).name).value_counts().to_dict()
    for prefix in ["MAIN_SEMI", "LARGE_MANUAL", "PURE_MANUAL", "PURE_SEMI"]:
        scalar_name = prefix + "_ENDPOINT_SCALARS.csv.gz"
        for kind in ["SCALARS", "GEOMETRY"]:
            name = prefix + f"_ENDPOINT_{kind}.csv.gz"
            add(LIB_FILES / name, "04_available_compact_endpoints", "prior_useful_taxonomy_v3_20261021_" + prefix,
                "V3 既有团队端点；保留 MAIN／LARGE／PURE 与条件身份", "restored_available_prior_endpoint",
                int(counts[scalar_name]), rows_source=key_index_path,
                note="行数引用旧端点索引的 scalar_file 导出归属；未解压此端点表重新计数。配对 geometry 属同一导出键集。")
    add(key_index_path, "05_source_indices_and_coverage", "prior_useful_taxonomy_v3_20261021",
        "360,681 个阶段导出引用，对应 360,676 个唯一团队；索引不含完整评分或几何", "reference_for_historical_membership_and_recovery",
        len(ki), rows_source=V3 / "integration/COVERAGE_CHECKPOINT.json",
        note="本轮仅按文件归属读取轻量索引；没有重算全部历史团队。")

    # Available source documentation and the 26x2 domain ledger are independently downloadable.
    references = [
        (V3 / "integration/PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv", "26×2 分域、分条件、分阶段覆盖账；算法变体不另算域子集"),
        (ROOT / "research/workers/personnel_global_composition_20261021/multivariate/domain_subset_26_coverage.csv", "第一阶段五域 2—5 域组合的原始覆盖账"),
        (V3 / "integration/PHASE3_METHOD_EXPERIMENT_COVERAGE.csv", "V3 方法与实际实验覆盖，不冒充新全域筛查"),
        (OLD / "delivery/CORE_PACKAGE_GUIDE_ZH.md", "上轮代码／输入包说明与冻结依赖"),
        (OLD / "delivery/CORE_PACKAGE_INPUTS.csv", "上轮包内与外部输入逐项原清单"),
        (OLD / "delivery/expanded_events/CHUNK_PLAN.json", "上轮 25 个完整事件分片的正式计划"),
        (manifest_path, "上轮 joint 完整事件和紧凑端点原 SHA／rows 清单"),
        (OLD / "joint_exchange/DELIVERY_RECEIPT.json", "上轮六张完整 joint 事件表交付回执"),
        (OLD / "README.md", "已合并 main 的上轮归档与独立验收身份说明"),
        (ROOT / "docs/thesis_main/人员标法分类与换类研究_总体进度_20261020.md", "main 当前人员专题；较早段落保留阶段历史身份"),
        (LIB_FILES / "HOHONET_完整文件下载目录.csv", "上轮下载目录历史原件；内部旧链接只作来源，不作为本轮可下载保证"),
        (LIB_FILES / "ALL_METHOD_LABELS_LOBO.csv.gz", "已恢复 V3 楼外标签，实际继承的分类输入"),
        (LIB_FILES / "PANELS.csv", "已恢复 V3 面板库存，实际继承的人员域与背景输入"),
    ]
    for path, meaning in references:
        if not path.exists():
            continue
        n = None
        if path.suffix == ".csv":
            # These are small coverage/manifests, not complete event tables.
            n = len(pd.read_csv(path, low_memory=False))
        add(path, "05_source_indices_and_coverage", "historical_source_reference", meaning,
            "actually_inherited_classification_or_inventory_input" if path.name in ["ALL_METHOD_LABELS_LOBO.csv.gz", "PANELS.csv"] else "reference_only_not_new_experiment",
            n, rows_source=path if n is not None else None)

    # Additional prior batches restored in three download-only stages. Their
    # original completion receipts, not the cloud collision-suffixed filenames,
    # determine scientific identity and the stable local path.
    restored_path = HERE / "OLD_ENDPOINT_RESTORED_FILES.csv"
    restored_rows = pd.read_csv(restored_path, keep_default_na=False).to_dict("records") if restored_path.exists() else []
    for r in restored_rows:
        add(r["local_path"], "04b_restored_prior_batch_endpoints", "prior_effective_exchange_20261022_" + r["batch_id"],
            "旧扩大／原生批次完整端点；按原 batch_id 保留标量与 geometry 身份", "restored_complete_download_only_no_scientific_rerun",
            int(r["rows"]), int(r["columns"]), r["rows_source"], r["sha256"], int(r["bytes"]),
            "从此前已交付原件恢复，压缩字节与原批回执完全相同；不另算新端点或新研究。")

    frame = pd.DataFrame(rows)
    frame.to_csv(HERE / "HISTORICAL_DOWNLOAD_INDEX.csv", index=False, encoding="utf-8-sig")
    complete = frame[frame.category.isin(["01_complete_expanded_events", "02_complete_joint_events"])]
    assert len(complete) == 31
    assert all(Path(p).is_file() for p in frame.local_path)
    # Byte identity is a file recovery check, not a repeated scientific audit.
    mismatches = frame[frame.archived_sha_match.eq(False) | frame.archived_size_match.eq(False)]

    old_index = pd.read_csv(LIB_FILES / "HOHONET_完整文件下载目录.csv", keep_default_na=False)
    expected_ep = old_index[old_index.topic_relative_path.str.match(r"expanded_blocks/batches/(?:expand|joint)_\d+/ENDPOINT_(?:SCALARS|GEOMETRY)\.csv\.gz$")]
    missing = []
    for item in expected_ep.to_dict("records"):
        path = OLD / item["topic_relative_path"]
        recovered_path = WORK / "source_recovery/previous_endpoints" / item["topic_relative_path"]
        if not path.is_file() and not recovered_path.is_file():
            missing.append(dict(historical_stage="prior_effective_exchange_20261022_expanded_endpoints",
                                original_relative_path=item["topic_relative_path"], archived_bytes=item["bytes"],
                                current_availability="not_restored_here", download_link="",
                                note="完整事件和小请求/摘要已可得；该独立旧端点片当前未恢复，不伪造旧 sandbox 链接。"))
    pd.DataFrame(missing, columns=["historical_stage", "original_relative_path", "archived_bytes", "current_availability", "download_link", "note"]).to_csv(HERE / "HISTORICAL_UNAVAILABLE_REFERENCES.csv", index=False, encoding="utf-8-sig")

    md = ["# 历史完整成果：现存文件下载索引", "",
          "本索引衔接本轮 `personnel_exchange_closure_20261022` 与此前成果，不新增分类、融合、评分或事件搜索。底层仍为真实 **v2**；旧包名中的 **v3 是研究轮次**。所有本页下载链接均已检查为本机现存绝对路径，未沿用旧目录里失效的 sandbox 地址。", "",
          f"已恢复并可独立下载 **31 张完整事件文件，共 {int(complete.rows.sum()):,} 条历史有向记录、{int(complete.bytes.sum()):,} 字节**：25 张扩大分片＋4 张 cached/cross＋2 张 native。总行数是文件记录量，不当成相互独立事件／团队／图片数；不同阶段及镜像的独立性保持原定义。", "",
          "完整 bytes、SHA256、行数、行数来源、恢复／复用身份及备用现存路径见 " + link(HERE / "HISTORICAL_DOWNLOAD_INDEX.csv") + "。大事件行数来自原 `COMPLETION.json`／`DELIVERY_MANIFEST.csv`；本轮只对压缩字节计算 SHA，没有解压扫描全部大事件或重新核验统计。", "",
          "## 1. 上轮扩大完整事件（25 片）", "",
          "这些文件恢复了 A2 n17/m9、旧 M 父内 n10/m5 与 m6、新 Manual 结构 n10/m7 的完整事件证据。m5、m6 各自保留，不能恢复成已经被后续扩大结果收窄的早期合并结论。", "",
          "| 独立文件 | 行数 | 字节 | SHA256 前12位 |", "|---|---:|---:|---|"]
    for r in expanded:
        md.append(f"| {link(r['local_path'])} | {int(r['rows']):,} | {r['bytes']:,} | `{r['sha256'][:12]}` |")
    md += ["", "## 2. 上轮联合分类完整匹配事件（6 张）", "",
           "cached 复用既有端点，cross 使用双条件历史形成的类别，native 是原单条件联合类的原生纯块匹配。Manual 与 Semi 各自评价，三种身份不合并冒充同一种分类或新一轮实验。", "",
           "| 独立文件 | 行数 | 字节 | 本轮处理 |", "|---|---:|---:|---|"]
    for r in joint:
        md.append(f"| {link(r['local_path'])} | {int(r['rows']):,} | {r['bytes']:,} | {'继承历史起点，不重算融合' if 'NATIVE' in r['file_name'] else '恢复可下载，不重算全表'} |")
    md += ["", "## 3. 已有代码与必要小输入包", "",
           "下面直接指向已恢复的原包，没有再生成大重复 ZIP。它们的内容和展开目标见 " + link(OLD / "delivery/CORE_PACKAGE_GUIDE_ZH.md") + "。", ""]
    for r in frame[frame.category.eq("03_existing_code_small_packages")].to_dict("records"):
        md.append(f"- {link(r['local_path'])}：{r['bytes']:,} 字节；{r['scientific_identity']}。")
    md += ["", "## 4. 当前可得的必要端点与成员定位", "",
           "端点标量与 geometry 必须按 `team_key` 配对；`ENDPOINT_KEY_INDEX` 只用于定位，不能替代质量和几何。旧联合 compact 的 44,328 个端点已实际进入本轮复用缓存；V3 MAIN／LARGE／PURE 的可得部分保留原导出身份。", "",
           "| 现存文件 | 行数／导出引用 | 字节 |", "|---|---:|---:|"]
    for r in frame[frame.category.eq("04_available_compact_endpoints")].to_dict("records"):
        md.append(f"| {link(r['local_path'])} | {int(r['rows']):,} | {r['bytes']:,} |")
    md += ["", "### 本轮补齐的上轮批次端点", "",
           f"已按原批身份恢复 {len(restored_rows)}/56 个标量／geometry 文件、{sum(int(r['bytes']) for r in restored_rows):,} 字节。所有下载后文件均与原批完成回执 SHA256 相同；原上传为了避免同名冲突而附加的编号／时间后缀与原 batch 的对应保存在 " + (link(restored_path) if restored_path.exists() else "恢复清单（尚无完成批次）") + "。只恢复原文件，没有新融合、评分或远端写入。", "",
           "| 原批次 | 标量文件 | geometry 文件 | 端点行数 |", "|---|---|---|---:|"]
    by_batch = {}
    for r in restored_rows:
        by_batch.setdefault(r["batch_id"], {})["scalars" if "SCALARS" in r["local_path"] else "geometry"] = r
    for bid, pair in sorted(by_batch.items()):
        md.append(f"| {bid} | {link(pair['scalars']['local_path'], 'ENDPOINT_SCALARS.csv.gz') if 'scalars' in pair else '尚未恢复'} | {link(pair['geometry']['local_path'], 'ENDPOINT_GEOMETRY.csv.gz') if 'geometry' in pair else '尚未恢复'} | {int(next(iter(pair.values()))['rows']):,} |")
    gap_text = (f"还有 {len(missing)} 个指定旧批次文件未恢复，详见 " if missing else "指定 28 个旧批次的 56 个文件已全部恢复；剩余缺项表为零行，见 ")
    md += ["", "旧端点索引：" + link(key_index_path) + "。" + gap_text + link(HERE / "HISTORICAL_UNAVAILABLE_REFERENCES.csv") + "。31 张完整事件和本节旧批次端点可以独立取得；这仍不等于全部更早阶段历史库存、原始全状态或原图全集的镜像。", "",
           "## 5. 历史覆盖与本轮身份", "",
           "### 选队收益与匹配换类分开", "",
           "此前 Manual 联合分类相对同候选域均匀选队的 Q +1.432、记录时间 −5.419%，属于选队研究。此前 Manual 纯块匹配 64 登记事件、62 三队可评分事件的 C−B Q +5.691、时间 −3.632%（另 2 个 C 失败），以及 Semi 28 个事件的 Q +0.153、时间 −8.544%，属于匹配换人／换类。前者不能代替后者，本轮新增成员／背景实验又在独立 closure 目录保存，不能反向改写旧阶段。依据见 " + link(OLD / "README.md") + " 与 " + link(ROOT / "docs/thesis_main/人员标法分类与换类研究_总体进度_20261020.md") + "。", "",
           "### 26×2 变量域覆盖保留原账", "",
           "五域 Q、T、难度、scope、Semi 的 2—5 域组合共 26 种，每条件分别记账，共 52 行。当前历史账第一阶段 37 行已筛查、15 行机会不足；Manual 26 行均有筛查，Semi 11 行有筛查、15 行机会不足。只有 3 行附有该阶段实际构成方法汇总；后续 n20 与 V3 深研分别另列，不能把所有筛查或算法/K变体当成 26 种域组合都做过深入换类。", "",
           "V3 四行映射有实际人数／类别块实验，48 行只是沿用历史而无新深研；52 行均不宣称 V3 又做了一轮新纯域筛查。结构＋Q/T 联合类含结构额外表达，不因映射在 Q+T 行就冒称新纯 Q/T 分类；旧 QTDS 中 S 的原结构语义与 scope 保持区别。", "",
           "- " + link(V3 / "integration/PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv") + "：52 行逐阶段完整覆盖账。",
           "- " + link(ROOT / "research/workers/personnel_global_composition_20261021/multivariate/domain_subset_26_coverage.csv") + "：第一阶段原账。",
           "- " + link(V3 / "integration/PHASE3_METHOD_EXPERIMENT_COVERAGE.csv") + "：V3 具体方法—实际实验身份。", "",
           "### 三种状态", "",
           "1. **实际复用／继承**：楼外分类输入、面板库存、冻结代码、44,328 端点 compact 及旧 native 基线；复用身份在 CSV 的 `use_status_this_round` 标明。",
           "2. **恢复完整可下载**：25 expanded 与 4 cached/cross 全事件、原代码／小输入包，以及本节实际完成的旧批次端点；恢复不另计新实验或全流程独立验证。",
           "3. **仅引用**：旧筛查、覆盖和公开 main 的整理／独立验收结论；索引不以一次文件 SHA 核对冒充科学复核。", "",
           "## 6. 校验与恢复说明", "",
           f"本索引列出 {len(frame)} 个现存原文件。31 张完整事件的 bytes/SHA 与原归档清单对比结果见同名 CSV；不匹配记录数为 {len(mismatches)}。恢复来源仍是原文件，不改内容、不覆盖旧冻结请求。", "",
           "若需旧事件重聚合，使用原 CORE 与 SMALL 包中的脚本及 frozen dependencies；大事件原件可直接从上表取得。无需重跑融合。旧完整目录仅作为历史来源原件 " + link(LIB_FILES / "HOHONET_完整文件下载目录.csv") + "，其中内部旧地址不作为本轮可下载承诺；请使用本页和本轮 CSV 的现存链接。", ""]
    (HERE / "HISTORICAL_DOWNLOAD_INDEX_ZH.md").write_text("\n".join(md), encoding="utf-8")
    receipt = dict(status="complete", files=len(frame), complete_event_files=len(complete),
                   complete_event_rows=int(complete.rows.sum()), complete_event_bytes=int(complete.bytes.sum()),
                   expanded_files=25, expanded_rows=sum(int(r["rows"]) for r in expanded),
                   joint_complete_files=6, joint_complete_rows=sum(int(r["rows"]) for r in joint),
                   all_download_links_exist=True, broken_generated_download_links=0,
                   archived_byte_or_hash_mismatch_count=len(mismatches),
                   large_event_decompressions=0, fusion_calls=0, scoring_calls=0, new_large_zip_files=0,
                   prior_unrestored_expanded_endpoint_files=len(missing),
                   prior_restored_batch_endpoint_files=len(restored_rows),
                   prior_restored_batch_endpoint_bytes=sum(int(r["bytes"]) for r in restored_rows),
                   historical_data_version="real_v2", v3_means="prior_research_round",
                   index_sha256=sha(HERE / "HISTORICAL_DOWNLOAD_INDEX.csv"),
                   markdown_sha256=sha(HERE / "HISTORICAL_DOWNLOAD_INDEX_ZH.md"))
    (HERE / "HISTORICAL_INDEX_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
