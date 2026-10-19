#!/usr/bin/env python3
"""Additional fixed-input sensitivity and Chinese per-person deliverables.

These diagnostics do not revise selection rules or classifications. They separate
pool/anchor changes, time sources, and the extra quality-amplitude information
contained in the multi-difficulty phenotype from genuine difficulty contrasts.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,gzip,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_profiles import DIFFS,METRICS,fit_fe,solve,labelq,labelt,relative,stats,js,digest,predict_fold,summaries

ZH={'across_strong':'三难度相对同伴较强','hard_specialist':'难图专长候选','hard_relative_lift_only':'难图相对上升、同伴优势不足（θ难<3，未必绝对低）','hard_drop':'难图相对下降候选','mixed_or_near':'混合或接近常态','unknown':'证据不足','Q+':'同任务相对Q较高','Q-':'同任务相对Q较低','fast':'相对快','slow':'相对慢','middle':'中间','above_peer':'高于同伴3分以上','below_peer':'低于同伴3分以上','near_peer':'同伴上下3分内'}
def translate(s):return ' × '.join(ZH.get(x,x)for x in str(s).split('|'))

def version_sensitivity(repo,out,m,full):
    v=pd.read_csv(out/'version_profiles.csv');a=full.copy();a['version_panel']='v2_all_5719';v=pd.concat([v,a],ignore_index=True);anchor=set(pd.read_csv(repo/'research/workers/worker_b8l2_d10_20261017/quality_panel.csv').worker_id)
    for panel,g in v.groupby('version_panel'):
        for metric in METRICS:
            offset=g.loc[g.worker_id.isin(anchor),'Q_effect_'+metric].mean();v.loc[g.index,'Q_legacy24_anchor_'+metric]=g['Q_effect_'+metric]-offset
    use=['worker_id','version_panel','Q_n','Q_images','Q_buildings','Q2_B8L2','Q3_B8L2','Q_effect_B8L2','Q_legacy24_anchor_B8L2','Q_effect_D10','Q_legacy24_anchor_D10','percentile_B8L2','T_source_effect','T_source_origin_effect','T_fixed_60_180','T_fixed_90_240','difficulty_type_B8L2']
    v[use].to_csv(out/'version_anchor_comparison.csv',index=False)
    shifts=pd.read_csv(out/'v1_fixed_answers_peer_pool_shift.csv');summary=shifts.groupby(['metric','worker_id']).agg(n=('object_id','size'),images=('image_id','nunique'),buildings=('building_id','nunique'),mean_old_percentile=('percentile','mean'),mean_new_percentile=('percentile_newpool','mean'),mean_percentile_shift=('percentile_shift','mean'),max_abs_percentile_shift=('percentile_shift',lambda x:x.abs().max()),mean_peer_delta_shift=('peer_delta_shift','mean')).reset_index();summary.to_csv(out/'v1_peer_pool_shift_by_worker.csv',index=False)
    record=m[['object_id','worker_id','image_id','building_id','difficulty','B8L2','D10']].copy();record['D10_minus_B8L2']=record.D10-record.B8L2;record.to_csv(out/'fixed_record_metric_sensitivity.csv',index=False)
    ms=[]
    for _,r in full.iterrows():
        x={'worker_id':r.worker_id,'n':r.Q_n,'Q_effect_difference':r.Q_effect_D10-r.Q_effect_B8L2,'absolute_mean_difference':r.absolute_D10_mean-r.absolute_B8L2_mean,'percentile_difference':r.percentile_D10-r.percentile_B8L2}
        for typ in ['Q2','Q3','QT','fine_dtype','difficulty_type']:
            x[typ+'_B8L2']=r[typ+'_B8L2'];x[typ+'_D10']=r[typ+'_D10'];x[typ+'_changed']=r[typ+'_B8L2']!=r[typ+'_D10']
        ms.append(x)
    pd.DataFrame(ms).to_csv(out/'worker_metric_class_sensitivity.csv',index=False)

def complexity_time(m,d,full,out):
    z=m[m.source_active_time_seconds.gt(0)&m.declared_pair_count.gt(0)].copy();z['lt']=np.log(z.source_active_time_seconds);z['lp']=np.log(z.declared_pair_count)
    ws=sorted(z.worker_id.unique());idx={w:i for i,w in enumerate(ws)};n=len(ws);A=np.zeros((n+1,n+1));b=np.zeros(n+1)
    for _,g in z.groupby('task'):
        X=np.zeros((len(g),n+1));X[np.arange(len(g)),[idx[w]for w in g.worker_id]]=1;X[:,-1]=g.lp;X-=X.mean(0);y=g['lt']-g['lt'].mean();A+=X.T@X;b+=X.T@y
    coeff=solve(A,b,np.r_[np.ones(n),0]);base,_=fit_fe(z,'lt');rows=[]
    for w in ws:
        f=full[full.worker_id.eq(w)].iloc[0];g=z[z.worker_id.eq(w)];supported=g.task.nunique()>=6 and g.building_id.nunique()>=3;r=dict(worker_id=w,n=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique(),supported_common=supported,source_effect_main=f.T_source_effect,source_effect_common=base[w],source_effect_after_count_diagnostic=coeff[idx[w]],common_t3=labelt(base[w],3,supported),count_adjusted_t3=labelt(coeff[idx[w]],3,supported));r['label_changed']=r['common_t3']!=r['count_adjusted_t3'];rows.append(r)
    pd.DataFrame(rows).to_csv(out/'time_count_adjustment_diagnostic.csv',index=False)
    ts=d[d.pool_analysis_eligible&d.condition.eq('manual')&d.ordinary_difficulty_eligible&d.difficulty.isin(DIFFS)&d.source_active_time_seconds.gt(0)].copy();ts['task']=ts.source_task;lo,hi=ts.source_active_time_seconds.quantile([.01,.99]);ts['rawlog']=np.log(ts.source_active_time_seconds);ts['winsorlog']=np.log(ts.source_active_time_seconds.clip(lo,hi));rb,_=fit_fe(ts,'rawlog');wb,_=fit_fe(ts,'winsorlog');tail=[]
    for w in sorted(set(rb)&set(full.worker_id)):
        f=full[full.worker_id.eq(w)].iloc[0];tail.append(dict(worker_id=w,supported=f.T_source_supported,raw_effect=rb[w],winsor_1_99_effect=wb[w],raw_t3=labelt(rb[w],3,f.T_source_supported),winsor_t3=labelt(wb[w],3,f.T_source_supported)))
    tt=pd.DataFrame(tail);tt['label_changed']=tt.raw_t3.ne(tt.winsor_t3);tt.to_csv(out/'time_tail_sensitivity.csv',index=False)
    correlations=[]
    for origin in ['all','v1','new']:
        g=full[full.Q_supported&full.T_source_supported]
        if origin!='all':g=g[g.origin.eq(origin)]
        correlations.append(dict(origin=origin,workers=len(g),Q_T_effect_pearson=g.Q_effect_B8L2.corr(g.T_source_effect),Q_T_effect_spearman=g.Q_effect_B8L2.corr(g.T_source_effect,method='spearman')))
    js(out/'TIME_DIAGNOSTIC_SUMMARY.json',dict(log_pair_count_coefficient=coeff[-1],count_adjustment_interpretation='within same task and worker; current drawn count may mediate effort and error, so diagnostic only and never replaces selected T',common_records=len(z),count_adjusted_t3_changes=int(pd.DataFrame(rows).label_changed.sum()),winsor_1pct_seconds=lo,winsor_99pct_seconds=hi,winsor_t3_changes=int(tt.label_changed.sum()),origin_adjustment_cannot_calibrate_cross_origin=bool(d.groupby('worker_id').origin.nunique().max()==1),person_Q_T_associations=correlations))

def published_comparison(repo,out,full):
    with gzip.open(repo/'research/statistics/v2_integrated_analysis_20261019/tables.json.gz','rt')as f:t=json.load(f)['tables']
    pub=pd.DataFrame(t['statistics__personnel_profiles']);pub=pub[pub.panel.eq('manual|ordinary_primary')&pub.difficulty.eq('all')];cols=['worker_id','n','buildings','relative_q','relative_q_D10','peer_delta','q_class','q_class_D10','time_median','time_n','t_class','t_class_sensitivity','fine_class','B8L2_candidate'];pub=pub[[c for c in cols if c in pub]];pub.to_csv(out/'published_v2_profiles_baseline.csv',index=False)
    cmp=pub.merge(full[['worker_id','Q_effect_B8L2','Q3_B8L2','Q2_B8L2','percentile_B8L2','T_source_n','T_source_median','T_relative_3','T_fixed_60_180','T_fixed_90_240','difficulty_type_B8L2','fine_dtype_B8L2']],on='worker_id',validate='one_to_one');assert (cmp.relative_q-cmp.percentile_B8L2).abs().max()<1e-10
    cmp['rank_percentile_exact_reproduction_error']=cmp.relative_q-cmp.percentile_B8L2;cmp.to_csv(out/'published_v2_classification_comparison.csv',index=False)
    # Explicit original group memberships only. No building-identity inference,
    # no relationship transitive closure, no invented missing room IDs.
    groups=[r for r in t['statistics__room_registry'] if r.get('group_kind')=='original' and r.get('classification',{}).get('physical_same')=='支持']
    ims=pd.read_csv(out/'validation_per_image.csv');rows=[]
    # Only continuous candidates have identical evaluable worker/peer sets in
    # these already-aggregated errors. Missingness-sensitive class comparisons
    # must use paired_model_comparison.csv, which reconstructs common peers.
    ims=ims[~ims.model.str.startswith('class_')]
    for r in groups:
        g=ims[ims.image_id.isin(r['image_ids'])]
        for (metric,model),a in g.groupby(['metric','model']):rows.append(dict(group_id=r['group_id'],metric=metric,model=model,images=a.image_id.nunique(),building_id=';'.join(sorted(a.building_id.unique())),relative_mse=a.relative_mse.mean()))
    rr=pd.DataFrame(rows);rr.to_csv(out/'declared_room_group_errors.csv',index=False)
    sums=[]
    for metric,g in rr.groupby('metric'):
        p=g.pivot(index='group_id',columns='model',values='relative_mse')
        for model in p:
            if model=='FE':continue
            a=p[['FE',model]].dropna();sums.append(dict(metric=metric,model=model,registered_groups=len(a),FE_mse=a.FE.mean(),model_mse=a[model].mean(),improvement_percent=100*(a.FE.mean()-a[model].mean())/a.FE.mean(),note='explicit original groups; overlapping memberships; descriptive weighting sensitivity only'))
    pd.DataFrame(sums).to_csv(out/'room_group_weighting_sensitivity.csv',index=False)
    return t

def chinese_table(out,d,full,evidence_path):
    uncertainty=pd.read_csv(out/'profile_stability_uncertainty.csv');uncertainty=uncertainty[uncertainty.metric.eq('B8L2')].set_index('worker_id');fs=pd.read_csv(out/'fine_dtype_stability.csv');fs=fs[fs.metric.eq('B8L2')].set_index('worker_id');ev=pd.read_csv(evidence_path);joined=full.merge(ev.drop(columns=[c for c in ['origin']if c in ev]),on='worker_id',validate='one_to_one');joined.to_csv(out/'full_profiles_with_independent_evidence.csv',index=False)
    text_path=Path(evidence_path).parent/'exclusion_text_review_25.csv'
    text_reviews=pd.read_csv(text_path)if text_path.exists()else None
    rows=[]
    for _,r in joined.iterrows():
        u=uncertainty.loc[r.worker_id];st=fs.loc[r.worker_id];x={'人员':r.worker_id,'来源':{'v1':'旧v1','new':'新批报告'}.get(r.origin,r.origin),'库存份数':int(r.inventory),'全条件合格Q份数':int(r.quality_n),'普通Manual图数':int(r.Q_images),'普通Manual建筑数':int(r.Q_buildings),'Q支持充分':bool(r.Q_supported),'B8L2均分':r.absolute_B8L2_mean,'B8L2中位数':r.absolute_B8L2_median,'B8L2低10分位':r.absolute_B8L2_p10,'B8L2标准差':r.absolute_B8L2_sd,'同任务百分位均值':100*r.percentile_B8L2,'任务调整Q效应':r.Q_effect_B8L2,'Q效应区间下界':u.Q_effect_ci_low,'Q效应区间上界':u.Q_effect_ci_high,'Q粗类':ZH[r.Q3_B8L2],'Q二分类':ZH[r.Q2_B8L2],'源时间支持充分':bool(r.T_source_supported),'源时间画像份数':int(r.T_source_n),'源时间画像图数':int(r.T_source_images),'源时间画像建筑数':int(r.T_source_buildings),'源时间中位秒':r.T_source_median,'源时间90分位秒':r.T_source_p90,'源时间相对效应':r.T_source_effect,'同来源内时间效应':r.T_source_origin_effect,'源时间相对三类':ZH[r.T_relative_3],'固定60和180秒类':ZH[r.T_fixed_60_180],'固定90和240秒类':ZH[r.T_fixed_90_240],'同目标时间画像份数':int(r.T_target_n),'同目标时间画像建筑数':int(r.T_target_buildings),'同目标时间支持充分':bool(r.T_target_supported),'难度类型候选':ZH[r.difficulty_type_B8L2],'细类候选':translate(r.fine_dtype_B8L2),'细类留建筑标签一致率':st.fine_dtype_same_fraction}
        for di,zh in [('easy','简单'),('medium','中等'),('hard','困难')]:
            x[zh+'图数']=int(r['images_'+di]);x[zh+'建筑数']=int(r['buildings_'+di]);x[zh+'支持充分']=bool(r['difficulty_supported_'+di]);x[zh+'实际均分']=r[f'absolute_{di}_B8L2_mean'];x[zh+'同任务百分位']=100*r[f'percentile_{di}_B8L2'];x[zh+'调整Q']=r[f'theta_{di}_B8L2']
        x.update({'困难减简单效应':r.hard_minus_easy_B8L2,'困难减简单区间下界':u.hard_minus_easy_ci_low,'困难减简单区间上界':u.hard_minus_easy_ci_high,'困难减中等效应':r.hard_minus_medium_B8L2,'困难减中等区间下界':u.hard_minus_medium_ci_low,'困难减中等区间上界':u.hard_minus_medium_ci_high,'旧Semi强错误机会':int(r.old_confirmed_opportunity_n),'旧Semi强证据错误残留':int(r.old_known_error_unchanged_n),'新Semi报告错误机会':int(r.new_reported_opportunity_n),'新Semi报告未改':int(r.new_reported_error_unchanged_n),'可归因人员Semi增益份数':int(r.worker_attributable_gain_n),'scope相容裁定机会':int(r.scope_compatible_gold_n),'scope相容裁定错误':int(r.scope_incorrect_n),'历史明确个人错误':int(r.legacy_person_error_n),'具体个人错误候选':int(r.specific_person_candidate_n),'不重复不利事件数':int(r.adverse_event_union_n),'个体明确审核覆盖':int(r.explicit_individual_verdict_n)})
        notes=[]
        if text_reviews is not None:
            text_rows=text_reviews[text_reviews.worker_id.eq(r.worker_id)]
            pending=text_rows.independent_text_review_state.eq('scope_context_attribution_pending')
            x['剔除候选独立文本复核记录数']=len(text_rows)
            x['独立文本复核归因待定数']=int(pending.sum())
            x['独立文本复核状态']='；'.join(sorted(text_rows.independent_text_review_state.unique()))if len(text_rows)else'未进入这25份定向文本复核；不代表无错误'
            if pending.any():notes.append('独立文本复核待定1：W001的UwV83HsGsw3-08处于scope/OOS归因待定；保留剔除事实，未确认为个人严重错误')
        else:
            x['剔除候选独立文本复核记录数']=np.nan;x['独立文本复核归因待定数']=np.nan;x['独立文本复核状态']='未提供根文本复核表'
        if not r.Q_supported:notes.append('Q画像证据不足；不可按数值效应判能力')
        if not r.T_source_supported:notes.append('源时间不足，不视作慢')
        if r.difficulty_type_B8L2=='unknown':notes.append('三难度至少一级支持不足，保留连续估计')
        if u.Q_effect_ci_low<=0<=u.Q_effect_ci_high:notes.append('Q正负边界区间跨0')
        if r.T_fixed_60_180!=r.T_fixed_90_240:notes.append('固定时间阈值标签会改变')
        if st.fine_dtype_same_fraction<.8:notes.append('留建筑细类标签一致率低于80%')
        if r.old_confirmed_opportunity_n+r.new_reported_opportunity_n==0:notes.append('无Semi错误机会不等于低风险')
        if r.scope_compatible_gold_n==0:notes.append('无scope相容金标准机会')
        x['边界与缺失说明']='；'.join(notes);rows.append(x)
    pd.DataFrame(rows).to_csv(out/'人员画像与候选细类60人.csv',index=False,encoding='utf-8-sig')
    absent=ev[~ev.worker_id.isin(full.worker_id)].copy();absent['explanation']='当前无质量资格；不可补零或解释为低能力';absent.to_csv(out/'库存中无Q画像人员2人.csv',index=False,encoding='utf-8-sig')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));ap.add_argument('--repo',type=Path,default=Path('repo_main_20261019'));ap.add_argument('--evidence',type=Path,default=Path('work_v2_20261019/audit/person_evidence_62.csv'));a=ap.parse_args();out=a.out;t0=time.time();d=pd.read_csv(out/'records_flat.csv');m=d[d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')];full=pd.read_csv(out/'full_profiles.csv')
    version_sensitivity(a.repo,out,m,full);complexity_time(m,d,full,out);published_comparison(a.repo,out,full);chinese_table(out,d,full,a.evidence)
    js(out/'DIAGNOSTIC_TABLES_RECEIPT.json',dict(completed=True,code_sha256=digest(Path(__file__)),runtime_seconds=time.time()-t0,independent_evidence_sha256=digest(a.evidence),classification_or_selection_rules_modified=False));print('COMPLETE',time.time()-t0)
if __name__=='__main__':main()
