"""Consumer tables and matched-policy summaries of actual v1 fusion replays."""
import itertools
import gzip
import json
import numpy as np
import pandas as pd

from .wall_consensus_v1_process_20261017 import OUT, ROOT, save
from .wall_consensus_population_20261014 import footprint


def random_panels(frame,stability):
    descriptive=[];main=[]
    for pool,g in frame[frame.path_kind.eq('random')].groupby('pool_id'):
        for lo,hi in [(4,8),(8,16)]:
            if g.k.max()<hi:continue
            a=g[g.k.eq(lo)].set_index('path_id');b=g[g.k.eq(hi)].set_index('path_id')
            common=a[['B8L2','D10','main_comparison_allowed']].join(b[['B8L2','D10','main_comparison_allowed']],lsuffix='_from',rsuffix='_to')
            valid=common.dropna(subset=['B8L2_from','B8L2_to','D10_from','D10_to'])
            sv=stability[stability.pool_id.eq(pool)]
            v1=sv[sv.k.eq(lo)].set_index(['path_a','path_b']).floor_jaccard_difference
            v2=sv[sv.k.eq(hi)].set_index(['path_a','path_b']).floor_jaccard_difference
            paired=pd.concat([v1.rename('a'),v2.rename('b')],axis=1).dropna()
            keys=lambda series:sorted('|'.join(map(str,key)) for key in series.dropna().index)
            base=dict(pool_id=pool,image=g.image.iloc[0],condition=g.condition.iloc[0],layer=g.layer.iloc[0],
                difficulty=g.difficulty.iloc[0],k_from=lo,k_to=hi,paths=len(a),
                V_from=v1.mean(),V_to=v2.mean(),V_pairs_from=int(v1.notna().sum()),V_pairs_to=int(v2.notna().sum()),
                V_valid_pair_ids_from=json.dumps(keys(v1)),V_valid_pair_ids_to=json.dumps(keys(v2)),
                V_pair_sets_equal=keys(v1)==keys(v2),V_strict_pairs=len(paired),
                V_strict_from=paired.a.mean(),V_strict_to=paired.b.mean(),
                complete_from=int(a.complete_evaluable.sum()),complete_to=int(b.complete_evaluable.sum()))
            for scope,values,target in [('descriptive_including_holdouts',valid,descriptive),
                ('main_comparison',valid[valid.main_comparison_allowed_from & valid.main_comparison_allowed_to],main)]:
                if scope=='main_comparison' and values.empty:continue
                target.append(dict(base,analysis_scope=scope,paired_quality_paths=len(values),
                    B8L2_change=(values.B8L2_to-values.B8L2_from).mean(),D10_change=(values.D10_to-values.D10_from).mean()))
    return pd.DataFrame(descriptive),pd.DataFrame(main)


