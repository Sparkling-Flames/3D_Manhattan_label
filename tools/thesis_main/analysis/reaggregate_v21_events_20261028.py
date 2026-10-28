"""Reattach v2.1 endpoints to frozen events; no relabeling or new teams."""
import argparse,gzip,importlib.util,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read

TARGET=OUT/'event_reaggregation'
MIX=ROOT/'research/workers/personnel_mixture_comparison_20261022'
DISC=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked'
CLOSURE=ROOT/'research/workers/personnel_exchange_closure_20261022'
BATCHES=['manual_joint_A','manual_joint_B','manual_structure','semi_joint']

def import_file(path,name):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def scored_endpoints(directory):
    values={}
    for path in sorted((directory/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);assert r['team_key'] not in values;values[r['team_key']]=r
    return values

def closure_endpoints(new):
    module=import_file(MIX/'exchanges/compare_saved_exchanges.py','frozen_exchange')
    ep=pd.read_csv(module.SCALAR,usecols=module.ENDPOINT_FIELDS,low_memory=False).set_index('team_key',drop=False)
    assert ep.index.is_unique
    extra=MIX/'inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz'
    if extra.exists():ep.update(pd.read_csv(extra).set_index('team_key')[['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']])
    if new:
        scored=scored_endpoints(OUT/'exchange_endpoint_rescore')
        for key,r in scored.items():
            if key not in ep.index:continue
            assert set(str(ep.at[key,'member_workers']).split('|'))==set(r['member_workers']) and ep.at[key,'pool_id']==r['pool_id']
            result=r['result'] or {};diag=r['reference_dependent_diagnostics']
            for c in ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','height_mean_ratio']:
                ep.at[key,c]=result.get(c,np.nan)
            for c in ['ref_node_recall_9','ref_edge_recall_9','diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05']:
                ep.at[key,c]=diag.get(c,np.nan)
            state=r['rescore_state'];ep.at[key,'score_status']='no_connection' if state=='original_no_connection' else state
            ep.at[key,'complete_evaluable']=bool(r['original_complete_evaluable'] and result.get('score_status')=='complete_conditional')
    return module,ep

def closure_batch(name):
    target=TARGET/'exchange';target.mkdir(parents=True,exist_ok=True)
    module,old=closure_endpoints(False);_,new=closure_endpoints(True);module.HERE=target
    d=pd.read_csv(MIX/f'exchanges/{name}/EXACT_EVENT_LINKS.csv.gz',low_memory=False).fillna('')
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    changed=d[d.pool_id.isin(ids)];keys=set(scored_endpoints(OUT/'exchange_endpoint_rescore'))
    assert all(set(changed['team_'+arm])<=keys for arm in 'ABC'),(name,'affected endpoint missing')
    saved=pd.read_csv(MIX/f'exchanges/{name}/EVENT_OUTCOMES.csv.gz',low_memory=False)
    assert len(d)==len(saved) and (d.event_id.to_numpy()==saved.event_id.to_numpy()).all()
    sample=module.outcomes(d.head(100),old);original=saved.head(100)
    for c in ['A_B8L2','B_B8L2','C_B8L2','same_B8L2','cross_B8L2','net_B8L2','abs_advantage_B8L2','same_D10','cross_D10','net_D10']:
        a=pd.to_numeric(sample[c],errors='coerce');b=pd.to_numeric(original[c],errors='coerce');assert a.isna().equals(b.isna()) and np.allclose(a.fillna(0),b.fillna(0),rtol=0,atol=1e-8),('old parity',name,c)
    out=module.outcomes(d,new)
    # Historical 'failure' means incomplete_evaluable; provide separate physical failure.
    for arm in 'ABC':
        status=new.reindex(d['team_'+arm]).score_status.reset_index(drop=True)
        out[arm+'_actual_consensus_failure']=status.isin(['no_connection','below_four'])
        out[arm+'_score_unavailable']=pd.to_numeric(out[arm+'_B8L2'],errors='coerce').isna()
    module.save(out,f'{name}/EVENT_OUTCOMES.csv.gz')
    sums,long,im,bl,bg=module.aggregate(d,out,name)
    oldscored=read(OUT/'exchange_endpoint_rescore/CHECKS.json')
    coverage=dict(group=name,registered_events=len(d),images=d.image.nunique(),buildings=d.building.nunique(),unique_oriented=int(d.actual_oriented_ABC.nunique()),events_all_three_scored=int(out.three_scores_available.sum()),original_sample_rows=len(sample),old_reference_sample_parity=True,design_identity='frozen_v2_labels_members_and_events',old_geometry_distances_reused=True,new_fusion=False)
    (target/name/'V21_COVERAGE.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(coverage,ensure_ascii=False),flush=True)

DISC_STAGES={
 'screen':'02A/results/screen/EVENT_METRICS.csv.gz',
 'confirm':'04A1/results/confirm/EVENT_METRICS.csv.gz',
 'target_omissions':'04A1/results/target_omissions/EVENT_METRICS.csv.gz',
 'reverse_screen':'04A2/results/reverse_screen/EVENT_METRICS.csv.gz',
 'reverse_confirm':'04A2/results/reverse_confirm/EVENT_METRICS.csv.gz',
 'size_paths':'05/results/size_paths/EVENT_METRICS.csv.gz',
 'large_team_ac_tail':'05/results/large_team_ac_tail/EVENT_METRICS.csv.gz',
}
UPDATE=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','height_mean_ratio','boundary_loss','direction_loss','height_loss','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','reference_node_shortfall','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg','matched_ref_pair_fraction']

def endpoint_fields(r):
    result=r['result'] or {};d=r['reference_dependent_diagnostics'];out={k:result.get(k) for k in UPDATE};out.update({k:d.get(k) for k in UPDATE if k in d})
    out['score_status']=r['rescore_state'];out['complete_evaluable']=bool(r['original_complete_evaluable'] and result.get('score_status')=='complete_conditional')
    out['actual_consensus_failure']=r['original_score_status'] in ('no_connection','below_four','fusion_exception');return out

def recompute_metrics(data,arms):
    for metric in UPDATE:
        if not all(a+'_'+metric in data for a in arms):continue
        values={a:pd.to_numeric(data[a+'_'+metric],errors='coerce') for a in arms}
        for left,right,tag in [('C','A','CA'),('C','B','CB'),('B','A','BA')]:
            col=metric+'_'+tag
            if col in data and left in values and right in values:data[col]=values[left]-values[right]
        if len(arms)==3:
            ok=values['A'].notna()&values['B'].notna()&values['C'].notna()
            within=(values['B']-values['A']).abs().where(ok);cross=((values['C']-values['A']).abs()+(values['C']-values['B']).abs()).div(2).where(ok)
            for suffix,value in [('within',within),('cross',cross),('gap',cross-within)]:
                col=metric+'_'+suffix
                if col in data:data[col]=value
    for arm in arms:
        if arm+'_failed' in data:data[arm+'_failed']=data[arm+'_B8L2'].isna()
    if len(arms)==3 and 'ABC_scored' in data:data['ABC_scored']=~(data.A_failed|data.B_failed|data.C_failed)
    for arm in 'AB':
        contrast='B8L2_C'+arm
        if arm not in arms or contrast not in data:continue
        q=data[contrast]
        for name,flag in [('C_loss10_C'+arm,q.lt(-10)),('C_improved_C'+arm,q.gt(0))]:
            if name in data:data[name]=flag.astype(float).where(q.notna())
        name='C_failure_or_loss10_C'+arm
        if name in data:data[name]=(data.C_failed|q.lt(-10)).astype(float).where(~data[arm+'_failed'])
    if 'B8L2_abs_CA' in data:data['B8L2_abs_CA']=data.B8L2_CA.abs()
    return data

def discrimination_stage(stage):
    target=TARGET/'discrimination'/stage;target.mkdir(parents=True,exist_ok=True)
    source=DISC/DISC_STAGES[stage];scores=scored_endpoints(OUT/'discrimination_endpoint_rescore');mapped={k:endpoint_fields(v) for k,v in scores.items()}
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    maps={field:{k:v.get(field) for k,v in mapped.items()} for field in UPDATE+['complete_evaluable','actual_consensus_failure']}
    dest=target/'EVENT_METRICS.csv.gz';tmp=target/'EVENT_METRICS.writing.gz';total=changed=0;images=set();buildings=set();parity=[];present_keys=set()
    with gzip.open(tmp,'wt',encoding='utf8',newline='') as f:
        for data in pd.read_csv(source,chunksize=3000,low_memory=False):
            arms=[a for a in 'ABC' if a+'_team_key' in data];assert arms in (['A','B','C'],['A','C'])
            affected=data.pool_id.isin(ids);changed+=int(affected.sum());total+=len(data);images.update(data.image.dropna());buildings.update(data.building.dropna())
            sample=data.head(30).copy();recomputed=recompute_metrics(sample.copy(),arms)
            for c in ['B8L2_CA','B8L2_CB','B8L2_BA','B8L2_within','B8L2_cross','B8L2_gap']:
                if c in sample and c in recomputed:
                    a=pd.to_numeric(sample[c],errors='coerce');b=pd.to_numeric(recomputed[c],errors='coerce');assert a.isna().equals(b.isna()) and np.allclose(a.fillna(0),b.fillna(0),atol=1e-8,rtol=0),(stage,c,'old event parity')
            for arm in arms:
                keys=data[arm+'_team_key'];assert set(keys[affected])<=set(mapped),(stage,arm,'missing affected endpoint');present_keys.update(keys[affected])
                for metric in UPDATE:
                    col=arm+'_'+metric
                    if col in data:
                        z=keys.map(maps[metric]);data.loc[affected,col]=z[affected]
                if arm+'_incomplete' in data:
                    z=keys.map(maps['complete_evaluable']);data.loc[affected,arm+'_incomplete']=~z[affected].astype(bool)
                data[arm+'_actual_consensus_failure_v21']=pd.Series(pd.NA,index=data.index,dtype='boolean')
                z=keys.map(maps['actual_consensus_failure']);data.loc[affected,arm+'_actual_consensus_failure_v21']=z[affected]
            # Only affected rows are rewritten; all old geometry comparisons and selection fields remain intact.
            if affected.any():
                updated=recompute_metrics(data.loc[affected].copy(),arms)
                for col in updated.columns:data.loc[affected,col]=updated[col]
            data['endpoint_data_release']=np.where(affected,'v2.1_rescored','v2_inherited_unchanged')
            data.to_csv(f,index=False,header=(total==len(data)))
    tmp.replace(dest)
    c=dict(stage=stage,events=total,affected_events=changed,images=len(images),buildings=len(buildings),affected_endpoint_teams=len(present_keys),old_reference_event_formula_parity=True,old_labels_and_members_retained=True,new_fusion=False)
    (target/'COVERAGE.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(c,ensure_ascii=False),flush=True)


def direct_ac():
    module=import_file(MIX/'direct_ac/analyze_direct_ac.py','frozen_direct_ac');target=TARGET/'direct_ac';target.mkdir(parents=True,exist_ok=True)
    data=pd.read_csv(MIX/'direct_ac/EXACT_AC_EVENTS_AND_OUTCOMES.csv.gz',low_memory=False);old=data.copy();scores=scored_endpoints(OUT/'exchange_endpoint_rescore');mapped={k:endpoint_fields(v) for k,v in scores.items()};ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'};affected=data.pool_id.isin(ids)
    dependent=set(UPDATE+['diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05'])
    for arm in ['A','C']:
        keys=data['team_'+arm];assert set(keys[affected])<=set(mapped)
        for met in dependent:
            col=arm+'_'+met
            if col in data:
                v=keys.map({k:(scores[k]['reference_dependent_diagnostics'].get(met) if met.startswith('diag_') else mapped[k].get(met)) for k in mapped});data.loc[affected,col]=v[affected]
        v=keys.map({k:mapped[k]['complete_evaluable'] for k in mapped});data.loc[affected,arm+'_complete_evaluable']=v[affected]
        data.loc[affected,arm+'_failure']=(~v[affected].astype(bool)).astype(float)
        data[arm+'_actual_consensus_failure_v21']=pd.Series(pd.NA,index=data.index,dtype='boolean')
        v=keys.map({k:mapped[k]['actual_consensus_failure'] for k in mapped});data.loc[affected,arm+'_actual_consensus_failure_v21']=v[affected]
    data['both_scored']=data.A_complete_evaluable.astype(bool)&data.C_complete_evaluable.astype(bool)&data.A_B8L2.notna()&data.C_B8L2.notna()
    for met in module.METRICS:
        if met in dependent and 'delta_'+met in data:
            delta=pd.to_numeric(data['C_'+met],errors='coerce')-pd.to_numeric(data['A_'+met],errors='coerce')
            if met in ['B8L2','D10']:delta=delta.where(data.both_scored)
            data.loc[affected,'delta_'+met]=delta[affected]
    data.loc[affected,'abs_delta_B8L2']=data.loc[affected,'delta_B8L2'].abs()
    for t in [5,10]:data.loc[affected,'loss_gt'+str(t)]=data.loc[affected,'delta_B8L2'].lt(-t).astype(float).where(data.loc[affected,'both_scored'])
    # Old parity on registered scoreable rows, before changing the reference.
    z=old[old.both_scored].head(100);assert np.allclose(z.delta_B8L2,z.C_B8L2-z.A_B8L2,rtol=0,atol=1e-8)
    data['endpoint_data_release']=np.where(affected,'v2.1_rescored','v2_inherited_unchanged');data.to_csv(target/'EXACT_AC_EVENTS_AND_OUTCOMES.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    cols=['delta_'+f for f in module.METRICS]+['abs_delta_B8L2','AC_centroid_distance_h','delta_recorded_time_pct','A_failure','C_failure','loss_gt10','loss_gt5']
    keys=['method_id','condition','tier','source_domain','direction_role','n','actual_m_AC','within_parent_fine_change']
    for label,group in [('CONDITION',keys),('DIFFICULTY',keys+['difficulty']),('ROLE',['method_id','condition','tier','direction_role','within_parent_fine_change'])]:
        sums,im,bu=module.summary(data,group,cols);sums.to_csv(target/(label+'_COMPARISON.csv'),index=False)
        if label=='CONDITION':im.to_csv(target/'IMAGE_EFFECTS.csv.gz',index=False,compression={'method':'gzip','mtime':0});bu.to_csv(target/'BUILDING_EFFECTS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    c=dict(events=len(data),affected_events=int(affected.sum()),images=data.image.nunique(),buildings=data.building.nunique(),both_scored=int(data.both_scored.sum()),old_reference_sample_parity=True,original_labels_members=True,new_fusion=False)
    (target/'COVERAGE.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('direct ac',json.dumps(c),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--part',required=True);a=p.parse_args()
    if a.part in BATCHES:closure_batch(a.part)
    elif a.part in DISC_STAGES:discrimination_stage(a.part)
    elif a.part=='direct_ac':direct_ac()
    else:raise ValueError(a.part)
