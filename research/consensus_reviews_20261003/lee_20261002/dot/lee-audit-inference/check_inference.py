"""Independent finite-set proofs by exhaustive small checks; no repository changes."""
from fractions import Fraction as F
from itertools import combinations, product, permutations
from math import comb
import json, csv
from pathlib import Path

OUT=Path(__file__).resolve().parent
INPUT=OUT.parent/'lee-audit-original/research/lee_tile_stage1_20261002/input.json'
GATES={'main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate'}

def cross(a,b): return a[0]*b[1]-a[1]*b[0]
def sub(a,b): return a[0]-b[0],a[1]-b[1]
def sign(v):return (v>0)-(v<0)
def orient(a,b,c):return cross(sub(b,a),sub(c,a))
def onseg(a,b,p):return orient(a,b,p)==0 and all(min(a[i],b[i])<=p[i]<=max(a[i],b[i]) for i in (0,1))
def intersects(a,b,c,d):
    z=[orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)]
    if any(x==0 for x in z):
        return onseg(a,b,c) or onseg(a,b,d) or onseg(c,d,a) or onseg(c,d,b)
    return sign(z[0])!=sign(z[1]) and sign(z[2])!=sign(z[3])
def simple(ps):
    n=len(ps)
    if len(set(ps))<n:return False
    return not any(intersects(ps[i],ps[(i+1)%n],ps[j],ps[(j+1)%n]) for i in range(n) for j in range(i+1,n) if j!=i+1 and not(i==0 and j==n-1))
def origin_location(ps):
    p=(F(0),F(0)); winding=0
    for a,b in zip(ps,ps[1:]+ps[:1]):
        if onseg(a,b,p):return 'boundary'
        if a[1]<=0<b[1] and orient(a,b,p)>0:winding+=1
        elif b[1]<=0<a[1] and orient(a,b,p)<0:winding-=1
    return 'inside' if winding else 'outside'
def kernel_test(coords):
    ps=[tuple(F(str(z)) for z in p) for p in coords]
    cr=[cross(a,b) for a,b in zip(ps,ps[1:]+ps[:1])]
    orient_sign=sign(sum(cr)); assert orient_sign
    scale=max(1.,max((float(x*x+y*y)**.5 for x,y in ps)))
    ds=[float(orient_sign*c)/(sum(float(x*x) for x in sub(b,a))**.5) for a,b,c in zip(ps,ps[1:]+ps[:1],cr)]
    tol=1e-10*scale
    mn=min(ds)
    status='strict_common_origin_kernel' if mn>tol else 'not_common_origin_kernel' if mn< -tol else 'near_boundary_uncertain'
    return dict(simple=simple(ps),origin_location=origin_location(ps),kernel_status=status,min_oriented_edge_distance=mn,scale=scale,tolerance=tol,negative_edges=sum(orient_sign*c<0 for c in cr),exact_zero_edges=sum(c==0 for c in cr),vertices=len(ps))

def vote(ps,k,strict):
    return sum(1<<i for i in range(8) if (sum((p>>i)&1 for p in ps)*2 > k if strict else sum((p>>i)&1 for p in ps)*2 >= k))
def iou(a,b):return F((a&b).bit_count(),(a|b).bit_count()) if a|b else F(1)
def hg(N,r,k,j):
    if j<0 or j>r or k-j<0 or k-j>N-r:return F(0)
    return F(comb(r,j)*comb(N-r,k-j),comb(N,k))

