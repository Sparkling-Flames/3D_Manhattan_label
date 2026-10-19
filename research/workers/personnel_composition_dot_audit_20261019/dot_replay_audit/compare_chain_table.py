import sys,json
from pathlib import Path
import pandas as pd
BASE=Path('/workspace/shared/composition_audit_20261019');PKG=BASE/'extracted/personnel_composition_study_20261019';OUT=BASE/'dot_replay_audit';sys.path.insert(0,str(PKG/'analysis/composition'))
from geometry_diagnostics import diagnose
x=json.loads((OUT/'case_snapshot_and_full_chains.json').read_text()); table=pd.read_csv(PKG/'analysis/figures_summary/threshold_transitions_plot_data.csv.gz'); result=[]
for chain in x['full_chains']:
 case=json.loads((PKG/'analysis/representative_cases/cases'/(chain['case']+'.json')).read_text()); points={p['point']['team_key']:p['result'] for p in chain['points']}
 for point in points.values():point.update(diagnose(point['geometry']['footprint'],case['reference']['floor_xz_h']))
 for row in table[table.before_team.isin(points)&table.after_team.isin(points)].to_dict('records'):
  a,b=points[row['before_team']],points[row['after_team']];checks={}
  for target,source in [('Q_change','B8L2'),('D10_change','D10'),('node_change','nodes'),('corner_change','diag_corner_recall_05'),('wall_change','diag_wall_coverage_05'),('IoU3D100_change','IoU3D100')]:
   actual=b[source]-a[source]; checks[target]={'expected':row[target],'actual':actual,'delta':actual-row[target],'passed':abs(actual-row[target])<1e-9}
  result.append(dict(case=chain['case'],before_k=row['before_k'],after_k=row['after_k'],checks=checks))
(OUT/'chain_table_comparison.json').write_text(json.dumps(dict(transitions=result,all_passed=all(all(c['passed'] for c in r['checks'].values()) for r in result)),indent=2))
print(len(result),'all_passed',all(all(c['passed'] for c in r['checks'].values()) for r in result))
