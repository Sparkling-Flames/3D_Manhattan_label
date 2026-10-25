"""Independent saved-input checks; writes only audit results, never source labels."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.decomposition import PCA

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent / 'unpacked/06A/research/workers/personnel_exchange_discrimination_20261025'
summary = {}
checks = []
def check(name, actual, expected, tol=1e-8):
    a, b = np.asarray(actual), np.asarray(expected)
    if a.dtype.kind in 'biufc' and b.dtype.kind in 'biufc':
        passed = np.allclose(a, b, atol=tol, rtol=tol, equal_nan=True)
        delta = np.abs(a.astype(float)-b.astype(float))
        diff = np.nanmax(delta) if np.isfinite(delta).any() else 0
        diff = float(diff) if np.isfinite(diff) else None
    else:
        passed = np.array_equal(a,b);diff = None
    checks.append(dict(check=name,passed=bool(passed),values=int(a.size),max_abs_diff=diff))
    assert passed, (name, diff)

raw = pd.read_csv(ROOT/'features/RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
hist = pd.read_csv(ROOT/'features/HISTORY_FEATURES_ALL_LOBO.csv.gz')
joint = pd.read_csv(ROOT/'features/HISTORY_FEATURES_WITH_SCOPE_ALL_LOBO.csv.gz')
labels = pd.read_csv(ROOT/'classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz')
metric = [c.removesuffix('_peer') for c in raw if c.endswith('_peer')]
for col in metric:
    groups=['image_id','condition'] + (['origin','time_source'] if col=='log_time' else [])
    expected=raw[col]-raw.groupby(groups,dropna=False)[col].transform('median')
    check('raw_peer_'+col,raw[col+'_peer'],expected)

for fold in hist.heldout_building.unique():
    records=raw[raw.history_eligible & (raw.building.ne(fold) if fold!='ALL' else True)]
    actual=hist[hist.heldout_building.eq(fold)].set_index('worker_id')
    for cond,prefix in [('manual','m'),('semi','s')]:
        for strata,levels in [('all',['简单','中等','困难']),('easy',['简单']),('medium',['中等']),('hard',['困难'])]:
            rows=records[records.condition.eq(cond)&records.difficulty_coarse.isin(levels)]
            avg=rows.groupby(['worker_id','building'])[[c+'_peer' for c in metric]].mean().groupby('worker_id').mean()
            avg.columns=[f'{prefix}_{strata}_{c}' for c in metric]
            avg=avg.reindex(actual.index)
            check(f'history_{fold}_{prefix}_{strata}',actual[avg.columns],avg)
            for suffix,expected in [('images',rows.groupby('worker_id').image_id.nunique()),('buildings',rows.groupby('worker_id').building.nunique()),('records',rows.groupby('worker_id').size()),('time_images',rows.groupby('worker_id').log_time.count())]:
                value=expected.reindex(actual.index)
                if len(rows): value=value.fillna(0)
                check(f'support_{fold}_{prefix}_{strata}_{suffix}',actual[f'{prefix}_{strata}_{suffix}'],value)

scope = pd.read_csv(ROOT/'features_scope/SCOPE_RECORDS_WITH_OPPORTUNITIES.csv.gz')
scope_hist = pd.read_csv(ROOT/'features_scope/SCOPE_FEATURES_ALL_LOBO.csv.gz')
check('scope_source_response_normalization',scope.recorded_rejection,scope.scope_feature_response.map({'in_scope':0.,'out_of_scope':1.}))
assert scope.groupby(['worker_id','image_id','condition']).recorded_rejection.nunique().max()==1
one=scope.groupby(['worker_id','image_id','condition'],as_index=False).agg(building_id=('building_id','first'),origin=('origin','first'),recorded_rejection=('recorded_rejection','mean'),scope_stratum=('scope_stratum','first'),difficulty_coarse=('difficulty_coarse','first'))
for fold in scope_hist.heldout_building.unique():
    d=one[one.building_id.ne(fold)].copy() if fold!='ALL' else one.copy()
    group=d.groupby(['image_id','condition','origin']).recorded_rejection
    d['residual']=(d.recorded_rejection-group.transform('mean')).where(group.transform('count').ge(3))
    d=d[d.scope_stratum.eq('current_ordinary')&d.condition.isin(['manual','semi'])]
    found={}
    for name,mask,ni,nb in [('manual',d.condition.eq('manual'),8,3),('semi',d.condition.eq('semi'),8,3),('hard',d.difficulty_coarse.eq('困难'),5,3),('easy',d.difficulty_coarse.eq('简单'),8,3)]:
        ds=d[mask&d.residual.notna()]
        g=ds.groupby('worker_id').agg(n=('image_id','nunique'),b=('building_id','nunique'),value=('residual','mean'))
        found[name]=g.value.where(g.n.ge(ni)&g.b.ge(nb))
    v=pd.DataFrame(found)
    v['scope_centered_rejection']=v[['manual','semi']].mean(axis=1)
    v['scope_hard_minus_easy']=v.hard-v.easy
    saved=scope_hist[scope_hist.heldout_building.eq(fold)].set_index('worker_id')
    for name in ['scope_centered_rejection','scope_hard_minus_easy']:
        check(f'{name}_{fold}',v[name].reindex(saved.index),saved[name])

st=['turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9']
bd=['matched_top_bias_deg','matched_bottom_bias_deg','log_area_ratio','log_height']
cols=lambda pre,levels,fields:[f'{pre}_{l}_{f}' for l in levels for f in fields]
domains={'mslevel':cols('m',['all'],st),'mshard':cols('m',['hard','hard_minus_easy'],st),'mblevel':cols('m',['all'],bd),'mbhard':cols('m',['hard','hard_minus_easy'],bd),'sstruct':cols('s',['all'],st),'sboundary':cols('s',['all'],bd),'q':['m_easy_B8L2','m_hard_B8L2','m_all_B8L2_p20','m_hard_minus_easy_B8L2'],'t':['m_easy_log_time','m_hard_log_time','m_hard_minus_easy_log_time'],'scope':['scope_centered_rejection','scope_hard_minus_easy']}
families={
 'DSTRUCT':(['mslevel','mshard'],['manual_geometry'],['m_hard_turn_n','m_hard_short_turn_edges','m_all_turn_n']),
 'DBOUNDARY':(['mblevel','mbhard'],['manual_geometry'],['m_all_matched_bottom_bias_deg','m_hard_matched_top_bias_deg','m_all_log_area_ratio']),
 'DJOINT':(['mshard','mbhard','q','t'],['manual_geometry','manual_time'],['m_hard_B8L2','m_hard_turn_n','m_hard_log_time']),
 'MSDGEOM':(['mshard','mbhard','sstruct','sboundary'],['manual_geometry','semi_geometry'],['m_hard_turn_n','s_all_turn_n','m_all_matched_bottom_bias_deg']),
 'MSDGEOM_SCOPE':(['mshard','mbhard','sstruct','sboundary','scope'],['manual_geometry','semi_geometry','scope_joint_supported'],['m_hard_turn_n','s_all_turn_n','scope_centered_rejection'])}
def encoded(df,groups):
    blocks=[]
    for cc in groups:
        a=df[cc].to_numpy(float)
        center=np.median(a,axis=0);scale=np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0)
        scale=np.where(scale>1e-9,scale,a.std(axis=0));scale=np.where(scale>1e-9,scale,1.)
        z=np.clip((a-center)/scale,-3,3)
        z=PCA(n_components=min(2,z.shape[1],len(df)-1),svd_solver='full').fit_transform(z)
        z=z/max(np.sqrt(np.mean(np.sum(z*z,axis=1))),1e-9)/np.sqrt(len(groups))
        blocks.append(z)
    return np.column_stack(blocks)
def clustered(df,groups,sort,k):
    x=encoded(df,groups)
    rawclass=cut_tree(linkage(x,method='ward',optimal_ordering=True),n_clusters=k).ravel()
    order=sorted(set(rawclass),key=lambda cl:tuple(df.loc[rawclass==cl,sort].mean()))
    return pd.Series([f'C{order.index(c)+1}' for c in rawclass],index=df.worker_id)
for fold,g in joint.groupby('heldout_building',sort=False):
    for fam,(ds,req,sort) in families.items():
        fields=[c for domain in ds for c in domains[domain]]
        d=g[g[req].all(axis=1)&g[fields].notna().all(axis=1)].reset_index(drop=True)
        for k in [2,3,4]:
            actual=labels[labels.heldout_building.eq(fold)&labels.method.eq(f'{fam}_K{k}')].set_index('worker_id')
            fitted=clustered(d,[domains[x] for x in ds],sort,k).reindex(actual.index).fillna('unknown')
            check(f'labels_{fold}_{fam}_K{k}',fitted,actual.class_id)

summary['forward']={'raw_records':len(raw),'eligible_records':int(raw.history_eligible.sum()),'folds':hist.heldout_building.nunique(),'ward_configurations_refitted':15*hist.heldout_building.nunique(),'scope_records':len(scope),'scope_recorded':int(scope.recorded_rejection.notna().sum()),'scope_restored':int(scope.scope_restored_from_historical_oos.sum()),'scope_dedup_opportunities':len(one)}
repo=OUT.parents[2]
ledger=pd.read_csv(repo/'research/workers/personnel_type_discovery_next_20261019/work_personnel_typing_A_20261019/input/RECORD_EVIDENCE_LEDGER.csv.gz')
old=pd.read_csv(repo/'research/workers/worker_b8l2_d10_20261017/scope_response_evidence.csv')
source=scope.merge(ledger[['object_id','worker_id','image_id','condition','scope_response']],on='object_id',suffixes=('','_source'),validate='one_to_one')
assert len(source)==len(scope)==len(ledger)
for col in ['worker_id','image_id','condition']:
    check('ledger_'+col,source[col],source[col+'_source'])
check('ledger_scope',source.scope_response_v2_original.fillna('missing'),source.scope_response.fillna('missing'))
bridge=scope[scope.scope_restored_from_historical_oos].merge(old[['worker_id','image_id','object_id','worker_scope']],on=['worker_id','image_id'],suffixes=('','_source'),validate='one_to_one')
assert len(bridge)==286
check('restored_original_object',bridge.historical_scope_object_id,bridge.object_id_source)
assert bridge.worker_scope_source.eq('oos').all() and bridge.scope_feature_response.eq('out_of_scope').all()
summary['scope_source']={'ledger_rows_exact':len(source),'historical_oos_bridge_exact':len(bridge),'restoration_conflicts':0}
pd.DataFrame(checks).to_csv(OUT/'CHECKS_FORWARD.csv',index=False)
(OUT/'SUMMARY_FORWARD.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False));print('all checks',len(checks),'passed',flush=True)
