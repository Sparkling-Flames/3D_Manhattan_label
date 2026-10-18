import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.v2_integrated_statistics_20261019 import (
    summarize, grouped, contextual_quality, pair_analysis, validate_evidence_join,
    raw_disagreement,
)


def records():
    return pd.DataFrame(dict(object_id=['a','b','c'],worker_id=['w','x','w'],
        image_id=['i','i','j'],image_code=['b-01','b-01','b-02'],building_id=['b']*3,
        condition=['manual']*3,quality_usable=[True,True,False],pool_analysis_eligible=[True]*3,
        source_pool_eligible=[True]*3,cleaning_disposition=['retained']*3,
        B8L2=[80.,60.,None],D10=[82.,61.,None],diagnostic_B8L2=[80.,60.,99.],
        source_active_time_seconds=[10.,None,30.],target_matched_time_seconds=[None]*3,
        chosen_target_id=['r','r','s'],reference_version=['v']*3,
        current_target_id=['r','r','s'],difficulty_class=['简单']*3,
        difficulty_reference_match=[True]*3,IoU3D100=[81.,60.,99.]))


def test_summary_uses_quality_mask_true_intersections_and_nonzero_missingness():
    s=summarize(records())
    assert s['B8L2_mean']==70 and s['IoU3D100_mean']==70.5
    assert s['n_quality']==2 and s['source_time_n']==2 and s['target_time_n']==0
    assert s['quality_source_time_n']==1 and s['source_time_missing']==1
    d=records();d.loc[0,'D10']=np.nan
    with pytest.raises(AssertionError):summarize(d)


def test_relative_percentile_requires_same_target_and_condition_and_peers():
    out=contextual_quality(records())
    assert out.loc[0,'B8L2_peer_residual']==20 and out.loc[0,'B8L2_rank_percentile']==100
    assert out.loc[1,'B8L2_rank_percentile']==0 and pd.isna(out.loc[2,'B8L2_rank_percentile'])
    d=records();d.loc[1,'chosen_target_id']='other'
    assert contextual_quality(d).B8L2_peer_residual.isna().all()


def test_vectorized_cross_table_preserves_weighting_and_missing_cells():
    d=records();out=grouped(d,['condition']).iloc[0];expected=summarize(d)
    for key in ['B8L2_mean','B8L2_image_equal_mean','source_time_n','target_time_n','n_quality','IoU3D100_mean']:
        assert out[key]==expected[key]
    per_image=grouped(d,['image_id','condition'])
    blank=per_image[per_image.image_id.eq('j')].iloc[0]
    assert blank.n_quality==0 and pd.isna(blank.B8L2_mean) and blank.target_time_n==0


def test_direct_pair_common_people_and_time_have_separate_denominators():
    d=records();d.loc[2,['quality_usable','B8L2','D10','IoU3D100']]=[True,40.,42.,41.]
    relation=[dict(image_a='i',image_b='j',tier='user_classified_comparable',
        physical_adopted=True,scope_comparable=True,substantive_conflict=False,user_group_ids=['G1'])]
    pairs,people=pair_analysis(d,relation)
    quality=pairs[(pairs.metric=='B8L2')&(pairs.scope_panel=='own_references')].iloc[0]
    time=pairs[(pairs.metric=='source_active_time_seconds')&(pairs.scope_panel=='own_references')].iloc[0]
    assert quality.n_paired==1 and quality.mean_delta_b_minus_a==-40
    assert time.n_paired==1 and time.mean_delta_b_minus_a==20
    assert not pairs.image_a.eq('unregistered').any()
    with pytest.raises(ValueError):pair_analysis(pd.concat([d,d.iloc[:1]]),relation)


def test_evidence_join_rejects_missing_duplicate_or_changed_identity():
    d=records();e=d[['object_id','worker_id','image_id']].copy()
    validate_evidence_join(d,e)
    with pytest.raises(AssertionError):validate_evidence_join(d,e.iloc[:2])
    with pytest.raises(AssertionError):validate_evidence_join(d,pd.concat([e,e.iloc[:1]]))
    e.loc[0,'worker_id']='other'
    with pytest.raises(AssertionError):validate_evidence_join(d,e)


def test_raw_floor_distance_does_not_fabricate_variable_structure_distance():
    d=records().iloc[:2].copy();d['pair_count']=[4,5]
    def points(xs):return [[x,y] for x in xs for y in [120.,370.]]
    objects={'a':dict(points_1024x512=points([0.,256.,512.,768.])),
        'b':dict(points_1024x512=points([0.,128.,256.,512.,768.]))}
    result=raw_disagreement(d,objects);pair=result['raw_answer_pairs'].iloc[0]
    assert pair.floor_pair_measurable and not pair.same_pair_count
    assert pair.structural_status=='different_count_not_computed'
    assert pd.isna(pair.structural_correspondence_distance)
    objects['b']['points_1024x512']=None
    pair=raw_disagreement(d,objects)['raw_answer_pairs'].iloc[0]
    assert not pair.floor_pair_measurable and pd.isna(pair.R_union_normalized)
    objects['b']['points_1024x512']=points([0.,256.,512.,1200.])
    pair=raw_disagreement(d,objects)['raw_answer_pairs'].iloc[0]
    assert not pair.floor_pair_measurable and pd.isna(pair.R_union_normalized)
