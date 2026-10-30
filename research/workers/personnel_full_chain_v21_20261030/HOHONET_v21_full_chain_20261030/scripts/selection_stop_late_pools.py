"""Complete the remote end of the frozen pool queue; main run resumes each file.

Launched while the original two workers were in early uNb pools. The disjoint
wc2/yqstnu pools are processed in reverse order and complete before the main
queue reaches them. RUN_EXTRA_PROGRESS preserves the actual acquisition counts.
"""
import multiprocessing,json
from concurrent.futures import ProcessPoolExecutor,as_completed
import pandas as pd
from selection_stop_prepare import OUT,save
from selection_stop_endpoints import worker

if __name__=='__main__':
    req=pd.read_csv(OUT/'design/ENDPOINT_REQUESTS.csv.gz');req=req[req.pool_id.str.startswith(('wc2','yqstnu'))]
    results=[]
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as ex:
        futures=[ex.submit(worker,(pid,g.to_dict('records'))) for pid,g in reversed(list(req.groupby('pool_id')))]
        for f in as_completed(futures):
            r=f.result();results.append(r);save('endpoints/RUN_EXTRA_PROGRESS.json',results);print(json.dumps(r),flush=True)
