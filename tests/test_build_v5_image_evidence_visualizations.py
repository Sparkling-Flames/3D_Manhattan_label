from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.full_uncertainty.build_v5_image_evidence_visualizations import ROOT, build


def test_build_v5_image_evidence_visualizations(tmp_path: Path) -> None:
    v5 = ROOT / "analysis_results/full_uncertainty_data_mining_20260821_v5"
    cases = build(v5, tmp_path, png=False)

    assert len(cases) == 16
    assert len({case.category for case in cases}) == 8
    assert all(1 <= sum(other.category == case.category for other in cases) <= 2 for case in cases)
    html = (tmp_path / "可视化总览.html").read_text(encoding="utf-8")
    assert "模型初始预标注" in html
    assert "GT 参考" in html
    assert "冻结有效操作时间" in html
    assert "不使用 Lead time 回填" in html
    assert "font-family:\"Microsoft YaHei UI\"" in html
    assert ">inf<" not in html
    index = pd.read_csv(tmp_path / "案例索引.csv", encoding="utf-8-sig")
    assert len(index) == 16
    assert set(index["案例类型"]) == {case.category for case in cases}
    assert len(list((tmp_path / "assets").glob("*.jpg"))) >= 8
