"""数据v1下，按固定难度/场景与同一人员比较质量、时间和计算覆盖。"""
import json
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty/difficulty_v1_analysis_20261017'
SOURCE = ROOT / 'research/quality/quality_b8l2_d10_20261017'
LEVELS = ('简单', '中等', '困难')
STATUSES = ('full_computed', 'floor_only_computed', 'input_uncomputable', 'pending_target')


def describe(values, prefix):
    x = pd.to_numeric(values, errors='raise').dropna()
    return {prefix+'_n': len(x), prefix+'_mean': x.mean() if len(x) else np.nan,
            prefix+'_median': x.median() if len(x) else np.nan,
            prefix+'_sd': x.std(ddof=1) if len(x)>1 else np.nan,
            prefix+'_p10': x.quantile(.10) if len(x)>=5 else np.nan,
            prefix+'_p25': x.quantile(.25) if len(x) else np.nan,
            prefix+'_p75': x.quantile(.75) if len(x) else np.nan}


def group_summary(frame, quality_use=None):
    assert frame.object_id.is_unique
    usable = frame.quality_usable.astype(bool)
    if quality_use: usable &= frame.quality_use.eq(quality_use)
    selected = frame[usable]
    assert selected[['B8L2','D10']].notna().all().all()
    row = dict(inventory_n=len(frame), inventory_images=frame.image_id.nunique(),
        inventory_workers=frame.worker_id.nunique(),inventory_buildings=frame.building_id.nunique(),
        pool_under3_n=int((~frame.pool_min3_pass.astype(bool)).sum()),
        quality_n=len(selected),quality_images=selected.image_id.nunique(),
        quality_workers=selected.worker_id.nunique(),quality_buildings=selected.building_id.nunique(),
        computed_but_not_quality_n=int((frame.calculation_status.eq('full_computed') & ~usable).sum()),
        quality_missing_or_excluded_n=len(frame)-len(selected))
    for status in STATUSES: row[status+'_n']=int(frame.calculation_status.eq(status).sum())
    row['input_uncomputable_rate']=row['input_uncomputable_n']/len(frame) if len(frame) else np.nan
    for metric in ('B8L2','D10'):
        row.update(describe(selected[metric], metric))
        per_image=selected.groupby('image_id')[metric].mean()
        row[metric+'_image_equal_mean']=per_image.mean() if len(per_image) else np.nan
        per_worker=selected.groupby('worker_id')[metric].mean()
        row[metric+'_worker_equal_mean']=per_worker.mean() if len(per_worker) else np.nan
    row.update(describe(selected.D10-selected.B8L2,'D10_minus_B8L2'))
    for name,column in [('source_time','source_active_time_seconds'),('target_time','target_matched_time_seconds')]:
        if column not in frame: continue
        row.update(describe(frame[column],name+'_inventory'))
        row.update(describe(selected[column],'quality_'+name))
    return row


def worker_pairs(rows, left, right, condition):
    if rows.empty: return pd.DataFrame()
    a=rows[(rows.condition==condition)&(rows.stratum==left)&(rows.quality_n>0)]
    b=rows[(rows.condition==condition)&(rows.stratum==right)&(rows.quality_n>0)]
    joined=a.merge(b,on='worker_id',suffixes=('_left','_right'))
    result=[]
    for _,r in joined.iterrows():
        x=dict(worker_id=r.worker_id,condition=condition,left=left,right=right,
            n_left=int(r.quality_n_left),n_right=int(r.quality_n_right),
            image_n_left=int(r.quality_images_left),image_n_right=int(r.quality_images_right))
        for m in ('B8L2','D10'):
            x[m+'_left']=r[m+'_mean_left'];x[m+'_right']=r[m+'_mean_right']
            x[m+'_delta']=r[m+'_mean_right']-r[m+'_mean_left']
            x[m+'_p10_left']=r[m+'_p10_left'];x[m+'_p10_right']=r[m+'_p10_right']
        x['source_time_n_left']=int(r.source_time_n_left)
        x['source_time_n_right']=int(r.source_time_n_right)
        x['uncomputable_rate_left']=r.input_uncomputable_rate_left
        x['uncomputable_rate_right']=r.input_uncomputable_rate_right
        x['uncomputable_rate_delta']=r.input_uncomputable_rate_right-r.input_uncomputable_rate_left
        x['source_time_delta']=(r.source_time_mean_right-r.source_time_mean_left
            if x['source_time_n_left'] and x['source_time_n_right'] else np.nan)
        result.append(x)
    return pd.DataFrame(result)


