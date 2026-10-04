"""Fixed fixtures, including explicitly synthetic controls. No hidden filtering."""
import copy,json
from pathlib import Path
import numpy as np
from arc_consensus import W,H,TAU,project,Ring,footprint
ROOT=Path(__file__).resolve().parents[1]

def make_record(poly,top=1.,id='s0',worker='s0'):
    p=np.asarray(poly,float);top=np.broadcast_to(top,len(p))
    a=project(np.c_[p[:,0],top,p[:,1]]);b=project(np.c_[p[:,0],-np.ones(len(p)),p[:,1]])
    points=np.stack([a,b],axis=1).reshape(-1,2).tolist()
    return dict(id=id,worker=worker,image='synthetic',points=points,independent=True,consensus_eligible=True,
        condition='synthetic',evidence_kind='synthetic_control',ring_confirmed=False,
        order_status='synthetic_known_order',source_pair_indices=list(range(len(p))),source_point_indices=list(range(2*len(p))))

def rectangle(radius=2.,top=1.,id='s0'):
    return make_record([[-radius,radius],[-radius,-radius],[radius,-radius],[radius,radius]],top,id,id)

def thin_feature():
    a=rectangle();r=Ring(a);q=np.array(a['points']).reshape(-1,2,2)
    positions=[100.2,100.4,100.6];y=r.evaluate(np.array(positions)/W*TAU)
    extras=[]
    for j,x in enumerate(positions):extras.append([[x,y[0,j]-(20. if j==1 else 0.)],[x,y[1,j]]])
    # The synthetic source has known monotone order; no observed input is reordered.
    p=sorted(q.tolist()+extras,key=lambda p:p[0][0]);b=copy.deepcopy(a)
    b.update(id='thin_top_feature',worker='thin_top_feature',points=[z for pair in p for z in pair],
             source_pair_indices=list(range(len(p))),source_point_indices=list(range(2*len(p))))
    return a,b

def records_and_refs():
    a=json.loads((ROOT/'inputs/current_excerpt.json').read_text())['images'][0]
    b=json.loads((ROOT/'inputs/real24_points.json').read_text())
    refs=json.loads((ROOT/'inputs/reference_excerpt.json').read_text())['references']
    return [('pilot3',a['code'],a['annotations'],refs),('real24',b['image'],b['records'],json.loads((ROOT/'inputs/real24_reference.json').read_text()))]

def failure_records():
    old=json.loads((ROOT/'inputs/prior_worker_rpc_geometry.json').read_text());by={r['id']:r for r in old['records']}
    triples={
    'R01518':[[84.62809917355372,121.30027548209368,400.5730027548209],[33.85123966942149,189.00275482093664,331.4600550964187],[150.92011019283746,212.98071625344355,304.6611570247934],[299.0192837465565,204.51790633608817,314.534435261708],[339.9228650137741,163.61432506887053,358.258953168044],[304.6611570247934,157.9724517906336,363.900826446281],[359.6694214876033,100.14325068870522,421.7300275482093],[428.7823691460055,139.63636363636363,382.23691460055096],[620.6060606060606,148.099173553719,373.7741046831956],[850.5123966942149,119.88980716253444,401.9834710743802],[897.0578512396694,90.26997245179064,431.60330578512395],[943.603305785124,121.30027548209368,401.9834710743802]],
    'R01784':[[57.66213592233011,123.27766990291262,385.73980582524274],[208.7766990291262,214.74174757281554,310.18252427184467],[288.31067961165047,208.7766990291262,310.18252427184467],[355.9145631067961,135.20776699029128,399.6582524271845],[427.49514563106794,159.06796116504853,353.926213592233],[618.3766990291263,161.05631067961164,353.926213592233],[845.0485436893205,131.23106796116505,399.6582524271845],[894.7572815533981,101.40582524271845,433.46019417475725]]}
    out=[]
    for id,t in triples.items():
        r=copy.deepcopy(by[id]);r['points']=[q for x,u,b in t for q in [[x,u],[x,b]]]
        r.update(image=old['image'],evidence_kind='human_observed',order_status='human_confirmed')
        r['source_point_indices']=list(range(16)) if id=='R01784' else [2,3,0,1,4,5,6,7,10,11,8,9,12,13,14,15,16,17,18,19,20,21,22,23]
        r['source_pair_indices']=list(range(8)) if id=='R01784' else [1,0,2,3,5,4,6,7,8,9,10,11]
        r['restored_footprint_max_error_h']=float(np.max(abs(footprint(r)[0]-np.array(r['footprint']))))
        out.append(r)
    return out
