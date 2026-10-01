#!/usr/bin/env python3
"""Independent focused audit; reads returned source, writes only audit directory."""
import os, sys, json, itertools, math
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
ROOT=Path(os.environ.get('RETURNED_ROOT','/workspace/scratch/a365811da80c/audit-oct1-inputs/returned/layout_methods_20261001'))
sys.path.insert(0,str(ROOT/'src'))
from geometry_core import from_floor,reconstruct,path_metrics
from matching import endpoint_costs,cyclic_align,align_cost,angular_window_paths
from run_order_and_hybrid import classify_path
from run_insertion_noise import unordered
from real_inputs import get
OUT=Path(__file__).resolve().parent

def all_circular_maps(c,gap):
    """Exhaustive independent enumeration: injective partial maps in either circle order."""
    n,m=c.shape;best=math.inf;maps=[]
    for k in range(min(n,m)+1):
        for aa in itertools.combinations(range(n),k):
            for bb in itertools.permutations(range(m),k):
                if k>2:
                    cyc=list(bb)+[bb[0]]
                    ds=sum(cyc[t]>cyc[t+1] for t in range(k))
                    if ds not in (1,k-1):continue
                val=sum(c[i,j] for i,j in zip(aa,bb))+(n+m-2*k)*gap
                if val<best-1e-9:best=val;maps=[tuple(zip(aa,bb))]
                elif abs(val-best)<1e-9:maps.append(tuple(zip(aa,bb)))
    return float(best),sorted(set(maps))

def all_dp_maps(c,gap):
    """Enumerate map identities from all optimal DP predecessors (not edit interleavings)."""
    n,m=c.shape;d=np.full((n+1,m+1),np.inf);d[:,0]=np.arange(n+1)*gap;d[0,:]=np.arange(m+1)*gap
    for i in range(1,n+1):
        for j in range(1,m+1):d[i,j]=min(d[i-1,j-1]+c[i-1,j-1],d[i-1,j]+gap,d[i,j-1]+gap)
    from functools import lru_cache
    @lru_cache(None)
    def trace(i,j):
        if not i or not j:return {()}
        out=set()
        if abs(d[i,j]-d[i-1,j-1]-c[i-1,j-1])<1e-9:out|={p+((i-1,j-1),) for p in trace(i-1,j-1)}
        if abs(d[i,j]-d[i-1,j]-gap)<1e-9:out|=trace(i-1,j)
        if abs(d[i,j]-d[i,j-1]-gap)<1e-9:out|=trace(i,j-1)
        return out
    return float(d[n,m]),trace(n,m)

def true_cyclic_dp_maps(c,gap):
    n,m=c.shape;best=math.inf;maps=set()
    for rev in (False,True):
        for k in range(m):
            ix=np.roll(np.arange(m)[::-1] if rev else np.arange(m),-k)
            cost,ss=all_dp_maps(c[:,ix],gap)
            orig={tuple((i,int(ix[j])) for i,j in s) for s in ss}
            if cost<best-1e-9:best=cost;maps=orig
            elif abs(cost-best)<1e-9:maps|=orig
    return best,sorted(maps)

results={}
# Actual bundle's published same-point/different-ring example.
p=np.array([[-3,-3],[3,-3],[3,3],[1,.7],[-3,3]],float);q=p[[0,1,3,2,4]]
a,b=from_floor(p),from_floor(q);ct,cb=endpoint_costs(a,b,4);c=(ct+cb)/2
best,maps=all_circular_maps(c,2);got=cyclic_align(a,b,4,2)
results['published_tie_counterexample']={'returned':got,'exhaustive_cost':best,'exhaustive_best_map_count':len(maps),'exhaustive_best_maps':maps}
assert got['cost']==best==4 and got['equally_best_maps']==1 and len(maps)==2
rotated=[]
for shift in range(len(p)):
    ix=np.roll(np.arange(len(p)),shift)
    r=cyclic_align(from_floor(p[ix]),b,4,2)
    rotated.append({'a_start_shift':shift,'reported_ties':r['equally_best_maps'],'map_in_original_indices':sorted((int(ix[i]),j) for i,j in r['matched'])})
results['published_tie_counterexample']['a_start_shift_sensitivity']=rotated

# Check optimum values, circular seam and reversal using random tiny costs.
rng=np.random.default_rng(1001);checks=[]
for n,m in [(3,3),(3,4),(4,3),(4,4),(5,4),(4,5)]:
    for rep in range(10):
        c=rng.integers(0,10,(n,m)).astype(float);gap=2
        brute,bmaps=all_circular_maps(c,gap);dp,dmaps=true_cyclic_dp_maps(c,gap)
        returned=min(align_cost(c[:,np.roll(seq,-k)],gap)['cost'] for seq in (np.arange(m),np.arange(m)[::-1]) for k in range(m))
        assert abs(brute-dp)<1e-9 and set(bmaps)==set(dmaps) and abs(returned-brute)<1e-9
        checks.append({'n':n,'m':m,'rep':rep,'cost':brute})
