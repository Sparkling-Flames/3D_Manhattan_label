"""Verify selection, provenance, and paired estimands against the frozen study."""
import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.q_only_exchange_v21_20261031 import OUT,UP,ROOT,members,rows,choose,aggregate,image_means,labor


def test_selection_and_strict_replacement():
    links=pd.read_csv(OUT/'DESIGN_LINKS.csv');candidates=pd.read_csv(OUT/'CANDIDATES.csv');req=pd.read_csv(OUT/'TEAM_REQUESTS.csv').set_index('team_key')
    labels=pd.read_csv(OUT/'LABEL_SNAPSHOT.csv').set_index(['heldout_building','worker_id'])
    assert len(links)==208*5 and len(req)==670
    for eid,d in links.groupby('event_id'):
        base=d.iloc[0];D,X,Y,Z=[members(base[k]) for k in ['D','X','Y','Z']]
        assert not any(a&b for i,a in enumerate([D,X,Y,Z]) for b in [D,X,Y,Z][i+1:])
        for ws,cl in [(X,'C2'),(Y,'C2'),(Z,'C3')]:
            assert all(labels.loc[(base.building,w),'class_id']==cl for w in ws)
        cand=candidates[candidates.event_id.eq(eid)].set_index('worker_id')
        assert Z<=set(cand.index) and not set(cand.index)&(D|X|Y)
        for r in d.itertuples():
            ws=members(req.loc[r.team_key,'members']);assert len(ws)==r.n and D<=ws and len(ws-D)==7
            if r.policy.startswith('Q_'):
                col='raw_q' if r.policy=='Q_RAW' else 'peer_q'
                assert ws-D==set(choose(cand.index,cand,col,7))
    # Deterministic equal-score tie, independent of input ordering.
    h=pd.DataFrame({'raw_q':[5.,5.,9.]},index=['W2','W1','W3'])
    assert choose(['W2','W3','W1'],h,'raw_q',2)==['W3','W1']


def test_history_recomputed_without_target_building():
    raw=pd.read_csv(UP/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    raw=raw[raw.history_eligible&raw.condition.eq('manual')]
    history=pd.read_csv(OUT/'HISTORY_LOBO.csv')
    for fold,h in history.groupby('heldout_building'):
        d=raw[raw.building.ne(fold)].dropna(subset=['B8L2','B8L2_peer']);assert not d.building.eq(fold).any()
        # Explicit building loops independently check the groupby implementation.
        result={}
        for w,g in d.groupby('worker_id'):
            means=[]
            for _,b in g.groupby('building'):
                means.append(b.groupby(['image_id','reference_id']).B8L2.mean().groupby(level=0).mean().mean())
            result[w]=np.mean(means)
        for r in h.itertuples():assert abs(r.raw_q-result[r.worker_id])<1e-10
        expected=aggregate(d,'B8L2_peer')
        assert np.allclose(h.set_index('worker_id').peer_q.sort_index(),expected.sort_index(),atol=1e-10)


def test_exact_endpoint_identity_and_scalar_reuse():
    req=pd.read_csv(OUT/'TEAM_REQUESTS.csv').set_index('team_key');ep={r['team_key']:r for r in rows(OUT/'ENDPOINTS.jsonl.gz')}
    pools={p['pool_id']:p for p in json.loads((OUT/'INPUT_POOLS.json').read_text(encoding='utf8'))['images']}
    assert set(req.index)==set(ep)
    for k,r in ep.items():
        q=req.loc[k];by={x['worker_id']:x['object_id'] for x in pools[q.pool_id]['records']}
        assert set(r['member_workers'])==members(q.members)
        assert set(r['member_object_ids'])=={by[w] for w in members(q.members)}
        assert (r['reference_id'],r['reference_version'])==(q.reference_id,q.reference_version)
    expected=pd.read_csv(OUT/'SCALAR_EXPECTATIONS.csv')
    assert expected.team_key.nunique()==624
    for r in expected.to_dict('records'):
        for f in ['B8L2','D10','IoU3D100']:
            v=ep[r['team_key']].get(f);assert pd.isna(r[f])==(v is None)
            if v is not None:assert abs(v-r[f])<1e-9


def test_hierarchical_weighting_and_missingness():
    # One block has three events, the other one; blocks have equal weight.
    d=pd.DataFrame({'n':[14]*4,'building':['b']*4,'image':['i']*4,'pool_id':['p']*4,'block_id':['x','x','x','y'],'background_id':['a','b','c','d'],'v':[0.,0.,0.,8.]})
    assert image_means(d,['v']).v.iloc[0]==4
    pair=pd.read_csv(OUT/'PAIRED_EVENTS.csv')
    assert pair.B8L2_delta.isna().sum()>0
    assert np.allclose(pair.B8L2_delta,pair.B8L2_structure-pair.B8L2_comparator,equal_nan=True)
    summary=pd.read_csv(OUT/'SUMMARY.csv')
    for r in summary[summary.metric.eq('B8L2')].itertuples():
        d=pair[pair.n.eq(r.n)&pair.comparator.eq(r.comparator)].dropna(subset=['B8L2_delta'])
        im=image_means(d,['B8L2_delta'])
        assert len(d)==r.events and len(im)==r.images and abs(im.B8L2_delta.mean()-r.effect)<1e-10


def test_labor_requires_complete_matching_sources():
    r={'record_time_by_kind_json':json.dumps({'a':{'n':2,'known_n':1,'total_seconds':None}})}
    assert labor(r)==((('a',2),),None)
    r['record_time_by_kind_json']=json.dumps({'a':{'n':2,'known_n':2,'total_seconds':12}})
    assert labor(r)==((('a',2),),12)


def test_frozen_abc_scores_are_preserved():
    old=pd.read_csv(UP/'HALF_EVENT_LEGALITY.csv.gz',low_memory=False).set_index('event_id')
    pair=pd.read_csv(OUT/'PAIRED_EVENTS.csv')
    for r in pair[pair.comparator.isin(['A','B'])].to_dict('records'):
        for field in ['B8L2','D10','IoU3D100']:
            before=old.loc[r['event_id'],field+('_CA' if r['comparator']=='A' else '_CB')]
            now=r[field+'_delta'];assert pd.isna(before)==pd.isna(now)
            if pd.notna(before):assert abs(before-now)<1e-7
