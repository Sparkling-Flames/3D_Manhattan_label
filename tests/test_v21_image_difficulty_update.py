import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.recompute_v21_image_difficulty_20261030 import block_direction

ROOT=Path(__file__).resolve().parents[1]
EXT=ROOT/'research/data/releases/v2.1/admitted_space_extension'
OUT=EXT/'image_difficulty_20261030'

def test_grade_update_cannot_change_quality_or_team_identity():
    old=pd.read_csv(EXT/'natural_analysis/UPDATED_CURVES.csv.gz',low_memory=False)
    new=pd.read_csv(OUT/'natural_analysis/UPDATED_CURVES.csv.gz',low_memory=False)
    pd.testing.assert_frame_equal(old.drop(columns='difficulty'),new.drop(columns='difficulty'))
    assert new.difficulty.isin(['简单','中等','困难']).all()
    raw=pd.DataFrame(json.loads((OUT/'ANALYSIS_RECORDS.json').read_text(encoding='utf8')))
    before=pd.DataFrame(json.loads((EXT/'ANALYSIS_RECORDS.json').read_text(encoding='utf8')))
    pd.testing.assert_frame_equal(raw.drop(columns='current_class'),before.drop(columns='current_class'))
    assert len(raw)==231

def test_updated_block_legality_requires_known_homogeneous_classes():
    row=dict(X='a|b',Y='c|d',Z='e|f')
    roster=dict(a='C1',b='C1',c='C1',d='C1',e='C2',f='C2')
    assert block_direction(row,roster)=='C1→C2'
    roster['b']='C2';assert block_direction(row,roster)==''
    roster['b']='C1';del roster['f'];assert block_direction(row,roster)==''

def test_frozen_and_updated_half_support_are_distinct():
    s=pd.read_csv(OUT/'HALF_SUMMARY.csv')
    a=s[(s.n==14)&s.scope.eq('frozen_design')].iloc[0]
    b=s[(s.n==14)&s.scope.eq('updated_labels_legal_subset')].iloc[0]
    assert a.events==197 and a.valid_images==83
    assert b.events==147 and b.valid_images==67
    assert np.isclose(a.gap_sym,3.3971346197)
    assert b.gap_sym>0 and b.positive_sym>b.valid_images/2

def test_lobo_history_excludes_target_building():
    raw=pd.read_csv(OUT/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    history=pd.read_csv(OUT/'classification/HISTORY_ALL_LOBO.csv.gz')
    for fold,g in history[history.heldout_building.ne('ALL')].groupby('heldout_building'):
        expected=raw[raw.history_eligible&raw.condition.eq('manual')&raw.building.ne(fold)].groupby('worker_id').image_id.nunique()
        actual=g.set_index('worker_id').m_all_images
        np.testing.assert_array_equal(actual.to_numpy(),expected.reindex(actual.index).fillna(0).to_numpy())

def test_background_uses_legal_events_at_both_sizes():
    links=pd.read_csv(OUT/'MATCHED_BACKGROUND_LINKS.csv')
    events=pd.read_csv(OUT/'HALF_EVENT_LEGALITY.csv.gz',low_memory=False)
    legal=set(events.loc[events.updated_class_legal,'event_id'])
    assert set(links.event_id_14)<=legal and set(links.event_id_20)<=legal
    assert len(links)==75

def test_updated_exports_are_complete():
    from PIL import Image
    for scope in ['primary','semi','other']:
        assert (OUT/'composition'/scope/'COMPLETE.json').is_file()
    index=pd.read_csv(OUT/'figures/INDEX.csv')
    assert len(index)==4
    for row in index.itertuples():
        for ext in ['pdf','svg','png']:
            assert (OUT/'figures'/f'{row.name}.{ext}').stat().st_size>1000
        with Image.open(OUT/'figures'/f'{row.name}.png') as im:
            assert abs(im.info['dpi'][0]-300)<1
