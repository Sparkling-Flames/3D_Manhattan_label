"""Actual selection in the complete, frozen F01 n12 new-source domain.

No new fusion, class fitting, or target-outcome-based policy choice occurs here.
The shared evaluator temporarily receives explicit F01 input adapters. A fine
label alias exists only to satisfy its common interface and is never delivered
as a second taxonomy tier or as a policy.
"""
from pathlib import Path
import argparse,json,time
import numpy as np
import pandas as pd
import policy_study as ps
from prepare_training import HERE,atomic_csv,atomic_json,sha

COMP=ps.COMP
REGIME='f01_finite_LOBO'
FAMILY='F01_fixed_history'

def load_inputs():
    teams=pd.read_csv(COMP/'F01_CAPACITY_TEAMS.csv.gz').rename(columns={'n':'k'})
    panels=pd.read_csv(COMP/'F01_PANELS.csv')
    membership=pd.read_csv(COMP/'F01_PANEL_MEMBERSHIP.csv.gz')
    rows=membership[['panel_id','team_key','selected_variable_workers']].merge(teams,on='team_key',validate='many_to_one')
    rows['center_id']=rows.panel_id;rows['image_id']=rows.image
    path=COMP/'F01_FROZEN_LABELS_LOBO.csv.gz';labels=pd.read_csv(path)
    assert set(labels.tier)=={'coarse'}
    assert labels.apply(lambda r:r.heldout_building not in str(r.training_buildings).split('|'),axis=1).all()
    labels=labels.rename(columns={'class_id':'coarse_label'})
    labels['fine_label']=labels.coarse_label # internal adapter alias, removed from deliverables
    ep_path=COMP/'batches/f01_001/ENDPOINT_SCALARS.csv.gz'
    ep=pd.read_csv(ep_path,low_memory=False)
    assert not ep.team_key.duplicated().any()
    assert set(teams.team_key)==set(ep.team_key)
    ep['failure']=(~ep.complete_evaluable.astype(bool)).astype(int)
    ok=ep.source_time_known_n.eq(ep.k)&ep.source_time_total_seconds.gt(0)&ep.time_source_kinds.fillna('').ne('')&~ep.time_source_kinds.fillna('').str.contains('|',regex=False)
    ep['total_time_compatible']=ok;ep['log_total_time']=np.log(ep.source_time_total_seconds.where(ok))
    return rows,panels,labels,path,ep,ep_path

def add_transferred_qt(rows,labels,out):
    """Apply existing main-population coefficients without refitting on F01."""
    fp=HERE/'cross_panel_LOBO/manual/old_structure/FITS.csv.gz'
    fits=pd.read_csv(fp,low_memory=False)
    fits=fits[fits.model.isin(['QT','QT_interaction'])].copy()
    common=pd.read_csv(out/'COMMON_CANDIDATES.csv.gz')
    frame=rows.merge(common[['panel_id','team_key']],on=['panel_id','team_key'],validate='one_to_one')
    feat=ps.load_features('manual')
    roster=sorted(set(w for s in frame.member_workers for w in s.split('|')))
    count=ps.counts_for(frame,roster);selected=[];usedfits=[]
    for b in sorted(frame.building.unique()):
        x,names,ix,valid,*_=ps.matrix(frame,count,roster,feat[feat.heldout_building.eq(b)],
            labels[labels.heldout_building.eq(b)],False,interactions=True)
        target=frame.building.eq(b).to_numpy();assert valid[target].all()
        z=frame.loc[target].reset_index(drop=True);xx=x[target]
        predictors={}
        for r in fits[fits.heldout_building.eq(b)].itertuples():
            fields=r.predictors.split('|');indices=[names.index(f) for f in fields]
            coef=np.asarray(json.loads(r.coefficient_json),float)
            predictors[(r.model,r.outcome)]=xx[:,indices]@coef
            usedfits.append(dict(r._asdict(),transfer_source_sha256=sha(fp),transfer_source_path=str(fp)))
        for model in ['QT','QT_interaction']:
            if (model,'B8L2') not in predictors:continue
            values={'quality':predictors[(model,'B8L2')]}
            if (model,'log_total_time') in predictors:
                values['balanced']=values['quality']-10*predictors[(model,'log_total_time')]
            for goal,pred in values.items():
                for pid,g in z.groupby('panel_id'):
                    idx=g.index.to_numpy();best=float(pred[idx].max());chosen=idx[np.abs(pred[idx]-best)<=ps.TIE_EPS]
                    for i in chosen:selected.append(dict(panel_id=pid,policy='transfer_main_'+model+'__'+goal,
                        team_key=z.iloc[i].team_key,probability=1/len(chosen),tie_count=len(chosen),objective_max=best))
    original=pd.read_csv(out/'SELECTIONS.csv.gz')
    atomic_csv(pd.concat([original,pd.DataFrame(selected)],ignore_index=True),out/'SELECTIONS.csv.gz')
    atomic_csv(pd.DataFrame(usedfits),out/'TRANSFER_MAIN_QT_FITS.csv.gz')

