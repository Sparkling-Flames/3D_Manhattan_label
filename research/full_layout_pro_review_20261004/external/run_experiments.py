"""Recompute all reported experiments. Outputs never alter repository baselines.
Real-data pilot is deliberately limited to the received 3-worker current image.
Synthetic transformations are not additional independent people.
"""
from __future__ import annotations
from pathlib import Path
from itertools import combinations,permutations
from collections import Counter,defaultdict
import copy,csv,hashlib,json,math,platform,sys
import numpy as np
from scipy.stats import binom
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from consensus_lab import *
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
SEED=20261004

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
    return x

def dump(name,x):
    (OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2),encoding='utf-8')
def table(name,rows):
    if not rows:return
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))

def real_pilot():
    inp=json.loads((ROOT/'inputs/current_excerpt.json').read_text(encoding='utf-8'));rs=inp['images'][0]['annotations'];rows=[];frozen=[]
    err=max(float(np.max(abs(footprint(r)-np.array(r['footprint'])))) for r in rs)
    for k in range(1,len(rs)+1):
        for ix in combinations(range(len(rs)),k):
            sub=[rs[i] for i in ix];key='+'.join(r['id'] for r in sub)
            for tau in [2.5,5.,6.,9.,12.]:
                base=baseline_candidates(sub,tau)
                rows.append(dict(subset=key,k=k,tolerance=tau,groups=len(base['groups']),
                    sizes=';'.join(str(g['support']) for g in base['groups']),
                    largest_distance=max(max(row) for row in base['distance_matrix'])))
                if tau==5.:
                    ens=derive_candidates(sub,tau)
                    frozen.append(dict(subset=key,k=k,baseline=base,prototype=ens,
                                       majority_strict=majority(sub).tolist(),majority_half=majority(sub,strict=False).tolist()))
    # Persist predictions BEFORE even opening the isolated reference file.
    dump('real_pilot_predictions_frozen.json',frozen)
    prediction_hash=hashlib.sha256((OUT/'real_pilot_predictions_frozen.json').read_bytes()).hexdigest()
    ref=json.loads((ROOT/'inputs/reference_excerpt.json').read_text(encoding='utf-8'))['references'][0];pg=polygon(ref)
    rb=band(ref,512)[1];evaluation=[]
    for v in frozen:
        for g in v['baseline']['groups']:
            evaluation.append(dict(subset=v['subset'],k=v['k'],method='whole_ring_median_5deg',candidate=g['anchor'],
                support=g['support'],reference_bev_iou=iou(polygon(g),pg),
                reference_erp_band_iou=band_iou(band(g)[1],rb)))
        for strict in [False,True]:
            b=np.array(v['majority_strict' if strict else 'majority_half'])
            evaluation.append(dict(subset=v['subset'],k=v['k'],method='ERP_strict' if strict else 'ERP_half',
                candidate='dense_contour_no_sparse_corner_claim',support=v['k'],reference_bev_iou=None,
                reference_erp_band_iou=band_iou(b,rb)))
    lookup={tuple(sorted(v['subset'].split('+'))):v for v in frozen}
    replay=[]
    for order_no,order in enumerate(permutations(rs),1):
        previous=None
        for k in range(1,4):
            ids=tuple(sorted(r['id'] for r in order[:k]));v=lookup[ids];candidate=v['baseline']['groups'][0]
            q=iou(polygon(candidate),pg)
            replay.append(dict(order_id=order_no,order='>'.join(r['worker'] for r in order),k=k,
                current_ids='+'.join(ids),reference_bev_iou=q,
                step_reference_delta=None if previous is None else q-previous[1],
                step_angle_deg=None if previous is None else full_alignment(pairs(previous[0]),pairs(candidate))['distance']))
            previous=(candidate,q)
    table('real_pilot_all_six_order_traces.csv',replay)
    table('real_pilot_thresholds.csv',rows);table('real_pilot_reference_after_freeze.csv',evaluation)
    # Actual 3-worker leave-one-out member effect on candidate geometry (all k=2).
    pair_candidates=[v['baseline']['groups'][0] for v in frozen if v['k']==2 and len(v['baseline']['groups'])==1]
    distances=[full_alignment(pairs(a),pairs(b))['distance'] for a,b in combinations(pair_candidates,2)]
    info=dict(images=1,workers=3,all_nonempty_subsets=7,input_projection_max_error_h=err,
      real_distance_matrix=full_distance_matrix(rs),same_k2_candidate_distances_deg=distances,
      prediction_sha256=prediction_hash,reference_loaded_after_prediction_write=True,
      limits='access-selected tiny pilot; original reference is not newly visually adjudicated; no method selection from reference')
    dump('real_pilot_summary.json',info);return rs,info

