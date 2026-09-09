import json
import pandas as pd
import pytest
from tools.thesis_main.data_prep.prepare_building_holdout_20260908 import prepare_index, splits


def sample():
    a=pd.DataFrame([dict(canonical_annotation_id=f'{b}-{w}',worker_id=str(w),building_id='house',image_id='image',
                        context_key=f'C2|{b}|image|manual',stage='C2',block_index=str(b),raw_condition='manual',
                        current20_member='True',historical_primary_eligibility_status='excluded' if w==6 else 'eligible',
                        legacy_exclusion_reason='old_rule' if w==6 else '') for b in [1,2] for w in range(1,7)])
    lineage=pd.DataFrame({'canonical_annotation_id':list(a.canonical_annotation_id)+['1-1'],
                          'raw_annotation_version_id':[str(i) for i in range(13)]})
    return a,lineage


def test_revisions_and_cross_block_never_inflate_counts_or_filter_old_exclusion():
    a,lineage=sample();index=prepare_index(a,lineage)
    assert len(index)==12 and index.raw_version_count.sum()==13
    assert index.worker_id.nunique()==6 and index.context_key.nunique()==2
    assert '6' in set(index.worker_id)
    with pytest.raises(ValueError):prepare_index(pd.concat([a,a.iloc[:1]]),lineage)
    with pytest.raises(ValueError):prepare_index(a,lineage.iloc[:-2])


def test_shared_permutation_fixed_building_assignment_and_floor_fraction():
    a,lineage=sample();index=prepare_index(a,lineage)
    orders,people,contexts=splits(index,replicates=2)
    people=list(people);contexts=list(contexts)
    assert len(orders)==2 and len(people)==4 and len(contexts)==8
    for p in people:
        h=json.loads(p['history_worker_ids_json']);v=json.loads(p['validation_worker_ids_json'])
        assert not set(h)&set(v) and set(h+v)==set(a.worker_id)
        assert len(h)==(4 if p['scheme']=='two_thirds' else 3)
        assert h+v==orders[p['replicate']]['worker_ids']
        sub=[r for r in contexts if r['split_id']==p['split_id']]
        assert len(sub)==2 and all(json.loads(r['history_worker_ids_json'])==h for r in sub)
    assert splits(index,replicates=2)[0]==orders
