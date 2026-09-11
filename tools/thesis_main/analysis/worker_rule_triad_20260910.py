"""规则执行代理指标与 Semi 修改/时间/参考质量三轴：历史探索。"""
from pathlib import Path
from urllib.parse import urlparse
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.stats import spearmanr

from tools.thesis_main.analysis import validate_worker_reuse_20260909 as reuse
from tools.thesis_main.analysis import worker_reference_feasibility_20260909 as ref
from tools.thesis_main.analysis.explore_semi_subtypes_20260909 import semi_features
from tools.thesis_main.analysis.worker_behavior_time_20260910 import clean_time, adjusted_time_keys
from tools.thesis_main.analysis import worker_behavior_time_20260910 as timing
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import informative, fit_one, predict_peers

ROOT=ref.ROOT
OUT=ROOT/'analysis_results/worker_rule_triad_20260910_v1'
BASE=ref.BASE
SEED=20260910
MODELS={'quality2':(['quality'],2),'edit_quality2':(['edit','quality'],2),
        'time_quality2':(['time','quality'],2),'triad2':(['edit','time','quality'],2),
        'triad3':(['edit','time','quality'],3)}


def fit_axes(data,axes,min_rows=6,min_buildings=3):
    d=data.dropna(subset=axes).copy()
    support=d.groupby('worker_id').agg(rows=('context_key','nunique'),buildings=('building_id','nunique'))
    eligible=support[(support.rows>=min_rows)&(support.buildings>=min_buildings)].index
    d=d[d.worker_id.isin(eligible)]
    if len(eligible)<3:return pd.DataFrame(),'insufficient_workers'
    parts=[]
    for axis in axes:
        p=ref.profiles(d.assign(value=d[axis]))
        if p.empty or p.component.nunique()!=1 or not p.fit_status.eq('usable').all():
            return pd.DataFrame(),'disconnected_or_unidentifiable'
        parts.append(p[['worker_id','effect']].rename(columns={'effect':axis}).set_index('worker_id'))
    p=pd.concat(parts,axis=1,join='inner').join(support).reset_index()
    assert p[axes].notna().all().all()
    return p,'usable'


