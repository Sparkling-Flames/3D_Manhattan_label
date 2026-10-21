"""Sequentially complete and package all frozen batches; safe to resume."""
import json,zipfile
from pathlib import Path
from run_multin_batches import HERE,gs,run,pd,sha

def package(bid):
    folder=HERE/'batches'/bid
    files=[folder/f for f in ['REQUESTS.csv.gz','ENDPOINT_SCALARS.csv.gz','ENDPOINT_GEOMETRY.csv.gz','COMPLETION.json','EXECUTION.json']]
    out=HERE/'ready'/f'HOHONET_v3_多人数完整成员面板_{bid}_20261021.zip';out.parent.mkdir(exist_ok=True)
    tmp=out.with_name(out.name+'.tmp')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in files:z.write(p,str(p.relative_to(HERE)))
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:raise ValueError('zip corruption')
    tmp.replace(out)
    receipt=dict(batch_id=bid,archive=str(out.relative_to(HERE)),bytes=out.stat().st_size,sha256=sha(out),files=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in files])
    gs.save(folder/'PACKAGE.json',receipt)
    print(json.dumps(dict(event='BATCH_PACKAGED',**{k:receipt[k] for k in ['batch_id','archive','bytes','sha256']})),flush=True)

def main():
    plan=pd.read_csv(HERE/'BATCH_PLAN.csv')
    # Execution order may prioritize a complete condition for independent
    # policy analysis. It never changes the frozen requests or membership.
    requested_order=__import__('os').environ.get('HOHONET_V3_BATCH_PRIORITY','').split(',')
    priority=[x for x in requested_order if x in set(plan.batch_id)]
    for bid in priority+[x for x in plan.batch_id if x not in priority]:
        folder=HERE/'batches'/bid
        if not (folder/'COMPLETION.json').exists():run(bid,4)
        if not (folder/'PACKAGE.json').exists():package(bid)
    gs.save(HERE/'ALL_BATCHES_COMPLETE.json',dict(status='complete',batches=len(plan),requested=int(plan.requested.sum()),frozen_plan_sha256=sha(HERE/'BATCH_PLAN.csv'),all_batches=[gs.read(HERE/'batches'/bid/'COMPLETION.json') for bid in plan.batch_id]))

if __name__=='__main__':main()