def projectivity(base):
    records=[]
    for name,delta in [('A',0),('B',4),('C',7),('D',9.5)]:
        r=copy.deepcopy(base);r['id']=r['worker']='synthetic_'+name;r['synthetic']=True;r['evidence_role']='controlled_transformation_not_new_human'
        p=np.asarray(r['points']);p[:,1]+=delta*H/180.;r['points']=p.tolist()
        records.append(r)
    out={}
    for name,sub in [('ABC',records[:3]),('ABCD',records)]:
        d=full_distance_matrix(sub);groups=complete_groups(d,5.)
        out[name]=dict(ids=[r['id'] for r in sub],distances=d,groups=[[sub[i]['id'] for i in g] for g in groups])
    out['old_pair_distances_max_change']=np.max(abs(np.asarray(out['ABC']['distances'])-np.asarray(out['ABCD']['distances'])[:3,:3]))
    out['interpretation']='B,C separated after D arrived; their pairwise distance and all old comparisons are unchanged. This is a partition-policy effect, not a changed annotation.'
    dump('projective_inconsistency.json',out);return out

def subdivisions(base):
    rows=[];all_records=[]
    for dp in [0.,2.,8.,20.]:
        r=insert_subdivision(base,0,.5,dp,worker=f'controlled_top_delta_{dp}')
        a=partial_alignment(pairs(base),pairs(r),5.)
        ba,bb=band(base,4096)[1],band(r,4096)[1]
        rows.append(dict(top_delta_px=dp,base_pairs=len(pairs(base)),other_pairs=len(pairs(r)),
          equal_count_baseline_distance=full_alignment(pairs(base),pairs(r))['distance'],
          partial_matches=a['matched'],partial_ambiguous=a['ambiguous'],unmatched_other=str(a['unmatched_other']),
          bev_iou=iou(polygon(base),polygon(r)),erp_band_iou=band_iou(ba,bb),
          top_max_difference_px=float(abs(ba[0]-bb[0]).max()),bottom_max_difference_px=float(abs(ba[1]-bb[1]).max())))
        all_records.append(r)
    out=derive_candidates([dict(base,id='original_anchor',worker='original_anchor'),all_records[0]],5.)
    dump('subdivision_candidates.json',out);dump('subdivision_records.json',all_records)
    table('subdivision_vs_upper_detail.csv',rows);return rows

def joint_support_counterexample():
    # Three disjoint attached tabs around the same room. No overlap between tabs.
    core=box(-2,-2,2,2);tabs=[box(-.5,2,.5,3),box(2,-.5,3,.5),box(-.5,-3,.5,-2)]
    patterns=[(1,1,0),(1,0,1),(0,1,1)]
    shapes=[unary_union([core]+[tabs[j] for j,b in enumerate(p) if b]) for p in patterns]
    mv=unary_union([a.intersection(b) for a,b in combinations(shapes,2)])
    all3=unary_union([core]+tabs)
    records=[from_floor(np.array(p.exterior.coords)[:-1],worker=f'pattern_{bits}') for p,bits in zip(shapes,patterns)]
    out=dict(patterns=patterns,local_feature_support=[2,2,2],denominator=3,
       full_111_joint_observation_support=0,each_pair_of_features_joint_support=1,
       majority_area=mv.area,each_input_area=[p.area for p in shapes],majority_equals_111=mv.equals(all3),
       majority_iou_to_each_observation=[iou(mv,p) for p in shapes],
       inputs_all_simple=[p.is_valid for p in shapes],majority_simple=mv.is_valid,
       records=records,majority_record=from_floor(np.array(mv.exterior.coords)[:-1],worker='synthetic_marginal_majority'),
       interpretation='This does NOT make marginal majority invalid. It proves local or even pairwise co-support is not full-layout observation support.')
    dump('local_majority_without_joint_witness.json',out);return out

