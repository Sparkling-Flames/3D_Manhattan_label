import ast, copy, importlib.util, json, pathlib
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from collections import defaultdict
import math

ROOT=pathlib.Path(__file__).parent
def get_functions(path,names,ns):
    tree=ast.parse((ROOT/path).read_text())
    tree.body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    exec(compile(tree,str(ROOT/path),'exec'),ns)
    return ns

spec=importlib.util.spec_from_file_location('audited_geometry',ROOT/'tools/label_studio/panorama_studio/geometry.py')
geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)
ns=dict(np=np,analyze=geometry.analyze,copy=copy,math=math,defaultdict=defaultdict,linkage=linkage,fcluster=fcluster,squareform=squareform)
get_functions('tools/thesis_main/analysis/paired_split_research/study.py',['angular'],ns)
get_functions('tools/thesis_main/analysis/point_pattern_demo_20261003.py',['_pairs'],ns)
get_functions('tools/thesis_main/analysis/research_round_20260929.py',['reconstruct'],ns)
get_functions('tools/thesis_main/analysis/union_branch_consensus_20260926.py',['_ring_key'],ns)
ns['SCHEMA']='global_pair_consensus_20261004_v1'
get_functions('tools/thesis_main/analysis/global_pair_consensus_20261004.py',['_identities','_ring_diagnostics','_result','build_global_pair_consensuses','build_global_pair_consensus'],ns)
def row(i,x):
    return dict(id='R'+str(i),worker='P'+str(i),points=[[float(q),y] for q in [x,384,640,896] for y in (120.,390.)],source_pair_indices=list(range(4)),ring_confirmed=True,order_status='human_confirmed')
a=[row(i,x) for i,x in enumerate([100,116,132])]
b=copy.deepcopy(a)
for r in b:r['worker']='P'+str(2-int(r['worker'][1:]));r['id']='R'+r['worker'][1:]
assert len({r['worker'] for r in a})==len({r['worker'] for r in b})==3
assert len({r['id'] for r in a})==len({r['id'] for r in b})==3
strip=lambda records:[{k:v for k,v in r.items() if k not in ('id','worker')} for r in records]
assert strip(a)==strip(b), 'Only identifiers may change; coordinates and original ring must not'
before=copy.deepcopy([a,b])
out=[]
for name,records in [('original',a),('renamed_only',b)]:
    r=ns['build_global_pair_consensus'](records,threshold_deg=5.0)
    assert all(ns['reconstruct'](record)['status']=='ok' for record in records)
    out.append(dict(name=name,records=records,status=r['status'],points=r['candidate']['points'],support=r['candidate']['point_support_counts'],correspondence=r['correspondence_diagnostics'],ring=r['ring_diagnostics'],identity_groups=r['identity_groups']))
angles=ns['angular'](np.array([[100,390],[116,390],[132,390]])-.5,np.array([[100,390],[116,390],[132,390]])-.5).tolist()
top=ns['angular'](np.array([[100,120],[116,120],[132,120]])-.5,np.array([[100,120],[116,120],[132,120]])-.5)
distance=np.maximum(angles,top)
assert distance[0,1]==distance[1,2], 'The source float values, with no rounding, must tie'
assert float(distance[0,1]).hex()==float(distance[1,2]).hex()
assert [a,b]==before, 'Fusion must not mutate inputs'
assert [r['points'][0][0] for r in out]==[108.,124.]
assert all(r['status']=='ok' and r['correspondence']['competing_worker_matches']==0 for r in out)
result=dict(test='worker/id relabeling only, exact tied complete-linkage alternatives',threshold_deg=5.0,bottom_angle_matrix=angles,max_endpoint_angle_matrix=distance.tolist(),
    exact_float_tie=True,tied_float_hex=[float(distance[0,1]).hex(),float(distance[1,2]).hex()],
    assertions=dict(distinct_workers=True,distinct_record_ids=True,all_non_identifier_fields_identical=True,original_ring_unchanged=True,inputs_unmutated=True,all_source_geometry_ok=True),results=out)
(ROOT/'partition_tie_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(dict(angles=angles,results=[{k:r[k] for k in ['name','status','points','support','correspondence']} for r in out]),ensure_ascii=False,indent=2))
