"""Verify the unchanged engine against four existing v2.1 case endpoints."""
from pathlib import Path
import sys, json, gzip
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / 'repo'
BASE = REPO / 'research/workers/personnel_v21_reselection_20261029'
OUT = Path(__file__).resolve().parents[1] / 'stage00_intake'
sys.path.insert(0, str(BASE / 'experiment'))
from benchmark_engine import load_engine, evaluated

def main():
    pools = {p['pool_id']: p for f in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json']
             for p in json.loads((REPO/'research/data/releases/v2.1'/f).read_text())['images']}
    s = pd.read_csv(BASE/'stage06_cases/CASE_ENDPOINT_SCALARS.csv')
    events = pd.read_csv(BASE/'stage06_cases/CASE_EVENTS_EXACT.csv.gz').set_index('event_id')
    selected = pd.concat([s[s.B8L2.notna()].drop_duplicates('pool_id').head(3), s[s.B8L2.isna()].head(1)])
    native = load_engine(REPO); rows = []; checks = []
    with native.Engine(full_state=False) as e:
        for r in selected.to_dict('records'):
            members = events.at[r['event_id'],r['arm']+'_members'].split('|')
            q = evaluated(e,native,pools[r['pool_id']],members); rows.append(q); diff = {}
            assert q['team_key'] == r['team_key']
            for k in ['B8L2','D10','nodes','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','omission','extension']:
                x,y = r.get(k),q.get(k)
                if pd.isna(x) or y is None:
                    assert pd.isna(x) and y is None,(k,x,y)
                else:
                    diff[k] = abs(float(x)-float(y)); assert diff[k] < 1e-8,(k,x,y)
            checks.append(dict(pool_id=r['pool_id'],team_key=q['team_key'],score_status=q['score_status'],
                               max_difference=max(diff.values(),default=0),differences=diff))
            print(checks[-1],flush=True)
    (OUT/'ENGINE_PARITY.json').write_text(json.dumps({'source':'stage06_cases/CASE_ENDPOINT_SCALARS.csv','cases':checks,'pass':True},indent=2))
    with gzip.open(OUT/'ENGINE_PARITY_ENDPOINTS.jsonl.gz','wt') as f:
        for r in rows:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')

if __name__ == '__main__':
    main()
