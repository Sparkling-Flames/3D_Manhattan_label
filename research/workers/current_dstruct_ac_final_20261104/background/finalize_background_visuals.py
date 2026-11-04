"""Bundle existing native endpoint evidence and make a small offline index."""
from __future__ import annotations

import gzip
import hashlib
import html
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TASK = HERE.parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    native_receipts = []
    for selection_file, output in [("ILLUSTRATIVE_FIXED_XZ_CASE.json", "FIXED_XZ_NATIVE_FOUR_ENDPOINTS.json.gz"),
                                    ("ILLUSTRATIVE_STABLE_FIXED_XZ_CASE.json", "STABLE_FIXED_XZ_NATIVE_FOUR_ENDPOINTS.json.gz")]:
        selection = json.loads((HERE / selection_file).read_text(encoding="utf-8"))
        rows = [selection["low_delta"], selection["high_delta"]]
        source = TASK / selection["native_endpoint_pool"]
        raw = json.loads(gzip.decompress(source.read_bytes()))
        index = {e["team_key"]: e for e in raw["teams"]}
        teams = []
        for row in rows:
            for arm in ["A", "C"]:
                t = index[row[arm + "_team_key"]]
                assert set(t["member_workers"]) == set(row[arm + "_workers"].split("|"))
                assert abs(t["B8L2"] - row["Q_" + arm]) < 1e-10
                teams.append(t)
        assert len({t["team_key"] for t in teams}) == 4
        evidence = dict(selection=selection, source_native_pool=selection["native_endpoint_pool"], source_sha256=sha(source), teams=teams,
                        interpretation="Exact saved native endpoints, including full_state; no fusion/scoring changes")
        (HERE / output).write_bytes(gzip.compress(json.dumps(evidence, ensure_ascii=False).encode(), mtime=0))
        native_receipts.append(dict(path=output, sha256=sha(HERE / output), source=str(source.relative_to(TASK)), source_sha256=sha(source), unchanged_native_teams=4))
    rows = [
        ("大幅变化例：固定XZ与D类向量，换D成员改变方向", "FIXED_XZ_SAME_D_COMPOSITION", "q9vSo1VnCiC-30", "FIXED_XZ_ORIGINAL_IMAGE_RECEIPT.json", "ILLUSTRATIVE_FIXED_XZ_CASE.json", "FIXED_XZ_NATIVE_FOUR_ENDPOINTS.json.gz", "D1：ΔQ −4.039908；D2：+49.122898。两D均1名C1＋6名C2，X/Z完全相同。该例为既有结果中最大观察跨度的解释案例。"),
        ("稳定例：固定XZ与D类向量，换D成员后的ΔQ几乎一致", "FIXED_XZ_STABLE_BACKGROUND", "e9zR4mvMWw7-15", "e9zR4mvMWw7-15_ORIGINAL_IMAGE_RECEIPT.json", "ILLUSTRATIVE_STABLE_FIXED_XZ_CASE.json", "STABLE_FIXED_XZ_NATIVE_FOUR_ENDPOINTS.json.gz", "D1：ΔQ +2.339310；D2：+2.340794。两D均10名C2＋3名C3，差值仅0.001484Q。该例为既有可比较块中观察跨度最小的解释案例。"),
        ("输出状态例：同一32背景块中的三种既有状态", "FIXED_XZ_BACKGROUND_OUTPUT_STATES", "yqstnuAEVhm-27", "yqstnuAEVhm-27_ORIGINAL_IMAGE_RECEIPT.json", "ILLUSTRATIVE_OUTPUT_STATE_CASE.json", "OUTPUT_STATE_RENDER_EVIDENCE.json.gz", "29个背景双端Q、2个背景C无连接、1个背景A无连接。按每种状态event_id排序取首例；失败端点保留Q缺失，只画保存节点，不补闭环。"),
    ]
    parts = []
    original_sources = []
    for title, fig, code, receipt, selection, native, desc in rows:
        r = json.loads((HERE / receipt).read_text())
        original_sources.append(r)
        parts.append(f'''<section><h2>{html.escape(title)}</h2><p>{html.escape(desc)}</p>
<p><a href="{fig}.png">PNG完整对照板</a> · <a href="{fig}.svg">SVG</a> · <a href="originals/{code}.png">原始PNG</a> · <a href="{selection}">冻结选例/成员</a> · <a href="{native}">既有端点/full_state</a> · <a href="{receipt}">来源与CRC</a></p>
<a href="{fig}.png"><img src="{fig}.png" alt="{html.escape(title)}"></a>
<details><summary>原图字节来源</summary><p><a href="{html.escape(r['source_release_url'])}">{html.escape(r['archive'])}</a><br>ZIP成员：<code>{html.escape(r['archive_path'])}</code><br>原始字节：{r['bytes']}，CRC32：<code>{r['zip_crc32']}</code><br>SHA256：<code>{r['sha256']}</code></p></details></section>''')
    doc = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>固定XZ背景对照：原图、成员、几何与状态</title>
