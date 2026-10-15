"""同房共同人员模式与楼外Q/T候选类型；沿用931条画像，不拟合新类型。"""
import argparse
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from .same_room_quality_curves_20261015 import (
    ROOT, QUALITY, METRICS, read, save, exact_curve, curve_distance, control_curve_distance,
)
from .same_room_similarity_20261003 import correlation

OUT = ROOT/'research/same_room_personnel_patterns_20261015'
PREVIOUS = ROOT/'research/same_room_quality_curves_20261015'
PERSONNEL = ROOT/'research/worker_four_axis_update_20261015'
TIME = ROOT/'research/worker_classification_progress_20261014'


def check_fold(rows, building):
    for row in rows.itertuples():
        if building in json.loads(row.training_buildings):
            raise ValueError('target building appears in training')


def person_pattern(source, target, ability):
    if set(source.index) != set(target.index) or not source.index.is_unique or not target.index.is_unique:
        raise ValueError('identical workers required')
    source, target = source.sort_index(), target.sort_index()
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError('nonfinite observed quality')
    a, b = source-source.mean(), target-target.mean()
    fitted = ability.reindex(source.index)
    supported = bool(np.isfinite(fitted).all())
    fitted = fitted-fitted.mean()
    return dict(n_workers=len(source), mean_gap=float(abs(source.mean()-target.mean())),
        raw_spearman=correlation(source.to_numpy(), target.to_numpy()),
        centered_rmse=float(np.sqrt(np.mean((a-b)**2))),
        general_ability_supported=supported,
        general_ability_rmse_target=float(np.sqrt(np.mean((b-fitted)**2))) if supported else None,
        residual_spearman=correlation((a-fitted).to_numpy(), (b-fitted).to_numpy()) if supported else None)


def split_types(profiles, workers):
    p = profiles[profiles.worker_id.isin(workers) & profiles.supported].set_index('worker_id')
    if not p.index.is_unique:
        raise ValueError('duplicate profile worker')
    positive = sorted(p.index[p.effect.gt(0)])
    negative = sorted(p.index[p.effect.lt(0)])
    return dict(positive=positive, negative=negative,
        unclassified=sorted(set(workers)-set(positive)-set(negative)),
        positive_usable=len(positive)>=2, negative_usable=len(negative)>=2,
        usable=len(positive)>=2 and len(negative)>=2)


def type_gap(values, groups):
    return float(values.loc[groups['positive']].mean()-values.loc[groups['negative']].mean())


