"""Publication filters must retain the accepted support and target identities."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/data/releases/v2.1/paper_evidence_20261030'


def test_publication_support_and_effects():
    half = pd.read_csv(OUT / 'F01_half_team_DATA.csv')
    assert len(half) == 85 and half.CB.notna().sum() == 83
    assert (half.CB > 0).sum() == 76
    assert np.isclose(half.gap_sym.mean(), 3.3971346197)
    same = pd.read_csv(OUT / 'F04_same_room_replacement_DATA.csv')
    assert same.groupby('n').size().to_dict() == {10: 19, 14: 2}
    assert not same.duplicated(['n', 'pair_key']).any()
    assert (same.loc[same.n.eq(10), 'CB_mean'] > 0).sum() == 19
    qt = pd.read_csv(OUT / 'F08_qt_selection_DATA.csv')
    n5 = qt[qt.n.eq(5)].set_index('metric')
    assert n5.loc['delta_q','boot_lo'] < 0 < n5.loc['delta_q','boot_hi']
    assert np.isclose(n5.loc['labor_ratio','value'], .813430, atol=1e-6)


def test_image_difficulty_reuses_current_grade():
    mapping = pd.read_csv(OUT / 'IMAGE_DIFFICULTY_MAPPING.csv')
    source = json.loads((ROOT / 'research/data/releases/v2.1/difficulty_records.json').read_text(encoding='utf8'))
    grades = {r['image']: r['current_class'] for r in source['records']}
    assert len(mapping) == 31 and mapping.image.nunique() == 28
    assert mapping.groupby('image').image_difficulty.nunique().eq(1).all()
    assert all(r.image_difficulty == grades[r.image] for r in mapping.itertuples())


def test_figure_formats_and_source_index():
    index = pd.read_csv(OUT / 'FIGURE_INDEX.csv')
    assert len(index) == 14
    for row in index.itertuples():
        for p in row.source_tables.split(';'):
            assert (ROOT / p).is_file()
        for ext in ('png','pdf','svg'):
            assert (OUT / f'{row.figure}.{ext}').stat().st_size > 1000
        with Image.open(OUT / f'{row.figure}.png') as im:
            assert abs(im.info['dpi'][0] - 300) < 1
    checks = json.loads((OUT / 'CHECKS.json').read_text(encoding='utf8'))
    assert checks['completeness']['modules'] == 18
    assert not checks['completeness']['unresolved_references']
    assert checks['review']['missing_image_grades'] == 0