def run():
    frame=pd.read_csv(OUT/'trajectory_scores.csv',low_memory=False)
    unique=frame.drop_duplicates(['pool_id','subset'])
    snapshot=json.loads((OUT/'input_snapshot.json').read_text(encoding='utf-8'))
    objects={r['object_id']:r['id'] for im in snapshot['images'] for r in im['records']}
    rows={(r['pool_id'],r['subset']):r for r in unique.to_dict('records')}
    polygons={}
    for path in (OUT/'pools').glob('*/states.json.gz'):
        payload=json.load(gzip.open(path,'rt',encoding='utf-8'))
        for e in payload['states']:
            polygons[payload['pool_id'],e['subset']]=footprint(e['automatic']['candidate']['footprint'])
    def floor_difference(pool,a,b):
        x=polygons.get((pool,a));y=polygons.get((pool,b))
        return None if x is None or y is None else 1-x.intersection(y).area/x.union(y).area
    numeric_keys=['k','nodes','below_four','connection_available','complete_evaluable','floor_evaluable',
        'score_status','quality_allowed','main_comparison_allowed','same_target','B8L2','D10','IoU3D100',
        'diagnostic_B8L2','diagnostic_D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
        'R_symdiff_h2','R_union_normalized','R_valid_pairs','R_possible_pairs','source_active_seconds','source_time_available']
    profile_path=OUT/'request_inputs/fold_person_profiles.csv'
    if profile_path.exists():
        profiles=pd.read_csv(profile_path,keep_default_na=False)
        profile_lookup={(r['fold'],r['metric'],r['worker_id']):r for r in profiles.to_dict('records')}
        compositions=[]
        for row in unique.to_dict('records'):
            building=row['image'].rsplit('-',1)[0]
            for metric in ['B8L2','D10']:
                people=[profile_lookup.get((building,metric,w),{}) for w in row['member_workers'].split('|')]
                compositions.append(dict(pool_id=row['pool_id'],subset=row['subset'],classification_metric=metric,profile_scope='ordinary_manual_target_building_excluded',
                    Q_higher=sum(p.get('Q_group')=='higher' for p in people),Q_lower=sum(p.get('Q_group')=='lower' for p in people),
                    Q_unknown=sum(p.get('Q_group') not in ('higher','lower') for p in people),
                    **{'QT_'+g:sum(p.get('QT_group')==g for p in people) for g in ['higher_faster','higher_slower','lower_faster','lower_slower']},
                    QT_unknown=sum(p.get('QT_group') not in ('higher_faster','higher_slower','lower_faster','lower_slower') for p in people)))
        pd.DataFrame(compositions).to_csv(OUT/'subset_composition.csv',index=False,encoding='utf-8-sig')
    source=OUT/'request_inputs/TEAM_REQUESTS.json'
    if source.exists():
        requests=json.loads(source.read_text(encoding='utf-8'));results=[]
        for team in requests['teams']:
            pool=team['image_code']+'__'+team['condition'];ids=[objects.get(o) for o in team['object_ids']]
            key='|'.join(sorted(ids)) if all(ids) else ''
            row=rows.get((pool,key))
            known_pool=any(im['pool_id']==pool for im in snapshot['images'])
            missing_status='pending_requested_subset' if known_pool and not (OUT/'failures'/f'{pool}.json').exists() else 'pool_input_failure_or_not_admitted'
            results.append(dict(request_id=team['request_id'],pool_id=pool,image=team['image_code'],subset=key,
                status='completed' if row else missing_status,
                worker_ids='|'.join(sorted(team['worker_ids'])),
                **({k:row.get(k) for k in numeric_keys} if row else {})))
        result=pd.DataFrame(results);result.to_csv(OUT/'TEAM_RESULTS.csv',index=False,encoding='utf-8-sig')
        by_id=result.set_index('request_id');paired=[]
        for path in requests['paths']:
            if path['policy']=='random':continue
            for k,(rid,baseid) in enumerate(zip(path['prefix_request_ids'],path['matched_random_prefix_request_ids']),1):
                a=by_id.loc[rid];b=by_id.loc[baseid]
                row=dict(image=path['image_code'],building=path['building_id'],path_id=path['path_id'],k=k,
                    selection_metric=path['selection_metric'],policy=path['policy'],focus_support=path['policy_has_focus_support'],
                    request_id=rid,random_request_id=baseid,status=a.status,
                    both_main=bool(a.get('main_comparison_allowed',False)==True and b.get('main_comparison_allowed',False)==True))
                for metric in ['B8L2','D10','R_union_normalized','source_active_seconds','nodes']:
                    row[metric+'_policy']=a.get(metric,np.nan);row[metric+'_random']=b.get(metric,np.nan)
                    row[metric+'_difference']=row[metric+'_policy']-row[metric+'_random']
                row['policy_complete']=a.get('complete_evaluable',False);row['random_complete']=b.get('complete_evaluable',False)
                row['floor_difference_from_random']=floor_difference(a.pool_id,a.subset,b.subset)
                paired.append(row)
        pairs=pd.DataFrame(paired);pairs.to_csv(OUT/'worker_policy_vs_random.csv',index=False,encoding='utf-8-sig')
        coverage=[]
        for (metric,policy,k),part in pairs.groupby(['selection_metric','policy','k']):
            focus=part[part.focus_support==True];main=focus[focus.both_main==True]
            coverage.append(dict(selection_metric=metric,policy=policy,k=k,requested_images=len(part),
                focus_supported_images=len(focus),both_main_eligible_images=len(main),
                policy_complete=int(main.policy_complete.eq(True).sum()),random_complete=int(main.random_complete.eq(True).sum()),
                paired_quality_images=int((main.B8L2_difference.notna()&main.D10_difference.notna()).sum())))
        pd.DataFrame(coverage).to_csv(OUT/'worker_policy_coverage.csv',index=False,encoding='utf-8-sig')
        # One outcome per image at k; unsupported focus policies are explicit, not positive evidence.
        g=pairs[(pairs.focus_support==True)&(pairs.both_main==True)]
        summaries=[]
        for (metric,policy,k),part in g.groupby(['selection_metric','policy','k']):
            valid=part[part.B8L2_difference.notna() & part.D10_difference.notna()]
            summaries.append(dict(selection_metric=metric,policy=policy,k=k,images=len(valid),
                main_eligible_images=len(part),policy_complete=int(part.policy_complete.eq(True).sum()),
                random_complete=int(part.random_complete.eq(True).sum()),
                buildings=valid.building.nunique(),B8L2_difference=valid.B8L2_difference.mean(),
                D10_difference=valid.D10_difference.mean(),R_difference=valid.R_union_normalized_difference.mean(),
                source_seconds_difference=valid.source_active_seconds_difference.mean(),
                source_time_pairs=int(valid.source_active_seconds_difference.notna().sum()),
                B8L2_better=int((valid.B8L2_difference>0).sum()),B8L2_worse=int((valid.B8L2_difference<0).sum())))
        pd.DataFrame(summaries).to_csv(OUT/'worker_policy_summary.csv',index=False,encoding='utf-8-sig')
        direct=[]
        for metric,part in g.groupby('selection_metric'):
            for policy_a,policy_b in [('Q_higher_first','Q_lower_first'),('QT_higher_faster_first','QT_higher_slower_first'),('QT_lower_faster_first','QT_lower_slower_first')]:
                a=part[part.policy.eq(policy_a)].set_index(['image','k'])
                b=part[part.policy.eq(policy_b)].set_index(['image','k'])
                for index in a.index.intersection(b.index):
                    x=a.loc[index];y=b.loc[index]
                    if pd.isna(x.B8L2_policy) or pd.isna(y.B8L2_policy):continue
                    direct.append(dict(image=index[0],k=index[1],selection_metric=metric,policy_a=policy_a,policy_b=policy_b,
                        B8L2_difference=x.B8L2_policy-y.B8L2_policy,D10_difference=x.D10_policy-y.D10_policy,
                        R_difference=x.R_union_normalized_policy-y.R_union_normalized_policy,
                        source_seconds_difference=x.source_active_seconds_policy-y.source_active_seconds_policy))
        pd.DataFrame(direct).to_csv(OUT/'worker_direct_contrasts.csv',index=False,encoding='utf-8-sig')
        save(OUT/'TEAM_RESULT_STATUS.json',dict(requested_teams=len(result),completed_teams=int(result.status.eq('completed').sum()),
            completed_images=result[result.status.eq('completed')].image.nunique(),failed_teams=int(result.status.eq('pool_input_failure_or_not_admitted').sum()),
            pending_teams=int(result.status.eq('pending_requested_subset').sum()),
            request_schema=requests['schema'],data_release='v1',classification_and_metric_changes_separate=True))
    room_path=OUT/'request_inputs/PAIR_PROCESS_REQUESTS.json'
    if room_path.exists():
        room=json.loads(room_path.read_text(encoding='utf-8'));room_rows=[];room_stability=[]
        for pair in room['pairs']:
            for side,view in pair['views'].items():
                pool=view['image']+'__'+view['condition'];by_replay={}
                member_map={r['worker_id']:r for r in view['records']}
                for replay in pair['replays']:
                    by_replay[replay['replay_id']]={}
                    for k in range(1,len(replay['worker_order'])+1):
                        workers=replay['worker_order'][:k];key='|'.join(sorted(objects[member_map[w]['object_id']] for w in workers));r=rows.get((pool,key))
                        trace=dict(request_id=pair['request_id'],replay_id=replay['replay_id'],side=side,k=k,
                            worker_ids='|'.join(sorted(workers)),object_ids='|'.join(sorted(member_map[w]['object_id'] for w in workers)),
                            image=view['image'],pool_id=pool,subset=key,data_release='v1',
                            reference_id=view['reference']['target_id'],reference_version=view['reference']['reference_version'],
                            geometry_source=str((OUT/'pools'/pool/'states.json.gz').relative_to(ROOT)).replace('\\','/'),geometry_subset=key)
                        trace.update({name:r.get(name) for name in numeric_keys} if r else {})
                        trace.update(output_status=r['score_status'] if r else 'not_run',
                            failure_reason='' if r and r['score_status']=='complete_conditional' else (r.get('geometry_reason') or r['score_status']) if r else 'requested_geometry_not_available',
                            quality_use='reference_quality_conditional' if r and r['quality_allowed'] else 'diagnostic_or_unavailable')
                        room_rows.append(trace);by_replay[replay['replay_id']][k]=key
                for first,second in itertools.combinations(by_replay,2):
                    for k in by_replay[first].keys() & by_replay[second].keys():
                        a=by_replay[first][k];b=by_replay[second][k]
                        room_stability.append(dict(request_id=pair['request_id'],side=side,k=k,replay_a=first,replay_b=second,
                            same_subset=a==b,floor_jaccard_difference=floor_difference(pool,a,b)))
        pd.DataFrame(room_rows).to_csv(OUT/'same_room_trajectory.csv',index=False,encoding='utf-8-sig')
        room_frame=pd.DataFrame(room_rows)
        assert (room_frame.groupby(['request_id','replay_id','k']).worker_ids.nunique()==1).all()
        assert room_frame.B8L2.notna().equals(room_frame.D10.notna())
        pd.DataFrame(room_stability).to_csv(OUT/'same_room_within_view_stability.csv',index=False,encoding='utf-8-sig')
        save(OUT/'SAME_ROOM_PROCESS_RESULTS.json',dict(schema='same_room_pair_process_results_v1',data_release='v1',
            request_schema=room['schema'],results_csv=str((OUT/'same_room_trajectory.csv').relative_to(ROOT)).replace('\\','/'),
            within_view_stability_csv=str((OUT/'same_room_within_view_stability.csv').relative_to(ROOT)).replace('\\','/'),
            requests=[dict(request_id=p['request_id'],condition=p['condition'],declared_pool=p['declared_pool'],
                common_N=p['n_common_process'],endpoint='all_common_people_not_original_full_pool') for p in room['pairs']],
            requested_pairs=len(room['pairs']),requested_prefix_states=len(room_rows),
            actual_states=sum(r['output_status']!='not_run' for r in room_rows),
            not_run=sum(r['output_status']=='not_run' for r in room_rows),cross_view_geometry_intersection=False))
    stability=pd.read_csv(OUT/'same_k_stability.csv')
    descriptive,main=random_panels(frame,stability)
    descriptive.to_csv(OUT/'random_matched_changes.csv',index=False,encoding='utf-8-sig')
    main.to_csv(OUT/'random_matched_changes_main.csv',index=False,encoding='utf-8-sig')
    select=lambda x:x[(x.condition=='manual')&(x.layer=='ordinary')&(x.k_from==8)].dropna(subset=['B8L2_change','V_from','V_to'])
    descriptive_panel=select(descriptive);main_panel=select(main)
    descriptive_panel.to_csv(OUT/'random_8to16_descriptive_panel.csv',index=False,encoding='utf-8-sig')
    main_panel.to_csv(OUT/'random_8to16_main_panel.csv',index=False,encoding='utf-8-sig')
    main_panel.dropna(subset=['V_strict_from','V_strict_to']).to_csv(OUT/'random_8to16_main_strict_V.csv',index=False,encoding='utf-8-sig')
    panels=[]
    for scope,part,a,b in [('descriptive_including_holdouts',descriptive_panel,'V_from','V_to'),
        ('main_comparison',main_panel,'V_from','V_to'),('main_strict_paired_V',main_panel,'V_strict_from','V_strict_to')]:
        valid=part.dropna(subset=[a,b])
        panels.append(dict(analysis_scope=scope,images=len(valid),
            buildings=valid.image.str.rsplit('-',n=1).str[0].nunique(),
            Q_improved=int(valid.B8L2_change.gt(0).sum()),Q_decreased=int(valid.B8L2_change.lt(0).sum()),
            B8L2_mean_change=valid.B8L2_change.mean(),D10_mean_change=valid.D10_change.mean(),
            V_decreased=int(valid[b].lt(valid[a]).sum()),V_increased=int(valid[b].gt(valid[a]).sum()),
            V_mean_from=valid[a].mean(),V_mean_to=valid[b].mean(),
            unequal_endpoint_pair_sets=int((~valid.V_pair_sets_equal).sum())))
    pd.DataFrame(panels).to_csv(OUT/'random_8to16_panel_summary.csv',index=False,encoding='utf-8-sig')
    if source.exists():
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,2,figsize=(13,5))
        sample=main_panel
        axes[0].scatter(sample.V_to-sample.V_from,sample.B8L2_change,s=25,alpha=.7)
        axes[0].axhline(0,color='grey',lw=.8);axes[0].axvline(0,color='grey',lw=.8)
        axes[0].set(xlabel='Floor variability change (8 to 16)\nEndpoint-available pair means; not strictly paired',ylabel='Matched-path B8L2 change',
            title='Main-eligible Manual replay; n='+str(len(sample))+' images')
        summary=pd.DataFrame(summaries)
        selected=summary[(summary.selection_metric=='B8L2')&(summary.k==8)]
        axes[1].barh(selected.policy,selected.B8L2_difference,color='#427cb5')
        for i,r in enumerate(selected.itertuples()):axes[1].text(r.B8L2_difference,i,'  n='+str(r.images),va='center',fontsize=8)
        axes[1].axvline(0,color='grey',lw=.8)
        axes[1].margins(x=.15)
        axes[1].set(xlabel='B8L2 difference from matched random prefix',title='B8L2 class selection; k=8; panels differ')
        fig.tight_layout();fig.savefig(OUT/'process_comparison.png',dpi=150);fig.savefig(OUT/'process_comparison.svg');plt.close(fig)
    # Canonical source subset is cached once; identical-set replays must have identical saved outcomes.
    invariants=frame.groupby(['pool_id','subset'])[['nodes','B8L2','D10','R_symdiff_h2']].nunique(dropna=False)
    assert (invariants<=1).all().all()
    assert frame.loc[frame.k.eq(2),'diagnostic_B8L2'].isna().all()
    assert frame.loc[frame.layer.eq('oos_diagnostic'),'B8L2'].isna().all()
    assert frame.B8L2.notna().equals(frame.D10.notna())
    save(OUT/'CHECKS.json',dict(data_release='v1',source_subset_outcomes_consistent=True,k2_quality_missing=True,
        OOS_quality_count=0,same_mask_B8L2_D10=True,actual_rows=len(frame),unique_pool_subsets=len(unique),
        completed_images=frame.image.nunique(),no_interpolation=True,no_all_pool_identity_used=True))
    status=json.loads((OUT/'STATUS.json').read_text(encoding='utf-8'))
    status['classification_selection']='target-building-excluded Q/T requests; fixed-team metrics and metric-driven re-selection remain separate'
    if (OUT/'TEAM_RESULT_STATUS.json').exists():status['worker_results']=json.loads((OUT/'TEAM_RESULT_STATUS.json').read_text(encoding='utf-8'))
    if (OUT/'SAME_ROOM_PROCESS_RESULTS.json').exists():status['same_room_results']=json.loads((OUT/'SAME_ROOM_PROCESS_RESULTS.json').read_text(encoding='utf-8'))
    save(OUT/'STATUS.json',status)
    print('Consumer tables written; output consistency checks passed.',flush=True)


if __name__=='__main__':run()
