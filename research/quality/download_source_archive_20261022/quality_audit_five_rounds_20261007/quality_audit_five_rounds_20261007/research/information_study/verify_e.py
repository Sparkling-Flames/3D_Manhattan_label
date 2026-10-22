from round_d import *
import pandas as pd
cases=pd.read_csv(OUT/'E_incremental_3d_guard.csv');cases=cases[cases.threeD_changes_choice==True]
inputs={(a['image'],a['record']['id']):a for a in json.loads((DENSITY/'round_c_inputs.json').read_text())};arts={(a['image'],a['expression_id']):a for a in json.loads((DENSITY/'round_c_fit_artifacts.json').read_text())}
rows=[]
for _,r in cases.iterrows():
 inp=inputs[(r.image,r.source_id)];fit=arts[(r.image,r.source_id)]['fits']['continuous_boundary'];a=inp['record'];b=fit['record'];g=next(q for q in inp['references'] if q['version']==r.reference_version)
 ta,ba=rawxyz(a);tb,bb=rawxyz(b);tg,bg=rawxyz(g)
 da,ea=independent_curve(ta,tg);db,eb=independent_curve(tb,tg);ua=independent_angular(a,g)[0];ub=independent_angular(b,g)[0]
 rows.append({'image':r.image,'source_id':r.source_id,'original_delta_top3d_h':r.delta_D3_angular,'independent_delta_top3d_h':db-da,'sum_adaptive_integration_error_h':ea+eb,'independent_delta_upper_mae_deg':ub-ua,'threeD_guard_still_blocks':bool(db-da>.01),'angular_tolerance_still_passes':bool(ub-ua<=.1),'max_delta3D_difference_h':abs((db-da)-r.delta_D3_angular)})
csvout('E_independent_incremental_cases.csv',rows);print(rows)
# Illustrative conditional wall-top reconstruction, no source-photo or semantic claim.
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
key=('B6ByNegPMKs-48','R00551');inp=inputs[key];fit=arts[key]['fits']['continuous_boundary'];g=next(q for q in inp['references'] if q['version']=='original')
before=compare(inp['record'],g,nlongitude=16384,ncurve=4096);after=compare(fit['record'],g,nlongitude=16384,ncurve=4096)
fig,axs=plt.subplots(1,4,figsize=(12,3.8))
for ax,key,label in zip(axs,['iou','centroid_distance_normalized','top_mae_deg','top3d_symmetric_mean_h'],['IoU (larger is closer)','Centroid C (smaller is closer)','Upper MAE / degree','Top 3D mean distance / h']):
 vals=[before[key],after[key]];ax.bar(['Original','Fit'],vals,color=['#2b6cb0','#c53030']);ax.set_title(label,fontsize=10);ax.set_ylim(0,max(vals)*1.18)
 for i,v in enumerate(vals):ax.text(i,v+max(vals)*.025,f'{v:.5f}',ha='center',fontsize=9)
fig.suptitle('B6-48 / R00551: angular improvement can coexist with spatial regression',fontsize=12)
fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(OUT/'E_B6_depth_tradeoff.png',dpi=170)
