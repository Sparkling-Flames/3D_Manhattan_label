"""Replay only saved claim teams through the repository's unmodified native engine."""
from pathlib import Path
import argparse,gzip,json,math,sys

def read(p):
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--repo',type=Path,required=True);a.add_argument('--claims',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a.add_argument('--pool',action='append');a.add_argument('--limit',type=int,help='Optional first N saved teams, for a small smoke replay; omit for all claim teams')
    args=a.parse_args();repo=args.repo.resolve();sys.path.insert(0,str(repo))
    from tools.thesis_main.analysis.fusion_change_mechanisms_20261020 import engine
    fe=engine();sys.path.insert(0,str(repo/'research/workers/personnel_interchangeability_20261020/analysis/composition'))
    import fusion_runner as fr
    fr.FE=fe
    pools={p['pool_id']:p for p in fe.load_pools()}
    selected=read(args.claims)
    if args.pool:selected=[r for r in selected if r['pool_id'] in args.pool]
    if args.limit:selected=selected[:args.limit]
    results=[]
    for pid in sorted({r['pool_id'] for r in selected}):
        with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (scorer,models):
            cache={}
            for expected in [r for r in selected if r['pool_id']==pid]:
                actual=fr.evaluate_one(pools[pid],expected['member_workers'],scorer,models,score_cache=cache)
                for field in ('B8L2','D10'):
                    x,y=actual.get(field),expected.get(field)
                    ok=(x is None and y is None) or (x is not None and y is not None and math.isclose(x,y,abs_tol=1e-7,rel_tol=1e-10))
                    if not ok:raise AssertionError((expected['team_key'],field,x,y))
                results.append(dict(team_key=actual['team_key'],B8L2=actual.get('B8L2'),D10=actual.get('D10'),score_status=actual.get('score_status'),matches_saved=True))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(dict(purpose='saved-claim replay, not new evidence observations',replayed=len(results),results=results),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(replayed=len(results),out=str(args.out)),ensure_ascii=False))

if __name__=='__main__':main()
