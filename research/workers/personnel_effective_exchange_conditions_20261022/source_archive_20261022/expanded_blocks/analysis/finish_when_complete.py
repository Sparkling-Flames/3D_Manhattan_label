"""Resume final analysis after every frozen cell has a completion receipt."""
from pathlib import Path
import csv,json,os,subprocess,sys,time

HERE=Path(__file__).resolve().parent
EX=HERE.parent
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
with (EX/'REGISTERED_EVENT_PARTS.csv').open(encoding='utf-8-sig',newline='') as f:
    parts=list(csv.DictReader(f))
while True:
    pending=[r for r in parts if not (EX/'results'/r['cell_id']/'COMPLETION.json').exists()]
    p=HERE/'FINAL_WAIT_STATUS.json';temp=p.with_name(p.name+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(dict(status='waiting_for_registered_cells' if pending else 'running_final_analysis',
          registered_cells=len(parts),pending_cells=len(pending),pending_events=sum(int(r['events']) for r in pending),
          fusion_calls=0,utc_checked=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())),f,indent=2)
        f.flush();os.fsync(f.fileno())
    temp.replace(p)
    if not pending:break
    time.sleep(15)
for command in [['analyze_expanded_results.py','--require-complete'],['prepare_readable_results.py']]:
    subprocess.run([sys.executable,str(HERE/command[0]),*command[1:]],check=True)
print('FINAL_TABLES_SAVED',flush=True)
