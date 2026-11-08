import json
import gzip
import re
import numpy as np
import pandas as pd

from tools.thesis_main.analysis.quality_validation_followup_20261107 import OUT, onset
from tools.thesis_main.analysis.build_independent_review_20261107 import HERE, packet
from tools.thesis_main.analysis.collect_independent_review_20261107 import validate_answer
import pytest


def test_onset_observation_window_and_missing():
    assert onset(np.ones(10),np.full(10,64),10,2,64)==3
    assert np.isnan(onset(np.ones(7),np.full(7,64),7,2,64))
    a=np.ones(10);a[-1]=np.nan
    assert np.isnan(onset(a,np.full(10,64),10,2,64))
    assert np.isnan(onset(np.ones(10),np.full(10,63),10,2,64))


def test_exact_support_all_scales():
    f=pd.read_csv(OUT/'HALF_COMMON_EVENTS.csv.gz')
    for _,g in f.groupby(['version','n']):
        sets=[set(x.loc[x.GA.notna(),'event_id']) for _,x in g.groupby('metric')]
        assert all(s==sets[0] for s in sets)
    n=pd.read_csv(OUT/'NATURAL_FIXED_PATH_CHANGES.csv')
    assert n.groupby(['pool_id','interval','statistic']).paired_paths.nunique().eq(1).all()
    assert n[n.interval.eq('20->30')].image.nunique()==171


def test_measured_control_identity_and_local_height():
    c=pd.read_csv(OUT/'CONTROL_RESPONSE_MATRIX.csv')
    assert len(c)==96
    assert np.allclose(c[c.severity.eq(0)].B8L2,100,atol=1e-6)
    assert np.allclose(c[c.family.eq('collinear_split')].B8L2,100,atol=1e-6)
    l=c[c.family.eq('local_height')&c.severity.gt(0)]
    assert l.B8L2.lt(100).all() and np.allclose(l.IoU3D100,100,atol=1e-4)


def test_public_packet_blinding_self_exclusion_and_flip():
    with gzip.open(HERE/'CASES_PRIVATE.json.gz','rt',encoding='utf-8') as f:cases=json.load(f)
    worker=cases[2]['excluded_workers'][0]
    a,key=packet(cases,'R01',worker)
    blocked={c['public']['id'] for c in cases if worker in c['excluded_workers']}
    assert not blocked.intersection(c['id'] for c in a)
    public=json.dumps([{k:v for k,v in c.items() if k!='image_data'} for c in a])
    for forbidden in ['algorithm_same','excluded_workers','team_key','member_workers','reference_version']:
        assert forbidden not in public
    assert not re.search(r'W\d{3}',public)
    original={c['public']['id']:c['public'] for c in cases};keys={k['case_id']:k for k in key}
    for c in a:
        o=original[c['id']];flip=keys[c['id']]['flip']
        assert c['left']==o['right' if flip else 'left']
        if c['type']=='correspondence':assert c['pair_indices']==o['pair_indices'][::-1 if flip else 1]
    formal={c['public']['image'] for c in cases if not c['public']['practice']}
    assert all(c['public']['image'] not in formal for c in cases if c['public']['practice'])


def test_preview_and_case_denominators():
    text=(HERE/'index.html').read_text(encoding='utf-8')
    p=json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>',text,re.S)[1])
    assert p['formal'] is True and p['packet_id']=='R00'
    assert '本人的独立评阅编号' in text
    assert sum(c['type']=='quality' and not c['practice'] for c in p['cases'])==30
    assert sum(c['type']=='correspondence' and not c['practice'] for c in p['cases'])==0
    assert len({c['id'] for c in p['cases']})==30
    assert 'id="confidence"' not in text and '练习' not in text
    assert '查看质量分数' in text and 'id="scopeBox"' not in text
    assert 'id="leftbev"' in text and 'id="left3d"' in text and 'id="spatialMode"' not in text


def test_answers_reject_preview_and_unassigned_and_align_sides():
    assignment={'R01':{'key':[{'case_id':'Q001','flip':True}]}}
    a=dict(schema='overall_quality_review_20261107_v3',reviewer='S_TEST',packet_id='R01',formal=False,case_ids=['Q001'],answers={'Q001':{'grades':{'left':'good','right':'poor'}}})
    with pytest.raises(AssertionError):validate_answer(a,assignment)
    a['formal']=True
    assert validate_answer(a,assignment)[0]['right_grade_initial']=='good'
    a['answers']['Q002']={'grades':{'left':'good','right':'poor'}}
    with pytest.raises(AssertionError):validate_answer(a,assignment)


def test_current_sampling_and_score_reveal_contract():
    from collections import Counter
    with gzip.open(HERE/'CASES_PRIVATE.json.gz','rt',encoding='utf-8') as f:cases=json.load(f)
    quality=[c for c in cases if c['public']['type']=='quality']
    assert Counter(c['public']['difficulty'] for c in quality)=={'简单':9,'中等':9,'困难':9,'门洞单列':3}
    assert all(c['public']['condition']=='manual' and not c['public']['practice'] for c in cases)
    assert sum(c['public']['doorway'] for c in quality)==3
    assert any(c['public']['multi_space'] and not c['public']['doorway'] for c in quality)
    root=OUT.parents[1]
    # Explicitly verify selected doorway answers are in the current retained cohort.
    pools=json.loads((root/'data/doorway_review_20261030/screen439_results_20261031/POOLS.json').read_text(encoding='utf-8'))
    retained={r for p in pools if p['version']=='after_screen' and not p['sensitivity'] for r in p['records']}
    for c in quality:
        if c['public']['doorway']:assert {c['private']['left_object'],c['private']['right_object']}<=retained
    assignment={'R00':{'key':[{'case_id':'Q001','flip':True}]}}
    a=dict(schema='overall_quality_review_20261107_v3',reviewer='test',packet_id='R00',formal=True,case_ids=['Q001'],answers={'Q001':{'grades':{'left':'poor','right':'good'},'score_viewed':True}})
    with pytest.raises(AssertionError):validate_answer(a,assignment)
    a['answers']['Q001']['before_score']={'grades':{'left':'good','right':'medium'},'scope':'different_valid','defects':{'left':['position'],'right':['none']}}
    r=validate_answer(a,assignment)[0]
    assert r['right_grade_initial']=='good' and r['right_grade_final']=='poor'


def test_defects_exclusive_and_initial_side_mapping():
    from tools.thesis_main.analysis.collect_independent_review_20261107 import validate_defects
    for bad in [{'left':['none','height']},{'right':['unknown','none']},{'left':['height','height']},{'left':['invented']}]:
        with pytest.raises(AssertionError):validate_defects(bad)
    a=dict(schema='overall_quality_review_20261107_v3',reviewer='test',packet_id='R00',formal=True,case_ids=['Q001'],answers={'Q001':{'grades':{'left':'good','right':'medium'},'defects':{'left':['none'],'right':['height']},'score_viewed':True,'before_score':{'grades':{'left':'good','right':'medium'},'defects':{'left':['position','height'],'right':['none']}}}})
    r=validate_answer(a,{'R00':{'key':[{'case_id':'Q001','flip':True}]}})[0]
    assert json.loads(r['right_defects_initial'])==['position','height'] and json.loads(r['right_defects_final'])==['none']
    assert r['valid_judgment']
