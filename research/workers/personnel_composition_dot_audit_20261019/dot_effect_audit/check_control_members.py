from pathlib import Path
import pandas as pd,numpy as np,gzip,json
R=Path('/workspace/shared/composition_audit_20261019');P=R/'extracted/personnel_composition_study_20261019/analysis';E=pd.read_csv(P/'composition/compact_block_evidence/01_highlight_events.csv.gz').set_index('event_id');F=pd.read_csv(P/'forward/results/features_train.csv.gz').set_index('worker_id');errors=[];n=0
for phase in ['discovery','validation']:
 with gzip.open(R/f'dot_replay_audit/requests/{phase.upper()}_BLOCK_REQUESTS.json.gz','rt') as f:d=json.load(f)
 for e in d['events']:
  if e['event_id'] not in E.index:continue
  row=E.loc[e['event_id']];col='theta_hard' if e['domain']=='hard' else 'q_beta';bs=[e[x] for x in ['outgoing_workers','within_incoming','cross_incoming']];source=[F.loc[b].person_origin.eq('new').sum() for b in bs];q=[F.loc[b,col].mean() if F.loc[b,col].notna().all() else np.nan for b in bs]
  for key,val in {'actual_source_match':len(set(source))==1,'incoming_Q_close_3':bool(abs(q[2]-q[1])<=3),'cross_minus_within_history_Q':q[2]-q[1]}.items():
   if not np.isclose(val,row[key],atol=1e-8,equal_nan=True):errors.append([e['event_id'],key])
  n+=1
out={'events_verified':n,'source_and_Q_control_errors':errors};(Path(__file__).parent/'control_members_checks.json').write_text(json.dumps(out,indent=2));print(out)
