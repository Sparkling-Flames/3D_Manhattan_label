"""Frozen wall-fusion geometry: original B8L2, current frozen v6 reference/eligibility."""
import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .wall_consensus_quality_20261015 import save, measured, matched_changes
from .wall_consensus_population_20261014 import prepare_record, summarize_state
from .worker_wq_integration_20261015 import read, geometry_equal
from .scope_quality_scoring_20261016 import scoring_engine, MODEL_SOURCE
from .scope_reference_reconstruction_20261016 import build_reference_catalog
from .scope_quality_binding_20261016 import build_affected_records
from .descriptive_pool_gate_20261015 import build_pool_gate, RULE_VERSION
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/fusion/wall_consensus_b8l2_20261016'
OLD=ROOT/'research/fusion/wall_consensus_quality_20261015'
POP=ROOT/'research/fusion/wall_consensus_population_20261014'
POINTER=ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
VERSION='WQ-B8L2-20261015'
COMPONENTS=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
SHARED=ROOT/'research/statistics/b8l2_shared_v6_20261016'


def current_use(pool_allowed,ordinary,scene,subtype,binding_pending):
    if not pool_allowed:return 'source_pool_held'
    if subtype=='nonorthogonal_annotatable':return 'nonorthogonal_diagnostic'
    if 'oos' in scene:return 'oos_applicability_diagnostic'
    if 'doorway' in scene:return 'doorway_conditional_diagnostic'
    if not ordinary:return 'pending_image_diagnostic'
    if binding_pending:return 'target_binding_pending_diagnostic'
    return 'ordinary_conditional'


def finite(row,keys):
    return all(row.get(k) is not None and np.isfinite(float(row[k])) for k in keys)


def apply_scores(row,models,use):
    result=dict(row,B8L2=None,B8L2_floor_upper_bound=None,B8L2_no_D_diagnostic=None)
    if use=='source_pool_held':
        result.update(WQ=None,IoU3D100=None)
        return result
    if finite(row,COMPONENTS[:3]):
        vals=[float(row[k]) for k in COMPONENTS[:3]]
        if use not in ('nonorthogonal_diagnostic','oos_applicability_diagnostic'):
            result['B8L2_floor_upper_bound']=float(models.floor_upper_bound(*vals,params=models.B))
    if finite(row,COMPONENTS):
        vals=[float(row[k]) for k in COMPONENTS]
        if use=='nonorthogonal_diagnostic':
            vals[2]=0.
            result.update(WQ=None,B8L2_no_D_diagnostic=float(models.score(*vals,params=models.B)))
        elif use=='oos_applicability_diagnostic':result['WQ']=None
        else:
            result.update(WQ=float(models.score(*vals,params=models.WQ)),B8L2=float(models.score(*vals,params=models.B)))
    return result