def run():
    results={}
    # Every possible pixel vote sequence through length 10; then aggregate independent pixels.
    tests=0
    for n in range(2,11):
      for bits in product((0,1), repeat=n):
       for strict in (False,True):
        for k in range(1,n):
          s=sum(bits[:k]); a=(2*s>k) if strict else (2*s>=k)
          b=(2*(s+bits[k])>k+1) if strict else (2*(s+bits[k])>=k+1)
          expands=(k%2==1) != strict
          assert (not a or b) if expands else (not b or a)
          tests+=1
    results['parity_checks']=tests
    # Exact finite-pool probability of changing inclusion in a nested step.
    max_error=F(0);checks=0
    for N in range(2,13):
      for r in range(N+1):
       for k in range(1,N):
        for strict in (False,True):
          t=k//2+1 if strict else (k+1)//2
          tn=(k+1)//2+1 if strict else (k+2)//2
          if t==tn: analytic=hg(N,r,k,t-1)*F(r-t+1,N-k)
          else: analytic=hg(N,r,k,t)*F(N-r-k+t,N-k)
          q0=sum(hg(N,r,k,j) for j in range(t,k+1))
          q1=sum(hg(N,r,k+1,j) for j in range(tn,k+2))
          assert analytic==abs(q1-q0)
          checks+=1
    results['adjacent_hypergeometric_checks']=checks
    # Deduplicated mean expectation under all ordered independent draw sequences.
    vals=[F(0),F(1,7),F(3,5),F(1)]
    draws=3;du=[];raw=[]
    for ids in product(range(len(vals)),repeat=draws):
      seen=set(ids);du.append(sum(vals[i] for i in seen)/len(seen));raw.append(sum(vals[i] for i in ids)/draws)
    mu=sum(vals)/len(vals)
    assert sum(du)/len(du)==mu
    results['dedup_exact_check']={'population_mean':float(mu),'expected_dedup_mean':float(sum(du)/len(du)),'var_dedup':float(sum((z-mu)**2 for z in du)/len(du)),'var_raw':float(sum((z-mu)**2 for z in raw)/len(raw))}
    # Common-center, equal-area tiles: majority can be worse than every person against G.
    persons=[0b0111,0b1011,0b1101];G=1;c=vote(persons,3,False)
    assert c==15
    results['majority_worse_than_every_person']={'persons_masks':persons,'reference_mask':G,'individual_ious':[str(iou(p,G)) for p in persons],'majority_iou':str(iou(c,G)),'curves':{m:[str(sum(iou(vote(p,k,s),G) for p in combinations(persons,k))/comb(3,k)) for k in range(1,4)] for m,s in [('mv50',False),('strict',True)]}}
    # Majority area-symmetric-difference optimum need not maximize average personal IoU.
    persons=[1,7,27];c=vote(persons,3,False);a=7
    results['not_personal_mean_iou_optimum']={'persons_masks':persons,'majority_mask':c,'alternative_mask':a,'majority_mean_iou':str(sum(iou(c,p) for p in persons)/3),'alternative_mean_iou':str(sum(iou(a,p) for p in persons)/3),'majority_mean_symmetric_difference':str(F(sum((c^p).bit_count() for p in persons),3)),'alternative_mean_symmetric_difference':str(F(sum((a^p).bit_count() for p in persons),3))}
    assert sum(iou(a,p) for p in persons)>sum(iou(c,p) for p in persons)
    # E[J] is not ratio of expected area even for nested predictions containing G.
    candidates=[1,3]
    results['expectation_ratio_counterexample']={'individual_ious':[str(iou(c,1)) for c in candidates],'mean_iou':str(sum(iou(c,1) for c in candidates)/2),'ratio_expected_intersection_union':str(F(sum((c&1).bit_count() for c in candidates),sum((c|1).bit_count() for c in candidates)))}
    # Kernel test has exact rational sign tests, tolerance only conservatively labels boundary closeness.
    data=json.load(INPUT.open(),parse_float=str)
    rows=[]
    for img in data['images']:
      for a in img['annotations']:
        gate=a['main_consensus_gate']['status']
        if a['independent'] and a['consensus_eligible'] and gate in GATES:
          if not a['footprint']:
            rows.append(dict(image=img['code'],condition=a['condition'],gate=gate,id=a['id'],kernel_status='missing_geometry'));continue
          rows.append(dict(image=img['code'],condition=a['condition'],gate=gate,id=a['id'],**kernel_test(a['footprint'])))
    groups=[]
    for key in sorted({(r['image'],r['condition'],r['gate']) for r in rows}):
      rs=[r for r in rows if (r['image'],r['condition'],r['gate'])==key]
      groups.append(dict(image=key[0],condition=key[1],gate=key[2],n=len(rs),all_simple=all(r['simple'] for r in rs),all_strictly_origin_star_shaped=all(r['kernel_status']=='strict_common_origin_kernel' for r in rs),strict_origin_star_shaped=sum(r['kernel_status']=='strict_common_origin_kernel' for r in rs),not_origin_star_shaped=[r['id'] for r in rs if r['kernel_status']=='not_common_origin_kernel'],near_boundary=[r['id'] for r in rs if r['kernel_status']=='near_boundary_uncertain'],camera_outside=[r['id'] for r in rs if r['origin_location']=='outside'],minimum_edge_distance=min(r['min_oriented_edge_distance'] for r in rs)))
    results['kernel_summary']={'n':len(rows),'all_simple':all(r['simple'] for r in rows),'strict_origin_star_shaped':sum(r['kernel_status']=='strict_common_origin_kernel' for r in rows),'not_origin_star_shaped':sum(r['kernel_status']=='not_common_origin_kernel' for r in rows),'near_boundary':sum(r['kernel_status']=='near_boundary_uncertain' for r in rows),'groups_all_star':sum(g['all_strictly_origin_star_shaped'] for g in groups),'groups':groups}
    (OUT/'verification_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'kernel_records.csv').open('w') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
