"""Materialize frozen follow-up and validation designs; no target outcomes read."""
import concurrent.futures,hashlib,json,subprocess,sys
from pathlib import Path
from fusion_runner import read,write

ROOT=Path(__file__).resolve().parent
SNAPSHOT=Path('restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')
COMMON=['--snapshot',str(SNAPSHOT),'--split',str(ROOT/'SPLIT.json'),'--labels','analysis/forward/results/worker_labels.csv.gz','--labels','analysis/reverse/worker_labels.csv.gz']

def generate(row):
    script,spec,out=row
    args=[sys.executable,str(ROOT/script),*COMMON,'--spec',str(ROOT/spec),'--out',str(ROOT/out)]
    done=subprocess.run(args,check=True,text=True,capture_output=True)
    return out,done.stdout.strip()

def main():
    jobs=[('design_curves.py','CONFIRM_DISCOVERY_SPEC.json','DISCOVERY_CONFIRM_REQUESTS.json.gz'),
          ('design_nested.py','NESTED_DISCOVERY_SPEC.json','DISCOVERY_NESTED_REQUESTS.json.gz'),
          ('design_curves.py','CURVES_VALIDATION_SPEC.json','VALIDATION_CURVE_REQUESTS.json.gz'),
          ('design_curves.py','CONFIRM_VALIDATION_SPEC.json','VALIDATION_CONFIRM_REQUESTS.json.gz'),
          ('design_blocks.py','BLOCK_VALIDATION_SPEC.json','VALIDATION_BLOCK_REQUESTS.json.gz'),
          ('design_nested.py','NESTED_VALIDATION_SPEC.json','VALIDATION_NESTED_REQUESTS.json.gz')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for out,result in ex.map(generate,jobs):print(out,result,flush=True)
    condition=ROOT/'VALIDATION_CONDITION_REQUESTS.json.gz'
    subprocess.run([sys.executable,str(ROOT/'design_condition_requests.py'),'--spec','analysis/forward/condition_experiment_spec.json','--phase','validation','--out',str(condition)],check=True)
    sources=[ROOT/out for _,_,out in jobs]+[condition]
    rows=[];receipts=[]
    for p in sources:
        data=read(p);rows.extend(data['requests']);receipts.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),requests=len(data['requests']),phase=data['spec']['phase']))
    assert len(rows)==len({r['request_id'] for r in rows})
    freeze=ROOT/'VALIDATION_FREEZE.json'
    write(ROOT/'FINAL_REQUESTS.json.gz',dict(freeze_sha256=hashlib.sha256(freeze.read_bytes()).hexdigest(),component_manifests=receipts,requests=rows))
    print(json.dumps(dict(requests=len(rows),unique_teams=len({r['team_key'] for r in rows}),pools=len({r['pool_id'] for r in rows}),by_phase={p:sum(r['phase']==p for r in rows) for p in ['discovery','validation']})),flush=True)

if __name__=='__main__':main()