def main(out=OUT):
    out=Path(out); out.mkdir(parents=True, exist_ok=True)
    bundle=load_current_bundle()
    with zipfile.ZipFile(QUALITY/'pro_closeout_delta.zip') as archive:
        assert bundle['data']==json.loads(archive.read('source/historical_current_formal_loader_data.json')), 'quality source version drift'
    inventory=pd.read_csv(PREVIOUS/'quality_inventory_1145.csv')
    primary=inventory[inventory.use_panel.eq('ordinary_same_target_conditional')].copy()
    training=pd.read_csv(PERSONNEL/'quality_panel_931.csv')
    assert len(training)==931 and not training.new_scope_binding_pending.any()
    common=inventory.set_index('record_id').loc[training.record_id]
    assert list(common.reference_id)==list(training.reference_id)
    assert np.allclose(common[METRICS],training[METRICS],atol=1e-10,rtol=0)
    assert set(primary.record_id)==set(training[training.use_panel.eq('ordinary_same_target_conditional')].record_id)
    objects={o['object_id']:o for o in bundle['data']['objects']}
    for row in primary.itertuples():
        obj=objects[row.object_id]
        assert (obj['image_id'],obj['worker_id'],obj['condition'])==(row.image_id,row.worker_id,row.condition)
        assert obj['independent_vote_eligible']
    profiles=pd.read_csv(PERSONNEL/'fold_profiles.csv')
    time=pd.read_csv(TIME/'time_assignments.csv')
    tasks=read(PREVIOUS/'transfer_tasks.json')
    buildings=sorted({t['building'] for t in tasks})
    profiles=profiles[profiles.fold.isin(buildings)].copy()
    time=time[time.fold.isin(buildings)].copy()
    for building in buildings:
        check_fold(profiles[profiles.fold.eq(building)],building)
        check_fold(time[time.fold.eq(building)],building)
    save(out,'source_quality_profiles.csv',profiles)
    save(out,'source_time_profiles.csv',time)
    selected=pd.concat([profiles[profiles.axis.eq('WQ')].assign(type_axis='Q'),time.assign(type_axis='T')],ignore_index=True)
    save(out,'source_type_profiles.csv',selected)
    images={i:g.set_index('worker_id') for i,g in primary.groupby('image_id')}
    def values(image,workers,metric):
        return images[image].loc[list(workers),metric]
    def effects(building,workers,metric):
        p=profiles[profiles.fold.eq(building)&profiles.axis.eq(metric)&profiles.supported]
        return p.set_index('worker_id').effect.reindex(workers)
    pairs=pd.read_csv(PREVIOUS/'quality_pairs.csv')
    pairs=pairs[pairs.layer.eq('ordinary_same_target_conditional') & pairs.metric.eq('WQ') & pairs.n_common.ge(4)
                & pairs.relation.isin(['confirmed_comparable','supported_other'])]
    pattern_rows=[]
    for row in pairs.itertuples():
        workers=row.workers.split('|')
        for metric in METRICS:
            result=person_pattern(values(row.image_a,workers,metric),values(row.image_b,workers,metric),effects(row.building,workers,metric))
            pattern_rows.append(dict(code_a=row.code_a,code_b=row.code_b,building=row.building,
                candidate_ids=row.candidate_ids,relation=row.relation,metric=metric,workers=row.workers,**result))
    save(out,'person_patterns.csv',pd.DataFrame(pattern_rows))
    coverage=[];type_rows=[];transfer=[];single_rows=[]
    frozen={(i['image_id'],tuple(i['workers'])):i for i in read(PREVIOUS/'current_common_worker_inputs.json')}
    curve_cache={}; curve_data=[];curve_comparisons=[];curve_k=[]
    for task in tasks:
        workers=task['workers'];building=task['building'];target=task['target'];source=task['source'];controls=task['controls']
        base=dict(task_id=task['task_id'],candidate_id=task['candidate_id'],building=building,
            target_code=task['target_code'],source_code=task['source_code'])
        for metric in METRICS:
            ability=effects(building,workers,metric)
            observed=person_pattern(values(source,workers,metric),values(target,workers,metric),ability)
            other=[person_pattern(values(c,workers,metric),values(target,workers,metric),ability) for c in controls]
            baseline_error=float(np.mean([r['centered_rmse'] for r in other])) if other else None
            control_rho=[r['raw_spearman'] for r in other if r['raw_spearman'] is not None]
            control_residual=[r['residual_spearman'] for r in other if r['residual_spearman'] is not None]
            transfer.append(dict(**base,metric=metric,n_common=len(workers),control_images=len(controls),**observed,
                baseline_centered_rmse=baseline_error,
                raw_rho_control_evaluable=len(control_rho),raw_rho_control=float(np.mean(control_rho)) if control_rho else None,
                residual_rho_control_evaluable=len(control_residual),residual_rho_control=float(np.mean(control_residual)) if control_residual else None))
        for axis in ['Q','T']:
            p=selected[selected.fold.eq(building)&selected.type_axis.eq(axis)]
            groups=split_types(p,workers)
            coverage.append(dict(**base,type_axis=axis,n_common=len(workers),positive_n=len(groups['positive']),negative_n=len(groups['negative']),
                positive_workers='|'.join(groups['positive']),negative_workers='|'.join(groups['negative']),
                unclassified='|'.join(groups['unclassified']),contrast_usable=groups['usable'],
                positive_curve_usable=groups['positive_usable'],negative_curve_usable=groups['negative_usable']))
            for metric in ['WQ','IoU3D100']:
                ability=effects(building,workers,metric)
                if groups['usable']:
                    a,b=type_gap(values(source,workers,metric),groups),type_gap(values(target,workers,metric),groups)
                    general=type_gap(ability,groups) if ability.notna().all() else None
                    errors=[abs(type_gap(values(c,workers,metric),groups)-b) for c in controls]
                    for member in workers:
                        label='positive' if member in groups['positive'] else 'negative' if member in groups['negative'] else 'unclassified'
                        single_rows.append(dict(**base,type_axis=axis,metric=metric,worker_id=member,label=label,
                            source_value=float(values(source,[member],metric).iloc[0]),target_value=float(values(target,[member],metric).iloc[0]),
                            general_effect=float(ability[member]) if pd.notna(ability[member]) else None))
                else:
                    a=b=general=None;errors=[]
                type_rows.append(dict(**base,type_axis=axis,metric=metric,usable=groups['usable'],
                    positive_n=len(groups['positive']),negative_n=len(groups['negative']),source_gap=a,target_gap=b,general_gap=general,
                    source_gap_error=abs(a-b) if a is not None else None,
                    general_gap_error=abs(general-b) if general is not None else None,
                    same_direction=bool(a*b>0) if a is not None and a!=0 and b!=0 else None,
                    source_residual_gap=a-general if general is not None else None,target_residual_gap=b-general if general is not None else None,
                    control_images=len(errors),single_control_gap_error=float(np.mean(errors)) if errors else None))
            for label in ['positive','negative']:
                if not groups[label+'_usable']:
                    continue
                members=tuple(groups[label])
                def get_curve(image):
                    key=(image,members)
                    if key not in curve_cache:
                        inp=frozen[(image,tuple(workers))]
                        records=[r for r in inp['records'] if r['worker'] in members]
                        result=exact_curve(records,inp['reference_floors'])
                        context_id=f'K{len(curve_cache)+1:03d}'
                        curve_cache[key]=pd.DataFrame(result)
                        for r in result:
                            curve_data.append(dict(context_id=context_id,image_id=image,
                                image_code=inp['image_code'],workers='|'.join(members),n=len(members),**r))
                    return curve_cache[key]
                for version in ['bound','original']:
                    def series(image):
                        d=get_curve(image)
                        return d[d.reference_version.eq(version)].set_index('k').iou_mean
                    a,b=series(source),series(target)
                    other=[series(i) for i in controls]
                    result=curve_distance(b,a)
                    baseline=control_curve_distance(b,other) if other else dict(level_mae=None,gain_mae=None)
                    curve_comparisons.append(dict(**base,type_axis=axis,label=label,n=len(members),workers='|'.join(members),
                        reference_version=version,interpretation='two_person_change_only' if len(members)==2 else 'short_finite_pool_curve',
                        control_images=len(controls),**{'same_room_'+k:v for k,v in result.items()},
                        **{'control_'+k:v for k,v in baseline.items()}))
                    for k in a.index:
                        curve_k.append(dict(**base,type_axis=axis,label=label,n=len(members),reference_version=version,k=int(k),
                            source_iou=float(a[k]),target_iou=float(b[k])))
        print('Q/T task complete',task['task_id'],flush=True)
    transfer=pd.DataFrame(transfer);types=pd.DataFrame(type_rows);curves=pd.DataFrame(curve_comparisons)
    for name,data in [('pattern_transfer.csv',transfer),('type_coverage.csv',pd.DataFrame(coverage)),('type_quality_gaps.csv',types),
                      ('type_member_scores.csv',pd.DataFrame(single_rows)),('type_lee_curves.csv',pd.DataFrame(curve_data)),
                      ('type_lee_comparisons.csv',curves),('type_lee_by_k.csv',pd.DataFrame(curve_k))]:
        save(out,name,data)
    targets=[]
    for keys,g in transfer[transfer.control_images.gt(0)].groupby(['building','target_code','metric']):
        targets.append(dict(building=keys[0],target_code=keys[1],metric=keys[2],tasks=len(g),
            source_rmse=float(g.centered_rmse.mean()),control_rmse=float(g.baseline_centered_rmse.mean()),
            ability_rmse=float(g.general_ability_rmse_target.mean()),source_rho=g.raw_spearman.mean(),control_rho=g.raw_rho_control.mean(),
            source_residual_rho=g.residual_spearman.mean(),control_residual_rho=g.residual_rho_control.mean()))
    save(out,'pattern_by_target.csv',pd.DataFrame(targets))
    save(out,'pattern_by_building.csv',pd.DataFrame(targets).groupby(['building','metric'],as_index=False).agg(
        targets=('target_code','nunique'),source_rmse=('source_rmse','mean'),control_rmse=('control_rmse','mean'),ability_rmse=('ability_rmse','mean'),
        source_rho=('source_rho','mean'),control_rho=('control_rho','mean'),source_residual_rho=('source_residual_rho','mean'),control_residual_rho=('control_residual_rho','mean')))
    for prefix,frame,dimensions,error_a,error_b in [
        ('type_gap',types[types.usable & types.control_images.gt(0)],['type_axis','metric'],'source_gap_error','single_control_gap_error'),
        ('type_curve',curves[curves.control_images.gt(0)],['type_axis','label','reference_version'],'same_room_level_mae','control_level_mae'),
        ('type_curve_gain',curves[curves.control_images.gt(0)],['type_axis','label','reference_version'],'same_room_gain_mae','control_gain_mae')]:
        grouped=frame.groupby(['building','target_code']+dimensions,as_index=False).agg(
            tasks=('task_id','size'),source_error=(error_a,'mean'),control_error=(error_b,'mean'))
        save(out,prefix+'_by_target.csv',grouped)
        save(out,prefix+'_by_building.csv',grouped.groupby(['building']+dimensions,as_index=False).agg(
            targets=('target_code','nunique'),source_error=('source_error','mean'),control_error=('control_error','mean')))
    balanced=[]
    task_by={t['task_id']:t for t in tasks}
    for entry in coverage:
        if not entry['contrast_usable']:
            continue
        task=task_by[entry['task_id']]
        upper=min(entry['positive_n'],entry['negative_n'])
        for label in ['positive','negative']:
            members=tuple(entry[label+'_workers'].split('|'))
            for version in ['bound','original']:
                def shortened(image):
                    f=curve_cache[(image,members)]
                    return f[f.reference_version.eq(version)&f.k.le(upper)].set_index('k').iou_mean
                source,target=shortened(task['source']),shortened(task['target'])
                result=curve_distance(target,source)
                controls=[shortened(c) for c in task['controls']]
                control=control_curve_distance(target,controls) if controls else dict(level_mae=None,gain_mae=None)
                for metric in ['level_mae','gain_mae']:
                    balanced.append(dict(task_id=entry['task_id'],candidate_id=entry['candidate_id'],building=entry['building'],
                        target_code=entry['target_code'],type_axis=entry['type_axis'],label=label,reference_version=version,
                        matched_k_upper=upper,type_pool_n=len(members),metric=metric,control_images=len(controls),
                        source_error=result[metric],control_error=control[metric]))
    balanced=pd.DataFrame(balanced)
    save(out,'type_curve_balanced_tasks.csv',balanced)
    balanced_target=balanced[balanced.control_images.gt(0)].groupby(
        ['building','target_code','type_axis','label','reference_version','metric'],as_index=False).agg(
        tasks=('task_id','size'),source_error=('source_error','mean'),control_error=('control_error','mean'))
    save(out,'type_curve_balanced_by_target.csv',balanced_target)
    save(out,'type_curve_balanced_by_building.csv',balanced_target.groupby(
        ['building','type_axis','label','reference_version','metric'],as_index=False).agg(
        targets=('target_code','nunique'),source_error=('source_error','mean'),control_error=('control_error','mean')))
    summary=dict(schema='same_room_personnel_patterns_v1',contract_version=bundle['data']['contract_version'],
        training_quality_rows=len(training),target_quality_rows=len(primary),type_axes=['Q','T'],
        sb_included=False,main_pairs=len({tuple(sorted([t['source'],t['target']])) for t in tasks}),
        main_relation_groups=sorted({t['candidate_id'] for t in tasks}),directed_tasks=len(tasks),
        matched_control_buildings=sorted(transfer[transfer.control_images.gt(0)].building.unique()),
        type_coverage={axis:dict(directions=len(g),contrast_usable=int(g.contrast_usable.sum()),
            positive_curve_usable=int(g.positive_curve_usable.sum()),negative_curve_usable=int(g.negative_curve_usable.sum()))
            for axis,g in pd.DataFrame(coverage).groupby('type_axis')},
        type_curve_contexts=len(curve_cache),type_curve_max_people=int(curves.n.max()),
        type_curve_two_person_directions=int(curves[curves.reference_version.eq('bound')].n.eq(2).sum()),
        residual_correlation='diagnostic only: shared baseline subtraction can create high correlation',
        target_centering='relative person-pattern comparison, not a deployment predictor of unknown absolute target quality',
        outcome='See actual tables; no significance, final types, independent-building generalization or causal structure claim.')
    save(out,'SUMMARY.json',summary)
    save(out,'FIELD_CONTRACT.json',dict(schema=summary['schema'],
        table_columns={f.name:list(pd.read_csv(f,nrows=0).columns) for f in sorted(out.glob('*.csv'))},
        Q='latest 931-row building-excluded WQ profiles; positive/negative is relative above/below pool, not final type',
        T='frozen 716 qualified log1p active-time evidence; positive slower / negative faster, not diligence',
        supports='existing profiles need 6 contexts/3 buildings; type contrasts require 2 workers each side, single-class curves only 2 within that class',
        quality='same reference and same workers; WQ and IoU3D100 at 0-100, raw components preserved',
        pattern='rank correlation and mean-centered RMSE; image centering uses target outcomes for description, no absolute score prediction',
        residual='shared estimated ability removed only for diagnostic correlation, not independent room effects or a second distance metric',
        type_gap='positive-class mean minus negative-class mean; same classes/workers across views and controls',
        curves='Lee MV50 bottom IoU, all subsets, fixed personnel; N=2 is only one pairwise fusion change; not wall-line WQ trajectories',
        balanced_curves='Both labels share the same task panel and k=1..min(positive_n,negative_n), retaining concrete-member differences; not a causal type effect',
        aggregation='single control expected error, then task -> target -> building; VFua missing matched controls retained',
        missing='unsupported type/profile remains unclassified; no success-only substitution; flat correlation blank'))
    plot(out,pd.DataFrame(pattern_rows),types,pd.DataFrame(curve_k),curves)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def plot(out,patterns,types,curve_k,comparisons):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,metric in zip(axes,['WQ','IoU3D100']):
        d=patterns[patterns.relation.eq('confirmed_comparable') & patterns.metric.eq(metric)]
        for candidate,g in d.groupby('candidate_ids'):
            ax.scatter(g.raw_spearman,g.residual_spearman,label=candidate)
        ax.set(xlim=(-1.05,1.05),ylim=(-1.05,1.05),xlabel='原分数人员排序相关',ylabel='扣楼外一般效应后的相关（仅诊断）',title=metric)
        ax.axhline(0,color='gray',lw=.7);ax.axvline(0,color='gray',lw=.7);ax.legend()
    fig.suptitle('残差高相关可由共享基线造成；不可单独作为房间规律证据')
    fig.savefig(out/'person_pattern_diagnostic.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,axis in zip(axes,['Q','T']):
        d=types[types.type_axis.eq(axis)&types.metric.eq('WQ')&types.usable&types.target_code.lt(types.source_code)]
        for candidate,g in d.groupby('candidate_id'):
            ax.scatter(g.source_gap,g.target_gap,label=candidate)
        ax.plot([-50,50],[-50,50],color='gray',lw=.7);ax.axhline(0,color='gray',lw=.5);ax.axvline(0,color='gray',lw=.5)
        meaning='较高Q−较低Q' if axis=='Q' else '较慢−较快'
        ax.set(xlabel='源视角WQ差（'+meaning+'）',ylabel='目标视角WQ差（'+meaning+'）',title=axis+'：楼外候选粗类');ax.legend()
    fig.savefig(out/'type_quality_gap.png',dpi=150);plt.close(fig)
    choices=comparisons[comparisons.reference_version.eq('bound')].sort_values(['n','task_id'],ascending=[False,True]).drop_duplicates(['candidate_id','type_axis','label'])
    save(out,'curve_plot_selection.json',choices[['task_id','candidate_id','type_axis','label','n']].to_dict('records'))
    fig,axes=plt.subplots(2,4,figsize=(14,7),layout='constrained')
    for ax,row in zip(axes.flat,choices.itertuples()):
        d=curve_k[curve_k.task_id.eq(row.task_id)&curve_k.type_axis.eq(row.type_axis)&curve_k.label.eq(row.label)&curve_k.reference_version.eq('bound')]
        ax.plot(d.k,d.source_iou,'o-',label=row.source_code.split('-')[-1]);ax.plot(d.k,d.target_iou,'o-',label=row.target_code.split('-')[-1])
        meaning={('Q','positive'):'Q较高',('Q','negative'):'Q较低',('T','positive'):'T较慢',('T','negative'):'T较快'}[(row.type_axis,row.label)]
        ax.set(ylim=(0,1),xlabel='人数k',ylabel='Lee底面IoU',title=f'{row.candidate_id} {meaning} N={row.n}')
        ax.set_xticks(d.k.tolist());ax.legend()
    for ax in list(axes.flat)[len(choices):]:ax.set_visible(False)
    fig.suptitle('仅按最高人员支持、固定任务号选例；全部曲线另存；2人仅一次融合变化')
    fig.savefig(out/'type_curve_examples.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    main(parser.parse_args().out)