def adjacency_counterexample():
    # Four outer vertices and one interior vertex. Each ring is a VALID observed polygonization.
    xy=np.array([[-3,-2],[3,-2],[3,2],[-3,2],[2.,.5]],float)
    cycles=[[0,4,1,2,3],[0,1,4,2,3],[0,1,2,4,3]]
    polys=[Polygon(xy[c]) for c in cycles]
    assert all(p.is_valid and p.area>0 and p.contains(Point(0,0)) for p in polys)
    witnesses=defaultdict(list)
    for k,c in enumerate(cycles):
        for a,b in zip(c,c[1:]+c[:1]):witnesses[tuple(sorted((a,b)))].append(k)
    selected={e:v for e,v in witnesses.items() if len(v)>=2};deg=Counter(v for e in selected for v in e)
    recs=[from_floor(xy[c],worker=f'valid_ring_{k}') for k,c in enumerate(cycles)]
    bs=[]
    for r in recs:
        try:band(r);bs.append('available')
        except ValueError as e:bs.append(str(e))
    geometric_cycles=[]
    for perm in permutations(range(1,5)):
        c=(0,)+perm
        if c[1]>c[-1]:continue
        ee={tuple(sorted((u,v))) for u,v in zip(c,c[1:]+c[:1])}
        if not ee.issubset(selected):continue
        pg=Polygon(xy[list(c)])
        if not pg.is_valid or not pg.contains(Point(0,0)):continue
        support=sum(ee=={tuple(sorted((u,v))) for u,v in zip(src,src[1:]+src[:1])} for src in cycles)
        geometric_cycles.append(dict(cycle=c,whole_ring_observation_support=support,
          discarded_majority_edges=[list(e) for e in selected if e not in ee]))
    out=dict(points_xy=xy,cycles=cycles,all_input_polygons_valid=True,camera_origin_inside_all=True,
      globally_admissible_cycles_using_a_subset_of_majority_edges=geometric_cycles,
      areas=[p.area for p in polys],edge_support=[dict(edge=e,workers=v,support=len(v)) for e,v in sorted(witnesses.items())],
      majority_edges=[list(e) for e in selected],majority_vertex_degrees=dict(deg),majority_graph_is_single_cycle=all(deg[i]==2 for i in range(5)),
      unordered_point_set_distance=0.,pairwise_bev_iou=[iou(a,b) for a,b in combinations(polys,2)],
      band_status=bs,records=recs,
      interpretation='All vertices are unanimous; the complete selected majority-edge set is not a ring. A separate all-vertex cycle constraint yields ONE valid cycle in this example, but discards a majority edge; that whole ring has only 1/3 observed support. This is not a proof that no unique reconstruction is possible.')
    dump('majority_adjacency_not_a_ring.json',out);return out

def cycle_consistency():
    recs=[]
    for k,angle in enumerate([0.,40.,80.]):
        x=(np.arange(4)*W/4+angle*W/360)%W
        a=np.stack([np.c_[x,np.repeat(5*H/180,4)],np.c_[x,np.repeat(H-5*H/180,4)]],axis=1)
        recs.append(dict(id=f'rot{k}',worker=f'rot{k}',points=a.reshape(-1,2).tolist(),source_pair_indices=list(range(4)),ring_confirmed=False,synthetic=True,evidence_role='controlled_example_not_real_human'))
    ab=full_alignment(pairs(recs[0]),pairs(recs[1]));bc=full_alignment(pairs(recs[1]),pairs(recs[2]));ac=full_alignment(pairs(recs[0]),pairs(recs[2]))
    composed=[bc['mapping'][j] for j in ab['mapping']]
    ensemble=derive_candidates(recs,5.)
    ps=[polygon(r) for r in ensemble['candidates']]
    out=dict(records=recs,AB=ab,BC=bc,AC=ac,composed_AB_BC=composed,
        mismatched_identities=sum(a!=b for a,b in zip(composed,ac['mapping'])),
        all_pair_distances_below_5=all(v['distance']<5 for v in [ab,bc,ac]),
        all_pairwise_optima_unique=not any(v['ambiguous'] for v in [ab,bc,ac]),
        candidate_pairwise_bev_iou=[iou(a,b) for a,b in combinations(ps,2)],candidates=ensemble,
        interpretation='An intentionally near-pole synthetic geometry: unique pairwise optima need not define a globally coherent multiworker identity system. Not an estimate of real conflict frequency.')
    dump('pairwise_unique_but_cycle_inconsistent.json',out);return out

