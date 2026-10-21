"""Independent frozen-support Manual personal-Q calibration; no new fusion or tuning.

Source peer Q excludes the predicted person. Personal residuals are measured only
on admitted tasks outside the held-out building; each residual is Q minus the
other admitted workers' same-image mean. Missing residuals remain missing.
"""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/same_room/same_room_multiview_20261020'
OUT = ROOT / 'research/same_room/same_room_independent_followup_20261021/calibration'

def peer_means(pivot):
    """Image-row peer means, also defined for a person absent from that image."""
    return pivot.rsub(pivot.sum(axis=1), axis=0).div(pivot.count(axis=1)-1, axis=0).where(pivot.notna(), pivot.mean(axis=1), axis=0)

def residual_history(records, metric, excluded_building):
    train = records[records.training_allowed & records.building_id.ne(excluded_building)].copy()
    sums = train.groupby('image_id')[metric].transform('sum')
    counts = train.groupby('image_id')[metric].transform('count')
    train['relative'] = train[metric] - (sums-train[metric])/(counts-1).where(counts.gt(1))
    return train.groupby('worker_id').agg(relative=('relative','mean'), relative_n=('relative','count'), baseline=(metric,'mean'))

def aggregate(rows):
    # Exact legacy order: repeated splits -> fixed worker/group/target across m ->
    # workers -> overlap groups -> target images -> buildings. All methods paired.
    keys=['metric','origin','group_id','building','target_image','worker_id','m','N','method']
    w=rows.groupby(keys,as_index=False).agg(mae=('absolute_error','mean'),bias=('error','mean'),actual=('actual','first'),relative=('relative','first'))
    identity=[k for k in keys if k!='m']
    w=w[w.groupby(identity).m.transform('nunique').eq(w.N-1-w.N//2)].copy()
    result=[]
    for stage, mask in [('minimum_majority',w.m.eq(w.N//2+1)),('maximum_history',w.m.eq(w.N-1))]:
        part=w[mask]
        for subset in ['all','target_Q_below_50','external_relative_bottom_quartile']:
            q=part.copy()
            if subset=='target_Q_below_50': q=q[q.actual.lt(50)]
            if subset=='external_relative_bottom_quartile':
                unique=q[['metric','origin','building','worker_id','relative']].drop_duplicates()
                thresholds=unique.groupby(['metric','origin','building']).relative.quantile(.25)
                threshold=pd.MultiIndex.from_frame(q[['metric','origin','building']]).map(thresholds)
                q=q[q.relative.le(np.asarray(threshold))]
            target=q.groupby(['metric','origin','group_id','building','target_image','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),workers=('worker_id','size'))
            image=target.groupby(['metric','origin','building','target_image','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'))
            b=image.groupby(['metric','origin','building','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),images=('target_image','nunique'))
            b['stage']=stage;b['subset']=subset;result.append(b)
    b=pd.concat(result,ignore_index=True)
    s=b.groupby(['metric','origin','stage','subset','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),buildings=('building','nunique'),images=('images','sum'))
    return w,b,s

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    raw=json.load(gzip.open(path,'rt',encoding='utf-8'))['records']
    d=pd.DataFrame([{**{k:r[k] for k in ['object_id','image_id','worker_id','building_id','condition','origin','is_oos','is_doorway','pool_analysis_eligible','quality_usable','quality_use','B8L2','D10']},'current_binding':r['binding_evidence']['chosen_target_id']==r['binding_evidence']['current_target_id']} for r in raw])
    admission=ROOT/'research/same_room/same_room_v2_prediction_20261019/training_admission.csv'
    gate=pd.read_csv(admission).set_index('object_id').training_allowed
    d['training_allowed']=d.object_id.map(gate)
    d=d[d.pool_analysis_eligible & d.condition.eq('manual') & ~d.is_oos & ~d.is_doorway & d.quality_usable & d.quality_use.eq('ordinary_primary') & d.current_binding].copy()
    assert d.training_allowed.notna().all()
    assert not d.duplicated(['image_id','worker_id']).any()
    p=pd.read_csv(BASE/'individual_features.csv.gz')
    split=pd.read_csv(BASE/'splits.csv.gz').set_index('split_id')
    groups={g['group_id']:g for g in json.loads((BASE/'GROUPS.json').read_text(encoding='utf-8'))}
    outputs=[];checks=[]
    for (metric,origin),part in p.groupby(['metric','origin'],sort=False):
        records=d[d[metric].notna() & (True if origin=='all' else d.origin.eq(origin))]
        piv=records.pivot(index='image_id',columns='worker_id',values=metric)
        peers=peer_means(piv)
        x=part.copy(); x['relative']=np.nan;x['relative_n']=np.nan;x['peer_source']=np.nan;x['peer_observed_source']=np.nan
        baseline_diff=0.;source_diff=0.;actual_diff=0.
        for building,inds in x.groupby('building').groups.items():
            hist=residual_history(records,metric,building)
            x.loc[inds,'relative']=x.loc[inds,'worker_id'].map(hist.relative)
            x.loc[inds,'relative_n']=x.loc[inds,'worker_id'].map(hist.relative_n)
            baseline_diff=max(baseline_diff,float(np.max(np.abs(x.loc[inds,'baseline']-x.loc[inds,'worker_id'].map(hist.baseline)))))
        for sid,inds in x.groupby('split_id').groups.items():
            sp=split.loc[sid];h=sp.history.split('|');targets=sp.targets.split('|');g=groups[sp.group_id]
            assert len(h)>len(g['images'])/2 and set(h).isdisjoint(targets)
            assert set(h)|set(targets)==set(g['images'])
            workers=x.loc[inds,'worker_id']; own=piv.loc[h]; peer=peers.loc[h]
            x.loc[inds,'peer_source']=workers.map(peer.mean())
            x.loc[inds,'peer_observed_source']=workers.map(peer.where(own.notna()).mean())
            source_diff=max(source_diff,float(np.max(np.abs(x.loc[inds,'source']-workers.map(own.mean())))))
        actual=np.array([piv.loc[t,w] for t,w in zip(x.target_image,x.worker_id)])
        actual_diff=float(np.max(np.abs(actual-x.actual)))
        assert max(baseline_diff,source_diff,actual_diff)<1e-9
        x['calibration_raw']=x.peer_source+x.relative
        before=len(x);x=x.dropna(subset=['relative','peer_source','peer_observed_source'])
        checks.append(dict(metric=metric,origin=origin,input_rows=before,supported_rows=len(x),missing_rows=before-len(x),max_baseline_difference=baseline_diff,max_source_difference=source_diff,max_actual_difference=actual_diff,clipped_rows=int((~x.calibration_raw.between(0,100)).sum())))
        methods={'same_person_source':x.source,'out_of_building_person':x.baseline,'half_blend':(x.source+x.baseline)/2,'peer_source_only':x.peer_source,'peer_plus_relative_unclipped':x.calibration_raw,'peer_plus_relative_clipped':x.calibration_raw.clip(0,100),'observed_peer_plus_relative_clipped':(x.peer_observed_source+x.relative).clip(0,100)}
        for method,value in methods.items():
            a=x.copy();a['method']=method;a['predicted']=value;a['error']=a.predicted-a.actual;a['absolute_error']=a.error.abs();outputs.append(a)
    allrows=pd.concat(outputs,ignore_index=True)
    worker,building,summary=aggregate(allrows)
    worker.to_csv(OUT/'worker_targets.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    building.to_csv(OUT/'building_metrics.csv',index=False);summary.to_csv(OUT/'summary.csv',index=False)
    pd.DataFrame(checks).to_csv(OUT/'support_checks.csv',index=False)
    paired=building.pivot(index=['metric','origin','stage','subset','building'],columns='method',values='mae').reset_index()
    paired['calibration_minus_own_source']=paired.peer_plus_relative_clipped-paired.same_person_source
    paired['calibration_minus_half_blend']=paired.peer_plus_relative_clipped-paired.half_blend
    paired['observed_calibration_minus_own_source']=paired.observed_peer_plus_relative_clipped-paired.same_person_source
    paired['observed_calibration_minus_half_blend']=paired.observed_peer_plus_relative_clipped-paired.half_blend
    paired.to_csv(OUT/'paired_building_comparisons.csv',index=False)
    leave=[]
    for key,part in paired.groupby(['metric','origin','stage','subset']):
        for omitted in part.building:
            rest=part[part.building.ne(omitted)]
            leave.append(dict(zip(['metric','origin','stage','subset'],key),omitted_building=omitted,remaining_buildings=len(rest),calibration_minus_own_source=rest.calibration_minus_own_source.mean(),observed_calibration_minus_own_source=rest.observed_calibration_minus_own_source.mean()))
    pd.DataFrame(leave).to_csv(OUT/'leave_one_building_out_sensitivity.csv',index=False)
    sources=[path,admission,BASE/'individual_features.csv.gz',BASE/'GROUPS.json',BASE/'splits.csv.gz']
    meta=dict(scope='Manual ordinary only; B8L2 primary, D10 sensitivity; origins all/new/v1 separate',semi='Not evaluated: frozen personal-Q supports are Manual only.',target_use='Target Q used only for evaluation and retrospective Q<50 subgroup, never feature construction.',relative='Mean of admitted out-of-building own Q minus same-image other-admitted-worker mean; singleton peer tasks missing.',source='Primary matched-history observed variant uses only history images on which person contributed, matching own-source image budget. All-source expanded variant uses every strict-majority history image, including peer-only images where person is absent. Both exclude predicted person from peers.',lowtail='Within held-out building/origin/metric, bottom quartile of unique eligible persons external task-relative Q; no target Q selection.',clipping='Fixed [0,100], no tuning.',comparison='Independent frozen-support calculation, not reproduction of inaccessible 47 MiB newPro package or its 11.116 claim.',weighting='Split, fixed worker across m, worker, overlapping group, image, building equal; minimum-majority and maximum-history separately.',sources={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},checks=checks)
    (OUT/'METHOD.json').write_text(json.dumps(meta,indent=2))
    print(summary[(summary.metric=='B8L2') & (summary.origin=='all')].to_string(index=False))

if __name__=='__main__':main()