def freeze():
    pointer=read(POINTER);difficulty=read(POINTER.parent/pointer['details'])
    assert difficulty['version']==pointer['version']
    bundle=load_current_bundle();projected,aliases=project_bundle(bundle)
    objects={aliases['records'][r['object_id']]:r for r in bundle['data']['objects']}
    projected_records={r['id']:r for im in projected['images'] for r in im['annotations']}
    pools,gates=build_pool_gate(bundle,difficulty['records'])
    gate_by={r['object_id']:r for r in gates};pool_by={(r['image_code'],r['condition']):r for r in pools}
    catalog=build_reference_catalog(bundle,difficulty['records']);refs={r['target_id']:r for r in catalog}
    bindings=build_affected_records(bundle,difficulty['records'],catalog)['affected_records']
    binding_by={r['object_id']:r for r in bindings}
    labels={r['image']:r for r in difficulty['records']}
    legacy={r['record_id']:r for r in read(OLD/'member_registry.json')+read(OLD/'special/member_registry.json')}
    images=[];member_rows=[]
    for group,oldimages in [('original12',read(POP/'input_snapshot.json')['images']),('special6',read(OLD/'special/input_snapshot.json')['images'])]:
        for im in oldimages:
            code=im['image'];label=labels[code];pool=pool_by[code,'manual'];members=[];changes=[]
            for r in im['records']:
                obj=objects[r['id']];g=gate_by[obj['object_id']]
                current=prepare_record(dict(projected_records[r['id']],source_pair_indices=obj['ordered_source_pair_indices']))
                equal=current['points']==r['points']
                if not equal:changes.append(r['id'])
                binding=binding_by.get(obj['object_id'])
                member=dict(image=code,record_id=r['id'],public_worker=r['worker'],object_id=obj['object_id'],
                    worker_id=obj['worker_id'],condition=obj['condition'],points_equal_frozen=equal,
                    pool_vote_eligible=g['pool_vote_eligible'],pool_vote_exclusion_reasons=g['pool_vote_exclusion_reasons'],
                    quality_gate=obj['main_quality_gate'],worker_quality_gate=obj['worker_quality_gate'],
                    original_holdout=legacy[r['id']]['original_holdout'],legacy_personnel_barriers=legacy[r['id']]['personnel_barriers'],
                    binding=binding,room_id=obj.get('room_id'),building_id=obj['building_id'])
                members.append(member);member_rows.append(member)
            frozen_workers={r['worker_id'] for r in members}
            same_pool=frozen_workers==set(pool['effective_worker_ids']) and all(r['pool_vote_eligible'] for r in members)
            ref=refs[label['target_version']]
            pending=any(m['binding'] and m['binding']['chosen_target_id']!=label['target_version'] for m in members)
            oldref=(next(r for r in read(OLD/'references'/f'{code}.json') if r['axis']=='selected_target') if group=='original12' else im['reference'])
            images.append(dict(image=code,image_id=im['image_id'],group=group,records=im['records'],members=members,
                source_pool=pool,difficulty=label,reference=ref,old_reference=oldref,
                members_equal_frozen=same_pool,changed_geometry_records=changes,
                old_difficulty=im.get('difficulty'),
                use=current_use(pool['pool_analysis_eligible'],pool['ordinary_difficulty_eligible'],label['scene'],label['oos_subtype'],pending),
                state_source=str((POP/'states'/f'{code}.json.gz' if group=='original12' else OLD/'special/states'/f'{code}.json.gz').relative_to(ROOT))))
    assert read(POINTER)==pointer,'CURRENT changed during preparation; rerun before freezing'
    snapshot=dict(difficulty_pointer=pointer,difficulty_version=difficulty['version'],pool_rule_version=RULE_VERSION,
        manifest=bundle['manifest'],fusion_version='MV50_gap7.5_all_members_median_frozen',images=images,
        scoring_source=str(MODEL_SOURCE.relative_to(ROOT)),score_version=VERSION)
    save(OUT/'input_snapshot.json',snapshot);save(OUT/'member_registry.json',member_rows)
    return snapshot


def old_subset_frame(im):
    if im['group']=='original12':
        frame=pd.read_csv(OLD/'scores'/f"{im['image']}.csv")
        return frame[frame.reference_axis.eq('selected_target')].set_index('subset')
    frame=pd.read_csv(OLD/'special'/f"{im['image']}_trajectory.csv")
    return frame.drop_duplicates('subset').set_index('subset')


def connect_shared_inputs(snapshot):
    """Join published frozen bindings; never import single-answer scores as fusion scores."""
    assert MODEL_SOURCE.read_bytes()==(SHARED/'inputs/working_models.py').read_bytes(),'shared scoring source differs'
    refs={r['target_id']:r for r in read(SHARED/'inputs/reference_catalog.json')}
    bindings={r['object_id']:r for r in read(SHARED/'inputs/binding_all.json')['affected_records']}
    checked=[]
    for im in snapshot['images']:
        ref=refs[im['reference']['target_id']]
        for key in ('points_1024x512','floor_xz_h','full_reference_available'):
            assert ref[key]==im['reference'][key],f'shared frozen reference mismatch: {im["image"]}/{key}'
        for member in im['members']:
            bound=bindings[member['object_id']]
            assert bound['condition']=='manual' and bound['worker_id']==member['worker_id']
            assert bound['pool_vote_eligible']==member['pool_vote_eligible']
            if member['binding']:
                assert member['binding']['chosen_target_id']==bound['chosen_target_id']
            member['binding']=bound
        checked.append(dict(image=im['image'],reference_id=ref['target_id'],reference_geometry_equal=True,
                            matched_members=len(im['members'])))
    save(OUT/'shared_input_comparison.json',dict(shared_source=str(SHARED.relative_to(ROOT)),
         reference_file='inputs/reference_catalog.json',binding_file='inputs/binding_all.json',checks=checked,
         single_annotation_scores_not_reused_as_fusion_scores=True))
    save(OUT/'input_snapshot.json',snapshot)
    save(OUT/'member_registry.json',[m for im in snapshot['images'] for m in im['members']])