results['circular_objective_crosscheck']={'cases':len(checks),'all_minimum_costs_match_exhaustive':True,'all_reference_dp_map_sets_match_exhaustive':True}

# Valid same room, same wedge, opposite traversal encoding.
p=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
wa=angular_window_paths(p,970,1035)[0];wb=angular_window_paths(p[::-1],970,1035)[0]
ca,cb=from_floor(p),from_floor(p[::-1]);dec=classify_path(wa['points'],wb['points'],.01,.005)
fixed=classify_path(wa['points'],wb['points'][::-1],.01,.005)
results['reversed_ring_local_counterexample']={'room':p.tolist(),'a_path':wa,'b_path':wb,'cyclic_match':cyclic_align(ca,cb,4,2),'as_implemented_decision':dec,'gate_aligned_decision':fixed}
assert dec['hausdorff_lower']<1e-12 and dec['geometry']=='geometrically_distinct' and fixed['geometry']=='geometrically_close'
assert cyclic_align(ca,cb,4,2)['cost']<1e-12
for shift in range(len(p)):
    pp=np.roll(p,shift,axis=0)
    got=np.asarray(angular_window_paths(pp,970,1035)[0]['points'])
    assert np.allclose(got,wa['points'])
assert np.allclose(angular_window_paths(p,1994,2059)[0]['points'],wa['points'])
results['window_seam_and_start']={'ring_start_shifts_tested':4,'window_plus_full_turn':True,'unchanged':True}
real_orientation=[]
for (ra,rb),lo,hi in [(get()[0],970,1035),(get()[2],483,515)]:
    pa,pb=reconstruct(ra)['floor'],reconstruct(rb)['floor']
    aa=angular_window_paths(pa,lo,hi)[0]['points'];bb=angular_window_paths(pb,lo,hi)[0]['points'];br=angular_window_paths(pb[::-1],lo,hi)[0]['points']
    original=classify_path(aa,bb,.01,.005);reversed_=classify_path(aa,br,.01,.005)
    real_orientation.append({'record':ra['id'],'original':original,'reversed_b_ring':reversed_})
results['real_window_reversal_effect']=real_orientation

# Arc-length summaries should not change under collinear input subdivision.
# Same horizontal segment; the comparison line is oblique, distance varies with x.
a0=np.array([[0,0],[1,0]],float)
a1=np.r_[np.c_[np.linspace(0,.001,1001),np.zeros(1001)],[[1.,0.]]]
b0=np.array([[0,0],[1,1]],float)
m0=path_metrics(a0,b0,.01);m1=path_metrics(a1,b0,.01)
results['vertex_density_summary_counterexample']={'geometry_a_identical':True,'sparse_nodes':len(a0),'dense_nodes':len(a1),'sparse_metrics':m0,'dense_metrics':m1,'analytic_arc_length_mean_a_b':1/(2*np.sqrt(2)),'analytic_arc_length_coverage_a_001':.01*np.sqrt(2)}

# Actual sensitivity grid: do tie omissions alter the existing 45-case claims?
amb=[];conflicts=0;zero_coverage=[]
for a,b in get():
    for sigma,gap in itertools.product((1,2,4,8,16),(.5,2,8)):
        sideouts={}
        for side in ('bound','top','bottom'):
            ct,cb=endpoint_costs(a,b,sigma);c=(ct+cb)/2 if side=='bound' else ct if side=='top' else cb
            got=cyclic_align(a,b,sigma,gap,side);true,ms=true_cyclic_dp_maps(c,gap)
            assert abs(got['cost']-true)<1e-8
            if len(ms)!=got['equally_best_maps']:amb.append({'record':a['id'],'sigma':sigma,'gap':gap,'side':side,'reported':got['equally_best_maps'],'true':len(ms)})
            sideouts[side]=got
            if not got['matched']:zero_coverage.append((a['id'],sigma,gap,side))
        tm=dict(sideouts['top']['matched']);bm=dict(sideouts['bottom']['matched']);ti={v:k for k,v in tm.items()};bi={v:k for k,v in bm.items()}
        conflicts+=bool(any(tm[k]!=bm[k] for k in tm.keys()&bm.keys()) or any(ti[k]!=bi[k] for k in ti.keys()&bi.keys()))
results['actual_sensitivity_grid']={'settings':45,'endpoint_mode_runs':135,'wrong_tie_counts':amb,'split_conflict_settings':conflicts,'zero_match_runs':len(zero_coverage)}
(OUT/'matching_audit_results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
print(json.dumps({k:v for k,v in results.items() if k not in ('vertex_density_summary_counterexample','published_tie_counterexample','reversed_ring_local_counterexample')},indent=2))
print('Tie counterexample:',got if False else results['published_tie_counterexample'])
print('Reversal decision:',dec)
print('Sparse/dense path mean:',m0['mean_a_b'],m1['mean_a_b'],'coverage:',m0['coverage_a_001'],m1['coverage_a_001'])
