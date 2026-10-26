"""Current-runtime compatibility/timing on the inherited prespecified 36 teams."""
from pathlib import Path
import argparse,time
import execute_extension as e

def run(base):
    n=e.init_native(base);pools=n.gs.pool_lookup()
    source=base/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/engine/benchmark'
    requests=list(e.readcsv(source/'REQUESTS.csv.gz'));expected={r['team_key']:r for r in e.readcsv(source/'ENDPOINT_SCALARS.csv.gz')}
    out=base/'engine26/benchmark26';out.mkdir(exist_ok=True);t=time.monotonic();rows=[];checks=[]
    with n.FrozenNativeEngine(full_state=False) as engine:
        last=None
        for req in requests:
            pid=req['pool_id']
            if pid!=last:engine.reset_pool();last=pid
            r=engine.evaluate(pools[pid],req['member_workers'].split('|'));rows.append(r);old=expected[r['team_key']];ok=True
            for field in ['B8L2','D10','nodes']:
                x,y=r.get(field),old.get(field)
                ok &= (x is None and y in ('',None)) or (x is not None and y not in ('',None) and abs(float(x)-float(y))<1e-9)
            ok &=r['score_status']==old['score_status'];checks.append(dict(team_key=r['team_key'],matches=bool(ok)));assert ok
    e.save_csv(out/'SCALARS.csv.gz',[n.scalar_row(r) for r in rows])
    result=dict(endpoints=len(rows),pools=len(set(r['pool_id'] for r in rows)),seconds=time.monotonic()-t,
        native_seconds=sum(r['native_evaluation_wall_seconds'] for r in rows),all_36_frozen_values_agree=True,checks=checks,
        selection='Inherited prespecified timing/compatibility set, no newly selected result-based cases. Not estimator observations.')
    e.savejson(out/'BENCHMARK_RECEIPT.json',result);return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--base',type=Path,required=True);args=a.parse_args();print(run(args.base.resolve()))
