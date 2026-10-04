import sys,json,itertools
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'fixtures'))
import consensus_lab_original as lab
from shapely.geometry import Point
known=json.loads((BASE/'fixtures/known_certification_objective_mismatch.json').read_text())
a,b=known['records']
rng=np.random.default_rng(704031)
orders=np.array(list(itertools.permutations(range(3))))
found=[]
for it in range(20000):
    cp=(lab.pairs(a)+lab.pairs(b))/2
    cp[:,:,1]+=rng.normal(0,7,(3,2))
    cp[:,:,0]+=rng.normal(0,1.5,(3,1))
    c={'id':'S2','worker':'S2','synthetic':True,'points':cp.reshape(-1,2).tolist()}
    rs=[a,b,c];mat={};full={};part={};okay=True
    for i,j in itertools.combinations(range(3),2):
        co=lab.costs(lab.pairs(rs[i]),lab.pairs(rs[j]));mat[i,j]=co
        selected=co[np.arange(3)[None,:],orders]
        maxes=selected.max(1);sums=selected.sum(1)
        order=np.argsort(maxes)
        if maxes[order[0]]>5 or maxes[order[1]]-maxes[order[0]]<1e-8:okay=False;break
        full[i,j]=orders[order[0]]
        feasible=np.where(maxes<=5+1e-10)[0];q=feasible[np.argmin(sums[feasible])]
        if len(feasible)>1 and np.sort(sums[feasible])[1]-sums[q]<1e-8:okay=False;break
        part[i,j]=orders[q]
    if not okay:continue
    if not np.array_equal(full[1,2][full[0,1]],full[0,2]):continue
    anchor= int(np.argmin([sum(mat[min(i,j),max(i,j)][np.arange(3),full[min(i,j),max(i,j)]].max() for j in range(3) if j!=i) for i in range(3)]))
    amaps={anchor:np.arange(3)}
    for j in range(3):
        if j==anchor:continue
        amaps[j]=part[anchor,j] if anchor<j else np.argsort(part[j,anchor])
    induced={f'{i}-{j}':float(mat[i,j][amaps[i],amaps[j]].max()) for i,j in itertools.combinations(range(3),2)}
    if max(induced.values())<=5+1e-8:continue
    if not all(lab.polygon(r).is_valid and lab.polygon(r).contains(Point(0,0)) for r in rs):continue
    dec=lab.conditional_decision(rs,tolerance=5.)
    if dec['status']!='single_candidate_conditional_on_method_tolerance':continue
    out={'seed':704031,'iteration':it,'records':rs,'full_maps':{f'{i}-{j}':v.tolist() for (i,j),v in full.items()},'partial_maps':{f'{i}-{j}':v.tolist() for (i,j),v in part.items()},'selected_anchor':anchor,'induced_actual_donor_diameters_deg':induced,'conditional_decision':dec,'scope':'synthetic existence counterexample; exploratory search, not frequency estimate'}
    (BASE/'fixtures/three_record_actual_mapping_diameter_counterexample.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ['records','conditional_decision']},indent=2));break
else: print('NO COUNTEREXAMPLE IN SEARCH WINDOW')