def cluster_profiles(p,axes,k):
    x=p[axes].to_numpy(float);scale=x.std(axis=0)
    if len(p)<2*k or np.any(scale<1e-10):return np.zeros(len(p),int),'insufficient_or_constant_axis'
    x=(x-x.mean(axis=0))/scale
    labels=cut_tree(linkage(x,method='ward'),n_clusters=k).ravel()+1
    if min(np.bincount(labels)[1:])<2:return np.zeros(len(p),int),'singleton_rejected'
    # Stable identifiers follow the last selected axis; they are not class meanings.
    order=p.assign(label=labels).groupby('label')[axes[-1]].mean().sort_values().index
    remap={label:i+1 for i,label in enumerate(order)}
    return np.array([remap[x] for x in labels]),'usable'


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    reuse.OUT=OUT
    manual,_,qa=reuse.load_measurements()
    manual=manual[~manual.imputed_point].copy()
    manual.to_csv(OUT/'manual.csv.gz',index=False)
    points={r['canonical_annotation_id']:r for r in ref.jsonlines(reuse.VIEW/'calculation_view.jsonl.gz')}
    refs={r['image_id']:r for r in ref.jsonlines(reuse.REFERENCE)}
    old=pd.read_csv(ROOT/'analysis_results/semi_subtype_exploration_20260909_v1/semi_response_features.csv',dtype={'worker_id':str})
    proposal=pd.read_csv(BASE/'facts/proposal_response.csv.gz',dtype={'worker_id':str}).set_index('canonical_annotation_id')
    trace=pd.read_csv(ROOT/'analysis_results/annotation_research_prework_20260905_v2/evidence/initialization_trace.csv',dtype={'worker_id':str}).set_index('canonical_annotation_id')
    imports={}; rows=[]; seen=set()
    for r in old.to_dict('records'):
        aid=r['canonical_annotation_id'];p=points[aid];init=json.loads(proposal.loc[aid,'initial_points_json'])
        assert np.allclose(json.loads(proposal.loc[aid,'final_points_json']),p['raw_points_1024x512'],atol=1e-7,rtol=0)
        for field in ['worker_id','image_id','building_id']:assert str(r[field])==str(p[field])
        for source in json.loads(trace.loc[aid,'initial_import_paths_json']):
            if source not in imports:imports[source]=json.loads((ROOT/source).read_text(encoding='utf-8-sig'))
            key=(source,r['image_id'])
            if key in seen:continue
            candidates=[t for t in imports[source] if t['data'].get('base_task_id')==r['image_id'] or Path(urlparse(t['data']['image']).path).stem==r['image_id']]
            assert len(candidates)==1,key
            candidate_points=[reuse.ordered_points(a['result']) for a in candidates[0].get('predictions',[])]
            assert any(np.shape(z)==np.shape(init) and np.allclose(sorted(z),sorted(init),atol=1e-7,rtol=0) for z in candidate_points),key
            seen.add(key)
        r.update(calculation_included=p['calculation_included'],imputed_point=p['imputed_point'],processing_status=p['processing_status'])
        if p['calculation_included'] and not p['imputed_point']:
            reference=refs[r['image_id']]
            r.update(semi_features(init,p['effective_points_1024x512'],reference['points_1024x512'] if reference['score_allowed'] else None))
        else:
            for key in ['edit_ospa30','edit_ospa60','final_ospa30','final_ospa60']:r[key]=np.nan
        rows.append(r)
    semi=pd.DataFrame(rows)
    t=pd.read_csv(BASE/'facts/active_time_context.csv.gz',dtype={'worker_id':str,'project_id':str,'runtime_task_id':str})
    # Prior turn checked these same stage-specific raw sources for all conditions.
    timing.OUT=OUT
    timing.audit_sources(t)
    semi=semi.merge(t,on='canonical_annotation_id',validate='one_to_one',suffixes=('','_timing'))
    assert semi.worker_id.equals(semi.worker_id_timing) and semi.stage.equals(semi.stage_timing)
    shifted=adjusted_time_keys()
    semi['known_time_shift']=[(p,t,w) in shifted for p,t,w in zip(semi.project_id,semi.runtime_task_id,semi.worker_id)]
    semi['usable_time']=clean_time(semi)&~semi.known_time_shift
    semi['time']=np.where(semi.usable_time,np.log1p(semi.active_time_seconds),np.nan)
    semi.to_csv(OUT/'semi.csv.gz',index=False)
    changed=semi[['canonical_annotation_id','edit_ospa30','final_ospa30']].merge(old[['canonical_annotation_id','edit_ospa30','final_ospa30']],on='canonical_annotation_id',suffixes=('','_old'))
    changed=changed[~np.isclose(changed.edit_ospa30,changed.edit_ospa30_old,equal_nan=True)|~np.isclose(changed.final_ospa30,changed.final_ospa30_old,equal_nan=True)]
    changed.to_csv(OUT/'semi_metric_changes.csv',index=False)
    qa.update(semi_rows=len(semi),initial_import_checks=len(seen),semi_changed_rows=len(changed),semi_usable_time=int(semi.usable_time.sum()))
    (OUT/'SOURCE_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    return manual,semi


def validate_groups(data,axes,models,meta,half_repeats=100):
    full,status=fit_axes(data,axes)
    if status!='usable':raise ValueError((meta,status))
    full_rows=[];fold_rows=[];predictions=[];half_rows=[]
    for model,(features,k) in models.items():
        labels,why=cluster_profiles(full,features,k)
        full_rows.append(full.assign(**meta,model=model,label=labels,status=why))
    for building,test in data.groupby('building_id'):
        train=data[data.building_id!=building]
        p,status=fit_axes(train,axes)
        if status!='usable':raise ValueError((meta,building,status))
        for model,(features,k) in models.items():
            labels,why=cluster_profiles(p,features,k)
            g=p.assign(label=labels,**meta,model=model,status=why,heldout_building=building,
                training_buildings='|'.join(sorted(train.building_id.unique())))
            fold_rows.append(g)
            for axis in axes:
                z=g[['worker_id','label',axis]].rename(columns={axis:'effect'}).copy()
                z['layer_value']=z.groupby('label').effect.transform('mean') if why=='usable' else 0.
                z=z.assign(component='0',fit_status='usable')
                pred=predict_peers(test.assign(value=test[axis]),z)
                predictions.append(pred.assign(**meta,model=model,axis=axis,classification_status=why))
    buildings=np.array(sorted(data.building_id.unique()));rng=np.random.default_rng(SEED)
    for repeat in range(half_repeats):
        left=set(rng.permutation(buildings)[:len(buildings)//2]);a,sa=fit_axes(data[data.building_id.isin(left)],axes);b,sb=fit_axes(data[~data.building_id.isin(left)],axes)
        for model,(features,k) in models.items():
            base=dict(**meta,model=model,repeat=repeat,left_buildings='|'.join(sorted(left)),right_buildings='|'.join(sorted(set(buildings)-left)))
            if sa!='usable' or sb!='usable':half_rows.append(dict(**base,status='unidentifiable',workers=0));continue
            la,wa=cluster_profiles(a,features,k);lb,wb=cluster_profiles(b,features,k)
            z=a.assign(label=la).merge(b.assign(label=lb),on='worker_id',suffixes=('_a','_b'))
            if wa!='usable' or wb!='usable' or len(z)<3:
                half_rows.append(dict(**base,status='unavailable_classification',workers=len(z)));continue
            row=dict(**base,status='usable',workers=len(z),ari=reuse.adjusted_rand(z.label_a,z.label_b))
            for axis in axes:row[axis+'_rho']=float(spearmanr(z[axis+'_a'],z[axis+'_b']).statistic)
            half_rows.append(row)
    return [pd.concat(x,ignore_index=True) if i<3 else pd.DataFrame(x) for i,x in enumerate([full_rows,fold_rows,predictions,half_rows])]


def run():
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'PLAN.json').write_text(json.dumps(dict(seed=SEED,cohorts=['all26','current20'],
        minimum_training_responses=6,minimum_training_buildings=3,minimum_cluster_members=2,
        singleton_rule='reject_classification; zero group prediction with explicit abstention, retain comparison rows',
        rule_execution='Manual reviewed-reference and all-reference; point location/count proxies, not human mental traits',
        triad='same Semi response complete panel; edit(initial,final), log1p(active_seconds), final_reference_deviation',
        models=MODELS,scaling='training-worker mean and population SD per axis; equal standardized axis weights',
        validation='leave whole building out for all features/scaling/clusters/centroids; no selecting k on test',
        half_repeats=100,half_unit='building; same support rules in each half',
        sensitivities=['OSPA60','exclude_synthetic','reviewed_reference_only'],
        provisional_not_natural_classes=True,no_convergence_claim=True),ensure_ascii=False,indent=2),encoding='utf-8')
    manual,semi=prepare()
    groups=[];folds=[];preds=[];halves=[];coarse_scores=[];coarse_profiles=[];coverage=[]
    for cohort in ['all26','current20']:
        m=manual if cohort=='all26' else manual[manual.current20_member]
        s=semi if cohort=='all26' else semi[semi.current20_member]
        for worker,g in s.groupby('worker_id'):
            coverage.append(dict(cohort=cohort,worker_id=worker,semi_rows=len(g),usable_time=int(g.usable_time.sum()),
                complete_triad=int((g.usable_time & g.final_ospa30.notna() & g.edit_ospa30.notna()).sum())))
        for scope,frame in [('all_reference',m[m.reference_allowed]),('reviewed_reference',m[m.reference_allowed&(m.reference_basis=='reviewed_reference')])]:
            for metric in ['ospa30','ospa60','matched_angle','missing_count_rate','extra_count_rate']:
                z=informative(frame.assign(value=frame[metric]))
                p,diag=fit_one(z,SEED);coarse_profiles.append(p.assign(cohort=cohort,scope=scope,metric=metric))
                held,audit=ref.cross_validate(z);sm,_=ref.summarize(held,dict(cohort=cohort,scope=scope,metric=metric));coarse_scores.append(sm)
            z=frame.assign(location=frame.matched_angle,missing=frame.missing_count_rate,extra=frame.extra_count_rate,quality=frame.ospa30)
            models={'quality2':(['quality'],2),'rule_vector2':(['location','missing','extra'],2),'rule_vector3':(['location','missing','extra'],3)}
            results=validate_groups(z,['location','missing','extra','quality'],models,dict(cohort=cohort,experiment='rule',scope=scope,metric='ospa30'))
            for dest,r in zip([groups,folds,preds,halves],results):dest.append(r)
        for scope,metric,z in [('all','ospa30',s),('all','ospa60',s),('without_synthetic','ospa30',s[s.source_group!='trap_synthetic_disjoint_source']),
                              ('reviewed_reference','ospa30',s[s.reference_basis=='reviewed_reference'])]:
            z=z.assign(edit=z['edit_'+metric],quality=z['final_'+metric]).dropna(subset=['edit','time','quality'])
            results=validate_groups(z,['edit','time','quality'],MODELS,dict(cohort=cohort,experiment='triad',scope=scope,metric=metric))
            for dest,r in zip([groups,folds,preds,halves],results):dest.append(r)
            print(json.dumps(dict(cohort=cohort,scope=scope,metric=metric,complete_rows=len(z))),flush=True)
    for name,items in [('members',groups),('fold_members',folds),('predictions',preds),('half_stability',halves)]:
        pd.concat(items,ignore_index=True).to_csv(OUT/(name+('.csv.gz' if name in ['predictions','fold_members'] else '.csv')),index=False)
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False)
    pd.DataFrame(coarse_scores).to_csv(OUT/'coarse_validation.csv',index=False)
    pd.concat(coarse_profiles,ignore_index=True).to_csv(OUT/'coarse_profiles.csv',index=False)
    p=pd.concat(preds,ignore_index=True);summary=[]
    for key,g in p.groupby(['cohort','experiment','scope','metric','model','axis']):
        bm=g.groupby('building_id')[['baseline_sqerr','continuous_sqerr','layer_sqerr']].mean()
        summary.append(dict(zip(['cohort','experiment','scope','metric','model','axis'],key),rows=len(g),workers=g.worker_id.nunique(),
            images=g.image_id.nunique(),buildings=len(bm),abstention_rows=int(g.classification_status.ne('usable').sum()),
            continuous_gain=1-bm.continuous_sqerr.mean()/bm.baseline_sqerr.mean(),group_gain=1-bm.layer_sqerr.mean()/bm.baseline_sqerr.mean()))
    pd.DataFrame(summary).to_csv(OUT/'validation.csv',index=False)


def auxiliary_checks():
    m=pd.read_csv(OUT/'manual.csv.gz',dtype={'worker_id':str})
    s=pd.read_csv(OUT/'semi.csv.gz',dtype={'worker_id':str})
    s=s.assign(edit=s.edit_ospa30,quality=s.final_ospa30).dropna(subset=['edit','time','quality'])
    records=[]
    for cohort in ['all26','current20']:
        a=m[m.reference_allowed];b=s
        if cohort=='current20':a=a[a.current20_member];b=b[b.current20_member]
        for building,test in a.groupby('building_id'):
            p,status=fit_axes(b[b.building_id!=building],['edit','time','quality'])
            if status!='usable':raise ValueError((building,status))
            manual=ref.profiles(a[a.building_id!=building].assign(value=a.ospa30))
            for model,(features,k) in MODELS.items():
                labels,why=cluster_profiles(p,features,k)
                z=p[['worker_id']].assign(label=labels).merge(manual[['worker_id','effect','fit_status','component']],on='worker_id')
                assert z.component.nunique()==1 and z.fit_status.eq('usable').all()
                z['layer_value']=z.groupby('label').effect.transform('mean') if why=='usable' else 0.
                pred=predict_peers(test.assign(value=test.ospa30),z)
                records.append(pred.assign(cohort=cohort,model=model,status=why))
    p=pd.concat(records,ignore_index=True);p.to_csv(OUT/'manual_transfer_predictions.csv.gz',index=False)
    result=[]
    for (cohort,model),g in p.groupby(['cohort','model']):
        bm=g.groupby('building_id')[['baseline_sqerr','layer_sqerr','continuous_sqerr']].mean()
        result.append(dict(cohort=cohort,model=model,rows=len(g),workers=g.worker_id.nunique(),buildings=len(bm),
            group_gain=1-bm.layer_sqerr.mean()/bm.baseline_sqerr.mean(),manual_continuous_gain=1-bm.continuous_sqerr.mean()/bm.baseline_sqerr.mean()))
    pd.DataFrame(result).to_csv(OUT/'manual_transfer.csv',index=False)
    # Descriptive interpretation of the full-data candidate pair, not independent validation.
    rows=[]
    for (worker,source),g in s[s.worker_id.isin(['6','11'])].groupby(['worker_id','source_group']):
        rows.append(dict(worker_id=worker,source_group=source,rows=len(g),unchanged=int(g.edit.abs().lt(1e-8).sum()),
            improved=int(g.gain_ospa30.gt(1e-8).sum()),worsened=int(g.gain_ospa30.lt(-1e-8).sum()),
            median_edit=g.edit.median(),median_seconds=g.active_time_seconds.median(),median_final_deviation=g.quality.median()))
    pd.DataFrame(rows).to_csv(OUT/'candidate_behavior_examples.csv',index=False)
    cases=ref.jsonlines(ROOT/'analysis_results/uncertainty_decision_ready_20260908_v1/semantics/case_evidence.jsonl')
    ledger={r['image_id']:r for r in ref.jsonlines(reuse.REFERENCE)}
    audit=[]
    for c in cases:
        r=ledger[c['image_id']];a=c['original_human_record']['answers'];g=m[m.image_id==c['image_id']]
        audit.append(dict(case_id=c['case_id'],image_id=c['image_id'],human_text=a.get('notes',''),
            supplement_text=(c.get('later_human_supplement') or {}).get('original_text',''),
            reference_basis=r['basis'],reference_allowed=r['score_allowed'],hold_reason=r['hold_reason'],
            manual_responses=len(g),workers=g.worker_id.nunique(),
            audit_note='旧账本gt_inaccurate与原文gt标的最对不一致；本轮无Manual响应，不改变估计' if c['case_id']=='V38' else '保留原文；不生成新的逐人规则违反判决'))
    pd.DataFrame(audit).to_csv(OUT/'human_rule_evidence_audit.csv',index=False)


def report():
    import matplotlib.pyplot as plt
    v=pd.read_csv(OUT/'validation.csv');h=pd.read_csv(OUT/'half_stability.csv')
    members=pd.read_csv(OUT/'members.csv');coverage=pd.read_csv(OUT/'coverage.csv')
    coarse=pd.read_csv(OUT/'coarse_validation.csv');transfer=pd.read_csv(OUT/'manual_transfer.csv')
    primary=members[(members.cohort=='current20')&(members.experiment=='triad')&(members.scope=='all')&
                    (members.metric=='ospa30')&(members.model=='triad3')].copy()
    primary=primary.sort_values(['label','quality'])
    cols=['edit','time','quality'];z=primary[cols].to_numpy();z=(z-z.mean(axis=0))/z.std(axis=0)
    plt.rcParams['font.sans-serif']=['Microsoft YaHei'];plt.rcParams['axes.unicode_minus']=False
    fig,ax=plt.subplots(figsize=(7,8),layout='constrained')
    im=ax.imshow(z,cmap='RdBu_r',vmin=-2.5,vmax=2.5,aspect='auto')
    ax.set_xticks(range(3),['修改幅度\n蓝少／红多','active time\n蓝快／红慢','参考偏差\n蓝低／红高'])
    ax.set_yticks(range(len(primary)),[f'候选{r.label} · W{r.worker_id}' for r in primary.itertuples()])
    ax.set_title('三指标候选三分：9／5／2人\n后续20人中16人有足够完整记录；校正任务后的人员效应')
    for i in range(len(primary)):
        for j in range(3):ax.text(j,i,f'{z[i,j]:+.2f}',ha='center',va='center',fontsize=9,color='white' if abs(z[i,j])>1.7 else 'black')
    fig.colorbar(im,ax=ax,label='人员间标准差单位；仅为候选画像')
    fig.savefig(OUT/'triad_profiles.png',dpi=160);plt.close(fig)
    lines=['# 规则执行粗依据与修改幅度—时间—质量三指标验证','',
        '2026-09-10。**规则执行表现可以继续作为粗依据，但应优先使用有复核来源的参考及连续画像。三指标能形成有行为解释的候选组；目前没有证据表明它稳定优于简单分类，也未证明类内收敛。**','',
        '## 一、两条探索分别回答什么','',
        'A线：纯Manual的参考执行表现能否跨图复现，并形成可用粗类。B线：同一批Semi响应的修改幅度、active time、最终参考质量，能否组成更有解释力、可复现的人员分类。两线都分别检查全部26人和后续20人。','',
        '“修改幅度”明确限定为真实预标注→最终响应的无序球面点集距离。纯Manual没有可比初始轮廓，不填成0修改。时间使用合格日志的log(1+seconds)，不补lead_time。所谓质量是最终响应到可评分参考的OSPA偏差，越低越接近参考，不能直接称为真实正确率、规则合规率或认真程度。','',
        '## 二、数据和可复现规则','',
        '- Manual从最新人工点处理视图及原始导出重新核验，1887条中排除2条补点记录；可评分参考保持复核优先、未决不评分。',
        '- Semi全部574条、43图、26人重新连接真实初始化和最新有效点。68项导入文件×图像匹配通过；W13的一条9→8点人工处理已纳入，1条修改／最终偏差数值更新。另4条未经确认的奇数点仍按当前计算视图保留，不能把点集可算当作建筑结构合法。',
        '- 时间复用并重跑上一轮各阶段原日志审计。排除lead_time回填、覆盖不足、协议偏离和已知人工加秒身份；441条Semi有合格时间，413条同时有修改、时间、可评分参考。后续20人有336条三指标完整响应。',
        '- 分类的训练支持下限固定为至少6条完整响应、至少3个building。全26人实际20人达到三指标支持，后续20人实际16人达到支持。单次留楼后重新检查支持，不能先用全部目标数据决定训练资格。',
        '- 对同一预标注上下文先消除任务截距，估计人员三轴效应；只在训练人员内标准化为等权三个轴，再尝试Ward二分／三分。不用测试楼选择标准化参数、类别数或组均值。',
        '- 对照为只用质量二分、修改＋质量二分、时间＋质量二分、三指标二分／三分，以及保留每个人连续效应。所有模型使用同一完整响应面板、同一批可预测人员。不同距离或初始化范围是敏感性分析，不是随机化干预。',
        '- 每类至少2人；若训练切分产生单人类，明确拒绝该折分类，类别预测退回不区分人员的基线，记录abstention，不把单人类偷偷合并。这个阈值约束人员分类，与单图“至少两人支持标法簇”是两件事。',
        '- 整楼留出检验其他楼上已知人员的相对表现；不是新人预测或绝对秒数预测。另重复100次互斥楼分半，两半完全独立估计效应和分类；ARI不受类别编号置换影响。不可分类的重复计数保留，不当成成功。','',
        '## 三、A线：规则执行作为粗依据','',
        '首先拆分点位匹配偏差、相对参考的点数不足量及点数超出量，不把相对点数不足直接称为已确认漏标。二者无法识别局部多标与漏标相互抵消，匹配距离也不是逐墙拓扑审计。','',
        '以下是连续人员效应的楼等权预测误差改善，正数为优于不区分人员；不是分类准确率：','',
        '| 人群 | 参考范围 | OSPA30综合偏差 | OSPA60综合偏差 | 点位偏差 | 点数不足 | 点数超出 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for cohort in ['all26','current20']:
        for scope in ['all_reference','reviewed_reference']:
            q=coarse[(coarse.cohort==cohort)&(coarse.scope==scope)].set_index('metric')
            vals=[q.loc[x,'building_mse_gain'] for x in ['ospa30','ospa60','matched_angle','missing_count_rate','extra_count_rate']]
            lines.append(f'| {cohort} | {scope} | '+' | '.join(f'{x:+.2%}' for x in vals)+' |')
    lines += ['',
        '后续20人在有复核来源参考上的OSPA预测改善约8.4%／8.8%，高于混合参考的3.3%／约0%。这支持优先整理参考明确的校准图。但它仍是连续差异信号，不足以确认天然高／低执行类型。此处“有复核来源”不等于每图每处边界均已由用户确认无歧义。','',
        '把点位、点数不足、点数超出合并后尝试二分：后续20人在混合参考上为7／13人，在有复核来源参考上为18／2人；后者小组为W34、W37。该二分对综合偏差的留楼预测改善只有2.47%，互斥分半ARI中位数0.155（91/100次能比较）；混合参考分半ARI中位数−0.009。分为三类也没有稳定优势。','',
        '全部人群的多指标Ward经常切出单人异常组，因此被明确拒绝；拒绝时的0收益表示未采用分类，不表示这些人完全没有差异。后续20人没有理由为了凑成均衡比例强行划档。','',
        '在有复核来源参考上，同时查看OSPA30/60的楼级bootstrap区间，当前较低偏差核心候选为W2、W15、W17、W33；较高偏差核心候选为W34、W35、W37。其余人的方向或边界证据较弱。这是全量资料下的保守候选描述，**尚未单独验证这份核心名单的类内收敛或跨图分类稳定性**。W12在OSPA30下较高、OSPA60下未分明，不能为了人数把它强并入高偏差类。','',
        '同时回读50条人工原文：多数是图像、范围、参考或显示顺序层面的判断，尚无覆盖所有工人/图片的逐条“违反哪条规则”标签。V16有明确W37标错的意见，但不能由一图推断永久粗心。还发现旧V38账本的gt_inaccurate与原文“gt标的最对”不一致；该图本轮无Manual响应、未进入此线估计，已在独立审计表指出，未悄悄改写原账本。','',
        '## 四、B线：三指标分类的实际结果','',
        '### 后续20人的同面板比较','',
        '主要结果使用OSPA30、全部初始化；16人、325条可留楼验证响应。336条完整响应与325条验证响应之差来自训练支持及同图可比人员要求，不是按质量高低筛选。','',
        '| 方法 | 修改幅度预测改善 | 时间预测改善 | 最终参考偏差预测改善 |','|---|---:|---:|---:|']
    q=v[(v.cohort=='current20')&(v.experiment=='triad')&(v.scope=='all')&(v.metric=='ospa30')]
    names={'quality2':'只用质量二分','edit_quality2':'修改＋质量二分','time_quality2':'时间＋质量二分','triad2':'三指标二分','triad3':'三指标三分'}
    for model,name in names.items():
        a=q[q.model==model].set_index('axis')
        lines.append('| '+name+' | '+' | '.join(f'{a.loc[x,"group_gain"]:+.2%}' for x in cols)+' |')
    a=q[q.model=='triad2'].set_index('axis')
    lines.append('| 保留人员连续三轴 | '+' | '.join(f'{a.loc[x,"continuous_gain"]:+.2%}' for x in cols)+' |')
    lines += ['',
        '三指标二分与“修改＋质量二分”在主要验证中的逐响应预测完全相同，加入时间没有形成额外收益。三指标三分改善了时间预测，但参考偏差预测稍差；不能把三个不同单位的收益随意相加，宣称总体更好。全部人群实际20人的三指标二分对修改／时间／参考偏差分别改善15.66%／28.93%／7.78%，连续画像分别为22.67%／62.88%／14.44%。','',
        '### 候选成员及其含义','',
        '- 后续20人的三指标二分为14／2人，小组是W6、W11。描述宜为“较强保留预标注倾向，当前完整面板上耗时较短、最终参考偏差较高”；不能叫“粗心”，也不意味着另外14人都是准确修正者。',
        '- 三分为9／5／2人。它把其余人再拆分，组内速度与质量仍有明显差异。全26人的可用20人分别得到16／4及6／10／4，并非所有26人已被成功分类。','',
        '| 三指标三分候选组 | 后续20人中的实际成员 |','|---|---|']
    for label,g in primary.groupby('label'):
        lines.append(f'| {label} | '+ '、'.join('W'+str(w) for w in sorted(g.worker_id))+' |')
    lines += ['', '![人员三轴候选画像](triad_profiles.png)','',
        '颜色是当前16名可用人员内标准化的任务校正效应，红色分别表示多改、较慢、偏差较高，三列不共享“好坏”方向。灰缺失未补入图片；W12、W31、W34、W35保留在覆盖表。','',
        '解释小组时补看原始行为：在本次完整面板中，W11有20/21条几何未改，W6有17/21条未改。自然trap子集各6图，W11的6条均未改、没有参考偏差改善；W6有4条未改、2条改善。自然control和部分C1初始化本来很接近参考，保留也可能合理。这里的改善是点集参考距离减少，不是新的人工正确性裁决。以上是候选组形成后的描述性核对，不冒充独立验证。','',
        '### 分类稳定性与敏感性','',
        '| 人群/范围 | 距离 | 分组 | 可比较重复/100 | 分半ARI中位数 |','|---|---|---|---:|---:|']
    hh=h[(h.experiment=='triad')&h.model.isin(['triad2','triad3'])]
    for key,g in hh.groupby(['cohort','scope','metric','model']):
        if key[0]=='all26' and key[1]!='all':continue
        lines.append('| '+' | '.join(key)+f' | {g.ari.notna().sum()} | {g.ari.median():.3f} |')
    lines += ['',
        '全部人群的OSPA30二分具有一定复现性（ARI中位数0.592，87次可比较）；后续20人只有0.107，三分0.200。换成OSPA60时后续20人提高至0.461／0.526，但可比较次数为81／71，说明结论依赖距离定义和样本支持。不能只挑最有利的一种。','',
        '去掉合成初始化后，后续20人的三指标二分变成5／11人，分半ARI中位数约0.005（63次可比较），对最终参考偏差的预测改善为−8.88%；三分为−9.47%。仅有复核来源参考时二分的ARI中位数虽为0.461，但仅29次可比较，另外71次没有满足分组比较要求，不能报告成稳定成功。','',
        '因此，这条线支持保留具体的修改行为候选；尚不支持在任何初始化上套用同一组人员类型。初始参考偏差与最终参考偏差的差值是改善量，同图初始化固定时它与最终偏差仅差常数，不能再作为第四个独立质量轴。','',
        '## 五、能否连接回Manual规则执行与类内收敛','',
        '额外检验：只在目标楼之外用Semi三指标分组，再用训练Manual估计组均值，预测留出楼Manual偏差。后续20人实际16人的二分／三分改善仅0.34%／3.48%，小于同面板Manual连续人员效应的7.63%；全部人群实际20人的二分／三分均为负。Semi行为类型不能直接当作Manual能力类型。','',
        '人数上，W6/W11两人组无法研究从k=2开始再增加若干人后的稳定阶段。三分中的5人组按此前保留5名未来支持者的规则也没有合法起点。14人组虽然有更长的有限池观察窗口，但其分类本身尚未充分复现，不能先看目标图是否收敛再挑组。','',
        '建议继续以“规则执行表现”为粗依据，先把独立可评分校准图和逐条执行问题证据整理扎实；三指标作为Semi条件下的连续行为画像及候选类型补充。近期最具体的可验证行为是“是否保留明确有偏差的初始化、是否修正”，比直接命名认真／粗心更贴近现有证据。后续采集不必为A、AB、AAB分别重做，但人员分类校准与目标图必须分开。','',
        '## 六、完整覆盖','', '| 人群 | 人员 | Semi记录 | 合格时间 | 三指标完整记录 |','|---|---|---:|---:|---:|']
    for r in coverage.sort_values(['cohort','worker_id']).itertuples():
        lines.append(f'| {r.cohort} | W{r.worker_id} | {r.semi_rows} | {r.usable_time} | {r.complete_triad} |')
    lines += ['',
        '后续20人中W12／W31／W35分别只有3／4／3条完整记录，W34为0；这些人有其他质量或修改证据，不表示无能力或不认真。若后续沿用三指标探索，应优先补共同校准图的合格时间和真实初始—最终记录；最低6条/3楼只是本轮可估计门槛，并非充分样本量保证。','',
        '## 七、复现、字段和验证边界','',
        '运行：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.worker_rule_triad_20260910`。','',
        '- `manual.csv.gz`、`semi.csv.gz`：逐响应计算输入副本，原始来源、人工处理、参考状态和时间状态仍保留；不是原始数据真源。`semi_metric_changes.csv`记录旧→最新计算差异。',
        '- `members.csv`：cohort×experiment×scope×metric×model×worker；label=0表示分类拒绝，不能当作一个正常类型。rows/buildings为训练支持；各轴值为校正任务后的人员效应。',
        '- `fold_members.csv.gz`：另有heldout_building、training_buildings与status，保存每折训练归类。`predictions.csv.gz`的axis是评估目标，target是同图中心化结果；baseline/continuous/layer_sqerr为三个对照误差。',
        '- `validation.csv`：按楼等权MSE计算continuous_gain和group_gain，abstention_rows是分类拒绝但仍计入相同评估面板的行数。不同scope的响应集合变化，不作因果比较。',
        '- `half_stability.csv`：两半楼清单、状态、共有人员、ARI；不可比较时ARI为空，不能填0或删除后不报告分母。',
        '- `coarse_profiles.csv`、`coarse_validation.csv`：参考执行各代理轴的500次楼级bootstrap区间、支持和留楼验证；个别清楚的区间不等于完整分类稳定。',
        '- `manual_transfer.csv`及其逐响应文件：Semi分型到Manual表现的独立楼迁移；`candidate_behavior_examples.csv`是候选人员的描述性解释，不是另一套训练外结果。',
        '- `SOURCE_QA.json`和`SOURCE_AUDIT.json`：原始标注、真实初始化、参考坐标、原日志重放检查；`human_rule_evidence_audit.csv`是既有人工原文的只读整理，不新增逐人错误判决。',
        '- `PLAN.json`记录门槛、标准化、模型与留出规则；本次是多配置探索，没有做显著性主张、因果主张、新人外推或类内收敛证明。测试及输出核验见`VERIFICATION.json`。',
        '', '所有改动局限于探索脚本、测试、结果与索引；原始导出、日志、正式人员资格、三轴合同、派发和路由未改。']
    (OUT/'README_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    run()
    auxiliary_checks()
    report()
