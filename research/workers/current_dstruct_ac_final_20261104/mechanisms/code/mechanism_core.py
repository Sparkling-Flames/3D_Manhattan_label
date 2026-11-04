"""Observation-anchored native fusion diagnostics for frozen direct AC pairs.

This module only reads saved native states. Cross-arm identities are not inferred
from the local feature number or from proximity to a reference corner.
"""
from __future__ import annotations
import gzip, hashlib, json, math
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
COMMIT = "48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b"

def clean(x):
    if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple,set)): return [clean(v) for v in x]
    if isinstance(x, np.ndarray): return clean(x.tolist())
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    return x

def digest(x):
    return hashlib.sha256(json.dumps(clean(x),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read_json(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:
        return json.load(f)

def iter_jsonl(p):
    with gzip.open(p,'rt',encoding='utf-8-sig') as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def save_json(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(clean(obj),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if p.suffix=='.gz': raw=gzip.compress(raw,compresslevel=5,mtime=0)
    tmp=p.with_name(p.name+'.writing');tmp.write_bytes(raw);tmp.replace(p)

def save_jsonl(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    b=b''.join((json.dumps(clean(r),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode() for r in rows)
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=5,mtime=0)
    tmp=p.with_name(p.name+'.writing');tmp.write_bytes(b);tmp.replace(p)

def save_csv(p,df):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    if not isinstance(df,pd.DataFrame):df=pd.DataFrame(df)
    b=df.to_csv(index=False).encode('utf-8-sig')
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=5,mtime=0)
    tmp=p.with_name(p.name+'.writing');tmp.write_bytes(b);tmp.replace(p)

def ws(x):
    return sorted(map(str,x)) if isinstance(x,(list,tuple,set)) else sorted(str(x).split('|')) if x not in (None,'') else []

def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (ValueError,TypeError):return False

def obs_key(m): return (str(m['id']),int(m['source_pair_index']))

def anchor_key(keys): return digest(sorted(keys))[:16]

def group_maps(row, background, object_worker):
    """Map exact original D observations to native within-arm identity groups."""
    groups=(row.get('full_state') or {}).get('identity_groups',[])
    by_id={str(g['feature_id']):g for g in groups}
    anchors={};obs={};supporters={};all_keys=set()
    for fid,g in by_id.items():
        who={str(m.get('worker') or object_worker[str(m['id'])]) for m in g['members']}
        assert len(who)==int(g['support'])
        assert bool(g['selected'])==(int(g['support'])>=int(row['minimum_support']))
        supporters[fid]=who
        keys=frozenset(obs_key(m) for m in g['members'] if (m.get('worker') or object_worker[str(m['id'])]) in background)
        for m in g['members']:
            k=obs_key(m);assert k not in all_keys;all_keys.add(k)
        for k in keys:
            assert k not in obs;obs[k]=fid
        anchors[fid]=keys
    return by_id,anchors,obs,supporters

def cyclic_edges(order):
    if len(order)<3:return set()
    return {tuple(sorted((order[i],order[(i+1)%len(order)]))) for i in range(len(order))}

def endpoint_ring_summary(row):
    st=row.get('full_state') or {};groups=st.get('identity_groups',[])
    selected={str(g['feature_id']) for g in groups if g['selected']}
    covers=[]
    for a in st.get('assignments',[]):
        projection=[str(f) for f in a['feature_ids'] if str(f) in selected]
        if len(selected)>=3 and len(projection)==len(selected) and set(projection)==selected:
            covers.append(a.get('worker') or str(a.get('id')))
    rd=st.get('ring_diagnostics') or {}
    return dict(selected_groups=len(selected),unresolved_selected_groups=sum(g['selected'] and g.get('center') is None for g in groups),
                source_ring_covering_all_selected_n=len(covers),source_ring_covering_all_selected_workers='|'.join(sorted(covers)),
                ring_reason=rd.get('reason'),ring_order=rd.get('feature_ids') or [],
                candidate_reason=(st.get('candidate') or {}).get('reason'),
                score_status=row.get('score_status'),connection_available=row.get('connection_available'))

def diagnose_pair(event,A,C,pool):
    """Return a one-pair summary plus every stable/ambiguous D anchor link.

    The support-threshold labels below are conditional on native group identity.
    They do not assert that all annotated points in that group are one true corner.
    """
    D=set(ws(event['D_workers']));X=set(ws(event['X_workers']));Z=set(ws(event['Z_workers']))
    assert not (D&X or D&Z or X&Z)
    assert set(A['member_workers'])==D|X and set(C['member_workers'])==D|Z
    n=int(A['k']);m=len(X)
    assert n==int(C['k']) and m==len(Z)
    threshold=math.ceil(n/2)
    assert A['minimum_support']==C['minimum_support']==threshold
    own={str(r['object_id']):str(r['worker_id']) for r in pool['records']}
    ga,aa,oa,sa=group_maps(A,D,own);gc,ac,oc,sc=group_maps(C,D,own)
    assert set(oa)==set(oc),('D observations changed',event.get('event_id'))
    a_index={v:k for k,v in aa.items() if v};c_index={v:k for k,v in ac.items() if v}
    assert len(a_index)==sum(bool(x) for x in aa.values())
    assert len(c_index)==sum(bool(x) for x in ac.values())
    stable=[];links=[];matched_a=set();matched_c=set()
    for keys in sorted(set(a_index)&set(c_index),key=lambda x:sorted(x)):
        af,cf=a_index[keys],c_index[keys];g,h=ga[af],gc[cf]
        matched_a.add(af);matched_c.add(cf)
        x,y=g.get('center'),h.get('center');movement={}
        if x is not None and y is not None:
            x=np.asarray(x,float);y=np.asarray(y,float)
            movement=dict(horizontal_shift_deg=float(((y[0,0]-x[0,0]+512)%1024-512)*360/1024),
                          top_vertical_shift_deg=float((y[0,1]-x[0,1])*180/512),
                          bottom_vertical_shift_deg=float((y[1,1]-x[1,1])*180/512))
        q=dict(event_id=event.get('event_id'),canonical_pair_id=event.get('canonical_pair_id'),pool_id=event['pool_id'],
               anchor_id=anchor_key(keys),A_group=af,C_group=cf,link_type='exact_same_nonempty_D_observations',
               common_D_observations=len(keys),D_observation_keys_json=json.dumps(sorted(keys),separators=(',',':')),
               A_support=int(g['support']),C_support=int(h['support']),minimum_support=threshold,
               A_selected=bool(g['selected']),C_selected=bool(h['selected']),
               threshold_cross_up=not g['selected'] and h['selected'],threshold_cross_down=g['selected'] and not h['selected'],
               A_replacement_support=int(g['support'])-len(keys),C_replacement_support=int(h['support'])-len(keys),
               A_center_json=json.dumps(g.get('center'),separators=(',',':')),C_center_json=json.dumps(h.get('center'),separators=(',',':')),
               **movement)
        stable.append(q);links.append(q)
    for af,ak in aa.items():
        if not ak or af in matched_a:continue
        for cf,ck in ac.items():
            overlap=ak&ck
            if not overlap:continue
            links.append(dict(event_id=event.get('event_id'),canonical_pair_id=event.get('canonical_pair_id'),pool_id=event['pool_id'],
                              anchor_id='',A_group=af,C_group=cf,link_type='D_partition_split_merge_or_reassignment',
                              common_D_observations=len(overlap),A_D_observations=len(ak),C_D_observations=len(ck),
                              D_observation_keys_json=json.dumps(sorted(overlap),separators=(',',':')),
                              A_support=ga[af]['support'],C_support=gc[cf]['support'],minimum_support=threshold,
                              A_selected=ga[af]['selected'],C_selected=gc[cf]['selected'],threshold_cross_up=None,threshold_cross_down=None))
    # Pairwise common-D coassignment disagreement is invariant to feature names.
    contingency=Counter((oa[k],oc[k]) for k in oa)
    na=Counter(oa.values());nc=Counter(oc.values())
    choose2=lambda x:x*(x-1)//2
    both_same=sum(choose2(v) for v in contingency.values())
    changed=sum(choose2(v) for v in na.values())+sum(choose2(v) for v in nc.values())-2*both_same
    total=choose2(len(oa))
    ra=endpoint_ring_summary(A);rc=endpoint_ring_summary(C)
    ma={r['A_group']:r['anchor_id'] for r in stable};mc={r['C_group']:r['anchor_id'] for r in stable}
    seta={ma[f] for f,g in ga.items() if g['selected'] and f in ma}
    setc={mc[f] for f,g in gc.items() if g['selected'] and f in mc}
    all_selected_anchored=all(f in ma for f,g in ga.items() if g['selected']) and all(f in mc for f,g in gc.items() if g['selected'])
    same_selected=all_selected_anchored and seta==setc
    order_a=[str(x) for x in ra['ring_order']];order_c=[str(x) for x in rc['ring_order']]
    ring_comparable=bool(same_selected and len(order_a)>=3 and len(order_c)>=3 and set(order_a)=={f for f,g in ga.items() if g['selected']} and set(order_c)=={f for f,g in gc.items() if g['selected']})
    ring_changed=(cyclic_edges([ma[f] for f in order_a])!=cyclic_edges([mc[f] for f in order_c])) if ring_comparable else None
    qvalid=finite(A.get('B8L2')) and finite(C.get('B8L2'))
    dq=float(C['B8L2']-A['B8L2']) if qvalid else None
    selected_stable=[r for r in stable if r['A_selected'] and r['C_selected'] and finite(r.get('horizontal_shift_deg'))]
    summary={k:event.get(k) for k in ('event_id','canonical_pair_id','pool_id','image','building','direction','unordered_pair','source_class_current','target_class_current','design_family','selection_hash')}
    summary.update(n=n,m=m,minimum_support_A=threshold,minimum_support_C=threshold,nominal_threshold_changed=False,
                   A_Q=A.get('B8L2'),C_Q=C.get('B8L2'),Q_pair_valid=qvalid,delta_Q=dq,abs_delta_Q=abs(dq) if dq is not None else None,
                   jump5=abs(dq)>=5 if dq is not None else None,jump10=abs(dq)>=10 if dq is not None else None,
                   A_nodes=A.get('nodes'),C_nodes=C.get('nodes'),same_node_count=A.get('nodes')==C.get('nodes'),
                   A_score_status=A.get('score_status'),C_score_status=C.get('score_status'),
                   state_changed=A.get('score_status')!=C.get('score_status'),
                   evaluability_changed=finite(A.get('B8L2'))!=finite(C.get('B8L2')),
                   common_D_observations_n=len(oa),common_D_observation_pairs_n=total,D_coassignment_changed_pairs=changed,
                   D_coassignment_changed_fraction=changed/total if total else None,D_partition_changed=bool(changed),
                   stable_anchored_groups=len(stable),ambiguous_anchor_links=sum(r['link_type']!='exact_same_nonempty_D_observations' for r in links),
                   A_all_groups=len(ga),C_all_groups=len(gc),A_selected_groups=ra['selected_groups'],C_selected_groups=rc['selected_groups'],
                   A_groups_without_stable_anchor=len(ga)-len(stable),C_groups_without_stable_anchor=len(gc)-len(stable),
                   A_selected_groups_without_stable_anchor=sum(g['selected'] and f not in ma for f,g in ga.items()),
                   C_selected_groups_without_stable_anchor=sum(g['selected'] and f not in mc for f,g in gc.items()),
                   A_ambiguous_D_anchored_groups=sum(bool(v) and f not in ma for f,v in aa.items()),
                   C_ambiguous_D_anchored_groups=sum(bool(v) and f not in mc for f,v in ac.items()),
                   A_unanchored_groups=sum(not v for v in aa.values()),C_unanchored_groups=sum(not v for v in ac.values()),
                   A_selected_unanchored_groups=sum(ga[k]['selected'] and not v for k,v in aa.items()),C_selected_unanchored_groups=sum(gc[k]['selected'] and not v for k,v in ac.items()),
                   stable_threshold_cross_up=sum(r['threshold_cross_up'] for r in stable),stable_threshold_cross_down=sum(r['threshold_cross_down'] for r in stable),
                   stable_threshold_cross_any=any(r['threshold_cross_up'] or r['threshold_cross_down'] for r in stable),
                   all_selected_anchored=all_selected_anchored,same_selected_anchor_set=same_selected,ring_topology_comparable=ring_comparable,
                   ring_topology_changed=ring_changed,
                   A_source_complete_rings=ra['source_ring_covering_all_selected_n'],C_source_complete_rings=rc['source_ring_covering_all_selected_n'],
                   A_ring_reason=ra['ring_reason'],C_ring_reason=rc['ring_reason'],
                   A_location_unresolved=ra['unresolved_selected_groups'],C_location_unresolved=rc['unresolved_selected_groups'],
                   stable_selected_node_horizontal_abs_shift_mean_deg=float(np.mean([abs(r['horizontal_shift_deg']) for r in selected_stable])) if selected_stable else None,
                   stable_selected_node_top_abs_shift_mean_deg=float(np.mean([abs(r['top_vertical_shift_deg']) for r in selected_stable])) if selected_stable else None,
                   stable_selected_node_bottom_abs_shift_mean_deg=float(np.mean([abs(r['bottom_vertical_shift_deg']) for r in selected_stable])) if selected_stable else None)
    return clean(summary),clean(links)
