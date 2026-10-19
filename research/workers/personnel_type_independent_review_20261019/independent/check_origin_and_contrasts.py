import pandas as pd,numpy as np,json,pathlib,math
P=pathlib.Path('/workspace/shared/personnel_partA_audit_20261019');R=P/'extracted/work_personnel_typing_A_20261019';O=P/'independent'
e=pd.read_csv(R/'assessment/COMMON_EVENT_ANALYSIS_INPUT.csv.gz',low_memory=False);w=pd.read_csv(R/'assessment/EVENT_PREDICTIONS_WIDE.csv.gz');v=pd.read_csv(R/'assessment/ORIGIN_CONTROL_PREDICTIONS.csv.gz');assert e.event_id.equals(v.event_id)
def s(g,c):
 im=g.groupby(['building','image_id'])[c].mean();a=im.groupby(level=0).mean().to_numpy();bs=np.random.default_rng(20261019).choice(a,(2000,len(a))).mean(1)
 return dict(n=len(g),images=g.image_id.nunique(),buildings=len(a),event_mean=float(g[c].mean()),image_mean=float(im.mean()),building_mean=float(a.mean()),ci=np.quantile(bs,[.025,.975]).tolist())
out={};f=e.copy();y=f.stable_main.to_numpy(float);f['improvement']=(v.p_origin_baseline-y)**2-(v['p_origin__reverse_selected']-y)**2
out['origin_control_k16']=s(f[(f.panel_id=='A_nested_even_v1')&(f.k==16)],'improvement')
f['relation']=w.rel__reverse_selected;f=f[(f.panel_id=='Pro_exact_fixed_background_v1')&(f.k==16)&f.relation.ne('unknown')];z=f.groupby(['building','image_id','background_id','relation']).stable_main.mean().unstack().dropna(subset=['within','between']).reset_index();z['difference']=z.between-z.within;out['old_panel_samebackground_k16']=s(z,'difference')
out['new_panel_samebackground_inference']='No new-panel background contains both known within and between selected-class events. Brier is same-event prediction evaluation, not matched within/between exchange causal contrast.'
(O/'independent_origin_contrast.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
# Persist no-support as null, not invalid JSON NaN.
p=O/'independent_metrics.json';d=json.loads(p.read_text())
def clean(x):
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,list):return [clean(z) for z in x]
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 return x
p.write_text(json.dumps(clean(d),indent=2,allow_nan=False))
