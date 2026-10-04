"""Independent checks for the 2026-10-04 complete-layout delivery.

Numerical formulas, 3-D spherical distances, and complete-link partitions are
implemented here rather than imported from the delivered implementation.
Only the final 18-prefix replay intentionally calls the delivered inference.
"""
from pathlib import Path
from itertools import combinations, permutations
from fractions import Fraction
import argparse, csv, hashlib, json, math, sys
import numpy as np

ROOT = Path(__file__).resolve().parent
P = ROOT / 'replay'
def rows(name):
    with (P/'results'/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def load(name): return json.loads((P/name).read_text(encoding='utf-8'))
def parts(d, cut):
    clusters = [(i,) for i in range(len(d))]
    while len(clusters) > 1:
        choices = [(max(d[a,b] for a in clusters[i] for b in clusters[j]), i, j)
                   for i,j in combinations(range(len(clusters)), 2)]
        dist, i, j = min(choices)
        if dist > cut: break
        merged = tuple(sorted(clusters[i] + clusters[j]))
        clusters = [c for k,c in enumerate(clusters) if k not in (i,j)] + [merged]
    return sorted(clusters)
def unit_vectors(points):
    points = np.asarray(points, float)
    u = points[...,0] * (2*math.pi/1024)
    v = (points[...,1]/512 - .5) * math.pi
    return np.stack((np.cos(v)*np.cos(u), np.cos(v)*np.sin(u), np.sin(v)),axis=-1)
def spherical_distance(a,b):
    av,bv=unit_vectors(a),unit_vectors(b)
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(av,bv),axis=-1),np.sum(av*bv,axis=-1)))
def whole_distance(a,b):
    m=len(a)
    return min(float(spherical_distance(a,b[ix]).max())
               for ix in [np.roll(order,s) for order in (np.arange(m),np.arange(m)[::-1]) for s in range(m)])

def main():
    result = {}
    raw = load('inputs/current_excerpt.json')['images'][0]['annotations']
    matrix = np.zeros((len(raw),len(raw)))
    for i,j in combinations(range(len(raw)),2):
        a,b=(np.array(raw[k]['points']).reshape(-1,2,2) for k in (i,j))
        matrix[i,j]=matrix[j,i]=whole_distance(a,b)
    expected=np.array(load('results/real_pilot_summary.json')['real_distance_matrix'])
    result['independent_spherical_3d']={'matrix':matrix.tolist(), 'maximum_difference':float(abs(matrix-expected).max())}
    assert abs(matrix-expected).max()<1e-12

    # Exact rational moments and all member-addition transitions, independent
    # of the delivery's floating-point variance calculations.
    x=[-1]*6+[1]*6; n=len(x); finite=[]
    for k in range(1,n+1):
        subsets=list(combinations(range(n),k))
        means=[Fraction(sum(x[i] for i in s),k) for s in subsets]
        avg=sum(means)/len(means)
        same=2*sum((m-avg)**2 for m in means)/len(means)
        want=Fraction(2*(n-k),k*(n-1))
        assert same==want
        if k<n:
            transitions=[(Fraction(sum(x[i] for i in s)+x[j],k+1)-m)**2
                         for s,m in zip(subsets,means) for j in range(n) if j not in s]
            nested=sum(transitions)/len(transitions)
            assert nested==Fraction(n,k*(k+1)*(n-1))
        else: nested=None
        finite.append({'k':k,'subsets':len(subsets),'same_exact':str(same),'nested_exact':str(nested) if nested is not None else None})
    supplied=rows('finite_pool_exact_enumeration.csv')
    result['finite_pool_exact_rational']={'subsets':sum(r['subsets'] for r in finite),'rows':finite,
      'max_float_difference':max(abs(float(Fraction(r['same_exact']))-float(s['same_k_squared_change'])) for r,s in zip(finite,supplied))}

    # Same seed and same known-correspondence vertical-noise experiment. The
    # scalar normal draw count differs from the count of independent pair trials.
    rng=np.random.default_rng(20261004); pair=[]
    for m in (4,8,16,24,40):
        errors=rng.normal(0,math.sqrt(2)*4,(20000,2*m))
        maxima=abs(errors).max(axis=1)*180/512
        exact=math.erf((5*512/180)/8)**(2*m)
        pair.append({'pair_count':m,'acceptance_mc':float(np.mean(maxima<=5)), 'acceptance_exact':exact,
                     'scalar_draws':errors.size})
    for r,s in zip(pair, rows('corner_count_bottleneck_effect.csv')):
        assert r['acceptance_mc']==float(s['pair_acceptance_mc'])
        assert r['acceptance_exact']==float(s['pair_acceptance_exact'])
    result['known_correspondence_noise']={'pair_trials':100000,'scalar_gaussian_draws':sum(r['scalar_draws'] for r in pair),'rows':pair}
    clusters=[]
    for m in (4,8,16,24):
        counts=[];singletons=[]
        for _ in range(300):
            obs=rng.normal(0,4,(12,2*m))
            d=np.zeros((12,12))
            for i,j in combinations(range(12),2): d[i,j]=d[j,i]=max(abs(obs[i]-obs[j]))*180/512
            group=parts(d,5)
            counts.append(len(group));singletons.append(sum(len(g)==1 for g in group)/12)
        clusters.append({'pair_count':m,'mean_clusters':float(np.mean(counts)),'mean_singleton_person_fraction':float(np.mean(singletons))})
    for r,s in zip(clusters,rows('corner_count_cluster_effect.csv')):
        assert r['mean_clusters']==float(s['mean_clusters'])
        assert r['mean_singleton_person_fraction']==float(s['mean_singleton_person_fraction'])
    result['independent_complete_link']={'settings':4,'repetitions_per_setting':300,'total':1200,'rows':clusters,'all_aggregate_values_equal':True}

    # Real-data prefixes: invoke inference freshly for every prefix, rather than
    # merely looking up the seven already-frozen subset predictions.
    sys.path.insert(0,str(P/'src'))
    from consensus_lab import baseline_candidates, derive_candidates
    frozen={tuple(sorted(v['subset'].split('+'))):v for v in load('results/real_pilot_predictions_frozen.json')}
    replay=[]
    for order_no,order in enumerate(permutations(raw),1):
        for k in range(1,4):
            records=list(order[:k]);key=tuple(sorted(r['id'] for r in records));target=frozen[key]
            baseline=baseline_candidates(records,5)
            prototype=derive_candidates(records,5)
            assert baseline==target['baseline'];assert prototype==target['prototype']
            replay.append({'order':order_no,'k':k,'member_ids':[r['id'] for r in records],'baseline_equal':True,'prototype_equal':True})
    result['fresh_18_prefix_inference']={'orders':6,'prefix_calls':len(replay),'distinct_subsets':len(frozen),'rows':replay}

    (ROOT/'independent_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:({x:v for x,v in val.items() if x not in ('rows','matrix')}) for k,val in result.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
