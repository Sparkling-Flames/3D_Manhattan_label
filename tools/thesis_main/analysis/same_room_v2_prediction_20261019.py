"""v2直接同房Q/T：排除OOS、门洞单列、按建筑留出预测。"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from .same_room_b8l2_20261016 import paired_values
from .same_room_quality_curves_20261015 import save

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research/statistics/v2_integrated_analysis_20261019'
OUT=ROOT/'research/same_room/same_room_v2_prediction_20261019'
VERSION='same_room_v2_prediction_20261019_r1'
METRICS=['B8L2','D10','source_active_time_seconds','target_matched_time_seconds']


def scene_layer(d):
    return pd.Series(np.select([d.is_oos,d.is_doorway],['excluded_oos','doorway'],default='ordinary'),index=d.index)


def worker_baseline(records,excluded):
    train=records[~records.building.isin(excluded)]
    return train.groupby('worker_id').value.mean(),train.groupby('worker_id').size(),train.value.mean()


def fit_transfer(x,y,weights):
    design=np.column_stack([np.ones(len(x)),x]);w=np.sqrt(np.asarray(weights))
    return np.linalg.lstsq(design*w[:,None],np.asarray(y)*w,rcond=None)[0]


def balanced_weights(d):
    keys=['building','source_image','target_image']
    n=d.groupby(keys).worker_id.transform('size')
    groups=d[keys].drop_duplicates().groupby('building').size()
    return 1/(n*d.building.map(groups))


def build_panel(d,relations):
    d=d.copy();d['layer']=scene_layer(d)
    image_layers=d.groupby('image_id').layer.first().to_dict()
    save(OUT,'record_coverage.csv',d.groupby(['origin','condition','layer','quality_use'],dropna=False).agg(
        records=('object_id','size'),images=('image_id','nunique'),workers=('worker_id','nunique')).reset_index())
    d=d[d.pool_analysis_eligible & d.condition.eq('manual') & d.layer.ne('excluded_oos')].copy()
    gates=json.loads((ROOT/'research/workers/worker_b8l2_d10_20261017/admission_snapshot.json').read_text(encoding='utf-8'))
    allowed={g['object_id']:not g['original_holdout'] and g['role']=='manual_development_candidate' and not g['personnel_barriers'] and not g['context_barriers'] for g in gates}
    d['training_allowed']=d.origin.eq('new') | d.object_id.map(allowed).eq(True)
    save(OUT,'training_admission.csv',d[['object_id','image_id','worker_id','origin','training_allowed']])
    assert not d.duplicated(['image_id','worker_id']).any()
    d['building']=d.building_id
    d['target_aligned']=d.chosen_target_id.eq(d.current_target_id)
    for metric in METRICS:
        valid=d.target_aligned.copy()
        if metric in ['B8L2','D10']:valid &= d.quality_usable & d.quality_use.isin(['ordinary_primary','doorway_quality'])
        else:valid &= d[metric].ge(0)
        d.loc[~valid,metric]=np.nan
    assert d.B8L2.notna().equals(d.D10.notna())
    cells={i:g for i,g in d.groupby('image_id')};empty=d.iloc[:0]
    summaries=[];people=[];audit=[]
    for j,r in enumerate(relations.itertuples()):
        a,b=cells.get(r.image_a,empty),cells.get(r.image_b,empty)
        layers={image_layers.get(r.image_a),image_layers.get(r.image_b)}
        layer='excluded_oos' if 'excluded_oos' in layers else 'doorway' if 'doorway' in layers else 'ordinary'
        admissible=r.physical_adopted and r.scope_comparable and not r.substantive_conflict
        audit.append(dict(pair_id=j,image_a=r.image_a,image_b=r.image_b,layer=layer,
            physical_adopted=r.physical_adopted,scope_comparable=r.scope_comparable,substantive_conflict=r.substantive_conflict,
            records_a=len(a),records_b=len(b),relation_eligible=bool(admissible),user_group_ids=r.user_group_ids))
        if a.empty or b.empty or not r.physical_adopted:continue
        for origin in ['all','v1','new']:
            aa=a if origin=='all' else a[a.origin.eq(origin)];bb=b if origin=='all' else b[b.origin.eq(origin)]
            for metric in METRICS:
                stats,common=paired_values(aa,bb,metric)
                base=dict(pair_id=j,image_a=r.image_a,image_b=r.image_b,building=r.image_a.split('_')[0],
                    layer=layer,origin=origin,metric=metric,relation_eligible=bool(admissible),user_group_ids=r.user_group_ids)
                summaries.append(dict(**base,**stats))
                if origin=='all' or not admissible or len(common)<4:continue
                am=aa.set_index('worker_id');bm=bb.set_index('worker_id')
                for worker,row in common.iterrows():
                    for side,(im1,im2,v1,v2) in enumerate([(r.image_a,r.image_b,row.iloc[0],row.iloc[1]),(r.image_b,r.image_a,row.iloc[1],row.iloc[0])]):
                        people.append(dict(**base,worker_id=worker,source_image=im1,target_image=im2,direction=side,
                            calibration_training_allowed=bool(am.loc[worker,'training_allowed'] and bm.loc[worker,'training_allowed']),
                            source_value=float(v1),actual=float(v2)))
    save(OUT,'relation_coverage.csv',pd.DataFrame(audit));save(OUT,'pair_descriptive.csv',pd.DataFrame(summaries))
    edges=pd.DataFrame(people);save(OUT,'directed_observations.csv',edges)
    return d,edges,pd.DataFrame(summaries)


def features(edges,records,outer,ks):
    rows=[];baseline_cache={}
    for group_index,((building,source,target),g) in enumerate(edges.groupby(['building','source_image','target_image'],sort=True)):
        if building not in baseline_cache:baseline_cache[building]=worker_baseline(records,{outer,building})
        means,counts,pop=baseline_cache[building]
        g=g.sort_values('worker_id').copy();g['baseline']=g.worker_id.map(means)
        warm=g.baseline.notna();g['baseline_n']=g.worker_id.map(counts).fillna(0).astype(int)
        # The source observation is allowed at prediction time; target values are outcomes only.
        for row in g.itertuples():
            base=dict(building=building,source_image=source,target_image=target,worker_id=row.worker_id,
                pair_id=row.pair_id,baseline=row.baseline if row.baseline_n else pop,baseline_n=row.baseline_n,
                calibration_training_allowed=row.calibration_training_allowed,
                source_value=row.source_value,actual=row.actual)
            rows.append(dict(**base,mode='individual',k=1,replay=0,feature=row.source_value-row.baseline))
        peers=g[warm].copy()
        if building!=outer:peers=peers[peers.calibration_training_allowed]
        peers['offset']=peers.source_value-peers.baseline
        if not ks or len(peers)<max(ks)+1:continue
        for i,row in enumerate(peers.itertuples()):
            other=peers[peers.worker_id.ne(row.worker_id)]
            for repeat in range(3):
                order=np.random.default_rng(20261019+group_index*10000+i*10+repeat).permutation(len(other))
                for k in ks:
                    rows.append(dict(building=building,source_image=source,target_image=target,worker_id=row.worker_id,
                        pair_id=row.pair_id,baseline=row.baseline,baseline_n=row.baseline_n,source_value=row.source_value,
                        calibration_training_allowed=row.calibration_training_allowed,
                        actual=row.actual,mode='other_source_people',k=k,replay=repeat,feature=other.offset.iloc[order[:k]].mean()))
    return pd.DataFrame(rows)


def predict(d,edges):
    predictions=[];folds=[]
    for (metric,origin),e in edges[edges.layer.eq('ordinary')].groupby(['metric','origin']):
        r=d[d.layer.eq('ordinary')&d.origin.eq(origin)&d.training_allowed&d[metric].notna()][['building','worker_id',metric]].rename(columns={metric:'value'})
        time=metric.endswith('seconds');e=e.copy()
        if time:
            r['value']=np.log1p(r.value);e[['source_value','actual']]=np.log1p(e[['source_value','actual']])
        ks=([4,8,12,16] if origin=='new' else [4,8]) if metric in ['B8L2','D10'] else []
        for held in sorted(e.building.unique()):
            f=features(e,r,held,ks)
            for (mode,k),g in f.groupby(['mode','k']):
                train=g[g.building.ne(held)&g.feature.notna()&g.calibration_training_allowed];test=g[g.building.eq(held)]
                if test.empty:continue
                supported=train.building.nunique()>=3
                coef=fit_transfer(train.feature,train.actual-train.baseline,balanced_weights(train)) if supported else [np.nan,np.nan]
                offset=np.average(train.actual-train.baseline,weights=balanced_weights(train)) if supported else np.nan
                folds.append(dict(metric=metric,origin=origin,held_out_building=held,mode=mode,k=int(k),
                    train_buildings=train.building.nunique(),train_rows=len(train),test_rows=len(test),
                    train_building_ids='|'.join(sorted(train.building.unique())),intercept=coef[0],slope=coef[1],baseline_calibration=offset,supported=supported))
                assert held not in set(train.building)
                for row in test.itertuples():
                    estimators={'worker_history':row.baseline}
                    if mode=='individual':estimators['copy_source']=row.source_value
                    if supported and row.baseline_n:estimators['calibrated_history']=row.baseline+offset
                    if supported and row.baseline_n:estimators['history_plus_source']=row.baseline+coef[0]+coef[1]*row.feature
                    for method,value in estimators.items():
                        value=max(0,value) if time else np.clip(value,0,100)
                        predictions.append(dict(metric=metric,origin=origin,building=held,pair_id=row.pair_id,
                            source_image=row.source_image,target_image=row.target_image,worker_id=row.worker_id,
                            mode=mode,k=int(k),replay=row.replay,method=method,baseline_n=row.baseline_n,
                            warm_start=bool(row.baseline_n),actual=np.expm1(row.actual) if time else row.actual,
                            predicted=np.expm1(value) if time else value,
                            absolute_error=abs(value-row.actual),error_unit='log1p_seconds' if time else 'score_points'))
    p=pd.DataFrame(predictions);save(OUT,'predictions.csv',p);save(OUT,'fold_models.csv',pd.DataFrame(folds))
    keys=['metric','origin','building','pair_id','source_image','target_image','worker_id','mode','k','replay']
    primary=p[p.method.eq('history_plus_source')][keys]
    matched=p.merge(primary,on=keys,validate='many_to_one')
    direction=matched.groupby(['metric','origin','building','source_image','target_image','mode','k','method'],as_index=False).agg(
        mean_absolute_error=('absolute_error','mean'),prediction_rows=('absolute_error','size'))
    bybuilding=direction.groupby(['metric','origin','building','mode','k','method'],as_index=False).agg(
        mae=('mean_absolute_error','mean'),directions=('source_image','size'),prediction_rows=('prediction_rows','sum'))
    summary=bybuilding.groupby(['metric','origin','mode','k','method'],as_index=False).agg(
        building_equal_mae=('mae','mean'),buildings=('building','nunique'),directions=('directions','sum'),prediction_rows=('prediction_rows','sum'))
    wide=bybuilding.pivot(index=['metric','origin','building','mode','k'],columns='method',values='mae').reset_index()
    wide['gain_vs_history']=wide.worker_history-wide.history_plus_source
    wide['gain_vs_calibrated_history']=wide.calibrated_history-wide.history_plus_source
    save(OUT,'prediction_by_building.csv',bybuilding);save(OUT,'prediction_summary.csv',summary);save(OUT,'prediction_gains.csv',wide)
    save(OUT,'prediction_coverage.csv',p.groupby(['metric','origin','mode','k','method','warm_start'],as_index=False).agg(rows=('worker_id','size'),workers=('worker_id','nunique'),buildings=('building','nunique')))
    return summary,wide


def report_outputs():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
    summary=pd.read_csv(OUT/'prediction_summary.csv');gains=pd.read_csv(OUT/'prediction_gains.csv')
    pairs=pd.read_csv(OUT/'pair_descriptive.csv');pred=pd.read_csv(OUT/'predictions.csv')
    door=pairs[pairs.layer.eq('doorway')&pairs.origin.eq('all')&pairs.metric.eq('B8L2')&pairs.n_paired.ge(4)]
    save(OUT,'doorway_separate.csv',door)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for origin,ax,title in zip(['new','v1'],axes,['新增人员','旧人员']):
        g=gains[gains.metric.eq('B8L2')&gains.origin.eq(origin)&gains['mode'].eq('individual')].sort_values('building')
        ax.bar(range(len(g)),g.gain_vs_calibrated_history,color=['#2575a6' if x>0 else '#c66c36' for x in g.gain_vs_calibrated_history])
        ax.set(xticks=range(len(g)),xticklabels=g.building,title=title+'：各留出建筑',ylabel='MAE降低（分）；正值表示同房信息有增益')
        ax.tick_params(axis='x',rotation=65);ax.axhline(0,color='black',lw=.8);ax.grid(axis='y',alpha=.2)
    fig.suptitle('同一人员跨视角预测：B8L2，相对校准后人员历史基线')
    fig.savefig(OUT/'prediction_by_building.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.5,5),layout='constrained')
    for metric,style in [('B8L2','-'),('D10','--')]:
        for method,color,label in [('calibrated_history','#888888','历史基线'),('history_plus_source','#1769aa','历史＋源视角其他人员')]:
            g=summary[summary.metric.eq(metric)&summary.origin.eq('new')&summary['mode'].eq('other_source_people')&summary.method.eq(method)].sort_values('k')
            ax.plot(g.k,g.building_equal_mae,style,color=color,marker='o',label=metric+' '+label)
    ax.set(title='新增人员固定评价面板：增加源视角可用人数',xlabel='源视角其他人员数（不含被预测者）',ylabel='建筑等权MAE（分；低为好）',xticks=[4,8,12,16]);ax.legend(fontsize=9);ax.grid(alpha=.2)
    fig.savefig(OUT/'source_people_learning.png',dpi=140);plt.close(fig)
    # Enforce the same target set at every k, not a changing high-N image panel.
    learning=pred[pred['mode'].eq('other_source_people')&pred.method.eq('history_plus_source')]
    for _,g in learning.groupby(['metric','origin']):
        sets=[set(map(tuple,x[['building','source_image','target_image','worker_id','replay']].to_numpy())) for _,x in g.groupby('k')]
        assert all(x==sets[0] for x in sets)
    for _,g in pred.groupby(['origin','mode','k','method']):
        parts=[set(map(tuple,x[['building','source_image','target_image','worker_id','replay']].to_numpy())) for _,x in g[g.metric.isin(['B8L2','D10'])].groupby('metric')]
        if len(parts)==2:assert parts[0]==parts[1]
    stats=json.loads((OUT/'SUMMARY.json').read_text(encoding='utf-8'))
    save(OUT,'CONSUMER_INTERFACE.json',dict(schema=VERSION,data_release='v2',status='exploratory_completed',
        source_manifest='research/data/releases/v2/analysis_input/manifest.json',score_source='research/quality/quality_workers_v2_20261019/CROSS_MODULE_INPUTS.json',
        statistics_source=SOURCE.relative_to(ROOT).as_posix()+'/CONSUMER_INTERFACE.json',
        historical_training_gate='research/workers/worker_b8l2_d10_20261017/admission_snapshot.json',
        files=dict(description='pair_descriptive.csv',predictions='predictions.csv',folds='fold_models.csv',summary='prediction_summary.csv',building_gains='prediction_gains.csv',doorway='doorway_separate.csv',plan='PLAN.json'),
        coverage=stats['coverage'],no_oos=True,doorway_in_primary=False,classes_deferred=True,new_fusion=False,
        checks=dict(learning_target_panel_equal_across_k=True,B8L2_D10_target_members_equal=True),human_decisions_required=[]))
    contract=json.loads((OUT/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    contract['tables']={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')}
    save(OUT,'FIELD_CONTRACT.json',contract)
    print('Figures, consumer interface and fixed-panel/metric-membership checks completed.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT,'PLAN.json',dict(version=VERSION,data_release='v2',primary='B8L2',sensitivity='D10',
        exclusions='OOS excluded including doorway x OOS; doorway kept separate; manual only; current image target; source pool gates preserved',
        description='all direct physical relations retained in audit; primary requires scope comparable and no substantive conflict; >=4 common valid workers separately by cohort and metric',
        prediction='leave one building out; worker means exclude outer building; calibration training features also exclude their own building; historical admission barriers and holdouts excluded from all training; source Q known at prediction time',
        calibration='weighted linear residual transfer with intercept; compare also intercept-only calibrated history to isolate source increment; equal building then directed image pair weights; >=3 training buildings; no model tuning',
        evaluation='identical warm-start test rows across methods, equal directed pairs within building then equal buildings; time error in log1p seconds',
        learning='ordinary Q only, other source people exclude target person; fixed max-k-support panel within cohort/fold, k 4/8 for v1 and 4/8/12/16 for new; 3 nested seeded draws',
        classes='deferred until classification accepted',new_fusion=False))
    d=pd.read_csv(SOURCE/'shared_records.csv',low_memory=False)
    score=pd.read_csv(ROOT/'research/quality/quality_workers_v2_20261019/quality_records.csv')
    assert d.object_id.is_unique
    check=d[d.quality_usable].set_index('object_id')[['B8L2','D10']].sort_index()
    pd.testing.assert_frame_equal(check,score.set_index('object_id')[['B8L2','D10']].sort_index(),check_exact=False,atol=1e-10,rtol=0)
    r=pd.read_csv(SOURCE/'direct_relation_registry.csv');panel,edges,descriptive=build_panel(d,r)
    result,gains=predict(panel,edges)
    primary=descriptive[descriptive.relation_eligible&descriptive.layer.eq('ordinary')&descriptive.origin.eq('all')&descriptive.n_paired.ge(4)]
    coverage=[]
    for metric,g in primary.groupby('metric'):
        coverage.append(dict(metric=metric,pairs=len(g),images=len(set(g.image_a)|set(g.image_b)),buildings=g.building.nunique(),
            median_common=g.n_paired.median(),paired_occurrences=int(g.n_paired.sum())))
    save(OUT,'SUMMARY.json',dict(version=VERSION,data_release='v2',coverage=coverage,new_fusion=False,new_personnel_classification=False,
        score_values_verified_against_current_quality=True,source=SOURCE.relative_to(ROOT).as_posix(),
        note='prediction is conditional on observed source evaluations; no claim of same-room specificity vs confirmed different rooms'))
    save(OUT,'FIELD_CONTRACT.json',dict(version=VERSION,tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')},
        prediction_unit='one target worker and directed known room pair; repeated edges and draws not independent',
        missing='absent numeric predictions are unsupported, never zero; all exclusions in record/relation/coverage tables',
        time='source reported task durations and historical source time separated by origin; target matched time separate; log1p error primary, actual/predicted columns seconds'))
    report_outputs()
    print(json.dumps(coverage,ensure_ascii=False,indent=2));print(result.to_string(index=False))


if __name__=='__main__':main()