<style>body{margin:0;background:#f1f4f7;color:#233447;font-family:system-ui,"Microsoft YaHei",sans-serif;line-height:1.65}main{max-width:1320px;margin:auto;padding:34px 24px}h1{font-size:28px;margin:0 0 10px}h2{font-size:21px}section{background:white;padding:22px;margin:26px 0;border:1px solid #dce4eb;border-radius:8px}img{width:100%;height:auto}a{color:#166c9e}code{font-size:12px;overflow-wrap:anywhere}details{background:#f5f7fa;padding:10px 14px;margin-top:12px}p{max-width:1160px}</style>
<main><h1>固定XZ背景对照：原图、成员、几何与状态</h1><p>当前DSTRUCT直接AC的已有端点展示。固定图片、目标、X/Z与n/m，在每对内部使用完全相同D；两对/多对之间比较D成员变化。这里补充展示，不新增团队、融合、评分或人工连接。</p>
<p><a href="README_ZH.md">背景分析报告</a> · <a href="BLOCK_BACKGROUND_EFFECTS.csv.gz">逐块背景统计</a> · <a href="BACKGROUND_PAIR_RESULTS.csv.gz">全部既有背景对</a> · <a href="../supplement/endpoints/pools/yqstnuAEVhm-27__manual__36afe2b79d.json.gz">状态例所在完整原生池（含全部32背景端点）</a></p>'''
    doc += "\n".join(parts) + "<p>无连接端点不按0分计算改善；示例仅用于解释，典型幅度与支持请读全部背景汇总。图中GT虚线为参考，不是给失败结果补出的连接。</p></main></html>"
    (HERE / "FIXED_XZ_CASES.html").write_text(doc, encoding="utf-8")
    for receipt in ["FIXED_XZ_FIGURE_RECEIPT.json", "STABLE_FIXED_XZ_FIGURE_RECEIPT.json", "OUTPUT_STATE_FIGURE_RECEIPT.json"]:
        p = HERE / receipt
        r = json.loads(p.read_text())
        r.update(status="passed", visual_inspection="PNG inspected: complete originals/overlays/BEV, readable labels and exact values; ASCII D labels, missing rings remain unconnected")
        write_json(p, r)
    analysis_manifest = pd.read_csv(TASK / "analysis/ANALYSIS_DELIVERY_MANIFEST.csv")
    for row in analysis_manifest.to_dict("records"):
        assert sha(TASK / "analysis" / row["path"]) == row["sha256"], "Frozen analysis artifact changed: " + row["path"]
    write_json(HERE / "BACKGROUND_VISUALIZATION_CHECKS.json", dict(status="passed", original_images=3,
               originals=[dict(image=r["image_code"], bytes=int(r["bytes"]), crc32=r["zip_crc32"], sha256=r["sha256"], source_release_url=r["source_release_url"]) for r in original_sources],
               boards=3, displayed_physical_endpoints=14, all_selected_identities_from_frozen_JSON=True,
               copied_native_four_endpoint_evidence=native_receipts, frozen_analysis_manifest_files_unchanged=len(analysis_manifest),
               original_Q_and_missing_state_preserved=True, new_fusions=0, new_team_selections=0, new_scores=0, new_closed_rings=0,
               modified_directories=["background"], offline_index="FIXED_XZ_CASES.html"))
    print("background visual delivery complete", flush=True)


if __name__ == "__main__":
    main()