def evaluate(im,engine,models):
    old=old_subset_frame(im);payload=json.load(gzip.open(ROOT/im['state_source'],'rt',encoding='utf-8'))
    ref=im['reference'];reference=dict(floor=ref['floor_xz_h'],points=ref['points_1024x512'] if ref['full_reference_available'] else None)
    oldref=im['old_reference'];same_geometry=False
    if reference['points'] is not None and oldref.get('points') is not None:
        same_geometry=geometry_equal(engine.geometry(reference['points']),engine.geometry(oldref['points']))
    rows=[];score_only=[];cache={};members={r['public_worker']:r for r in im['members']}
    for entry in payload['states']:
        workers=sorted(entry['workers']);subset='|'.join(workers);state=entry['automatic'];summary=summarize_state(state)
        previous=old.loc[subset].to_dict();selected=[members[w] for w in workers]
        old_use=previous.get('use','ordinary_conditional')
        old_use={'nonorthogonal_no_direction_quality':'nonorthogonal_diagnostic','applicability_unresolved_geometry_only':'oos_applicability_diagnostic','reference_hold':'source_pool_held'}.get(old_use,old_use)
        change=apply_scores(previous,models,old_use)
        score_only.append(dict(image=im['image'],subset=subset,k=state['n'],reference_id=previous['reference_id'],
            old_WQ=previous.get('WQ'),old_IoU3D100=previous.get('IoU3D100'),B8L2=change['B8L2'],
            B8L2_no_D_diagnostic=change['B8L2_no_D_diagnostic'],use='same_frozen_geometry_reference_and_historical_policy'))
        if not im['members_equal_frozen'] or im['changed_geometry_records']:
            result=dict(score_status='historical_members_or_geometry_changed',WQ=None,IoU3D100=None)
            use='source_pool_held';origin='historical_only'
        elif im['use']=='source_pool_held':
            result=dict(score_status='current_source_pool_held',WQ=None,IoU3D100=None);use=im['use'];origin='policy_hold'
        elif same_geometry and (finite(previous,COMPONENTS) or state['n']==2 or summary['below_four']):
            result={k:previous.get(k) for k in ['score_status','WQ','IoU3D100',*COMPONENTS,'height_mean_ratio','omission','extension']}
            use=im['use'];origin='reused_identical_reference_components'
        else:
            key=json.dumps([state['candidate'],summary['below_four'],state['n']==2],sort_keys=True)
            if key not in cache:cache[key]=measured(engine,state,reference)
            result=cache[key];use=im['use'];origin='measured_frozen_geometry_current_reference'
        result=apply_scores(result,models,use)
        clear=all(m['quality_gate']['status']=='candidate_pending_geometry' and m['worker_quality_gate']=='candidate_pending_geometry'
                  and not m['legacy_personnel_barriers'] for m in selected)
        holdout=any(m['original_holdout'] for m in selected)
        binding_clear=all(not m['binding'] or m['binding']['chosen_target_id']==ref['target_id'] for m in selected)
        primary=(use=='ordinary_conditional' and clear and not holdout and binding_clear and pd.notna(result['B8L2']))
        rows.append(dict(image=im['image'],image_id=im['image_id'],group=im['group'],subset=subset,
            member_record_ids='|'.join(sorted(m['record_id'] for m in selected)),worker_ids='|'.join(sorted(m['worker_id'] for m in selected)),
            condition='manual',difficulty=im['difficulty']['current_class'],scene=im['difficulty']['scene'],
            difficulty_version=SNAPSHOT_VERSION,reference_id=ref['target_id'],reference_version=ref['reference_version'],
            reference_axis='current_target',full_reference_available=ref['full_reference_available'],
            reference_geometry_equal_old=same_geometry,reference_id_equal_old=previous['reference_id']==ref['target_id'],
            source_pool_workers=im['source_pool']['n_effective_workers'],source_pool_allowed=im['source_pool']['pool_analysis_eligible'],
            members_equal_frozen=im['members_equal_frozen'],use=use,measurement_origin=origin,
            member_quality_restrictions_clear=clear,original_holdout=holdout,member_target_bindings_clear=binding_clear,
            primary_comparison_eligible=primary,formal_eligibility_newly_granted=False,
            score_version=VERSION,comparison_score_version='WQ-LS08-20261014',
            geometry_source=im['state_source'],**summary,**result))
    current=pd.DataFrame(rows);oldscore=pd.DataFrame(score_only)
    current.to_csv(OUT/'scores'/f"{im['image']}.csv",index=False,encoding='utf-8-sig')
    oldscore.to_csv(OUT/'score_only'/f"{im['image']}.csv",index=False,encoding='utf-8-sig')
    paths=[]
    for path,order in enumerate(payload['orders']):
        paths.extend(dict(image=im['image'],subset='|'.join(sorted(order[:k])),path=path,k=k) for k in range(1,len(order)+1))
    pd.DataFrame(paths).merge(current,on=['image','subset','k'],validate='many_to_one').to_csv(OUT/'paths'/f"{im['image']}.csv",index=False,encoding='utf-8-sig')
    return dict(image=im['image'],states=len(current),paths=len(paths),current_B8L2=int(current.B8L2.notna().sum()),remeasurements=len(cache))