def multiplicity():
    rng=np.random.default_rng(SEED);rows=[];trials=20000
    # Controlled click noise: common x remains exact; upper and lower y fluctuate
    # independently. Thus same-index spherical angle is exactly |delta_y|*180/H.
    # Conditioning on known correspondence isolates the bottleneck-max mechanism.
    sigma_px=4.;tau=5.
    for m in [4,8,16,24,40]:
        differences=rng.normal(0,math.sqrt(2)*sigma_px,(trials,2*m))
        mx=np.max(abs(differences),axis=1)*180/H
        probability=math.erf((tau*H/180)/(2*sigma_px))**(2*m)
        rows.append(dict(pair_count=m,identical_latent_layout=True,vertical_sigma_px=sigma_px,
          trials=trials,threshold_deg=tau,pair_acceptance_mc=float((mx<=tau).mean()),
          mc_standard_error=math.sqrt(probability*(1-probability)/trials),
          pair_acceptance_exact=probability,mean_max_angle=float(mx.mean()),q95_max_angle=float(np.quantile(mx,.95))))
    group_rows=[];n=12;reps=300
    for m in [4,8,16,24]:
        counts=[];singles=[]
        for _ in range(reps):
            obs=rng.normal(0,sigma_px,(n,2*m))
            d=np.max(abs(obs[:,None]-obs[None,:]),axis=2)*180/H
            groups=complete_groups(d,tau);counts.append(len(groups));singles.append(sum(len(g)==1 for g in groups)/n)
        group_rows.append(dict(pair_count=m,workers=n,repeats=reps,mean_clusters=float(np.mean(counts)),mean_singleton_person_fraction=float(np.mean(singles)),threshold_deg=tau))
    table('corner_count_bottleneck_effect.csv',rows);table('corner_count_cluster_effect.csv',group_rows)
    return dict(pair_experiment=rows,cluster_experiment=group_rows,
      assumption='Synthetic independent Gaussian VERTICAL errors, fixed known correspondence, no x errors; one latent layout per cell. Not real-person estimates.')

def finite_pool():
    x=np.array([-1.]*6+[1.]*6);N=len(x);v=np.mean((x-x.mean())**2);rows=[]
    for k in range(1,N+1):
        subsets=list(combinations(range(N),k));means=np.array([x[list(ix)].mean() for ix in subsets])
        member_exact=2*float(np.var(means));formula=2*(N-k)/(k*(N-1))*v
        add=[]
        if k<N:
            for ix,mu in zip(subsets,means):
                for j in set(range(N))-set(ix):add.append(((x[j]-mu)/(k+1))**2)
        nested=float(np.mean(add)) if add else None
        nf=N/(k*(k+1)*(N-1))*v if k<N else None
        rows.append(dict(N=N,k=k,subsets=len(subsets),same_k_squared_change=member_exact,
          same_k_formula=formula,nested_squared_change=nested,nested_formula=nf,
          fresh_iid_same_k_squared_change=2*v/k))
    table('finite_pool_exact_enumeration.csv',rows)
    return dict(population=x,variance_divisor_N=v,rows=rows,
      same_k_max_formula_error=max(abs(r['same_k_squared_change']-r['same_k_formula']) for r in rows),
      nested_max_formula_error=max(abs(r['nested_squared_change']-r['nested_formula']) for r in rows[:-1]),
      interpretation='Exact arithmetic-mean mechanism, NOT a correction formula for nonlinear Lee/IoU/median. At k=N, fixed-pool same-k variability must be zero.')

