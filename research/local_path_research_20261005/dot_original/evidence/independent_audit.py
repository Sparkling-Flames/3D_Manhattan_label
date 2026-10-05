#!/usr/bin/env python3
"""Independent, exact rational, standard-library audit of this frozen toy domain.
No import of finite_paths or Shapely/NumPy. No cached candidate/prediction input.
All synthetic geometry/probes are rebuilt from declared paths. Optional --source
compares independent results to delivered artifacts, without changing source.
"""
import argparse, csv, hashlib, itertools, json
from collections import Counter, defaultdict
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS = {'small_left': (0,1), 'small_right': (1,1), 'narrow': (2,1),
          'range_right': (3,1), 'top_only': (3,2), 'range_left': (4,1), 'inset': (5,1)}

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rat(x): return Q(str(x))
def vec(p): return tuple(map(rat,p))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return a[0]*b[1]-a[1]*b[0]
def orient(a,b,c): return cross(sub(b,a),sub(c,a))
def onseg(p,a,b): return orient(a,b,p)==0 and all(min(x,y)<=z<=max(x,y) for x,y,z in zip(a,b,p))
def hit(a,b,c,d):
    x,y,z,w=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
    return (x*y<0 and z*w<0) or any(t==0 and onseg(p,u,v) for t,p,u,v in [(x,c,a,b),(y,d,a,b),(z,a,c,d),(w,b,c,d)])

def valid_ring(nodes):
    p=[v[:2] for v in nodes]; n=len(p)
    if n<3 or any(p[i]==p[(i+1)%n] for i in range(n)): return False
    if sum(cross(p[i],p[(i+1)%n]) for i in range(n))==0: return False
    if any(v[2]<=0 for v in nodes): return False
    for i in range(n):
        prev,here,nxt=p[i-1],p[i],p[(i+1)%n]
        if orient(prev,here,nxt)==0 and dot(sub(prev,here),sub(nxt,here))>0: return False
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1): continue
            if hit(p[i],p[(i+1)%n],p[j],p[(j+1)%n]): return False
    return True

def canonical(nodes):
    a=list(nodes)
    while len(a)>3:
        remove=None
        for i,c in enumerate(a):
            p,n=a[i-1],a[(i+1)%len(a)]; e=sub(n,p); w=sub(c,p); den=dot(e,e)
            if den and 0<=dot(w,e)<=den and all(w[k]*den==e[k]*dot(w,e) for k in range(3)):
                remove=i; break
        if remove is None: break
        a.pop(remove)
    variants=[tuple(s[i:]+s[:i]) for s in [a,a[::-1]] for i in range(len(a))]
    return min(variants)

def covers(nodes,p):
    ring=[v[:2] for v in nodes]; p=vec(p); yes=False
    for a,b in zip(ring,ring[1:]+ring[:1]):
        if onseg(p,a,b): return True
        if (a[1]>p[1]) != (b[1]>p[1]):
            x=a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if p[0]<x: yes=not yes
    return yes

def predict(c,probe):
    if probe['kind']=='occupancy': return covers(c['nodes'],probe['xz'])
    x=rat(probe['x']); vals=[]
    nodes=c['paths'][probe['segment']]
    for a,b in zip(nodes,nodes[1:]):
        if b[0]!=a[0]:
            t=(x-a[0])/(b[0]-a[0])
            if 0<=t<=1: vals.append(a[2]+t*(b[2]-a[2]))
    return max(vals)>rat(probe['height_threshold_h']) if vals else None

def build(D,P):
    out=[]; anchors=list(map(vec,D['anchors_xz_top']))
    for q in itertools.product(*[range(len(s['paths'])) for s in D['segments']]):
        paths=[list(map(vec,s['paths'][j]['nodes_xz_top'])) for s,j in zip(D['segments'],q)]
        joined=all(p[0]==anchors[i] and p[-1]==anchors[(i+1)%len(anchors)] for i,p in enumerate(paths))
        nodes=[n for p in paths for n in p[:-1]]
        geom=joined and valid_ring(nodes)
        violated=[r['id'] for r in D['incompatibilities'] if all(q[int(j)]==v for j,v in r['assignments'].items())]
        unknown=[r['id'] for r in D['unknown_compatibilities'] if all(q[int(j)]==v for j,v in r['assignments'].items())]
        c={'id':'C'+''.join(map(str,q)),'q':q,'paths':paths,'nodes':nodes,'geometry_valid':geom,
           'admissible':geom and not violated,'compatibility':'incompatible' if violated else ('unresolved' if unknown else 'compatible')}
        c['key']=canonical(nodes) if geom else None
        c['code']=tuple(predict(c,p) for p in P) if geom else None
        c['features']=tuple(q[j]==k for j,k in EVENTS.values())
        out.append(c)
    return out

