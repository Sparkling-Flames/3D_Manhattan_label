"""本地核验外部连续路径原型；不修改其代码，不接入正式融合。"""
import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
PRO = ROOT/'research/structure_paths_20261006/pro_original'
DOT = ROOT/'research/structure_paths_20261006/dot_original'
OUT = ROOT/'analysis_results/structure_paths_review_20261006'


def save(name, value):
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def compare_replay():
    """分开列出浮点差异与离散结果差异，不要求跨平台字节相同。"""
    original=PRO/'results'; replay=OUT/'pro_replay'
    paths={p.relative_to(original) for p in original.rglob('*') if p.is_file()}
    assert paths=={p.relative_to(replay) for p in replay.rglob('*') if p.is_file()}
    numeric=[]; other=[]; changed=[]
    def compare(a,b,path):
        if isinstance(a,dict) and isinstance(b,dict):
            if a.keys()!=b.keys():other.append(dict(path=path,reason='keys_differ'))
            for key in a.keys() & b.keys():compare(a[key],b[key],path+'/'+key)
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):other.append(dict(path=path,reason='length_differs'))
            for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
        elif a!=b:
            if type(a) in (int,float) and type(b) in (int,float):
                numeric.append(dict(path=path,absolute_difference=abs(a-b)))
            else:other.append(dict(path=path,original=a,replay=b))
    def read(p):
        if p.name.endswith('.jsonl.gz'):
            with gzip.open(p,'rt',encoding='utf-8') as f:return [json.loads(s) for s in f]
        return json.loads(p.read_text(encoding='utf-8'))
    for p in sorted(paths):
        if (original/p).read_bytes()==(replay/p).read_bytes():continue
        changed.append(str(p))
        if str(p).endswith(('.json','.jsonl.gz')):compare(read(original/p),read(replay/p),p.as_posix())
    save('pro_replay_comparison.json',dict(files=len(paths),byte_equal=len(paths)-len(changed),
        changed_files=changed,numeric_differences=len(numeric),largest_numeric_differences=sorted(numeric,key=lambda r:r['absolute_difference'],reverse=True)[:20],
        nonnumeric_differences=other,scope='Parsed comparison includes metadata ordering and file digests; inspect these separately from scientific statuses. CSV differences covered by companion JSON, not compared cellwise here.'))
    print('Pro replay files:',len(paths),'byte equal:',len(paths)-len(changed),'numeric changes:',len(numeric),'other:',len(other),flush=True)


def verify_current_handoff():
    from tools.thesis_main.analysis.point_route_panel_20261005 import build_routes
    folder=ROOT/'research/structure_constraints_20261006'
    inputs=json.loads((folder/'inputs.json').read_text(encoding='utf-8'))
    expected=json.loads((folder/'baselines.json').read_text(encoding='utf-8'))['states']
    actual=[]
    for image in inputs['images']:
        for t in [5,9,12]:
            for route,result in build_routes(image['records'],t).items():
                actual.append(dict(image=image['image'],threshold_deg=t,route=route,result=result))
    assert actual==expected
    save('main_handoff_check.json',dict(images=len(inputs['images']),records=sum(len(i['records']) for i in inputs['images']),
        states=len(actual),current_repository_results_equal_saved_baselines=True,zip_required=False))
    print('Current repository: 108 baseline states reproduced',flush=True)


def replay_events():
    os.environ['STRUCTURE_SOURCE']=str(PRO)
    sys.path.insert(0,str(DOT/'event_exploration'))
    from run_exploration import banks
    from event_search import POLICY, event_signature, subdivide
    saved=json.loads((PRO/'results/controls/fixed_hop_subdivision_counterexample.json').read_text(encoding='utf-8'))
    a=copy.deepcopy(saved['records'][0]);b=copy.deepcopy(a);b.update(id='B',worker='B')
    windows=[dict(name='synthetic_square',records=[a,b],focals=[['A',0],['B',0]])]
    for spec in POLICY['real_windows']:
        data=json.loads((PRO/'inputs'/f"{spec['image']}.json").read_text(encoding='utf-8'))
        by_id={r['id']:r for r in data['records']}
        windows.append(dict(spec,records=[by_id[rid] for rid,k in spec['focals']]))
    rows=[]
    for w in windows:
        signatures={};old_status={}
        variants=[(1,1)]+[(1,k) for k in POLICY['subdivision_factors']]+[(k,k) for k in POLICY['subdivision_factors']]
        for factors in variants:
            records=[subdivide(r,k)[0] for r,k in zip(w['records'],factors)]
            old,event,D,ix=banks(records)
            focals=[ix[(rid,k*factor)] for (rid,k),factor in zip(w['focals'],factors)]
            for metric in ['pair','bottom','top']:
                for gate in POLICY['thresholds_deg']:
                    raw=old.witness(*focals,metric,gate,D);new=event.witness(*focals,metric,gate,D)
                    signature=event_signature(event,new);key=(metric,gate)
                    if factors==(1,1):signatures[key]=signature;old_status[key]=raw['status']
                    rows.append(dict(window=w['name'],factors=factors,metric=metric,gate_deg=gate,
                        old_status=raw['status'],event_status=new['status'],same_event_signature=signature==signatures[key],
                        old_status_changed=raw['status']!=old_status[key]))
        print('Event window:',w['name'],flush=True)
    comparisons=[r for r in rows if r['factors']!=(1,1)]
    result=dict(settings=len(rows),subdivision_comparisons=len(comparisons),
        event_signature_changes=sum(not r['same_event_signature'] for r in comparisons),
        fixed_hop_status_changes=sum(r['old_status_changed'] for r in comparisons),rows=rows,
        scope='Same dot policy and 8 fixed windows; this rerun bypasses no geometry gate. Original test exact-float equality failed by 7.1e-15 degrees and is reported separately. No identity partition or full-layout success is inferred.')
    save('dot_event_local_replay.json',result)
    assert len(comparisons)==432 and result['event_signature_changes']==0
    print({k:v for k,v in result.items() if k not in ('rows','scope')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['current','events','compare'],required=True)
    args=parser.parse_args()
    {'current':verify_current_handoff,'events':replay_events,'compare':compare_replay}[args.stage]()