def stability_quality():
    # Two genuine expression patterns A/B; hypothetical target is B solely for this
    # controlled example. Majority learns prevalence, not this target.
    rows=[];p=.7
    for k in [1,3,5,9,15,25,51]:
        pa=float(binom.sf(k//2,k,p))
        rows.append(dict(k=k,population_prevalence_A=p,prob_output_A=pa,
           independent_same_k_output_disagreement=2*pa*(1-pa),
           error_if_target_is_B=pa,expected_minority_B_output_coverage=1-pa,
           constant_A_disagreement=0.,constant_A_error_if_target_B=1.))
    table('stability_without_quality.csv',rows);return rows

def odd_even():
    # Repeated order replay, not additional independent measured workers.
    rows=[]
    for k in range(2,13):
        count_A=(k+1)//2;count_B=k//2;qhalf=(k+1)//2;qstrict=k//2+1
        for name,q in [('half',qhalf),('strict',qstrict)]:
            onlyA=count_A>=q;onlyB=count_B>=q
            rows.append(dict(k=k,A=count_A,B=count_B,rule=name,threshold=q,
             output='union' if onlyA and onlyB else 'A' if onlyA else 'B' if onlyB else 'intersection'))
    table('odd_even_majority_mechanism.csv',rows);return rows

def main():
    rs,pilot=real_pilot()
    results=dict(real_pilot=pilot,projectivity=projectivity(rs[0]),subdivision=subdivisions(rs[0]),
        joint_support=joint_support_counterexample(),adjacency=adjacency_counterexample(),
        cycle_consistency=cycle_consistency(),multiplicity=multiplicity(),finite_pool=finite_pool(),
        stability_quality=stability_quality(),odd_even=odd_even())
    decisions=[]
    for name,recs in [('real_three',rs),('cycle_counterexample',results['cycle_consistency']['records']),
                      ('neutral_subdivision',[rs[0],insert_subdivision(rs[0])])]:
        for tau in [2.5,5.,9.]:
            decisions.append(dict(case=name,tolerance=tau,details=conditional_decision(recs,tolerance=tau)))
    dump('conditional_decisions.json',decisions)
    joint=[]
    for name,recs in [('real_three',rs),('cycle_counterexample',results['cycle_consistency']['records'])]:
        for tau in [2.5,5.,9.]:
            joint.append(dict(case=name,tolerance=tau,result=joint_ring_alignment(recs,tau)))
    dump('joint_correspondence_search.json',joint)
    # Identical observable distributions under two incompatible latent stories.
    observable={'110':1/3,'101':1/3,'011':1/3}
    dump('observational_nonidentifiability.json',dict(
      model_A='One underlying 111 layout; each person omits one uniformly chosen detail',
      model_B='Three complete scope interpretations 110/101/011, each chosen with probability 1/3, no omission noise',
      observed_distribution_A=observable,observed_distribution_B=observable,KL_A_B=0.,total_variation=0.,
      consequence='More annotations of the same type cannot distinguish these two models without additional assumptions/observations. This is not a claim that one model is true for the real images.'))
    conversions=[]
    for latitude in [0,30,60,80]:
      ang=float(angular([[100,H*(.5-latitude/180)]],[[125.6,H*(.5-latitude/180)]])[0,0])
      conversions.append(dict(latitude_deg=latitude,pixel_dx=25.6,horizontal_spherical_angle_deg=ang,
        vertical_25_6px_angle_deg=25.6*180/H,
        dx_for_5deg_at_this_latitude=float(W/np.pi*np.arcsin(np.sin(np.radians(2.5))/np.cos(np.radians(latitude))))))
    table('pixel_vs_spherical_tolerance.csv',conversions)
    # Central summary intentionally excludes large coordinate ledgers duplicated in per-test files.
    dump('summary.json',{k:v for k,v in results.items() if k not in ['joint_support','cycle_consistency','adjacency']})
    dump('environment.json',dict(python=platform.python_version(),numpy=np.__version__,seed=SEED,
        selected_source_commit='c4e8f908f3725900600dec5909586658092d6234'))
    print(json.dumps(clean(dict(pilot=pilot,subdivision=results['subdivision'],
      majority_joint={k:results['joint_support'][k] for k in ['majority_area','each_input_area','majority_iou_to_each_observation','full_111_joint_observation_support']},
      edge_majority={k:results['adjacency'][k] for k in ['majority_vertex_degrees','pairwise_bev_iou','band_status']},
      cycle={k:results['cycle_consistency'][k] for k in ['AB','BC','AC','mismatched_identities','candidate_pairwise_bev_iou']},
      multiplicity=results['multiplicity'],finite_pool_max_error=results['finite_pool']['same_k_max_formula_error'])),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
