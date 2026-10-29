"""Cumulative (across restarts) counts of the completed endpoint batch."""
from pathlib import Path
import argparse,hashlib,json
import pandas as pd
from register_adaptive import write_json

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--requests',required=True);a=ap.parse_args();out=Path(a.output)
 cols=['team_key','pool_id','endpoint_reused','B8L2','D10','complete_evaluable']
 scalar=pd.read_csv(out/'ENDPOINT_SCALARS.csv.gz',usecols=cols,low_memory=False);req=pd.read_csv(a.requests,usecols=['team_key'],low_memory=False)
 assert scalar.team_key.is_unique and set(scalar.team_key)==set(req.team_key)
 reused=scalar.endpoint_reused.astype(str).str.lower().isin(['true','1','1.0']);complete=scalar.complete_evaluable.astype(str).str.lower().isin(['true','1','1.0'])
 receipt=dict(data_release='v2.1',endpoint_rows=len(scalar),pools=scalar.pool_id.nunique(),unique_requested_teams=len(req),
    cumulative_native_endpoints=int((~reused).sum()),cumulative_reused_endpoints=int(reused.sum()),Q_available=int(scalar.B8L2.notna().sum()),
    D10_available=int(scalar.D10.notna().sum()),complete_evaluable=int(complete.sum()),Q_missing=int(scalar.B8L2.isna().sum()),
    all_requests_completed=True,requests_sha256=hashlib.sha256(Path(a.requests).read_bytes()).hexdigest(),
    count_contract='Each exact team endpoint once; native/reused from persisted endpoint provenance, regardless of process restarts.')
 write_json(out/'CUMULATIVE_COMPLETION.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