def load():
    manifest=json.loads((SOURCE/'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))
    release=json.loads((ROOT/'research/data/releases/v1/RELEASE.json').read_text(encoding='utf-8'))
    rows=pd.read_csv(SOURCE/'shared_records.csv',low_memory=False)
    difficulty=json.loads((SOURCE/'difficulty_records.json').read_text(encoding='utf-8'))
    assert manifest['version']=='quality_b8l2_d10_20261017_v2'
    assert release['data_release']=='v1' and release['input_revision']=='annotation_batch_98_20261017_v1'
    assert release['counts']['annotations']==manifest['counts']['inventory']
    assert release['counts']['quality_usable']==manifest['counts']['quality_rows']
    assert len(rows)==manifest['counts']['inventory']==3222 and rows.object_id.is_unique
    assert len(difficulty)==261 and len({r['image_id'] for r in difficulty})==261
    assert rows.image_id.nunique()==261 and set(rows.image_id)=={r['image_id'] for r in difficulty}
    assert rows.quality_usable.sum()==manifest['counts']['quality_rows']==1911
    assert rows.loc[rows.quality_usable,['B8L2','D10']].notna().all().all()
    assert rows.loc[~rows.quality_usable,['B8L2','D10']].isna().all().all()
    target={r['image_id']:r['target_version'] for r in difficulty}
    rows['difficulty_target_id']=rows.image_id.map(target)
    assert rows.loc[rows.quality_usable,'rescore_target_id'].eq(rows.loc[rows.quality_usable,'difficulty_target_id']).all()
    assert not rows.loc[rows.quality_usable,'is_oos'].any()
    assert rows.loc[rows.source_active_time_seconds.notna(),'time_status'].eq('usable').all()
    assert not rows.loc[rows.new_batch,'target_matched_time_seconds'].notna().any()
    assert rows.calculation_status.isin(STATUSES).all()
    assert rows.quality_use.isin(['ordinary_primary','doorway_quality','special_conditional_only','not_qualified']).all()
    rows['scene_axis']=rows.is_doorway.map({False:'非门洞',True:'门洞'})+'∩'+rows.is_oos.map({False:'非OOS',True:'OOS'})
    return rows,difficulty,manifest,release


def save_table(name,rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records,difficulty,manifest,release=load()
    version='data_v1_difficulty_analysis_20261017_r1'
    key=['object_id','image_id','image_code','building_id','worker_id','condition','difficulty_class',
         'difficulty_target_id','rescore_target_id','scene_axis','is_doorway','is_oos','doorway_status','oos_subtype',
         'pool_min3_pass','gt_error_excluded','difficulty_analysis_exclusion','quality_usable','quality_use',
         'calculation_status','input_geometry_reasons','quality_exclusion_reasons','B8L2','D10',
         'diagnostic_B8L2','diagnostic_D10','worker_unmarkable_choice',
         'source_active_time_seconds','target_matched_time_seconds','time_status','target_time_interpretation']
    save_table('record_ledger.csv',records[key])
    strata=[]
    axes=[('difficulty','difficulty_class'),('scene','scene_axis'),('doorway_markability','doorway_status'),
          ('oos_subtype','oos_subtype')]
    for axis,column in axes:
        for (condition,stratum),f in records.groupby(['condition',column],dropna=False):
            use='ordinary_primary' if axis=='difficulty' and stratum in LEVELS else None
            strata.append(dict(axis=axis,condition=condition,stratum=stratum,
                quality_use_filter=use or 'all_qualified',**group_summary(f,use)))
    summary=pd.DataFrame(strata)
    save_table('strata_summary.csv',summary)
    workers=[]
    for axis,column in [('difficulty','difficulty_class'),('scene','scene_axis')]:
        for (worker,condition,stratum),f in records.groupby(['worker_id','condition',column],dropna=False):
            use='ordinary_primary' if axis=='difficulty' and stratum in LEVELS else None
            x=group_summary(f,use)
            # Each worker can see a different task mix within the same coarse class.
            workers.append(dict(worker_id=worker,axis=axis,condition=condition,stratum=stratum,
                quality_use_filter=use or 'all_qualified',**x,
                source_time_n=x.get('quality_source_time_n',0),
                source_time_mean=x.get('quality_source_time_mean',np.nan)))
    worker=pd.DataFrame(workers)
    save_table('worker_strata.csv',worker)
    all_pairs=[]
    pair_summary=[]
    targets=[('difficulty',a,b) for a,b in combinations(LEVELS,2)]+[
        ('scene','非门洞∩非OOS','门洞∩非OOS')]
    for axis,left,right in targets:
        for condition in ('manual','semi','oos'):
            p=worker_pairs(worker[worker.axis==axis],left,right,condition)
            if p.empty: continue
            p['axis']=axis;all_pairs.append(p)
            pair_summary.append(dict(axis=axis,condition=condition,left=left,right=right,
                workers=len(p),workers_ge3_each=int(((p.n_left>=3)&(p.n_right>=3)).sum()),
                median_n_left=p.n_left.median(),median_n_right=p.n_right.median(),
                B8L2_mean_delta=p.B8L2_delta.mean(),B8L2_median_delta=p.B8L2_delta.median(),
                B8L2_positive_workers=int((p.B8L2_delta>0).sum()),
                B8L2_p10_paired_workers=int((p.B8L2_p10_left.notna() & p.B8L2_p10_right.notna()).sum()),
                B8L2_p10_median_delta=(p.B8L2_p10_right-p.B8L2_p10_left).median(),
                D10_mean_delta=p.D10_delta.mean(),D10_median_delta=p.D10_delta.median(),
                D10_positive_workers=int((p.D10_delta>0).sum()),
                time_paired_workers=p.source_time_delta.notna().sum(),
                source_time_median_delta=p.source_time_delta.median(),
                uncomputable_rate_median_delta=p.uncomputable_rate_delta.median()))
    pairs=pd.concat(all_pairs,ignore_index=True) if all_pairs else pd.DataFrame()
    save_table('worker_pairs.csv',pairs)
    save_table('worker_pair_summary.csv',pair_summary)
    images=[]
    for (image,condition),f in records.groupby(['image_id','condition']):
        images.append(dict(image_id=image,image_code=f.image_code.iloc[0],condition=condition,
            difficulty_class=f.difficulty_class.iloc[0],scene_axis=f.scene_axis.iloc[0],
            quality_use_filter='ordinary_primary' if f.difficulty_class.iloc[0] in LEVELS else 'all_qualified',
            **group_summary(f,'ordinary_primary' if f.difficulty_class.iloc[0] in LEVELS else None)))
    save_table('image_condition.csv',images)
    reasons=[]
    for field in ['input_geometry_reasons','quality_exclusion_reasons']:
        for _,r in records.iterrows():
            for reason in json.loads(r[field] if pd.notna(r[field]) else '[]'):
                reasons.append(dict(object_id=r.object_id,axis='difficulty',condition=r.condition,
                    difficulty_class=r.difficulty_class,scene_axis=r.scene_axis,reason_field=field,reason=reason))
    save_table('reason_ledger.csv',reasons)
    reason_counts=(pd.DataFrame(reasons).groupby(['condition','difficulty_class','scene_axis','reason_field','reason']).agg(
        records=('object_id','nunique')).reset_index() if reasons else pd.DataFrame())
    save_table('reason_counts.csv',reason_counts)

    fusion_root=ROOT/'research/fusion/wall_consensus_v1_process_20261017'
    fusion_result=None
    if (fusion_root/'MANIFEST.json').exists():
        fusion_manifest=json.loads((fusion_root/'MANIFEST.json').read_text(encoding='utf-8'))
        fusion_status=json.loads((fusion_root/'STATUS.json').read_text(encoding='utf-8'))
        assert fusion_manifest['data_release']=='v1'
        assert fusion_manifest['input_manifest']==manifest['input_manifest']
        complete=pd.read_csv(fusion_root/'completion.csv')
        elig=pd.read_csv(fusion_root/'pool_eligibility.csv')
        by_k=pd.read_csv(fusion_root/'by_pool_k.csv')
        done=set(complete.loc[complete.status.eq('completed'),'pool_id'])
        assert len(done)>=fusion_status['completed_pools']
        ordinary=by_k[by_k.pool_id.isin(done) & by_k.layer.eq('ordinary') & by_k.condition.eq('manual') &
                      by_k.path_kind.eq('random') & by_k.k.isin([3,4,6])].copy()
        candidate=set.intersection(*(set(ordinary.loc[ordinary.k.eq(k),'pool_id']) for k in [3,4,6]))
        panel_path=OUT/'fusion_panel.json'
        if panel_path.exists():
            panel=json.loads(panel_path.read_text(encoding='utf-8'))
            chosen=set(panel['pool_ids'])
            assert panel['source_version']==fusion_manifest['version'] and chosen <= candidate
        else:
            chosen=candidate
            panel=dict(source_version=fusion_manifest['version'],data_release='v1',
                condition='manual',layer='ordinary',fixed_k=[3,4,6],pool_ids=sorted(chosen),
                selection='completed ordinary manual pools with actual random paths at k=3,4,6 at first build; later reruns keep IDs')
            panel_path.write_text(json.dumps(panel,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        assert chosen
        selected=ordinary[ordinary.pool_id.isin(chosen)].merge(
            elig[['pool_id','difficulty','source_workers','included']],on='pool_id',validate='many_to_one')
        assert len(selected)==3*len(chosen) and selected[['pool_id','k']].duplicated().sum()==0
        assert selected.included.all() and selected.path_states.eq(4).all()
        assert all((fusion_root/'pools'/pool/'DONE.json').exists() for pool in chosen)
        by_image={r['image']:r['current_class'] for r in difficulty}
        assert all(by_image[r.image]==r.difficulty for r in selected.itertuples())
        selected['complete_rate']=selected.complete_geometry/selected.path_states
        selected['quality_rate']=selected.quality_numeric/selected.path_states
        save_table('fusion_fixed_pool_k.csv',selected)
        summaries=[]
        for (level,k),f in selected.groupby(['difficulty','k']):
            summaries.append(dict(difficulty=level,k=int(k),pools=f.pool_id.nunique(),images=f.image.nunique(),
                path_states=int(f.path_states.sum()),complete_geometry=int(f.complete_geometry.sum()),
                complete_rate=f.complete_geometry.sum()/f.path_states.sum(),
                quality_numeric=int(f.quality_numeric.sum()),quality_rate=f.quality_numeric.sum()/f.path_states.sum(),
                original_R_pool_mean=f.R_mean.mean(),R_pool_n=f.R_mean.notna().sum(),
                same_k_V_pool_mean=f.same_k_floor_difference.mean(),V_pool_n=f.same_k_floor_difference.notna().sum(),
                B8L2_pool_mean=f.B8L2_mean.mean(),B8L2_pool_n=f.B8L2_mean.notna().sum(),
                D10_pool_mean=f.D10_mean.mean(),D10_pool_n=f.D10_mean.notna().sum()))
        save_table('fusion_fixed_panel_summary.csv',summaries)
        chart=pd.DataFrame(summaries)
        figure,axes=plt.subplots(1,3,figsize=(11,3.4))
        for level,english in [('简单','Easy'),('中等','Medium'),('困难','Hard')]:
            f=chart[chart.difficulty.eq(level)].sort_values('k')
            for ax,metric in zip(axes,['original_R_pool_mean','same_k_V_pool_mean','complete_rate']):
                ax.plot(f.k,f[metric],marker='o',label=f'{english} n={int(f.pools.iloc[0])}')
        for ax,title in zip(axes,['Original-answer R','Same-k output V','Complete geometry rate']):
            ax.set_title(title);ax.set_xticks([3,4,6]);ax.set_xlabel('True pool prefix k')
        axes[0].set_ylim(bottom=0);axes[1].set_ylim(bottom=0);axes[2].set_ylim(0,1.05)
        axes[0].legend(frameon=False,fontsize=8)
        figure.tight_layout();figure.savefig(OUT/'fusion_fixed_panel.png',dpi=160);plt.close(figure)
        left=selected[selected.k.eq(3)].set_index('pool_id')
        right=selected[selected.k.eq(6)].set_index('pool_id')
        changes=[]
        for pool in sorted(chosen):
            a,b=left.loc[pool],right.loc[pool]
            changes.append(dict(pool_id=pool,image=a.image,difficulty=a.difficulty,source_workers=int(a.source_workers),
                R_delta=b.R_mean-a.R_mean,V_delta=b.same_k_floor_difference-a.same_k_floor_difference,
                complete_rate_delta=b.complete_rate-a.complete_rate,
                quality_rate_delta=b.quality_rate-a.quality_rate,
                B8L2_delta=b.B8L2_mean-a.B8L2_mean,D10_delta=b.D10_mean-a.D10_mean))
        save_table('fusion_k3_to_k6.csv',changes)
        fusion_result=dict(source_version=fusion_manifest['version'],source_partial=fusion_manifest['partial_publication'],
            consumed_analysis_revision=fusion_manifest.get('analysis_revision','initial_random_publication'),
            completed_pools_at_build=fusion_status['completed_pools'],planned_pools=fusion_status['planned_pools'],
            fixed_pools=len(chosen),fixed_images=selected.image.nunique(),
            by_difficulty=selected.loc[selected.k.eq(3),'difficulty'].value_counts().to_dict(),
            panel='fusion_panel.json',source_status='research/fusion/wall_consensus_v1_process_20261017/STATUS.json')
        (OUT/'FUSION_STATUS.json').write_text(json.dumps(fusion_result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

    # Two compact figures: class-level quality and worker-matched differences.
    manual=summary[(summary.axis=='difficulty')&(summary.condition=='manual')&summary.stratum.isin(LEVELS)].set_index('stratum').reindex(LEVELS)
    figure,ax=plt.subplots(figsize=(8,4.2))
    x=np.arange(3)
    ax.bar(x-.18,manual.B8L2_mean,width=.32,label='B8L2 answers')
    ax.bar(x+.18,manual.B8L2_image_equal_mean,width=.32,label='B8L2 images')
    ax.set_xticks(x,['Easy','Medium','Hard']);ax.set_ylabel('Score (0–100)')
    ax.set_ylim(0,100);ax.legend(frameon=False)
    for i,n in enumerate(manual.quality_n):
        ax.text(i,max(manual.iloc[i].B8L2_mean,manual.iloc[i].B8L2_image_equal_mean)+2,
                'n='+str(int(n)),ha='center',fontsize=8)
    figure.tight_layout();figure.savefig(OUT/'manual_class_quality.png',dpi=160);plt.close(figure)
    p=pairs[(pairs.axis=='difficulty')&(pairs.condition=='manual')&(pairs.left=='简单')&(pairs.right=='困难')] if len(pairs) else pd.DataFrame()
    if len(p):
        figure,ax=plt.subplots(figsize=(8,3.8))
        ax.axvline(0,color='gray',linewidth=1)
        ax.scatter(p.B8L2_delta,np.arange(len(p)),s=25,label='B8L2')
        ax.scatter(p.D10_delta,np.arange(len(p)),s=25,marker='x',label='D10')
        ax.set_yticks(np.arange(len(p)),p.worker_id,fontsize=8)
        ax.set_xlabel('Hard minus easy: within-worker mean score')
        ax.legend(frameon=False);figure.tight_layout()
        figure.savefig(OUT/'worker_easy_hard_pair.png',dpi=160);plt.close(figure)
    source=dict(data_release='v1',input_revision=release['input_revision'],
        quality_revision=manifest['version'],difficulty_source=str((SOURCE/'difficulty_records.json').relative_to(ROOT)),
        score_source=str((SOURCE/'shared_records.csv').relative_to(ROOT)),
        input_manifest=manifest['input_manifest'],release_manifest='research/data/releases/v1/RELEASE.json',
        score_versions={m:manifest['parameters'][m]['version'] for m in ('B8L2','D10')},
        analysis_revision=version,quality_eligibility='shared quality_usable and exact current target',
        fusion_source='research/fusion/wall_consensus_v1_process_20261017',
        fusion_partial_analysis=fusion_result)
    (OUT/'SOURCES.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    contract=dict(record_ledger='one row per canonical object_id; 3222 full inventory, no score imputation',
        strata_summary='axis x condition x stratum; quality_use_filter defines scored subset; inventory always full group',
        worker_pairs='same worker in both strata; different images and task mix; no causal difficulty effect',
        source_time='source_active_time_seconds only where time_status usable; task-worker seconds, not target-specific for new batch',
        target_time='target_matched_time_seconds separate, missing preserved',
        score='B8L2 and D10 same quality_usable + reference target + quality_use; D10 changes direction scale only',
        low_tail='p10 only for >=5 scores, p25 otherwise still descriptive; null means insufficient or missing',
        computation='full_computed/floor_only_computed/input_uncomputable/pending_target partition inventory; quality exclusion separate',
        scene='doorway and OOS crossed; doorway_status and oos_subtype retained as separate axes; unknown not forced negative',
        group_weight='answer mean, image-equal mean, worker-equal mean separately; per-person pairs worker-equal')
    contract['fusion']='frozen completed ordinary Manual pools with random paths at k=3,4,6; pool then class mean, paths are not independent images; source publication status recorded separately'
    (OUT/'FIELD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    checks=dict(inventory=len(records),images=records.image_id.nunique(),workers=records.worker_id.nunique(),
        quality=int(records.quality_usable.sum()),status_counts=records.calculation_status.value_counts().to_dict(),
        group_partition=int(summary[summary.axis=='scene'].inventory_n.sum()),
        scene_quality_partition=int(summary[summary.axis=='scene'].quality_n.sum()),
        ordinary_manual=int(records.quality_usable.mul(records.quality_use.eq('ordinary_primary')).mul(records.condition.eq('manual')).sum()),
        target_consistent=True,release_version='v1')
    assert checks['group_partition']==len(records) and checks['scene_quality_partition']==checks['quality']
    assert checks['ordinary_manual']==1258 and checks['quality']==1911
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__':main()
