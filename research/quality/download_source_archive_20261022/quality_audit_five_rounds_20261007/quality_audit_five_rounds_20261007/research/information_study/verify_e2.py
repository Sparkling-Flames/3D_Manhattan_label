from round_d import *
import pandas as pd
removed=pd.read_csv(OUT/'E2_lower_boundary_removed_cases.csv');extra=pd.read_csv(OUT/'E2_threeD_incremental_cases.csv');cases=pd.concat([removed[['image','source_id','reference_version']],extra[['image','source_id','reference_version']]]).drop_duplicates()
inputs={(a['image'],a['record']['id']):a for a in json.loads((DENSITY/'round_c_inputs.json').read_text())};arts={(a['image'],a['expression_id']):a for a in json.loads((DENSITY/'round_c_fit_artifacts.json').read_text())};rows=[]
for _,r in cases.iterrows():
 inp=inputs[(r.image,r.source_id)];a=inp['record'];b=arts[(r.image,r.source_id)]['fits']['continuous_boundary']['record'];g=next(q for q in inp['references'] if q['version']==r.reference_version)
 ua=independent_angular(a,g);ub=independent_angular(b,g);_,ba=rawxyz(a);_,bb=rawxyz(b);_,bg=rawxyz(g);da,ea=independent_curve(ba,bg);db,eb=independent_curve(bb,bg)
 rows.append({'image':r.image,'source_id':r.source_id,'independent_delta_upper_deg':ub[0]-ua[0],'independent_delta_bottom_deg':ub[1]-ua[1],'independent_delta_floor3d_h':db-da,'floor_integration_error_sum_h':ea+eb,'bottom_tolerance_exceeded':bool(ub[1]-ua[1]>.1),'floor3d_tolerance_exceeded':bool(db-da>.01)})
csvout('E2_independent_lower_checks.csv',rows);print(rows)