def select(C,claims,P,b):
    pi={p['id']:i for i,p in enumerate(P)}
    out=[]
    for c in C:
        bad={e['source_group'] for e in claims if e['status']=='observed' and
             (c['code'][pi[e['probe_id']]] is None or c['code'][pi[e['probe_id']]]!=e['value'])}
        if len(bad)<=b: out.append(c)
    return out

def status(cs):
    if not cs: return 'no_feasible_candidate'
    if len({c['key'] for c in cs})>1: return 'multiple_candidates'
    return 'compatibility_unresolved' if any(c['compatibility']=='unresolved' for c in cs) else 'single_geometry_conditional'

def csvout(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows: w.writerow({k:json.dumps(v) if isinstance(v,(tuple,list,dict)) else v for k,v in r.items()})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);ap.add_argument('--out',type=Path,default=ROOT/'results');args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    D=read(ROOT/'inputs/domain.json');P=read(ROOT/'inputs/probes.json');S=read(ROOT/'inputs/evidence_streams.json')
    C=build(D,P);H=[c for c in C if c['admissible']]
    reps=defaultdict(list)
    for c in H: reps[c['key']].append(c)
    G=[v[0] for v in reps.values()]; byid={c['id']:c for c in C}
    summary={'independent_implementation':'Python stdlib Fraction; exact geometry, ray crossings, top interpolation, constraint enumeration and group union; no imports from audited code',
             'raw':len(C),'geometry_valid':sum(c['geometry_valid'] for c in C),'admissible_representations':len(H),'admissible_geometries':len(G),
             'incompatible_with_valid_geometry':sum(c['geometry_valid'] and not c['admissible'] for c in C),
             'unresolved_representations':sum(c['compatibility']=='unresolved' for c in H),'unresolved_geometries':sum(any(x['compatibility']=='unresolved' for x in v) for v in reps.values())}
    assert (len(C),summary['geometry_valid'],len(H),len(G))==(324,144,110,70)
    assert len({c['code'] for c in G})==70
    # A second independent algebraic description checks the exact geometric codes.
    # x=(small_left, small_right, narrow, range_right, top_only, range_left, not inset).
    abstract={x for x in itertools.product((False,True),repeat=7)
              if not (x[0] and x[1] and x[2]) and not (x[3] and x[4]) and not (x[3] and x[5])}
    assert abstract=={c['code'] for c in G}
    assert all(c['features']==c['code'][:6]+(not c['code'][6],) for c in G)
    summary['algebraic_crosscheck']={'codebook_factorization':'7 x 5 x 2 = 70','response_domain_exactly_equal':True,
        'constraints':['not(x0 & x1 & x2)','not(x3 & x4)','not(x3 & x5)'],'x6':'not inset'}
    baseline=[]
    for s in S:
        for b in (0,1):
            cs=select(H,s['claims'],P,b)
            baseline.append({'stream':s['id'],'b':b,'candidate_ids':[c['id'] for c in cs],'status':status(cs),
                             'representations':len(cs),'geometries':len({c['key'] for c in cs})})
    summary['independent_stream_budget_checks']=len(baseline)
    if args.source:
        old=read(args.source/'results/final/finite/all_candidates.json')
        assert len(old)==len(C)
        for c in old:
            d=byid[c['id']]
            assert c['geometry_valid']==d['geometry_valid'] and c['admissible']==d['admissible'] and c['compatibility']==d['compatibility'],c['id']
            if d['geometry_valid']:
                assert tuple(c['probe_predictions'][p['id']] for p in P)==d['code'],c['id']
                assert canonical(list(map(vec,c['geometry_key'])))==d['key'],c['id']
        olddec=read(args.source/'results/final/finite/policy_outputs_before_truth.json')
        om={(d['stream_id'],d['policy']['max_wrong_source_groups']):d for d in olddec if d['policy']['kind']=='evidence'}
        for r in baseline:
            o=om[r['stream'],r['b']]
            assert set(r['candidate_ids'])==set(o['candidate_ids']) and r['status']==o['status']
        comparison={'candidate_rows_equal':324,'valid_probe_vectors_equal':144,'evidence_outputs_equal':64,
                    'source_files_sha256':{str(p.relative_to(args.source)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [args.source/'REPORT_ZH.md',args.source/'src/finite_paths.py',args.source/'src/diagnostic_extensions.py',
                              args.source/'build_fixtures.py',args.source/'run_research.py',args.source/'PLAN.json',args.source/'tests/test_finite_paths.py']}}
        save(out/'delivered_comparison.json',comparison)
    # Exact projection code distances, all subsets (128 fixed probe subsets).
    dist=lambda a,b:sum(x!=y for x,y in zip(a,b))
    pairs=[(dist(a['code'],b['code']),a,b) for a,b in itertools.combinations(G,2)]
    summary['minimum_hamming_distance']=min(d for d,a,b in pairs)
    masks=[]
    for k in range(8):
        for ids in itertools.combinations(range(7),k):
            classes=defaultdict(list)
            for c in G: classes[tuple(c['code'][i] for i in ids)].append(c['id'])
            masks.append({'probes':ids,'size':k,'response_classes':len(classes),'max_ambiguity':max(map(len,classes.values()))})
    summary['minimum_exact_probe_count']=min(r['size'] for r in masks if r['response_classes']==70)
    summary['six_probe_classes']=[r for r in masks if r['size']==6]
    summary['feature_cross_class_distance']={e:min(d for d,a,b in pairs if a['features'][j]!=b['features'][j]) for j,e in enumerate(EVENTS)}
    save(out/'minimum_distance_witnesses.json',{e:next({'a':a['id'],'b':b['id'],'code_a':a['code'],'code_b':b['code'],'distance':d} for d,a,b in pairs if d==summary['feature_cross_class_distance'][e] and a['features'][j]!=b['features'][j]) for j,e in enumerate(EVENTS)})
    csvout(out/'probe_subsets.csv',masks)
    # Bounded experiment: clean, one flipped group, one missing group; budgets 0/1.
    # Separate fixed 70*21 two-coordinate flips are a diagnostic beyond b=1.
    cases=[];aggreg=defaultdict(Counter);stage_sizes=Counter();witness=[]
    for t in G:
        scenarios=[('clean',(),())]+[('single_flip',(i,),()) for i in range(7)]+[('single_missing',(),(i,)) for i in range(7)]+[('double_distinct_flip',(i,j),()) for i,j in itertools.combinations(range(7),2)]
        for mode,flips,missing in scenarios:
            y=tuple((not v) if i in flips else v for i,v in enumerate(t['code']))
            for b in (0,1):
                cs=[c for c in G if sum(c['code'][i]!=y[i] for i in range(7) if i not in missing)<=b]
                covered=any(c['key']==t['key'] for c in cs)
                s=status(cs);fixed=wrong=0;dec=[]
                for j,e in enumerate(EVENTS):
                    vals={c['features'][j] for c in cs}
                    decisive=len(vals)==1;value=next(iter(vals)) if decisive else None
                    err=decisive and value!=t['features'][j]
                    fixed+=decisive;wrong+=err;dec.append(value)
                    ag=aggreg[mode,b,e];ag['cases']+=1;ag['fixed']+=decisive;ag['wrong_fixed']+=err
                    ag['true_present']+=t['features'][j]
                    ag['true_confirmed_present']+=decisive and value is True and t['features'][j]
                    ag['true_confirmed_absent']+=decisive and value is False and not t['features'][j]
                row={'truth':t['id'],'mode':mode,'flip_groups':flips,'missing_groups':missing,'b':b,'geometry_count':len(cs),'truth_covered':covered,'status':s,'fixed_events':fixed,'wrong_fixed_events':wrong,'event_values':dec,'candidate_ids':[c['id'] for c in cs]}
                cases.append(row);stage_sizes[mode,b]+=1
                if wrong and len([w for w in witness if (w['mode'],w['b'])==(mode,b)])<3: witness.append(row)
                if b==1 and len(flips)<=1: assert covered and wrong==0
                if b==0 and not flips: assert covered and wrong==0
    result=[]
    for (mode,b),n in sorted(stage_sizes.items()):
        rr=[r for r in cases if r['mode']==mode and r['b']==b]
        result.append({'mode':mode,'b':b,'cases':n,'truth_covered':sum(r['truth_covered'] for r in rr),'unique_geometries':sum(r['geometry_count']==1 for r in rr),
                       'empty':sum(r['geometry_count']==0 for r in rr),'fixed_event_count':sum(r['fixed_events'] for r in rr),'event_count':7*n,'wrong_fixed_event_count':sum(r['wrong_fixed_events'] for r in rr),
                       'geometry_count_min':min(r['geometry_count'] for r in rr),'geometry_count_max':max(r['geometry_count'] for r in rr),
                       'all_seven_events_undetermined':sum(r['fixed_events']==0 for r in rr),
                       'status_counts':dict(Counter(r['status'] for r in rr)),
                       'cases_with_wrong_fixed_event':sum(r['wrong_fixed_events']>0 for r in rr),
                       'multiple_candidate_cases_with_wrong_fixed_event':sum(r['wrong_fixed_events']>0 and r['status']=='multiple_candidates' for r in rr)})
    summary['bounded_experiment']=result
    summary['one_error_coverage_checks']=sum(r['cases'] for r in result if r['b']==1 and r['mode'] in ('clean','single_flip'))
    feature_rows=[dict(mode=mode,b=b,event=e,**dict(v)) for (mode,b,e),v in sorted(aggreg.items())]
    csvout(out/'case_results.csv',cases);csvout(out/'feature_summary.csv',feature_rows);save(out/'wrong_decision_witnesses.json',witness)
    # Actual delivered four-world streams: verify truth coverage and event decisions.
    W=read(ROOT/'inputs/synthetic_truth.json')['worlds'];wk={w['id']:byid['C'+''.join(map(str,w['choices']))] for w in W};world_rows=[]
    for s in S:
        for b in (0,1):
            cs=select(H,s['claims'],P,b); t=wk[s['evaluation_world']]; ev=[]
            for j,e in enumerate(EVENTS):
                vals={c['features'][j] for c in cs};v=next(iter(vals)) if len(vals)==1 else None
                ev.append({'event':e,'decision':v,'truth':t['features'][j],'wrong':v is not None and v!=t['features'][j]})
            world_rows.append({'world':s['evaluation_world'],'mode':s['mode'],'b':b,'geometry_count':len({c['key'] for c in cs}),'truth_covered':any(c['key']==t['key'] for c in cs),'status':status(cs),'events':ev})
    save(out/'four_world_evidence.json',world_rows);save(out/'independent_baseline_outputs.json',baseline)
    # Fixed grouping sensitivity: merge all probes vs split repeated erroneous claim.
    sensitivity=[]
    for w,t in wk.items():
        s=next(s for s in S if s['evaluation_world']==w and s['mode']=='misclassified_probe0')
        scenarios={'seven_groups':s['claims'],'all_claims_one_group':[dict(e,source_group='shared_image') for e in s['claims']],
                   'same_error_same_group_repeat':s['claims']+[dict(s['claims'][0],id='repeat')],
                   'same_error_new_group_repeat':s['claims']+[dict(s['claims'][0],id='repeat',source_group='new_group')]}
        for mode,claims in scenarios.items():
            cs=select(H,claims,P,1);sensitivity.append({'world':w,'mode':mode,'geometry_count':len({c['key'] for c in cs}),'truth_covered':any(c['key']==t['key'] for c in cs)})
    save(out/'grouping_sensitivity.json',sensitivity)
    # Two bounded condition-failure controls. These do not alter the input domain.
    import copy
    D2=copy.deepcopy(D)
    for p in D2['segments'][0]['paths'][1]['nodes_xz_top']:
        if p[1] < -2.03: p[1]=-2.06
    outside=next(c for c in build(D2,P) if c['id']=='C101100')
    assert outside['key'] not in reps and outside['code']==byid['C101100']['code']
    direct_claims=lambda c:[{'id':p['id'],'probe_id':p['id'],'source_group':p['id'],'status':'observed','value':v} for p,v in zip(P,c['code'])]
    exact_area=lambda c:abs(sum(cross(a[:2],b[:2]) for a,b in zip(c['nodes'],c['nodes'][1:]+c['nodes'][:1])))/2
    cs=select(H,direct_claims(outside),P,0)
    truth_area=exact_area(outside); chosen_area=exact_area(cs[0])
    control=[{'case':'out_of_domain_0.06h_bump','probe_code':outside['code'],'all_observed_claims_correct':True,
              'true_geometry_in_frozen_domain':False,'E0_status':status(cs),'E0_candidates':[c['id'] for c in cs],
              'lost_rectangular_area_h2_exact':str(truth_area-chosen_area),'nested_layout_iou_exact':str(chosen_area/truth_area),
              'iou':float(chosen_area/truth_area),'note':'Only the authored small rectangular bump is extended by 0.02h; area nesting is explicit.'}]
    excluded=byid['C111100']
    assert excluded['geometry_valid'] and not excluded['admissible']
    for b in (0,1):
        cs=select(H,direct_claims(excluded),P,b)
        control.append({'case':'geometrically_valid_truth_but_wrong_given_threeway_exclusion','truth':'C111100',
                        'probe_code':excluded['code'],'b':b,'status':status(cs),'candidate_ids':[c['id'] for c in cs],
                        'truth_covered':any(c['key']==excluded['key'] for c in cs)})
    save(out/'condition_failure_controls.json',control)
    summary['input_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'inputs').glob('*.json'))}
    save(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
