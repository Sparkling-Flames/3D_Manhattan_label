"""Coverage, counterexamples and auxiliary evidence for the fixed-rule worker analysis."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis import fit_worker_evidence_strata_20260908 as m


def full_effects(d):
    """Unclassified auxiliary effects, keeping independent graph components separate."""
    d=m.informative(d);rows=[]
    for number,c in enumerate(m.worker_task_components(d.assign(base_task_id=d.context_key).to_dict('records'))):
        sub=d[d.worker_id.isin(c['workers'])];s=m.sufficient(sub);beta,status,_=m.solve(s,np.ones(len(s['buildings'])))
        if beta is not None:
            rows.extend(dict(worker_id=w,effect=float(b),component=str(number),fit_status=status,
                             rows=int((sub.worker_id==w).sum()),buildings=sub[sub.worker_id==w].building_id.nunique())
                        for w,b in zip(s['workers'],beta))
    return pd.DataFrame(rows)


def paired_effects(a,b):
    """Compare only common workers, centered again within each component intersection."""
    z=a[['worker_id','effect','component']].merge(b[['worker_id','effect','component']],on='worker_id',suffixes=('_a','_b'),validate='one_to_one')
    keys=['component_a','component_b'];z=z[z.groupby(keys).worker_id.transform('size')>=2].copy()
    for side in ['a','b']:z['centered_'+side]=z['effect_'+side]-z.groupby(keys)['effect_'+side].transform('mean')
    return z


def verify_delivery(out):
    index=pd.read_csv(out/'inputs/canonical_index.csv.gz');evidence=pd.read_csv(out/'worker_evidence_26.csv')
    assert len(index)==2501 and index.canonical_annotation_id.is_unique and len(evidence)==26
    assert set(index.worker_id)==set(evidence.worker_id) and evidence.canonical_rows.sum()==2501
    profiles=pd.read_csv(out/'worker_profiles_all_folds.csv.gz');fits=profiles.drop_duplicates('fit_id').set_index('fit_id')
    counts={k:0 for k in fits.index};valid=counts.copy();statuses={}
    with gzip.open(out/'bootstrap_diagnostics.csv.gz','rt',encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            key=row['fit_id'];weights=json.loads(row['building_counts_json']);buildings=json.loads(fits.loc[key,'training_buildings'])
            assert int(row['replicate'])==counts[key] and len(weights)==len(buildings) and sum(weights)==len(buildings)
            counts[key]+=1;valid[key]+=int(row['status']=='usable');statuses[row['status']]=statuses.get(row['status'],0)+1
    assert set(counts.values())=={500}
    assert all(valid[k]==fits.loc[k,'bootstrap_valid'] for k in fits.index)
    assert all(r.fold=='full' or str(r.fold) not in json.loads(r.training_buildings) for r in fits.itertuples())
    coverage=pd.read_csv(out/'worker_stage_metric_evidence.csv')
    assert (coverage.groupby(m.KEY).worker_id.nunique()==26).all()
    pred=pd.read_csv(out/'heldout_predictions.csv.gz');summary,_=m.evaluate_tables(pred)
    stored=pd.read_csv(out/'validation_summary.csv');cols=['evaluation',*m.KEY]
    a=summary.set_index(cols).sort_index();b=stored.set_index(cols).sort_index()
    assert a.index.equals(b.index) and (a.decision==b.decision).all()
    for col in [c for c in a if c.endswith('_r2')]:assert np.allclose(a[col],b[col],equal_nan=True)
    groups=['evaluation',*m.KEY,'context_key','component','heldout_building']
    assert np.allclose(pred.groupby(groups)[['target','continuous_prediction','layer_prediction']].mean(),0,atol=1e-10)
    assert (pred.building_id==pred.heldout_building).all()
    result=dict(canonical=2501,workers=26,fit_count=len(fits),draw_count=sum(counts.values()),draw_status=statuses,
                profile_rows=len(profiles),validation_rows=len(stored),heldout_rows=len(pred),coverage_rows=len(coverage),checks='passed')
    (out/'DELIVERY_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='FILE_LIST.json']
    (out/'FILE_LIST.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result))


def summarize(out=m.OUT):
    read=lambda name:pd.read_csv(out/name,dtype={'worker_id':str,'block_index':str,'component':str})
    metrics=read('inputs/worker_metrics.csv.gz');index=read('inputs/canonical_index.csv.gz')
    history=read('inputs/response_history_flags.csv')
    data=m.analysis_cohorts(metrics,history);full=read('worker_strata_results.csv')
    pred=read('heldout_predictions.csv.gz');profiles=read('worker_profiles_all_folds.csv.gz')
    workers=sorted(index.worker_id.unique(),key=int)
    # Every worker has a row even for absent stages, unusable geometry or excluded cohorts.
    oos=metrics[metrics.raw_condition=='oos'].assign(cohort='available')
    coverage=[]
    for key,g in pd.concat([data,oos]).groupby(m.KEY):
        usable=m.informative(g);lookup=full
        for col,value in zip(m.KEY,key):lookup=lookup[lookup[col]==value]
        for w in workers:
            raw=g[g.worker_id==w];valid=raw[np.isfinite(raw.value)];info=usable[usable.worker_id==w]
            p=lookup[lookup.worker_id==w]
            total=index[(index.worker_id==w)&(index.stage==key[0])&(index.raw_condition==key[1])]
            reason=('no_stage_data' if total.empty else 'outside_manual_semi_scope' if key[1]=='oos' else
                    'excluded_by_sensitivity' if raw.empty else 'no_computable_metric' if valid.empty else
                    'no_multiworker_context' if info.empty else 'component_relative_only' if lookup.component.nunique()>1 else 'identifiable')
            r=dict(zip(m.KEY,key));r.update(worker_id=w,stage_total=len(total),cohort_rows=len(raw),
                finite_rows=len(valid),informative_rows=len(info),informative_buildings=info.building_id.nunique(),
                missing_status_counts=json.dumps(raw.loc[~np.isfinite(raw.value),'status'].value_counts().to_dict()),coverage_status=reason)
            if len(p):r.update(p.iloc[0][['effect','lower','upper','label','bootstrap_valid_fraction','component','decision']].to_dict())
            else:r.update(label=reason,decision='not_evaluable')
            coverage.append(r)
    coverage=pd.DataFrame(coverage);coverage.to_csv(out/'worker_stage_metric_evidence.csv',index=False)
    membership=[]
    for key,g in coverage.groupby(m.KEY):
        row=dict(zip(m.KEY,key));row['decision']=next((x for x in g.decision if x!='not_evaluable'),'not_evaluable')
        for label in ['high','low','uncertain','insufficient']:
            row[label+'_workers']=','.join('W'+w for w in sorted(g.loc[g.label==label,'worker_id'],key=int))
        row['unscored_workers']=','.join('W'+w for w in sorted(g.loc[~g.label.isin(['high','low','uncertain','insufficient']),'worker_id'],key=int))
        row['member_label_scope']='full_sample_interval_candidates; use only if axis retained in this condition'
        row['delivery_status']=('no_full_sample_members' if not g.label.isin(['high','low']).any() else
                                'conditional_strata' if row['decision']=='retain_strata' else 'axis_not_retained')
        membership.append(row)
    pd.DataFrame(membership).to_csv(out/'strata_membership_summary.csv',index=False)

    # Bi residuals stay visible beside head preference; neither small delta nor its sign means correctness.
    bi=metrics[(metrics.metric=='bi_delta')&np.isfinite(metrics.value)]
    bi.groupby(['worker_id','stage','raw_condition','reading','representation']).agg(
        rows=('value','size'),mean_delta=('value','mean'),median_delta=('value','median'),
        mean_distance_enclosed=('d_enclosed','mean'),mean_distance_extended=('d_extended','mean'),
        mean_head_gap=('d_bi','mean'),median_head_gap=('d_bi','median'),
        mean_minimum_residual=('minimum_residual','mean'),median_minimum_residual=('minimum_residual','median'),
        maximum_minimum_residual=('minimum_residual','max')).reset_index().to_csv(out/'worker_bi_residuals.csv',index=False)
    main_bi=bi[(bi.stage=='C1')&(bi.raw_condition=='manual')&(bi.representation=='native_uv')].copy()
    main_bi['abs_delta']=main_bi.value.abs()
    examples=[]
    for reading,g in main_bi.groupby('reading'):
        for selection,col in [('largest_absolute_head_delta','abs_delta'),('largest_both_head_residual','minimum_residual')]:
            examples.append(g.sort_values([col,'canonical_annotation_id'],ascending=[False,True]).head(10).assign(selection=selection))
    pd.concat(examples).to_csv(out/'bi_counterexample_candidates.csv',index=False)

    # Raw quantities are descriptive; task-adjusted reference and time are kept as separate axes.
    ref=read('inputs/reference_measurement.csv.gz');time=read('inputs/active_time_context.csv.gz')
    q=ref[(ref.stage=='C1')&(ref.raw_condition=='manual')&(ref.measurement_role=='worker_final')&
          (ref.metric_name=='c1_iou_to_gt')&(ref.measurement_status=='available')&
          (ref.reference_dispute_status!='source_researcher_confirmed_bad_gt')].copy()
    q['value']=q.measurement_value
    t=time[(time.stage=='C1')&(time.raw_condition=='manual')&time.active_time_formal_available&
           (time.active_time_seconds>0)].copy();t['value']=np.log(t.active_time_seconds)
    aux=[]
    for name,d in [('c1_iou_to_gt_unknown_adjudication',q),('log_active_seconds_strict',t[t.timing_status=='eligible']),('log_active_seconds_formal_including_flagged',t)]:
        p=full_effects(d);p['auxiliary_metric']=name;aux.append(p)
    aux=pd.concat(aux,ignore_index=True);aux.to_csv(out/'auxiliary_adjusted_effects.csv',index=False)
    main=full[(full.stage=='C1')&(full.raw_condition=='manual')&(full.cohort=='available')&
              ~full.representation.isin(['legacy_integer','pixel_center_integer'])]
    correlations=[]
    for key,g in main.groupby(['metric','reading','representation']):
        for name,h in aux.groupby('auxiliary_metric'):
            z=paired_effects(g,h)
            for components,v in z.groupby(['component_a','component_b']):
                correlations.append(dict(zip(['metric','reading','representation'],key))|dict(auxiliary_metric=name,
                    components=json.dumps(components),workers=len(v),spearman=v.centered_a.rank().corr(v.centered_b.rank()),
                    purpose='descriptive_not_independent_validation'))
    z=paired_effects(aux[aux.auxiliary_metric=='c1_iou_to_gt_unknown_adjudication'],aux[aux.auxiliary_metric=='log_active_seconds_strict'])
    correlations.append(dict(metric='c1_iou_to_gt_unknown_adjudication',reading='source_reference',representation='source_metric',
        auxiliary_metric='log_active_seconds_strict',components='component_intersection',workers=len(z),
        spearman=z.centered_a.rank().corr(z.centered_b.rank()),purpose='descriptive_not_independent_validation'))
    pd.DataFrame(correlations).to_csv(out/'auxiliary_axis_associations.csv',index=False)
    proposals=read('inputs/proposal_response.csv.gz')
    semi=pred[(pred.raw_condition=='semi')&(pred.cohort=='available')&~pred.representation.isin(['legacy_integer','pixel_center_integer'])].merge(
        proposals[['canonical_annotation_id','initialization_source_kind']],on='canonical_annotation_id',validate='many_to_one')
    source_scores=[]
    for source,g in semi.groupby('initialization_source_kind'):
        score,_=m.evaluate_tables(g);score['initialization_source_kind']=source;source_scores.append(score)
    pd.concat(source_scores).to_csv(out/'semi_validation_by_initialization.csv',index=False)
    # Full-stage coefficients are only descriptive after a common-reference recentering.
    cross=[]
    for key,g in main.groupby(['metric','reading','representation']):
        h=full[(full.metric==key[0])&(full.reading==key[1])&(full.representation==key[2])&(full.cohort=='available')]
        for (stage,condition),target in h.groupby(['stage','raw_condition']):
            if (stage,condition)==('C1','manual'):continue
            z=paired_effects(g,target)
            for k,v in zip(['metric','reading','representation'],key):z[k]=v
            z['target_stage']=stage;z['target_condition']=condition;cross.append(z)
    pd.concat(cross,ignore_index=True).to_csv(out/'cross_stage_common_reference_effects.csv',index=False)

    # Leave-one-image influence is a descriptive diagnostic, never used to select classes.
    influence=[]
    for key,g in data[(data.stage=='C1')&(data.raw_condition=='manual')&(data.cohort=='available')&
                      ~data.representation.isin(['legacy_integer','pixel_center_integer'])].groupby(m.KEY):
        d=m.informative(g);base=full_effects(d)
        for image_id in sorted(d.image_id.unique()):
            p=full_effects(d[d.image_id!=image_id]);z=paired_effects(base,p)
            # Refuse to compare if deletion changed the original reference roster/components.
            same=(set(base.worker_id)==set(p.worker_id) and base.component.nunique()==p.component.nunique()==1)
            for row in z.to_dict('records'):
                influence.append(dict(zip(m.KEY,key))|dict(worker_id=row['worker_id'],removed_image=image_id,
                    fixed_reference=same,full_effect=row['centered_a'] if same else np.nan,
                    deleted_effect=row['centered_b'] if same else np.nan))
    pd.DataFrame(influence).to_csv(out/'leave_one_image_influence.csv.gz',index=False)
    # Building contribution diagnostic deletes only held-out score rows; it does not rerun selection.
    diagnostics=[]
    selected=pred[(pred.evaluation=='within_stage_lobo')&(pred.stage=='C1')&(pred.raw_condition=='manual')&
                  (pred.cohort=='available')&~pred.representation.isin(['legacy_integer','pixel_center_integer'])]
    for key,g in selected.groupby(m.KEY):
        for b in sorted(g.building_id.unique()):
            s,_=m.evaluate_tables(g[g.building_id!=b]);r=s.iloc[0].to_dict();r['omitted_score_building']=b;diagnostics.append(r)
    pd.DataFrame(diagnostics).to_csv(out/'leave_one_building_score_influence.csv',index=False)
    # Full 26-person entry: available-stage coverage, main estimates, auxiliary values and limitations.
    evidence=read('worker_evidence_26.csv')
    for (stage,condition),g in read('inputs/worker_stage_condition_coverage.csv').groupby(['stage','raw_condition']):
        prefix=stage+'_'+condition+'__';cols=['worker_id','canonical_responses','contexts','buildings']
        new=g[cols].rename(columns={c:prefix+c for c in cols if c!='worker_id'})
        evidence=evidence.drop(columns=[c for c in new if c!='worker_id' and c in evidence],errors='ignore').merge(new,on='worker_id',validate='one_to_one')
    for name,g in aux.groupby('auxiliary_metric'):
        col=name+'__effect';evidence=evidence.drop(columns=[col],errors='ignore').merge(g[['worker_id','effect']].rename(columns={'effect':col}),on='worker_id',how='left',validate='one_to_one')
    evidence['limitation']='仅阶段/条件内相对倾向；不代表质量、人格或enclosed/extended语义；面积读取敏感；Bi分层未通过C1验证'
    evidence.loc[evidence.C1_manual__canonical_responses==0,'limitation']='无C1数据，不借P1成绩补分；其他阶段见逐阶段表'
    for col in [c for c in evidence if c.endswith('__label')]:evidence[col]=evidence[col].fillna('no_C1_identifiable_data')
    fold_counts=profiles[(profiles.stage=='C1')&(profiles.raw_condition=='manual')&(profiles.metric=='corner_pair_count')&
                         (profiles.cohort=='available')&(profiles.fold!='full')].groupby(['worker_id','label']).size().unstack(fill_value=0)
    for label in ['high','low','uncertain','insufficient']:
        col='C1_corner_training_folds__'+label
        evidence[col]=evidence.worker_id.map(fold_counts[label] if label in fold_counts else pd.Series(dtype=float)).fillna(0).astype(int)
    evidence.to_csv(out/'worker_evidence_26.csv',index=False)
    text=['# 26人工人证据表','',
          '全部2501份canonical均保留。下表的分层仅指C1 Manual原始角点数量；95%区间为500次building重采样的探索性区间。偏多/偏少不等于正确/错误。其他轴、缺失原因与辅助证据见[完整逐阶段证据](worker_stage_metric_evidence.csv)和[辅助证据](inputs/auxiliary_worker_summary.csv)。','',
          '| 人员 | 当前20人 | P1 Manual | C1 Manual | C1可用building | 调整后角点对差异 [95%区间] | 暂定证据 | 13折训练中同向分层次数 | Semi P1/C1 | C2 B/RP |',
          '|---|---|---:|---:|---:|---|---|---:|---|---|']
    base='corner_pair_count__raw_point_count__not_applicable__'
    labels={'high':'角点数量偏多','low':'角点数量偏少','uncertain':'区间跨零，证据不足','no_C1_identifiable_data':'无C1数据'}
    for row in evidence.to_dict('records'):
        label=row[base+'label'];interval=(f"{row[base+'effect']:+.3f} [{row[base+'lower']:+.3f}, {row[base+'upper']:+.3f}]" if np.isfinite(row[base+'effect']) else '—')
        count=row.get('C1_corner_training_folds__'+label,0) if label in ['high','low'] else '—'
        text.append(f"| W{row['worker_id']} | {'是' if row['current20_member'] else '否'} | {row['P1_manual__canonical_responses']} | {row['C1_manual__canonical_responses']} | {int(row[base+'informative_buildings']) if np.isfinite(row[base+'informative_buildings']) else '—'} | {interval} | {labels.get(label,label)} | {count} | {row['P1_semi__canonical_responses']}/{row['C1_semi__canonical_responses']} | {row['C2-B_manual__canonical_responses']}/{row['C2-A-RP_manual__canonical_responses']} |")
    text+=['','“同向分层次数”是13次不同训练集下的诊断，不是属于某类的概率，也不用于另设准入门槛。跨阶段未普遍复现，因此所有名称保留阶段与条件限定。']
    (out/'26人工人证据表.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    # A single exportable scientific figure; no new dashboard or rendering framework.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    corner=main[main.metric=='corner_pair_count'].sort_values('effect')
    fig,ax=plt.subplots(figsize=(7,8));colors={'high':'#ab4b28','low':'#246b97','uncertain':'#888888'}
    for y,row in enumerate(corner.to_dict('records')):
        ax.errorbar(row['effect'],y,xerr=[[row['effect']-row['lower']],[row['upper']-row['effect']]],fmt='o',color=colors[row['label']],capsize=3)
    ax.set_yticks(range(len(corner)),['W'+w for w in corner.worker_id]);ax.axvline(0,color='black',linewidth=.8)
    ax.set(xlabel='Task-adjusted exported corner-pair count difference',title='C1 Manual: 23 observed workers, 500 building bootstrap draws')
    ax.grid(axis='x',alpha=.2);fig.tight_layout();fig.savefig(out/'C1_corner_intervals.png',dpi=170);plt.close(fig)
    qa=dict(canonical_rows=len(index),workers=len(evidence),complete_evidence_rows=len(coverage),
            auxiliary_adjusted_rows=len(aux),image_influence_rows=len(influence),raw_annotations_changed=False,
            historical_flags_exclude_outcomes=False,auxiliary_inference='descriptive_only_no_new_classification',
            single_image_influence='full_estimate_diagnostic_not_reclassification',
            building_score_influence='omit_scored_building_only_not_new_training_validation')
    (out/'SUMMARY_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=m.OUT);parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    if args.verify_only:verify_delivery(args.out)
    else:summarize(args.out)
