#!/usr/bin/env python3
"""Independent denominator, scope-sensitivity and historic failure audit.

No fusion, scoring, manual adjudication or repository mutation. Standard library only.
Read sources pinned to d4c73943ae58476880bf3ceb7b774e4ec59a95b5.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'sources'
OUT = ROOT / 'results'
TARGETS = ['全部', '空间1', '空间2']
SCOPE_MAP = {'both': '全部', 'space1': '空间1', 'space2': '空间2'}

def read(name):
    return json.loads((SRC / name).read_text(encoding='utf-8-sig'))

def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def write_csv(name, rows):
    if not rows: return
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

def signed_area(poly):
    return sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(poly,poly[1:]+poly[:1]))/2

def area(poly):
    return abs(signed_area(poly)) if len(poly)>=3 else 0.0

def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def clean(poly, eps=1e-12):
    out=[]
    for p in poly:
        if not out or math.dist(out[-1], p)>eps: out.append(list(p))
    if len(out)>1 and math.dist(out[0],out[-1])<=eps: out.pop()
    return out

def clip(poly, cut):
    a,b=cut['line']; side=cut['side']
    def dist(p): return side*cross(a,b,p)
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        dp,dq=dist(p),dist(q)
        if dp>=0: out.append(p)
        if (dp>=0)!=(dq>=0):
            t=dp/(dp-dq)
            out.append([p[i]+t*(q[i]-p[i]) for i in range(2)])
    return clean(out)

def floor(points):
    result=[]
    for x,y in (points or [])[1::2]:
        r=1/math.tan((y/512-.5)*math.pi)
        a=(x/1024-.5)*math.tau
        result.append([r*math.sin(a),-r*math.cos(a)])
    return clean(result)

def valid_simple(poly):
    poly=clean(poly)
    if len(poly)<3 or not all(math.isfinite(x) for p in poly for x in p): return False
    if area(poly)<=1e-14: return False
    # All checked inputs are simple non-self-touching rings. Explicitly reject crossings.
    n=len(poly)
    for i in range(n):
        a,b=poly[i],poly[(i+1)%n]
        for j in range(i+1,n):
            if j in (i,(i+1)%n) or (j+1)%n==i: continue
            c,d=poly[j],poly[(j+1)%n]
            ca,cb=cross(a,b,c),cross(a,b,d)
            cc,cd=cross(c,d,a),cross(c,d,b)
            if ca*cb<0 and cc*cd<0: return False
            for p,v in [(c,ca),(d,cb)]:
                if abs(v)<1e-14 and min(a[0],b[0])-1e-14<=p[0]<=max(a[0],b[0])+1e-14 and min(a[1],b[1])-1e-14<=p[1]<=max(a[1],b[1])+1e-14:
                    return False
    return True

def triangulate(poly):
    """Ear-clip a simple ring; no external geometry library or repair operation."""
    poly=clean(poly)
    if signed_area(poly)<0: poly=poly[::-1]
    # Remove exactly collinear points, preserving the enclosed region.
    again=True
    while again and len(poly)>3:
        again=False
        for i in range(len(poly)):
            if abs(cross(poly[i-1],poly[i],poly[(i+1)%len(poly)]))<1e-14:
                poly.pop(i);again=True;break
    todo=list(range(len(poly)));out=[]
    while len(todo)>3:
        for pos,i in enumerate(todo):
            a,b,c=poly[todo[pos-1]],poly[i],poly[todo[(pos+1)%len(todo)]]
            if cross(a,b,c)<=1e-14: continue
            others=[poly[j] for j in todo if j not in (todo[pos-1],i,todo[(pos+1)%len(todo)])]
            if any(cross(a,b,p)>=-1e-14 and cross(b,c,p)>=-1e-14 and cross(c,a,p)>=-1e-14 for p in others): continue
            out.append([a,b,c]);todo.pop(pos);break
        else: raise ValueError('Ear clipping failed; refuse silent polygon repair')
    out.append([poly[j] for j in todo])
    assert abs(sum(area(t) for t in out)-area(poly))<1e-9*max(1,area(poly))
    return out

def triangle_intersection(a,b):
    out=a
    if signed_area(b)<0: b=b[::-1]
    for p,q in zip(b,b[1:]+b[:1]):
        if not out: return 0.0
        out=clip(out,dict(line=[p,q],side=1))
    return area(out)

def intersection(a,b):
    return sum(triangle_intersection(x,y) for x in triangulate(a) for y in triangulate(b))

def classify(f1,f2):
    if f1>=.85 and f2<=.1: return 'space1'
    if f2>=.85 and f1<=.1: return 'space2'
    if min(f1,f2)>=.15: return 'both'
    if max(f1,f2)<.15: return 'neither'
    return 'borderline'

def scope_summary(ledger, field):
    base=[r for r in ledger if r['base_candidate']]
    pools=defaultdict(list)
    for r in base:
        if r[field] in TARGETS: pools[r['image'],r[field]].append(r)
    rows=[]
    for (image,target),rr in sorted(pools.items()):
        workers={r['worker'] for r in rr}
        assert len(workers)==len(rr), ('duplicate person within a target pool',image,target)
        n=len(workers)
        rows.append(dict(image=image,target=target,n=n,qualified_n_ge_3=n>=3,
            human_n=sum(r['scope_adoption'].startswith('user') for r in rr),
            agent_visual_n=sum(r['scope_adoption'].startswith('agent_visual') for r in rr),
            automatic_n=sum(r['scope_adoption'].startswith('automatic') for r in rr),
            planned_prefixes256_k3_to_n=256*max(n-2,0)))
    support=[]
    for k in [1,2,3,4,5,6,8,10,12,16,20,24,28,30,32,35]:
        support.append(dict(k=k,eligible_target_pools=sum(r['n']>=k for r in rows),
            eligible_images=len({r['image'] for r in rows if r['n']>=k})))
    return dict(scope_counts=dict(Counter(r[field] or '未定' for r in base)),
        nonempty_pools=len(rows), qualified_pools=sum(r['n']>=3 for r in rows),
        records_in_qualified_pools=sum(r['n'] for r in rows if r['n']>=3),
        planned_prefixes256_k3_to_n=sum(r['planned_prefixes256_k3_to_n'] for r in rows),
        pool_table=rows, support_by_k=support)

def selftests():
    a=[[0,0],[2,0],[2,2],[0,2]]
    b=[[1,1],[3,1],[3,3],[1,3]]
    ell=[[0,0],[3,0],[3,1],[1,1],[1,3],[0,3]]
    for x,y,expected in [(a,a,4),(a,b,1),(ell,a,3),(ell,ell,5),(a,[[4,4],[5,4],[5,5],[4,5]],0)]:
        assert abs(intersection(x,y)-expected)<1e-12
        assert abs(intersection(x[::-1],y[::-1])-expected)<1e-12
    assert not valid_simple([[0,0],[2,2],[0,2],[2,0]])
    assert valid_simple(ell)
    assert classify(.85,.1)=='space1'
    assert classify(.15,.15)=='both'
    assert classify(.14,.14)=='neither'
    assert classify(.8,.12)=='borderline'
    return dict(geometry_examples=10, simple_ring_examples=2, classification_examples=4, passed=True)

def main():
    OUT.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    source_checks=[]
    for entry in manifest['files']:
        raw=(SRC/entry['local']).read_bytes()
        digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert digest==entry['git_blob_sha'], ('Source Git blob changed',entry['local'])
        source_checks.append(dict(local=entry['local'],git_blob_sha=digest,bytes=len(raw),verified=True))
    write('SOURCE_GIT_BLOB_CHECKS.json',source_checks)
    tests=selftests()
    data=json.loads((SRC/'data.js').read_text().split('=',1)[1].rstrip(';\r\n '))
    cases={r['image']:r for r in data['cases']}
    final={r['image']:r for r in read('ALIGNMENT_DECISIONS.json')}
    ledger=read('UPDATED_RECORD_LEDGER.json')
    prior={r['record_id']:r for r in csv.DictReader((SRC/'classification.csv').open(encoding='utf-8-sig'))}
    records={r['id']:r for c in cases.values() for r in c['records']}
    assert len(ledger)==len(records)==len(prior)==708
    assert len({r['object_id'] for r in ledger})==708
    assert len(cases)==len(final)==20
    diagnostics=[];changes=[];parity=[];geometry_checks=[];cuts_parity=[]
    for image,c in cases.items():
        f=final[image]
        if f['status']!='manhattan': continue
        pp=f['space_polygons']
        assert len(pp)==2 and all(valid_simple(p) for p in pp)
        gt=c['floor']; assert valid_simple(gt)
        geometry_checks.append(dict(image=image,space1_area=area(pp[0]),space2_area=area(pp[1]),
            removed_consecutive_duplicate_vertices=[len(p)-len(clean(p)) for p in pp],
            overlap_area=intersection(pp[0],pp[1]),
            outside_gt_space1=max(0,area(pp[0])-intersection(pp[0],gt)),
            outside_gt_space2=max(0,area(pp[1])-intersection(pp[1],gt)),
            gt_area=area(gt),reference_adopted=f['reference_adopted']))
    for r in ledger:
        oid=r['object_id']; a=records[oid]; c=cases[r['image']]; f=final[r['image']]
        assert a['worker']==r['worker'] and c['image_id']==r['image_id']
        poly=floor(a['points']); valid=valid_simple(poly)
        if valid:
            oldfra=[area(clip(poly,cut))/area(poly) for cut in c['cuts']]
            old=classify(*oldfra)
        else: old='invalid';oldfra=None
        parity.append(old==prior[oid]['space_verdict'])
        # Independent source-contract check on every stored automatic fraction.
        ev=r.get('automatic_scope_evidence')
        if ev and valid:
            ff=[area(clip(poly,cut))/area(poly) for cut in ev['cuts']]
            delta=max(abs(ff[i]-ev['fractions']['space'+str(i+1)]) for i in (0,1))
            cuts_parity.append(delta)
        d=dict(object_id=oid,image=r['image'],worker=r['worker'],base_candidate=r['base_candidate'],
            protected_source=r['scope_adoption'].startswith(('user','agent_visual')),
            scope_source=r['scope_adoption'], prior_adopted_scope=r['adopted_scope'],
            paired_polygon_valid=valid,final_space_defined=f['status']=='manhattan',
            final_cut_class=None,final_polygon_class=None,
            final_cut_fractions=None,final_polygon_fractions=None,outside_gt_fraction=None)
        r['diagnostic_final_cut_scope']=r['adopted_scope']
        r['diagnostic_final_polygon_scope']=r['adopted_scope']
        if valid and f['status']=='manhattan':
            cutfra=[area(clip(poly,cut))/area(poly) for cut in f['cuts']]
            polyfra=[intersection(poly,p)/area(poly) for p in f['space_polygons']]
            assert all(-1e-10<=x<=1+1e-10 for x in cutfra+polyfra)
            cutclass=classify(*cutfra);polyclass=classify(*polyfra)
            d.update(final_cut_class=cutclass,final_polygon_class=polyclass,
                final_cut_fractions=cutfra,final_polygon_fractions=polyfra,
                outside_gt_fraction=max(0,1-intersection(poly,c['floor'])/area(poly)))
            if not d['protected_source']:
                r['diagnostic_final_cut_scope']=SCOPE_MAP.get(cutclass)
                r['diagnostic_final_polygon_scope']=SCOPE_MAP.get(polyclass)
        if r['base_candidate']:
            assert valid and f['status']=='manhattan'
            if r['diagnostic_final_cut_scope']!=r['adopted_scope'] or r['diagnostic_final_polygon_scope']!=r['adopted_scope']:
                changes.append(dict(object_id=oid,image=r['image'],worker=r['worker'],scope_source=r['scope_adoption'],old=r['adopted_scope'],
                    final_cut_diagnostic=r['diagnostic_final_cut_scope'],final_polygon_diagnostic=r['diagnostic_final_polygon_scope']))
        d['diagnostic_final_cut_scope']=r['diagnostic_final_cut_scope']
        d['diagnostic_final_polygon_scope']=r['diagnostic_final_polygon_scope']
        diagnostics.append(d)
    assert all(parity), f'Original label reproduction failed: {sum(parity)}/708'
    assert max(cuts_parity,default=0)<1e-10
    base=[r for r in ledger if r['base_candidate']]
    protected=[r for r in base if r['scope_adoption'].startswith(('user','agent_visual'))]
    assert all(r['adopted_scope']==r['diagnostic_final_cut_scope']==r['diagnostic_final_polygon_scope'] for r in protected)
    assert sum(r['base_candidate'] for r in ledger)==584
    assert sum(r['screened_version_candidate'] for r in ledger)==553
    variants={n:scope_summary(ledger,f) for n,f in [('prior_supplement','adopted_scope'),('final_cut_diagnostic','diagnostic_final_cut_scope'),('final_polygon_sensitivity','diagnostic_final_polygon_scope')]}
    for name,value in variants.items():
        write_csv(name+'_pools.csv',value['pool_table'])
        write_csv(name+'_support_by_k.csv',value['support_by_k'])
    combos=Counter(tuple(sorted(r['base_blockers'])) for r in ledger if not r['base_candidate'])
    source_scope=[]
    for source in sorted({r['scope_adoption'] for r in base}):
        rr=[r for r in base if r['scope_adoption']==source]
        source_scope.append(dict(source=source,n=len(rr),old=dict(Counter(r['adopted_scope'] or '未定' for r in rr)),
            final_cut=dict(Counter(r['diagnostic_final_cut_scope'] or '未定' for r in rr)),
            final_polygon=dict(Counter(r['diagnostic_final_polygon_scope'] or '未定' for r in rr))))
    summary=dict(source_commit='d4c73943ae58476880bf3ceb7b774e4ec59a95b5', inventory=708,images=20,
        unique_workers_inventory=len({r['worker'] for r in ledger}),unique_workers_base=len({r['worker'] for r in base}),
        base_records=584,screened_records=553,kept_human_or_visual_records=len(protected),
        base_exclusion_union=708-len(base),exclusion_combinations=[dict(reasons=list(k),n=v) for k,v in combos.items()],
        tests=tests,original_classification_parity=sum(parity),old_automatic_fraction_max_abs_delta=max(cuts_parity),
        original_automatic_fraction_records=len(cuts_parity),
        paired_valid_records=sum(d['paired_polygon_valid'] for d in diagnostics),
        ready_to_score_count=sum(r['ready_to_score'] for r in ledger),
        formally_adopted_targets=sum(r['reference_adopted'] for r in final.values()),
        base_changed_final_cut=sum(r['adopted_scope']!=r['diagnostic_final_cut_scope'] for r in base),
        base_changed_final_polygon=sum(r['adopted_scope']!=r['diagnostic_final_polygon_scope'] for r in base),
        auto_base_final_cut_vs_polygon_disagreement=sum(r['diagnostic_final_cut_scope']!=r['diagnostic_final_polygon_scope'] for r in base),
        variants=variants,source_scope=source_scope,
        warning='All refreshed scopes are diagnostic only. Final cuts preserve the original half-plane rule; bounded-polygon intersection additionally tests shape/extent and is not a replacement scope rule. No fusion, scoring, formal target adoption, qualification change, or human/visual overwrite.')
    write('SCOPE_SUMMARY.json',summary)
    write('ALL708_SCOPE_DIAGNOSTICS.json',diagnostics)
    write('BASE_SCOPE_CHANGES.json',changes)
    write('FINAL_REGION_GEOMETRY_CHECKS.json',geometry_checks)
    # Historic saved endpoints: extract distinct endpoint identities and paired trajectories.
    hist=list(csv.DictReader((SRC/'CASE_PREFIXES.csv').open(encoding='utf-8-sig')))
    assert len(hist)==768 and len({r['path_id'] for r in hist})==24
    def flag(r,k): return r[k]=='True'
    def quality(r): return float(r['B8L2']) if r['B8L2'] else None
    by_k=[]
    for k in range(1,33):
        rr=[r for r in hist if int(r['k'])==k]
        assert len(rr)==24
        qq=[quality(r) for r in rr if quality(r) is not None]
        by_k.append(dict(k=k,path_rows=len(rr),unique_teams=len({r['team_key'] for r in rr}),
            complete_evaluable_n=sum(flag(r,'complete_evaluable') for r in rr),
            q_available_n=len(qq),policy_deferred_n=sum(flag(r,'policy_deferred') for r in rr),
            below_four_n=sum(flag(r,'below_four') for r in rr),
            no_connection_n=sum(not flag(r,'connection_available') for r in rr),
            conditional_q_mean=statistics.mean(qq) if qq else None,
            conditional_q_min=min(qq) if qq else None,conditional_q_max=max(qq) if qq else None))
    by_path=defaultdict(dict)
    for r in hist: by_path[r['path_id']][int(r['k'])]=r
    transitions=[];paired_intervals=[]
    for k in range(3,32):
        pairs=[(r[k],r[k+1]) for r in by_path.values()]
        cc=Counter((flag(a,'complete_evaluable'),flag(b,'complete_evaluable')) for a,b in pairs)
        transitions.append(dict(from_k=k,to_k=k+1,both_complete=cc[True,True],lost_complete=cc[True,False],
            gained_complete=cc[False,True],both_incomplete=cc[False,False]))
    for k1,k2 in [(3,10),(3,20),(10,20),(20,28),(28,32),(3,32)]:
        pairs=[(r[k1],r[k2]) for r in by_path.values()]
        both=[(quality(a),quality(b)) for a,b in pairs if quality(a) is not None and quality(b) is not None]
        paired_intervals.append(dict(from_k=k1,to_k=k2,path_pairs=24,both_q_valid=len(both),
            lost_q=sum(quality(a) is not None and quality(b) is None for a,b in pairs),
            gained_q=sum(quality(a) is None and quality(b) is not None for a,b in pairs),
            paired_q_from_mean=statistics.mean(a for a,b in both) if both else None,
            paired_q_to_mean=statistics.mean(b for a,b in both) if both else None,
            paired_q_mean_delta=statistics.mean(b-a for a,b in both) if both else None))
    full=list(csv.DictReader((SRC/'DOORWAY_FULL_POOL_STATUS.csv').open(encoding='utf-8-sig')))
    fq=[float(r['B8L2']) for r in full if r['B8L2']]
    historic_summary=dict(identity='Historical original-reference unsplit frozen v2 doorway pool; not new v2.1 per-space curves',
        case_image='7y3sRwLe3Va-06',case_paths=24,prefix_rows=768,unique_case_teams=len({r['team_key'] for r in hist}),
        full_pool_images=len(full),full_pool_complete=sum(flag(r,'complete_evaluable') for r in full),
        full_pool_incomplete=sum(not flag(r,'complete_evaluable') for r in full),
        full_pool_conditional_mean_q=statistics.mean(fq),full_pool_q80_n=sum(q>=80 for q in fq),
        full_pool_q90_n=sum(q>=90 for q in fq),
        case_paths_ever_complete_k3_plus=sum(any(flag(r[k],'complete_evaluable') for k in range(3,33)) for r in by_path.values()),
        case_paths_ever_lost_completeness_k3_plus=sum(any(flag(r[k],'complete_evaluable') and not flag(r[k+1],'complete_evaluable') for k in range(3,32)) for r in by_path.values()),
        case_paths_ever_regained_completeness_k3_plus=sum(any(not flag(r[k],'complete_evaluable') and flag(r[k+1],'complete_evaluable') for k in range(3,32)) for r in by_path.values()),
        adjacent_lost_complete=sum(r['lost_complete'] for r in transitions),adjacent_gained_complete=sum(r['gained_complete'] for r in transitions),
        case_by_k=by_k,paired_intervals=paired_intervals,
        warning='Path rows share workers and endpoints; they are not independent experiments. k=1 is raw-answer baseline, k=2 policy-deferred. Missing Q is not zero and conditional Q means have changing valid subsets.')
    write('HISTORICAL_FAILURE_SUMMARY.json',historic_summary)
    write_csv('HISTORICAL_CASE_BY_K.csv',by_k)
    write_csv('HISTORICAL_ADJACENT_TRANSITIONS.csv',transitions)
    write_csv('HISTORICAL_PAIRED_INTERVALS.csv',paired_intervals)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SRC.iterdir()) if p.is_file()}
    write('SOURCE_SHA256.json',hashes)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['variants','source_scope']},ensure_ascii=False,indent=2))
    print(json.dumps({n:{k:v for k,v in x.items() if k not in ['pool_table','support_by_k']} for n,x in variants.items()},ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in historic_summary.items() if k not in ['case_by_k','paired_intervals']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
