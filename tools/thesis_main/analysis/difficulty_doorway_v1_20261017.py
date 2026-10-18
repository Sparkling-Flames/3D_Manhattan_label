"""消费当前门洞随机过程；固定机会/主资格面板，不重建融合或改参考。"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .difficulty_v1_analysis_20261017 import ROOT, group_summary

BASE=ROOT/'research/difficulty/difficulty_v1_analysis_20261017'
OUT=BASE/'doorway'
FUSION=ROOT/'research/fusion/wall_consensus_v1_process_20261017'
QUALITY=ROOT/'research/quality/quality_b8l2_d10_20261017'


def panel_summary(nodes, stability):
    """Input includes every declared node, including failures and diagnostic-only nodes."""
    q=nodes[nodes.main_comparison_allowed & nodes.B8L2.notna()]
    assert q.D10.notna().all()
    valid=stability[stability.both_complete_floor & stability.floor_jaccard_difference.notna()]
    different=valid[~valid.same_subset]
    time=nodes[nodes.source_time_available & nodes.source_active_seconds.notna()]
    return dict(images=nodes.pool_id.nunique(),opportunities=len(nodes),complete=int(nodes.complete_evaluable.sum()),
        complete_rate=nodes.complete_evaluable.mean(),quality=len(q),quality_rate=len(q)/len(nodes),
        quality_images=q.pool_id.nunique(),
        B8L2_answer_equal_mean=q.B8L2.mean(),B8L2_image_equal_mean=q.groupby('pool_id').B8L2.mean().mean(),
        D10_image_equal_mean=q.groupby('pool_id').D10.mean().mean(),
        R_image_equal_mean=nodes.groupby('pool_id').R_union_normalized.mean().mean(),
        R_images=int(nodes.groupby('pool_id').R_union_normalized.count().gt(0).sum()),
        V_image_equal_mean=valid.groupby('pool_id').floor_jaccard_difference.mean().mean(),
        V_images=valid.pool_id.nunique(),V_pairs=len(valid),V_possible_pairs=len(stability),
        V_different_subset_image_mean=different.groupby('pool_id').floor_jaccard_difference.mean().mean(),
        V_same_subset_pairs=int(valid.same_subset.sum()),
        time_n=len(time),time_rate=len(time)/len(nodes),time_images=time.pool_id.nunique(),
        time_mean_seconds=time.source_active_seconds.mean(),unique_pool_subsets=nodes[['pool_id','subset']].drop_duplicates().shape[0])


def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    OUT.mkdir(exist_ok=True)
    consumed=json.loads((FUSION/'MANIFEST.json').read_text(encoding='utf-8'))
    status=json.loads((FUSION/'STATUS.json').read_text(encoding='utf-8'))
    shared_manifest=json.loads((QUALITY/'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))
    assert consumed['data_release']=='v1' and not consumed['partial_publication']
    # Preserve the 312 ordinary rows; check shared public columns against the current source.
    ordinary_path=BASE/'fusion_fixed_pool_k.csv'
    ordinary_bytes=ordinary_path.read_bytes()
    ordinary=pd.read_csv(ordinary_path)
    current=pd.read_csv(FUSION/'by_pool_k.csv')
    current=current[current.path_kind.eq('random')]
    columns=[c for c in ordinary if c in current]
    keys=['pool_id','k','path_kind']
    checked=ordinary[keys].merge(current,on=keys,validate='one_to_one')[columns]
    pd.testing.assert_frame_equal(ordinary[columns].reset_index(drop=True),checked.reset_index(drop=True),check_dtype=False)
    assert len(ordinary)==312 and ordinary.pool_id.nunique()==104

    inventory=pd.read_csv(QUALITY/'shared_records.csv',low_memory=False)
    difficulty=json.loads((QUALITY/'difficulty_records.json').read_text(encoding='utf-8'))
    raw=pd.read_csv(FUSION/'trajectory_scores.csv',low_memory=False)
    stability=pd.read_csv(FUSION/'same_k_stability.csv')
    door_inventory=inventory[inventory.is_doorway].copy()
    assert len(door_inventory)==246 and door_inventory.image_id.nunique()==20
    assert door_inventory.condition.eq('manual').all()
    qualified=door_inventory[door_inventory.quality_usable]
    assert len(qualified)==188 and qualified.image_id.nunique()==15 and qualified.worker_id.nunique()==24
    assert not qualified.is_oos.any()
    image_lookup={r['image']:r for r in difficulty}
    q_images=set(qualified.image_code)
    random=raw[raw.path_kind.eq('random')&raw.layer.eq('doorway_conditional')].copy()
    assert len(random)==808 and random.image.nunique()==17
    assert random.condition.eq('manual').all()
    assert set(random.image)<=set(door_inventory.loc[~door_inventory.is_oos,'image_code'])
    for r in random[['image','reference_id']].drop_duplicates().itertuples():
        assert r.reference_id==image_lookup[r.image]['target_version']
    assert random[['pool_id','path_id','k']].duplicated().sum()==0
    assert random.B8L2.notna().eq(random.D10.notna()).all()
    random['primary_score_usable']=random.main_comparison_allowed & random.B8L2.notna()
    pools=set(random.pool_id)
    main_pools=set(random.loc[random.image.isin(q_images),'pool_id'])
    assert len(pools)==17 and len(main_pools)==15
    groups=[('opportunity17',pools,[1,3,4,6]),('primary15',main_pools,[1,3,4,6])]
    for k in [8,12]:
        possible=set(random.loc[random.k.eq(k),'pool_id'])
        groups += [(f'opportunity_Nge{k}',possible,[1,3,4,6]+([8] if k==8 else [8,12])),
                   (f'primary_Nge{k}',possible&main_pools,[1,3,4,6]+([8] if k==8 else [8,12]))]
    summaries=[]; panels=[]; pool_stats=[]
    for name,ids,ks in groups:
        for pool in sorted(ids):panels.append(dict(panel=name,pool_id=pool,image=random.loc[random.pool_id.eq(pool),'image'].iloc[0],
            main_panel=pool in main_pools,ks='|'.join(map(str,ks))))
        for k in ks:
            x=random[random.pool_id.isin(ids)&random.k.eq(k)]
            assert x.pool_id.nunique()==len(ids) and len(x)==4*len(ids)
            v=stability[stability.pool_id.isin(ids)&stability.k.eq(k)]
            summaries.append(dict(panel=name,k=k,**panel_summary(x,v)))
            for pool,z in x.groupby('pool_id'):
                vv=v[v.pool_id.eq(pool)]
                pool_stats.append(dict(panel=name,pool_id=pool,image=z.image.iloc[0],k=k,**panel_summary(z,vv)))
    summary=pd.DataFrame(summaries)
    summary.to_csv(OUT/'panel_summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(panels).to_csv(OUT/'panels.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(pool_stats).to_csv(OUT/'pool_k.csv',index=False,encoding='utf-8-sig')
    random.to_csv(OUT/'random_nodes.csv',index=False,encoding='utf-8-sig')
    stability[stability.pool_id.isin(pools)].to_csv(OUT/'same_k_pairs.csv',index=False,encoding='utf-8-sig')
    door_inventory.to_csv(OUT/'inventory_records.csv',index=False,encoding='utf-8-sig')
    image_records=[]
    for image,f in door_inventory.groupby('image_code'):
        image_records.append(dict(image=image,oos=bool(f.is_oos.iloc[0]),doorway_status=f.doorway_status.iloc[0],
            doorway_conditional_process=image+'__manual' in pools,
            oos_diagnostic_random_process=bool(((raw.image==image)&raw.path_kind.eq('random')&raw.layer.eq('oos_diagnostic')).any()),
            **group_summary(f)))
    pd.DataFrame(image_records).to_csv(OUT/'image_coverage.csv',index=False,encoding='utf-8-sig')

    worker=pd.read_csv(BASE/'worker_strata.csv')
    worker=worker[worker.axis.eq('scene')&worker.condition.eq('manual')&worker.stratum.isin(['非门洞∩非OOS','门洞∩非OOS'])]
    worker.to_csv(OUT/'person_scene.csv',index=False,encoding='utf-8-sig')
    pairs=pd.read_csv(BASE/'worker_pairs.csv')
    pairs=pairs[pairs.axis.eq('scene')&pairs.condition.eq('manual')].copy()
    extra=worker.pivot(index='worker_id',columns='stratum',values=['B8L2_sd','B8L2_p10','source_time_n','quality_target_time_n'])
    pairs['B8L2_sd_delta']=pairs.worker_id.map(extra['B8L2_sd']['门洞∩非OOS']-extra['B8L2_sd']['非门洞∩非OOS'])
    pairs['B8L2_p10_delta']=pairs.B8L2_p10_right-pairs.B8L2_p10_left
    pairs['source_time_ge3_each']=pairs.source_time_n_left.ge(3)&pairs.source_time_n_right.ge(3)
    pairs.to_csv(OUT/'person_scene_pairs.csv',index=False,encoding='utf-8-sig')
    pair_summary=dict(workers=len(pairs),quality_ge3_each=int((pairs.n_left.ge(3)&pairs.n_right.ge(3)).sum()),
        B8L2_median_delta=pairs.B8L2_delta.median(),D10_median_delta=pairs.D10_delta.median(),
        higher_on_doorway=int(pairs.B8L2_delta.gt(0).sum()),
        B8L2_sd_median_delta=pairs.B8L2_sd_delta.median(),
        low_tail_workers=int(pairs.B8L2_p10_delta.notna().sum()),low_tail_median_delta=pairs.B8L2_p10_delta.median(),
        time_workers=int(pairs.source_time_delta.notna().sum()),time_ge3_each=int(pairs.source_time_ge3_each.sum()),
        time_median_delta_seconds=pairs.source_time_delta.median())
    write_json(OUT/'person_summary.json',pair_summary)

    # Predeclared cases illustrate valid output, loss of complete output and mixed targets.
    cases=[]
    for image,kind in [('S9hNv5qa7GM-08','complete_output'),('7y3sRwLe3Va-06','insufficient_endpoint_nodes'),
                       ('B6ByNegPMKs-43','mixed_targets'),('q9vSo1VnCiC-24','mixed_targets')]:
        f=random[random.image.eq(image)]; end=f[f.k.eq(f.original_pool_n.max())]
        cases.append(dict(image=image,case=kind,pool_id=f.pool_id.iloc[0],N=int(f.original_pool_n.max()),
            endpoints=len(end),endpoint_complete=int(end.complete_evaluable.sum()),
            endpoint_quality=int(end.primary_score_usable.sum()),nodes='|'.join(map(str,sorted(end.nodes.unique()))),
            same_target=bool(f.same_target.all()),photo=image_lookup[image]['photo'],
            existing_review='research/difficulty/difficulty_scope_resolution_20261016/review.html',
            user_adjudication_needed=False))
    pd.DataFrame(cases).to_csv(OUT/'cases.csv',index=False,encoding='utf-8-sig')

    fig,axes=plt.subplots(2,2,figsize=(10,7))
    for name,label in [('opportunity17','17 opportunity images'),('primary15','15 primary images')]:
        f=summary[summary.panel.eq(name)].sort_values('k')
        for ax,field in zip(axes.flat,['B8L2_image_equal_mean','R_image_equal_mean','V_image_equal_mean','complete_rate']):
            ax.plot(f.k,f[field],marker='o',label=label)
    for ax,title in zip(axes.flat,['B8L2: quality-available images','Original-answer R','Same-k output V','Complete geometry rate']):
        ax.set_title(title);ax.set_xticks([1,3,4,6]);ax.set_xlabel('k');ax.set_ylim(bottom=0)
    axes[0,0].set_ylim(0,100);axes[1,1].set_ylim(0,1.05);axes[0,0].legend(fontsize=8,frameon=False)
    axes[0,1].set_ylim(0,summary.loc[summary.panel.isin(['opportunity17','primary15']),'R_image_equal_mean'].max()*1.12)
    fig.tight_layout();fig.savefig(OUT/'doorway_process.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.5))
    for name,label in [('opportunity17','17 opportunity images'),('primary15','15 primary images')]:
        f=summary[summary.panel.eq(name)].sort_values('k')
        axes[0].plot(f.k,f.quality_rate,marker='o',label=label)
        axes[1].plot(f.k,f.time_rate,marker='o',label=label)
    for ax,title in zip(axes,['Primary score availability','All-member source time coverage']):
        ax.set_title(title);ax.set_xticks([1,3,4,6]);ax.set_xlabel('k');ax.set_ylim(0,1.05)
    axes[0].legend(frameon=False,fontsize=8)
    fig.tight_layout();fig.savefig(OUT/'doorway_coverage.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4.5))
    for ax,col,title in [(axes[0],'B8L2_delta','Doorway minus ordinary: B8L2'),(axes[1],'source_time_delta','Doorway minus ordinary: mean source seconds')]:
        f=pairs[pairs[col].notna()].sort_values(col)
        ax.axvline(0,color='gray',lw=1);ax.scatter(f[col],range(len(f)),s=18)
        ax.set_yticks(range(len(f)),f.worker_id,fontsize=7);ax.set_title(title,fontsize=10)
    fig.tight_layout();fig.savefig(OUT/'person_scene_differences.png',dpi=160);plt.close(fig)
    assert ordinary_path.read_bytes()==ordinary_bytes
    check=dict(data_release='v1',inventory=246,images=20,quality=188,quality_images=15,quality_workers=24,
        oos_intersection_records=int(door_inventory.is_oos.sum()),oos_intersection_images=int(door_inventory.loc[door_inventory.is_oos,'image_id'].nunique()),
        random_images=17,random_nodes=len(random),random_complete=int(random.complete_evaluable.sum()),
        main_quality_nodes=int(random.primary_score_usable.sum()),time_nodes=int(random.source_time_available.sum()),
        ordinary_104_rows_unchanged=312,current_fusion_public_fields_equal=True,
        high_k_panel_sizes={name:len(ids) for name,ids,_ in groups},manual_adjudication_needed=[])
    write_json(OUT/'CHECKS.json',check)
    write_json(OUT/'SOURCES.json',dict(analysis_revision='doorway_v1_analysis_20261017_r1',data_release='v1',
        quality_manifest=shared_manifest,fusion_manifest=consumed,
        fusion_status=dict(completed_pools=status['completed_pools'],completed_images=status['completed_images'],path_states=status['path_states']),
        auxiliary_fields='source r2 payload including restored auxiliary values and failure reasons copied into random_nodes; summaries use stable main-score/geometry fields; auxiliary interpretation not expanded',
        auxiliary_nonmissing={c:int(random[c].notna().sum()) for c in ['floor_WQ_upper_bound','boundary_loss','height_loss']},
        low_people='current pool gate preserved; no collection started'))
    write_json(OUT/'FIELD_CONTRACT.json',dict(key_random_nodes=['pool_id','path_id','k'],
        panels='opportunity17 includes two mixed-target diagnostic pools; primary15 is frozen from individually quality-eligible doorway images, never selected by fused score',
        main_Q='main_comparison_allowed AND nonmissing B8L2/D10; same reference masks; failed states stay in opportunities',
        R='source-answer disagreement, pool mean then image mean; k1 undefined',
        V='same-k valid output pairs, pool mean then image mean; valid/possible and identical subset counts retained',
        time='all members source_active_seconds observed; no missing=0, no target-time fabrication',
        high_k='N>=8 and N>=12 have separately frozen image panels and their own earlier-k baselines',
        low_tail='person p10 only >=5 quality answers each side; no independent difficulty validation'))
    write_json(BASE/'CROSS_MODULE_INPUTS.json',dict(data_release='v1',analysis_revision='difficulty_doorway_v1_20261017_r1',
        quality_version=shared_manifest['version'],fusion_version=consumed['version'],
        fusion_analysis_revision=consumed['analysis_revision'],fusion_partial_publication=consumed['partial_publication'],
        ordinary_fixed_panel='research/difficulty/difficulty_v1_analysis_20261017/fusion_fixed_pool_k.csv',
        ordinary_panel_rows=312,doorway=dict(root='research/difficulty/difficulty_v1_analysis_20261017/doorway',
        summary='panel_summary.csv',panel_members='panels.csv',pool_k='pool_k.csv',nodes='random_nodes.csv',
        pairwise_stability='same_k_pairs.csv',worker_pairs='person_scene_pairs.csv',worker_strata='person_scene.csv',
        worker_summary='person_summary.json',coverage='image_coverage.csv',
        inventory='inventory_records.csv',cases='cases.csv',figures=['doorway_process.png','doorway_coverage.png','person_scene_differences.png'],
        field_contract='FIELD_CONTRACT.json',source='SOURCES.json',checks='CHECKS.json')))
    print(json.dumps(check,ensure_ascii=False))


if __name__=='__main__':main()
