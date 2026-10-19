"""Count real support once across experiments; compare repeated team outputs."""
import argparse,collections,hashlib,json
from pathlib import Path
import pandas as pd
from fusion_runner import read,write,team_key,digest,SCORE_KEYS

STAGES=[
 ('screen','SCREEN_REQUESTS','runs'),
 ('breadth_discovery','DISCOVERY_GRID_REQUESTS','runs'),
 ('blocks_discovery','DISCOVERY_BLOCK_REQUESTS','runs_blocks'),
 ('curves_discovery','DISCOVERY_CURVE_REQUESTS','runs_curves'),
 ('conditions_discovery','DISCOVERY_CONDITION_REQUESTS','runs'),
 ('confirm_discovery','DISCOVERY_CONFIRM_REQUESTS','runs_final'),
 ('nested_discovery','DISCOVERY_NESTED_REQUESTS','runs_final'),
 ('curves_validation','VALIDATION_CURVE_REQUESTS','runs_final'),
 ('confirm_validation','VALIDATION_CONFIRM_REQUESTS','runs_final'),
 ('blocks_validation','VALIDATION_BLOCK_REQUESTS','runs_final'),
 ('nested_validation','VALIDATION_NESTED_REQUESTS','runs_final'),
 ('conditions_validation','VALIDATION_CONDITION_REQUESTS','runs_final'),
 ('special_descriptive','SPECIAL_REQUESTS','runs_special')]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,default=Path('analysis/composition'));ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    # The completed receipt prevents treating an in-flight pool as missing data.
    assert (a.base/'runs_final/RUN_FINAL_REQUESTS.json').exists()
    pools={p['pool_id']:p for p in read(a.snapshot)['images']};all_by_pool=collections.defaultdict(dict);stages=[];requests=0
    for stage,name,run in STAGES:
        path=a.base/(name+'.json.gz');d=read(path);qs=d['requests'];requests+=len(qs)
        unique={q['team_key']:q for q in qs};images={pools[q['pool_id']]['meta']['image'] for q in qs};buildings={pools[q['pool_id']]['meta']['building'] for q in qs};workers={w for q in qs for w in q['worker_ids']}
        cells={(q['pool_id'],q.get('method_id'),q.get('domain'),q['k'],q.get('composition')) for q in qs}
        row=dict(stage=stage,requests=len(qs),unique_teams=len(unique),pools=len({q['pool_id'] for q in qs}),images=len(images),buildings=len(buildings),workers=len(workers),k_values='|'.join(map(str,sorted({q['k'] for q in qs}))),count_vector_cells=len(cells),events=len(d.get('events',[])),chains=len(d.get('chains',[])),manifest=str(path),manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),runs=str(a.base/run))
        for q in unique.values():
            assert q['team_key']==team_key(q['pool_id'],q['worker_ids'])
            rec=all_by_pool[q['pool_id']].setdefault(q['team_key'],dict(workers=tuple(q['worker_ids']),k=q['k'],stages=set(),runs=set(),phase=q['phase']))
            assert rec['workers']==tuple(q['worker_ids']) and rec['k']==q['k'];rec['stages'].add(stage);rec['runs'].add(run)
        stages.append(row)
    support=[];duplicate_instances=0;score_statuses=collections.Counter();repeated_checked=0;allworkers=set();allimages=set();allbuildings=set();uniq=0
    for pid,teams in all_by_pool.items():
        meta=pools[pid]['meta'];needed_runs={r for t in teams.values() for r in t['runs']};caches={run:{r['team_key']:r for r in read(a.base/run/'pools'/(pid+'.json.gz'))['teams']} for run in needed_runs}
        groups=collections.defaultdict(list)
        for key,t in teams.items():
            rows=[caches[r][key] for r in sorted(t['runs'])];r=rows[0];assert tuple(r['member_workers'])==t['workers'];assert r['k']==t['k']
            stable={k:r.get(k) for k in SCORE_KEYS+['geometry','nodes','minimum_support','member_workers','member_object_ids','complete_evaluable']}
            for other in rows[1:]:
                assert stable=={k:other.get(k) for k in stable},'same real team yielded differing frozen result';repeated_checked+=1
            duplicate_instances+=len(t['stages'])-1;uniq+=1;allworkers.update(t['workers']);allimages.add(meta['image']);allbuildings.add(meta['building']);score_statuses[r['score_status']]+=1
            groups[(t['phase'],t['k'])].append(r)
        for (phase,k),rs in groups.items():
            support.append(dict(pool_id=pid,image=meta['image'],building=meta['building'],difficulty=meta['difficulty'],scene=meta['scene'],layer=meta['layer'],phase=phase,k=k,unique_teams=len(rs),workers=len({w for r in rs for w in r['member_workers']}),score_available=sum(r.get('B8L2') is not None for r in rs),complete=sum(bool(r.get('complete_evaluable')) for r in rs),score_status_counts=json.dumps(dict(collections.Counter(r['score_status'] for r in rs)),sort_keys=True)))
    a.out.mkdir(parents=True,exist_ok=True);pd.DataFrame(stages).to_csv(a.out/'stage_coverage.csv',index=False);S=pd.DataFrame(support);S.to_csv(a.out/'unique_support_by_pool_n.csv.gz',index=False)
    layers=[]
    for (phase,layer),g in S.groupby(['phase','layer']):
        pids=set(g.pool_id);actualworkers={w for pid in pids for t in all_by_pool[pid].values() for w in t['workers']}
        layers.append(dict(phase=phase,layer=layer,unique_teams=int(g.unique_teams.sum()),score_available=int(g.score_available.sum()),complete=int(g.complete.sum()),pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),workers=len(actualworkers)))
    pd.DataFrame(layers).to_csv(a.out/'unique_support_by_layer.csv',index=False)
    write(a.out/'STUDY_COVERAGE_RECEIPT.json',dict(request_rows=requests,unique_actual_teams=uniq,pools=len(all_by_pool),images=len(allimages),buildings=len(allbuildings),workers=len(allworkers),workers_exact=sorted(allworkers),duplicate_team_stage_instances=duplicate_instances,repeated_output_copies_compared=repeated_checked,all_repeated_outputs_exact=True,score_status_counts=dict(score_statuses),interpretation='team = actual worker set + frozen pool; repeated teams/replays deduplicated; different teams on one image are not independent images; building holdout uses known workers',stages=stages))

if __name__=='__main__':main()
