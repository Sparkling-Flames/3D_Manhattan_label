"""更新既有精确边际；新Manual池仅补原合同要求的缺失有限团队。"""
import gzip
import importlib.util
import itertools
import json
import math
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read
from .prepare_v21_natural_inputs_20261028 import PRIOR, EXT, METRICS, overlay
from .fuse_v21_new_pools_20261028 import TARGET as NEW, adapter

TARGET = OUT / 'exact_marginals'


def summarize(g, meta):
    k = int(g.k.iloc[0]); n = int(meta['pool_n']); expected = math.comb(n, k)
    assert g.team_key.nunique() == len(g) == expected
    q = g.B8L2.dropna(); attempted = g[g.k.ne(2)]
    failure = attempted.B8L2.isna()
    result = dict(**meta, k=k, finite_population_teams=expected, quality_valid_teams=len(q),
        policy_deferred_teams=len(g) if k == 2 else 0, nondeferred_attempts=len(attempted),
        score_unavailable_teams=int(failure.sum()), exact_complete=True,
        exact_kind='all_small_pool_subsets' if n <= 10 else 'singletons' if k == 1 else 'leave_one_out' if k == n-1 else 'full_pool',
        Q_mean=q.mean(), Q_p10=q.quantile(.1) if len(q) else np.nan,
        Q_p10_inverse_cdf=float(np.quantile(q, .1, method='inverted_cdf')) if len(q) else np.nan,
        Q_sd_population=q.std(ddof=0), D10_mean=g.D10.mean(),
        floor_turn5_mean=g.floor_turn5_n.mean(), floor_redundant5_mean=g.floor_redundant5_n.mean(),
        nodes_mean=g.nodes.mean(), failure_rate=failure.mean(),
        incomplete_rate=(~attempted.complete_evaluable.astype(bool)).mean())
    if 'status_class' in g:
        executed=attempted[attempted.status_class.ne('not_executed')]
        result['actual_executed_nondeferred_teams']=len(executed)
        for name,status in [('actual_consensus_failure','consensus_not_formed'),('output_unscoreable','output_unscoreable'),('reference_unavailable','reference_unavailable'),('not_executed','not_executed')]:
            base=executed if name in ['actual_consensus_failure','output_unscoreable'] else attempted
            result[name+'_teams']=int(base.status_class.eq(status).sum())
            result[name+'_rate']=base.status_class.eq(status).mean()
    return result


def main():
    TARGET.mkdir(exist_ok=True)
    pools = {p['pool_id']: p for p in read(OUT / 'pools/INPUT_SNAPSHOT.json')['images']}
    old = pd.read_csv(PRIOR / 'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz', low_memory=False)
    needed = set(old.team_key); patches = {}
    for p in (OUT / 'historical_population_rescore').glob('*.jsonl.gz'):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                if r['team_key'] in needed:
                    m = r['result'] or {}
                    patches[r['team_key']] = dict(team_key=r['team_key'], **{c:m.get(c) for c in METRICS},
                        score_status=m.get('score_status',r['original_score_status']))
    old = overlay(old, pd.DataFrame(patches.values()).set_index('team_key'))
    frames = [old]; checks = []
    native = adapter(); prefix_path = ROOT / 'research/workers/personnel_population_curves_v2_20261023/code/run_prefix_endpoints.py'
    spec = importlib.util.spec_from_file_location('v21_exact_features', prefix_path)
    prefix = importlib.util.module_from_spec(spec); spec.loader.exec_module(prefix)
    deps = read(OUT / 'pools/DEPENDENCIES.json')
    for dep in deps:
        if dep['action'] != 'new_or_changed_pool' or dep['condition'] != 'manual': continue
        pid = dep['pool_id']; pool = pools[pid]; folder = NEW / pid
        assert read(folder / 'CHECKS.json')['complete']
        people = sorted(r['worker_id'] for r in pool['records']); n = len(people)
        ks = range(1,n+1) if n <= 10 else sorted({1,n-1,n})
        wanted = {tuple(t) for k in ks for t in itertools.combinations(people,k)}
        rows = {}
        for p in sorted(folder.glob('part_*.jsonl.gz')):
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for line in f:
                    r = json.loads(line); team = tuple(r['member_workers'])
                    if team in wanted: rows[team] = r
        extra = TARGET / (pid + '__extra.jsonl.gz')
        if extra.exists():
            with gzip.open(extra,'rt',encoding='utf-8') as f:
                for line in f:
                    r=json.loads(line); rows[tuple(r['member_workers'])]=r
        missing = sorted(wanted - rows.keys()); added = []
        with native.Engine(full_state=False) as engine:
            for team in missing:
                row = engine.evaluate(pool,list(team)); row['data_release']='v2.1'
                rows[team]=row; added.append(row)
            if added:
                assert not extra.exists()
                with gzip.open(extra,'wt',encoding='utf-8') as f:
                    for r in added:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
            records = [prefix.geometry_enrich(r,pool,engine.fr) for r in rows.values()]
        assert set(rows) == wanted
        frame = pd.DataFrame(records)
        frame = frame.drop(columns=[c for c in frame if c=='geometry' or frame[c].map(lambda v:isinstance(v,(list,dict))).any()])
        frames.append(frame)
        checks.append(dict(pool_id=pid,finite_teams=len(wanted),missing_fused=len(added),saved_reused=len(wanted)-len(added)))
        print('exact margins',pid,len(wanted),'new',len(added),flush=True)
    full=pd.concat(frames,ignore_index=True); summaries=[]
    sys.path.insert(0,str(EXT/'analysis_precision26'))
    from analyze_natural import status_class
    full['status_class']=[status_class(r) for r in full.to_dict('records')]
    for field in ['image','image_id','building','condition','layer','difficulty','pool_n','reference_id','reference_version']:
        full[field]=full.pool_id.map({pid:p['meta'][field] for pid,p in pools.items()})
    full['data_release']='v2.1'
    for (pid,k),g in full.groupby(['pool_id','k']):
        meta={c:pools[pid]['meta'][c] for c in ['pool_id','image','image_id','building','condition','layer','difficulty','pool_n','reference_id','reference_version']}
        summaries.append(summarize(g,meta))
    pd.DataFrame(summaries).to_csv(TARGET/'EXACT_FINITE_MARGINAL_STATISTICS.csv',index=False,encoding='utf-8-sig')
    full.to_csv(TARGET/'EXACT_MARGINAL_VALUES.csv.gz',index=False,encoding='utf-8-sig')
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(new_pools=checks,original_teams=len(old),
        original_teams_rescored=len(patches),all_cells_complete=True),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
