from __future__ import annotations
import hashlib, json, sys
from itertools import combinations
from math import comb
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from analyze_profiles import load, higher_mask, admissible_halves, fit_lobo
from composition_kernel import basis_of, inclusion_probability, additive_measures, threshold
from paired_replacement import paired_effects

def test_four_source_blobs_match_exactly():
    checks=json.loads((ROOT/'inputs/transfer_checks.json').read_text())
    assert len(checks)==4
    for ch in checks:
        b=(ROOT/'inputs'/ch['file']).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==ch['expected_git_blob_sha']

def test_lobo_calibration_target_isolation():
    f,y=load('matrix_original_iou.csv');b=f.building.to_numpy()
    target=b[0];train=b!=target
    hi=higher_mask(y[train].mean(0))
    z=y.copy();z[~train]=np.random.default_rng(2).random(z[~train].shape)
    assert np.array_equal(hi,higher_mask(z[train].mean(0)))
    # The target's own held-out evaluation can change; it must not change its training group.
    assert not np.array_equal(y[~train],z[~train])

def test_cutoff_ties_are_not_broken_by_worker_id():
    x=np.array([1.,2.,2.,3.])
    assert higher_mask(x) is None
    a=admissible_halves(x)
    assert len(a)==2 and np.all(a.sum(1)==2)
    assert np.all(a[:,3]) and not np.any(a[:,0])

def test_disjoint_design_keeps_all_splits_and_ties():
    d=pd.read_csv(ROOT/'results/disjoint_building_splits.csv')
    for _,p in d.groupby('policy'):
        assert len(p)==35
        assert ((p.admissible_halves_a>1)|(p.admissible_halves_b>1)).sum()==1
        assert np.median(p.same_half_fraction)==pytest.approx(14/24)
        for r in p.itertuples():
            assert not set(r.buildings_a.split('|')) & set(r.buildings_b.split('|'))

def test_hypergeometric_kernel_all_small_compositions_vs_enumeration():
    NH,NL=3,2
    for mH in range(NH+1):
        for mL in range(NL+1):
            v=np.array([1]*mH+[0]*(NH-mH)+[1]*mL+[0]*(NL-mL))
            for h in range(NH+1):
                for l in range(NL+1):
                    if h+l==0:continue
                    counts=[sum(v[list(a)+list(b)]) for a in combinations(range(NH),h)
                            for b in combinations(range(NH,NH+NL),l)]
                    for method in ('mv50','mv_strict'):
                        empirical=np.mean(np.asarray(counts)>=threshold(h+l,method))
                        assert inclusion_probability(NH,NL,mH,mL,h,l,method)==pytest.approx(empirical,abs=1e-14)

def test_area_decomposition_includes_reference_outside_union():
    records=[dict(worker='a',footprint=list(box(0,0,1,1).exterior.coords)[:-1]),
             dict(worker='b',footprint=list(box(1,0,2,1).exterior.coords)[:-1])]
    basis=basis_of(records,list(box(0,0,3,1).exterior.coords)[:-1])
    q=np.full(len(basis['area']),.3)
    m=additive_measures(basis,q)
    assert m['expected_under_h2']>1.
    assert m['expected_symdiff_h2']==pytest.approx(m['consensus_field_bias_h2']+.5*m['member_symdiff_h2'])

def test_iou_of_expected_areas_is_not_expected_iou():
    # Output areas 1 or 4, both contain a unit reference: IoUs 1 and 1/4.
    expected_iou=(1+1/4)/2
    ratio=1/((1+4)/2)
    assert expected_iou==.625 and ratio==.4 and expected_iou!=ratio

def test_source_compositions_reproduce_and_counts_complete():
    c=pd.read_csv(ROOT/'results/composition_30_field_checks.csv')
    assert len(c)==30 and c.absolute_difference.max()<1e-12
    d=pd.read_csv(ROOT/'results/one_image_k4_exact.csv')
    for _,g in d.groupby('method'):
        assert list(g.n)==[495,2640,4356,2640,495]
        assert g.n.sum()==comb(24,4)
        assert g.q_enum_max_difference.max()<1e-12

def test_actual_identical_footprints_keep_all_24_votes():
    d=json.loads((ROOT/'results/composition_kernel_summary.json').read_text())
    assert d['candidate_n']==24 and d['unique_footprints']==19
    assert ['P003','P008','P009'] in d['identical_footprint_groups']

def test_equal_iou_does_not_imply_equal_output_geometry():
    d=json.loads((ROOT/'results/composition_kernel_summary.json').read_text())['toys']
    assert d['equal_score_iou_a']==pytest.approx(d['equal_score_iou_b'])
    assert d['iou_sd']==0 and d['independent_pair_expected_symdiff_h2']>0
    assert d['stable_wrong_variation_h2']==0 and d['stable_wrong_iou']<1

def test_fixed_context_replacement_recovers_additive_worker_contrast():
    members=np.array(list(combinations(range(5),3)))
    w=np.array([.1,.2,.3,.4,.5])
    r=paired_effects(members,w[members].sum(1),[str(j) for j in range(5)])
    for row in r.itertuples():
        assert row.common_context_n==comb(3,2)
        assert row.mean_a_minus_b==pytest.approx(w[int(row.worker_a)]-w[int(row.worker_b)])
        assert row.sd_a_minus_b<1e-14

def test_fixed_context_replacement_refuses_missing_subsets():
    members=np.array(list(combinations(range(5),3)))[:-1]
    with pytest.raises(ValueError,match='all distinct'):
        paired_effects(members,np.ones(len(members)),list('abcde'))