def assisted_endpoints(snapshot,engine,models):
    rows=[]
    for im in snapshot['images']:
        if im['group']=='original12':
            payload=read(POP/'endpoints'/f"{im['image']}.json")
            state=payload['prior_assisted'];same_input=payload['endpoint_summary']['input_same_as_1008']
        else:
            path=ROOT/'analysis_results/consensus_delivery_20261008'/f"{im['image']}.json"
            state=read(path).get('assisted') if path.exists() else None
            same_input=im['members_equal_frozen'] and not im['changed_geometry_records']
        if state is None:continue
        ref=im['reference']
        if im['use']=='source_pool_held':result=dict(score_status='current_source_pool_held',WQ=None,IoU3D100=None)
        else:result=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512'] if ref['full_reference_available'] else None))
        result=apply_scores(result,models,im['use'])
        rows.append(dict(image=im['image'],version='historical_assisted',same_input_as_current_automatic=same_input,
            use=im['use'],reference_id=ref['target_id'],score_version=VERSION,
            interpretation='separate same-input endpoint' if same_input else 'historical input; not a paired current comparison',
            **summarize_state(state),**result))
    pd.DataFrame(rows).to_csv(OUT/'assisted_endpoints.csv',index=False,encoding='utf-8-sig')


def aggregate(snapshot):
    frame=pd.concat([pd.read_csv(OUT/'paths'/f"{im['image']}.csv") for im in snapshot['images']],ignore_index=True)
    frame.to_csv(OUT/'trajectory_scores.csv',index=False,encoding='utf-8-sig')
    unique=frame.drop_duplicates(['image','subset'])
    unique.to_csv(OUT/'subset_scores.csv',index=False,encoding='utf-8-sig')
    rows=[]
    for (image,k),g in frame.groupby(['image','k']):
        rows.append(dict(image=image,k=k,group=g.group.iloc[0],difficulty=g.difficulty.iloc[0],use=g.use.iloc[0],
            total_paths=len(g),B8L2_paths=int(g.B8L2.notna().sum()),IoU3D_paths=int(g.IoU3D100.notna().sum()),
            primary_paths=int(g.primary_comparison_eligible.sum()),B8L2_unavailable_rate=float(g.B8L2.isna().mean()),
            below_four_paths=int(g.below_four.sum()),two_person_deferred_paths=int(g.k.eq(2).sum()),
            no_connection_paths=int((~g.connection_available).sum()),B8L2_mean=g.B8L2.mean(),WQ_mean=g.WQ.mean(),
            IoU3D100_mean=g.IoU3D100.mean(),B8L2_no_D_mean=g.B8L2_no_D_diagnostic.mean(),
            primary_B8L2_mean=g.loc[g.primary_comparison_eligible,'B8L2'].mean()))
    pd.DataFrame(rows).to_csv(OUT/'by_image_k.csv',index=False,encoding='utf-8-sig')
    comparisons=[r for lo,hi in [(1,8),(8,16),(8,24),(16,24)] for metric in ['B8L2','WQ','IoU3D100'] for r in matched_changes(frame,lo,hi,metric)]
    pd.DataFrame(comparisons).to_csv(OUT/'matched_changes.csv',index=False,encoding='utf-8-sig')
    terminal=frame[frame.k.eq(frame.groupby('image').k.transform('max'))].drop_duplicates('image')
    terminal.to_csv(OUT/'automatic_endpoints.csv',index=False,encoding='utf-8-sig')
    inventory=[]
    for im in snapshot['images']:
        ref=im['reference'];label=im['difficulty'];previous=im['old_difficulty']
        old_class=previous.get('current_class') if isinstance(previous,dict) else previous
        inventory.append(dict(image=im['image'],image_id=im['image_id'],group=im['group'],
            old_difficulty=old_class,current_difficulty=label['current_class'],difficulty_version=snapshot['difficulty_version'],
            target_id=ref['target_id'],reference_version=ref['reference_version'],reference_method=ref['method'],
            old_full_reference=im['old_reference'].get('points') is not None,current_full_reference=ref['full_reference_available'],
            pool_workers=im['source_pool']['n_effective_workers'],pool_min3_pass=im['source_pool']['pool_min3_pass'],
            source_pool_allowed=im['source_pool']['pool_analysis_eligible'],use=im['use'],
            members_equal_frozen=im['members_equal_frozen'],changed_geometry_records='|'.join(im['changed_geometry_records']),
            geometry_source=im['state_source'],input_snapshot='input_snapshot.json'))
    pd.DataFrame(inventory).to_csv(OUT/'coverage_and_changes.csv',index=False,encoding='utf-8-sig')
    oldchanges=pd.concat([pd.read_csv(p) for p in sorted((OUT/'score_only').glob('*.csv'))])
    oldchanges.to_csv(OUT/'score_only_comparison.csv',index=False,encoding='utf-8-sig')
    pair_rows=[]
    for (image,k),g in frame.groupby(['image','k']):
        g=g.set_index('path')
        for pair in range(len(g)//2):
            a,b=g.loc[2*pair],g.loc[2*pair+1]
            pair_rows.append(dict(image=image,k=k,pair=pair,abs_B8L2_difference=abs(a.B8L2-b.B8L2),
                abs_WQ_difference=abs(a.WQ-b.WQ),abs_IoU3D100_difference=abs(a.IoU3D100-b.IoU3D100),
                subset_a=a.subset,subset_b=b.subset,both_current_quality=bool(pd.notna(a.B8L2) and pd.notna(b.B8L2))))
    geometry=pd.concat([pd.read_csv(POP/'same_k_pairs.csv'),pd.read_csv(OLD/'special/same_k_geometry.csv')],ignore_index=True)
    pd.DataFrame(pair_rows).merge(geometry,on=['image','k','pair'],validate='one_to_one').to_csv(OUT/'same_k_comparison.csv',index=False,encoding='utf-8-sig')
    save(OUT/'SUMMARY.json',dict(difficulty_version=snapshot['difficulty_version'],score_version=VERSION,
        path_states=len(frame),unique_subsets=len(unique),current_B8L2_states=int(frame.B8L2.notna().sum()),
        primary_states=int(frame.primary_comparison_eligible.sum()),current_IoU3D_states=int(frame.IoU3D100.notna().sum()),
        by_use=frame.groupby('use').agg(states=('k','size'),B8L2=('B8L2','count'),IoU3D=('IoU3D100','count')).reset_index().to_dict('records'),
        score_status=frame.score_status.value_counts().to_dict(),fusion_rerun=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for group,shape in [('original12',(3,4)),('special6',(2,3))]:
        fig,axs=plt.subplots(*shape,figsize=(16,10) if group=='original12' else (14,7))
        for ax,(code,g) in zip(axs.flat,pd.DataFrame(rows).query('group==@group').groupby('image')):
            ax.plot(g.k,g.B8L2_mean,'o-',ms=2,label='B8L2');ax.plot(g.k,g.WQ_mean,'--',label='old WQ same target')
            ax.plot(g.k,g.IoU3D100_mean,'s-',ms=2,label='3D IoU x100')
            ax.plot(g.k,100*(1-g.B8L2_unavailable_rate),':',color='gray',label='B8L2 available %')
            ax.set_title(code+'\n'+g.use.iloc[0],fontsize=8);ax.set_ylim(0,103);ax.grid(alpha=.2)
        axs.flat[0].legend(fontsize=7);fig.supxlabel('Number of workers');fig.tight_layout();fig.savefig(OUT/f'{group}_curves.png',dpi=150);plt.close(fig)


SNAPSHOT_VERSION=None


def main():
    global SNAPSHOT_VERSION
    parser=argparse.ArgumentParser();parser.add_argument('--aggregate-only',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ['scores','score_only','paths']:(OUT/name).mkdir(exist_ok=True)
    snapshot=read(OUT/'input_snapshot.json') if (OUT/'input_snapshot.json').exists() else freeze()
    connect_shared_inputs(snapshot)
    SNAPSHOT_VERSION=snapshot['difficulty_version']
    if not args.aggregate_only:
        with scoring_engine() as (engine,models):
            assert models.B.version==VERSION and models.B.direction_scale_deg==8 and models.B.pooling_order==2
            save(OUT/'score_parameters.json',asdict(models.B))
            for im in snapshot['images']:print(json.dumps(evaluate(im,engine,models)),flush=True)
            assisted_endpoints(snapshot,engine,models)
    aggregate(snapshot)


if __name__=='__main__':main()
