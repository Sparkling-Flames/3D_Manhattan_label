import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from tools.thesis_main.analysis import quality_coarse_review_20261015 as q


def test_selection_is_fixed_and_preserves_target_holds():
    rows = q.select_rows()
    assert rows.record_id.is_unique and len(rows) == 44
    assert rows.phase.value_counts().to_dict() == {'ordinary': 32, 'doorway': 12}
    assert not rows.same_target_quality_hold.any() and not rows.original_holdout.any()
    assert rows.loc[rows.phase == 'ordinary', 'image_id'].nunique() == 28
    assert rows.loc[rows.phase == 'doorway', 'image_id'].nunique() == 10
    assert rows.record_id.tolist() == q.select_rows().record_id.tolist()
    source = pd.read_csv(q.TABLE).set_index('record_id')
    for _, row in rows.iterrows():
        assert row.reference_id == source.loc[row.record_id, 'reference_id']
        assert row.WQ == source.loc[row.record_id, 'WQ']


def test_display_round_trip_and_receipt_bindings():
    data = json.loads((q.OUT / 'manifest.json').read_text(encoding='utf-8'))
    assert len(data['cards']) == 44 and data['schema'] == q.SCHEMA
    geos = json.loads((q.OUT / 'geometries.json').read_text(encoding='utf-8'))
    for card in data['cards']:
        b = card['bindings'][0]
        assert (q.OUT / b['photo']).resolve().is_file()
        for key in ['object_id', 'reference_object_id']:
            g = geos[b[key]]
            a = np.array(g['points_1024x512'])
            for ring, expected in [('top3d', a[::2]), ('bottom3d', a[1::2])]:
                p = np.array(g[ring])
                xy = np.c_[(np.arctan2(p[:, 0], -p[:, 2]) / (2*np.pi) + .5)*1024,
                           (-np.arctan2(p[:, 1], np.hypot(p[:, 0], p[:, 2])) / np.pi + .5)*512]
                dx = (xy[:, 0] - expected[:, 0] + 512) % 1024 - 512
                assert np.max(np.abs(dx)) < 1e-8
                assert np.max(np.abs(xy[:, 1] - expected[:, 1])) < 1e-8
    assert 'id="scores" hidden' in (q.OUT / 'REVIEW.html').read_text(encoding='utf-8')


def test_receipt_round_trip_and_wrong_reference_rejected():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');
const api=require('./tools/thesis_main/analysis/quality_coarse_review_20261015.js');
const data=JSON.parse(fs.readFileSync('./research/quality/quality_coarse_review_20261015/manifest.json','utf8'));
const state=api.fresh(data),id=data.cards[0].id;
assert(Object.values(state.decisions).every(a=>a.grade===null && a.score_revealed_at===null));
let result=api.receipt(state,data);
assert(Object.values(result.decisions).every(a=>a.status==='not_reviewed'));
state.decisions[id].grade='scope';state.decisions[id].comment='目标不同，不算低质量';
result=api.receipt(state,data);
const restored=api.validate(JSON.parse(JSON.stringify(result)),data);
assert.equal(restored.decisions[id].grade,'scope');
assert.equal(result.decisions[id].phase,'ordinary');
assert.equal(result.decisions[id].bindings[0].record_id,data.cards[0].bindings[0].record_id);
const tampered=JSON.parse(JSON.stringify(result));tampered.decisions[id].bindings[0].reference_object_id='wrong';
assert.throws(()=>api.validate(tampered,data),/绑定/);
const invalid=JSON.parse(JSON.stringify(result));invalid.decisions[id].grade='great';
assert.throws(()=>api.validate(invalid,data),/档位/);
assert.equal(restored.decisions[data.cards[32].id].grade,null);
for(const grade of ['good_average','average_poor']){
  state.decisions[id].grade=grade;
  const exported=api.receipt(state,data);
  assert.equal(exported.grade_scale,'five_level_transition_v1');
  assert.equal(api.validate(JSON.parse(JSON.stringify(exported)),data).decisions[id].grade,grade);
}
for(const grade of ['good','average','poor']){
  state.decisions[id].grade=grade;
  const legacy=api.receipt(state,data);delete legacy.grade_scale;
  assert.equal(api.validate(legacy,data).decisions[id].grade,grade);
}
console.log('receipt round-trip, missing answers, separate phases and reference binding passed');
"""
    subprocess.run(['node', '-e', script], cwd=q.ROOT, check=True, capture_output=True)