def main():
    p=argparse.ArgumentParser();p.add_argument('--wait',action='store_true');a=p.parse_args()
    ready=[COMP/'batches/f01_001/COMPLETION.json',HERE/'cross_panel_LOBO/manual/old_structure/SELECTION_RECEIPT.json']
    last=None
    while True:
        missing=[str(p) for p in ready if not p.exists()]
        if missing!=last:print('WAIT_F01',missing,flush=True);last=missing
        if not missing:break
        if not a.wait:raise SystemExit('F01 native batch or primary Manual model not ready')
        time.sleep(5)
    rows,panels,labels,lp,ep,ep_path=load_inputs()
    def target_adapter(condition):
        assert condition=='manual';return rows.copy(),panels.copy()
    def label_adapter(family,condition):
        assert family==FAMILY and condition=='manual';return labels.copy(),lp
    def endpoint_adapter(need,allow_missing=False):
        got=ep[ep.team_key.isin(need)].copy();missing=set(need)-set(got.team_key)
        assert not missing or allow_missing;return got,[ep_path]
    ps.load_target=target_adapter;ps.labels_for=label_adapter;ps.load_new_endpoints=endpoint_adapter
    ps.select('manual',FAMILY,REGIME,use_structure=False)
    out=HERE/REGIME/'manual'/FAMILY
    for name,field in [('SELECTIONS.csv.gz','policy'),('FITS.csv.gz','model')]:
        d=pd.read_csv(out/name);d=d[~d[field].str.contains('fine')];atomic_csv(d,out/name)
    supports=pd.read_csv(out/'SUPPORT.csv');supports['fine_k']=np.nan;supports['has_native_fine_class']=False
    supports=supports.merge(panels[['panel_id','domain_pool_n','member_variation_estimable']],on='panel_id',validate='one_to_one')
    supports.loc[supports.registered_teams.eq(1),'status']='single_set_no_selection_opportunity'
    atomic_csv(supports,out/'SUPPORT.csv')
    add_transferred_qt(rows,labels,out)
    receipt=json.loads((out/'SELECTION_RECEIPT.json').read_text())
    receipt.update(design_path=str(COMP/'F01_CAPACITY_TEAMS.csv.gz'),design_sha256=sha(COMP/'F01_CAPACITY_TEAMS.csv.gz'),
        panel_path=str(COMP/'F01_PANELS.csv'),panel_sha256=sha(COMP/'F01_PANELS.csv'),
        class_definition='unchanged frozen historical10 F01; native coarse only',
        response_fitting='other legal target buildings in complete finite F01 domain',
        single_set_panels_excluded_from_selection=int(supports.registered_teams.eq(1).sum()),
        selected_records=len(pd.read_csv(out/'SELECTIONS.csv.gz')))
    atomic_json(receipt,out/'SELECTION_RECEIPT.json')
    ps.evaluate('manual',FAMILY,REGIME)
    results=pd.read_csv(out/'PANEL_POLICY_RESULTS.csv.gz',low_memory=False)
    results=results.drop(columns=[c for c in results if c.startswith(('selected_fine_','ordinary_fine_'))])
    atomic_csv(results,out/'PANEL_POLICY_RESULTS.csv.gz')
    classes=pd.read_csv(out/'POLICY_CLASS_COMPOSITIONS.csv.gz');classes=classes[classes.tier.eq('coarse')]
    atomic_csv(classes,out/'POLICY_CLASS_COMPOSITIONS.csv.gz')
    atomic_json(dict(status='complete',native_teams=len(ep),native_panels=len(panels),
        selection_panels=results.panel_id.nunique(),single_set_panels=int(panels.possible_member_sets.eq(1).sum()),
        native_fine_class_exists=False,endpoint_path=str(ep_path),endpoint_sha256=sha(ep_path)),HERE/'F01_UTILITY_COMPLETION.json')
    print('F01 COMPLETE',results.shape,flush=True)

if __name__=='__main__':main()
