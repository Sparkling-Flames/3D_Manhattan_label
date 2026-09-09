import pandas as pd
import pytest
from tools.thesis_main.data_prep.prepare_building_convergence_20260908 import context_rows, building_rows, candidate_rows, link_contexts


def data():
    return pd.DataFrame([dict(canonical_annotation_id=f'{b}-{w}',context_key=f'C2|{b}|image|manual',
        image_id='image',building_id='building',stage='C2',block_index=str(b),raw_condition='manual',
        worker_id=str(w),current20_member='True',raw_geometry_computable='True') for b in [1,2] for w in [1,2,3]])


def test_independent_counts_and_building_union_not_per_image_support():
    a=data();c=context_rows(a)
    assert len(c)==2 and c.worker_count.tolist()==[3,3]
    assert c.max_equal_disjoint_k.tolist()==[1,1]
    b=building_rows(c,a)
    assert b.iloc[0].building_union_worker_count==3 and b.iloc[0].contexts==2 and b.iloc[0].images==1
    with pytest.raises(ValueError):context_rows(pd.concat([a,a.iloc[:1]]))
    bad=a.copy();bad.loc[0,'canonical_annotation_id']='another_version'
    with pytest.raises(ValueError):context_rows(pd.concat([a,bad.iloc[:1]]))


def test_candidates_zero_and_unknown_fields_explicit():
    a=data();images=pd.DataFrame([dict(image_id='candidate',building_id='building',population_role='candidate_without_historical_annotation')])
    c=candidate_rows(images,a)
    assert c.iloc[0].historical_response_count==0 and c.iloc[0].has_historical_building
    bad=a.copy();bad.loc[0,'current20_member']='unknown'
    with pytest.raises(ValueError):context_rows(bad)
    with pytest.raises(ValueError):candidate_rows(images.assign(image_id='image'),a)


def test_legacy_context_order_and_ambiguous_block_never_guessed():
    a=data();row=dict(stage='C2',condition='manual',image='image',context='C2|2|manual|image')
    result=link_contexts(pd.DataFrame([row]),context_rows(a))
    assert result.iloc[0].context_key=='C2|2|image|manual'
    result=link_contexts(pd.DataFrame([{k:v for k,v in row.items() if k!='context'}]),context_rows(a))
    assert result.iloc[0].context_link_status=='ambiguous_context' and result.iloc[0].context_key==''
    with pytest.raises(ValueError,match='metadata_conflict'):
        link_contexts(pd.DataFrame([dict(context_key='C2|2|image|manual',stage='C2',image_id='wrong')]),context_rows(a))
