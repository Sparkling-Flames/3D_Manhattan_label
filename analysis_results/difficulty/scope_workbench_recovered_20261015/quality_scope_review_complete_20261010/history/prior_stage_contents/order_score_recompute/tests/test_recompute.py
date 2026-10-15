"""Portable regression suite; no repository, network, or state mutation required."""
import copy,json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recompute import read,project,score_geometry,area_diagnostics
OLD=read(ROOT/'inputs/old_formal.json');NEW=read(ROOT/'inputs/new_formal.json')
OM={o['object_id']:o for o in OLD['objects']};NM={o['object_id']:o for o in NEW['objects']}
FULL=read(ROOT/'results/full_old_new_results.json');RECEIPT=read(ROOT/'inputs/confirmed_orders.json')
GT=read(ROOT/'results/fixed_GT.json')

def test_exactly_three_changed_effective_objects():
    assert {k for k,v in OLD['object_digests'].items() if NEW['object_digests'][k]!=v}==set(RECEIPT['records'])
    assert len(OLD['object_digests'])==3441

def test_no_source_GT_or_gate_change():
    assert OLD['protected_object_digests']==NEW['protected_object_digests']
    gid=NEW['image']['references']['gt_original'];assert OM[gid]==NM[gid]

def test_authoritative_commit_identity():
    assert OLD['source_commit']=='fae48e69aa4ae879b8268c34afb8f8221ee53022'
    assert NEW['source_commit']=='24360ad8544d76d8aba18a8e641f784a76ca0d42'

@pytest.mark.parametrize('oid',list(RECEIPT['records']))
def test_actual_confirmed_order_not_sort_removed(oid):
    bound=json.loads(RECEIPT['records'][oid]['binding']);order=RECEIPT['records'][oid]['order']
    assert NM[oid]['points_1024x512']==[bound['points'][j] for i in order for j in (2*i,2*i+1)]
    p=project(NM[oid]);old=project(OM[oid])
    for k in ('top3d','bottom3d'):assert np.array_equal(p[k],np.asarray(old[k])[order])
    assert score_geometry(p,GT)['quality_score']==FULL[oid]['new']['result']['quality_score']
    assert FULL[oid]['new']['result']['quality_score']<FULL[oid]['old']['result']['quality_score']-10

def test_projection_matches_existing_frozen_convention():
    anchors=read(ROOT/'inputs/frozen_projection_anchors.json')['records'];assert len(anchors)==21
    for r in anchors:
        g=project(r)
        for k in ('top3d','bottom3d'):assert np.allclose(g[k],r[k],rtol=0,atol=1e-12)

def test_fixed_parameters_and_samples():
    frozen=read(ROOT/'frozen_engine/frozen_parameters.json')
    for versions in FULL.values():
        for r in versions.values():
            q=r['result'];assert q['parameters']==frozen['parameters']
            assert q['numerical_settings']=={'spherical_samples':2048,'height_samples':4096}

def test_unaffected_records_identical():
    other=[k for k in FULL if k not in RECEIPT['records']];assert len(other)==3
    for k in other:assert FULL[k]['old']==FULL[k]['new']

def test_score_deductions_conserve_total():
    for versions in FULL.values():
        for r in versions.values():
            m=r['result']['metrics'];assert abs(sum(m[k] for k in ('range_deduction_points','boundary_deduction_points','height_deduction_points','intrinsic_deduction_points'))+r['result']['quality_score']-100)<1e-10

def test_all_scores_diagnostic_only():
    for o in NM.values():
        if o['object_kind']=='annotation':assert o['main_quality_gate']['status']=='hold_scene_or_reference'
    s=read(ROOT/'results/image_summary.json');assert s['official_score_count']==0 and not s['all_corpus_recomputed']

def test_old_saved_area_metrics_reproduced():
    for r in read(ROOT/'inputs/saved_old_image_scope_evidence.json')['observations']:
        metrics=area_diagnostics(project(OM[r['object_id']]),GT)
        for k in ('symmetric_difference','excess','missing'):assert abs(r['selected_gt_metrics'][k]-metrics[k])<1e-12

def test_sensitivity_and_no_sort_negative_control():
    r=read(ROOT/'results/independent_validation.json');assert r['max_abs_sampling_Q_change']<0.0002
    assert r['deliberate_x_sort_restores_old_scores_for_all_three']

def test_frozen_engine_checksums():
    import hashlib
    for r in read(ROOT/'results/source_provenance.json')['frozen_engine_unchanged_files']:
        relative=r['file'].split('research/quality_scope_comparison_20261010/')[1]
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==r['sha256']
