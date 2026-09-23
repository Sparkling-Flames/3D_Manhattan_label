"""离线审核页与已计算数值的最小身份绑定检查。"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_results/consensus_visual_review_20260923"


def payload(path, prefix):
    text = path.read_text(encoding="utf-8")
    assert text.startswith(prefix) and text.endswith(";\n")
    return json.loads(text[len(prefix):-2])


def test_full_index_and_case_binding():
    data = payload(OUT / "data.js", "window.REVIEW_DATA=")
    rows = data["rows"]
    assert data["manifest"]["contract_version"] == "consensus_research_20260923_v1"
    assert len(rows) == len({r["id"] for r in rows}) == 3019
    assert len({r["image_id"] for r in rows}) == len(list((OUT / "cases").glob("*.js"))) == 259
    assert sum(r["known_wrong"] for r in rows) == 2
    assert sum(r["modes"]["curve"]["failure"] is not None for r in rows) == 89

    row = next(r for r in rows if r["modes"]["curve"]["quality"]["gt_revised"]["status"] == "ok")
    case = payload(OUT / "cases" / (row["image_id"] + ".js"), "window.REVIEW_CASE=")
    item = next(a for a in case["annotations"] if a["canonical_annotation_id"] == row["id"])
    assert case["image_id"] == row["image_id"]
    assert (OUT / case["image_src"]).resolve().is_file()
    assert len(item["views"]["curve"]["bands"]) == 512
    assert item["views"]["curve"]["centroid"]["area_pixels"] > 0
    assert item["quality"]["curve"]["gt_revised"]["iou"] == row["modes"]["curve"]["quality"]["gt_revised"]["iou"]
    assert {r["name"] for r in case["references"]} == {"gt_original", "gt_revised", "hohonet", "bilayout_enclosed", "bilayout_extended"}
    assert item['screening']['cues'] == row['screening']['cues']
    assert data['manifest']['screening']['candidate_count'] == sum(bool(r['screening']['cues']) for r in rows)
    # 不能再以IoU作为唯一入口；高IoU的结构候选依然进入队列。
    assert any('singleton' in r['screening']['cues'] and 'iou' not in r['screening']['cues'] for r in rows)
    assert any('geometry' in r['screening']['cues'] and 'iou' not in r['screening']['cues'] for r in rows)


def test_screening_geometry_and_missing_cluster_are_not_quality_verdicts(tmp_path):
    import gzip
    from tools.thesis_main.analysis.build_consensus_visual_review_20260923 import screening
    with gzip.open(tmp_path / 'pointsets.json.gz', 'wt', encoding='utf-8') as f:
        json.dump([], f)
    (tmp_path / 'memberships.json').write_text('[]', encoding='utf-8')
    row = dict(canonical_annotation_id='a', image_id='i', raw_condition='manual', known_wrong=False,
               pairs_shared_x=[[[100,100],[100,200]],[[400,100],[400,350]],[[700,100],[700,350]]],
               effective_points_1024x512=[], links_zero_based=[[0,1],[2,3],[4,5]])
    result = screening([row], tmp_path)['a']
    assert result['cues'] == ['geometry']
    assert 'wrong_hemisphere' in result['geometry']['issues']
    assert result['cluster_coverage'] == 'not_covered_or_changed'
    assert 'verdict' not in result
