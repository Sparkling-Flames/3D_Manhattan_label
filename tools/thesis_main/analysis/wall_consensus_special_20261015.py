"""Scene-selected special-layer diagnostics; frozen fusion, no score-based selection."""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import argparse
import gzip
import json
import zipfile
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from .wall_consensus_quality_20261015 import ROOT,OUT,ARCHIVE,VERSION,save,measured
from .worker_wq_integration_20261015 import read,frozen_engine
from .wall_consensus_population_20261014 import prepare_record,compact,summarize_state,automatic_prefixes,compare_outputs
from .consensus_delivery_20261008 import fuse
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle

SPECIAL=OUT/'special'


def special_use(scene,subtype,hold):
    if hold:return 'reference_hold'
    if subtype=='nonorthogonal_annotatable':return 'nonorthogonal_no_direction_quality'
    if 'oos' in scene:return 'applicability_unresolved_geometry_only'
    if scene=='doorway_annotatable':return 'doorway_conditional'
    return 'doorway_scope_unresolved_diagnostic'


def prepare():
    bundle=load_current_bundle();data,aliases=project_bundle(bundle)
    objects={aliases['records'][r['object_id']]:r for r in bundle['data']['objects']}
    labels=read(ROOT/'analysis_results/difficulty_scope_preferred_20261011/current_259.json')['records']
    current={r['code']:r for r in data['images']}
    old={r['image']:r for r in read(ROOT/'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json')['images']}
    outputs={r['image']:r for r in read(ROOT/'analysis_results/consensus_delivery_20261008/outputs.json')}
    registry=read(ROOT/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json')
    holds={r['image_id']:r['classification'] for name in ('confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine') for r in registry[name]}
    inventory=[];images=[]
    for d in labels:
        if not ('oos' in d['scene'] or 'doorway' in d['scene']):continue
        im=current[d['image']];records=[];failures=[]
        for r in im['annotations']:
            if not(r['condition']=='manual' and r['independent'] and r['consensus_eligible']):continue
            try:records.append(prepare_record(dict(r,source_pair_indices=objects[r['id']]['ordered_source_pair_indices'])))
            except ValueError as e:failures.append(dict(id=r['id'],reason=str(e)))
        records.sort(key=lambda r:r['worker'])
        assert len({r['worker'] for r in records})==len(records)
        ref=dict(id=d['target_version'],floor=d['selected']['floor'],points=None)
        for r in im['references']:
            if objects[r['id']]['object_id']==ref['id']:
                ref['points']=prepare_record(r)['points']
        hold=holds.get(d['image_id'])
        use=special_use(d['scene'],d['oos_subtype'],hold)
        source_same=False
        if d['image'] in old:
            source_same={r['id']:r['points'] for r in old[d['image']]['records']}=={r['id']:r['points'] for r in records}
        meta=dict(image=d['image'],image_id=d['image_id'],scene=d['scene'],oos_subtype=d['oos_subtype'],
            doorway_status=d['doorway_status'],reference_id=ref['id'],reference_hold=hold,
            full_reference_available=ref['points'] is not None,current_manual_pool_n=len(records),
            all_condition_counts=json.dumps(Counter(r['condition'] for r in im['annotations'])),
            consensus_gate_counts=json.dumps(Counter(r['main_consensus_gate']['status'] for r in im['annotations'])),
            pool_input_failures=json.dumps(failures),prior177_available=d['image'] in outputs,
            prior_pool_same_coordinates=source_same,use=use,condition='manual',
            difficulty=d['current_class'],conditional_difficulty=d['conditional_difficulty'])
        inventory.append(meta);images.append(dict(meta,records=records,reference=ref))
    # Coverage/scene choice is fixed before measuring scores: all clear doorway and nonorthogonal
    # cases, existing unresolved-OOS endpoint, plus largest difficult-doorway pool (code tie-break).
    chosen=[im for im in images if im['scene']=='doorway_annotatable' or im['oos_subtype']=='nonorthogonal_annotatable' or (im['prior177_available'] and 'oos' in im['scene'])]
    difficult=sorted([im for im in images if im['scene']=='doorway_difficult' and im['current_manual_pool_n']>=3],key=lambda x:(-x['current_manual_pool_n'],x['image']))
    if difficult:chosen.append(difficult[0])
    chosen_codes={r['image'] for r in chosen}
    for r in inventory:r['selected_for_limited_panel']=r['image'] in chosen_codes
    pd.DataFrame(inventory).to_csv(SPECIAL/'coverage_inventory.csv',index=False,encoding='utf-8-sig')
    save(SPECIAL/'input_snapshot.json',dict(source='current loader, separate manual exploratory pools, 2026-10-15',images=chosen))
    gates={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    save(SPECIAL/'member_registry.json',[dict(image=im['image'],public_worker=r['worker'],**gates[r['id']])
        for im in chosen for r in im['records']])
    save(SPECIAL/'DESIGN.json',dict(seed=20261015,paths=8,selection='all annotatable doorways; all explicitly nonorthogonal annotatable; unresolved OOS with prior177 output; largest difficult doorway pool with lexical tie-break',
        selected_images=sorted(chosen_codes),fusion='MV50 gap7.5 all-source median; no GT input',
        full_quality_policy='nonorthogonal WQ suppressed; WQ_no_D diagnostic only; unknown OOS geometry only; reference holds no reference scoring',
        no_formal_eligibility_granted=True))
    return chosen


def restrict(row,use):
    if use=='nonorthogonal_no_direction_quality':
        row['WQ']=None;row['floor_WQ_upper_bound']=None
        row['score_status']='nonorthogonal_diagnostic' if row.get('IoU3D100') is not None else row['score_status']
    elif use=='applicability_unresolved_geometry_only':
        for key in ('WQ','WQ_no_D','floor_WQ_upper_bound'):row[key]=None
        row['score_status']='applicability_unresolved_diagnostic' if row.get('IoU3D100') is not None else row['score_status']
    return row


def run_image(im):
    code=im['image'];records=im['records'];ref=im['reference'];n=len(records)
    if json.loads(im['pool_input_failures']):return dict(image=code,status='whole_pool_input_failure')
    rng=np.random.default_rng(20261015);workers=[r['worker'] for r in records]
    orders=[list(rng.permutation(workers)) for _ in range(8)]
    cache={};rows=[];measurement_cache={}
    gate={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    with zipfile.ZipFile(ARCHIVE) as archive,frozen_engine(archive) as engine:
        if ref['points']:
            floor=np.asarray(engine.geometry(ref['points'])['bottom3d'])[:,[0,2]]
            assert Polygon(floor).symmetric_difference(Polygon(ref['floor'])).area<1e-7,'selected floor/full reference mismatch'
        def score(state):
            key=json.dumps(state['candidate'],sort_keys=True)+str(state['n']==2)
            if key not in measurement_cache:
                if im['reference_hold']:
                    measurement_cache[key]=dict(score_status='reference_hold',WQ=None,IoU3D100=None)
                else:measurement_cache[key]=restrict(measured(engine,state,ref),im['use'])
            return measurement_cache[key]
        for path,order in enumerate(orders):
            states=automatic_prefixes(records,order,cache)
            for k,state in enumerate(states,1):
                members=set(order[:k]);rs=[r for r in records if r['worker'] in members]
                rows.append(dict(image=code,image_id=im['image_id'],path=path,subset='|'.join(sorted(members)),
                    member_record_ids='|'.join(sorted(r['id'] for r in rs)),worker_ids='|'.join(sorted(gate[r['id']]['worker_id'] for r in rs)),
                    original_holdout=any(gate[r['id']]['original_holdout'] for r in rs),
                    restricted_members='|'.join(r['id'] for r in rs if gate[r['id']]['role']!='manual_development_candidate'),
                    scene=im['scene'],use=im['use'],reference_id=ref['id'],reference_axis='selected_target',condition='manual',
                    fusion_version='MV50_gap7.5_automatic',score_version=VERSION,**summarize_state(state),**score(state)))
        endpoint=states[-1];endpoint_rows=[dict(image=code,version='current_automatic',source_input='special/input_snapshot.json',
            reference_id=ref['id'],use=im['use'],**summarize_state(endpoint),**score(endpoint))]
        historical=ROOT/'analysis_results/consensus_delivery_20261008'/f'{code}.json'
        if historical.exists():
            prior=read(historical)
            for version in ('automatic','assisted'):
                if prior.get(version):endpoint_rows.append(dict(image=code,version='prior_'+version,source_input='population/inputs.json',
                    current_input_equal=im['prior_pool_same_coordinates'],reference_id=ref['id'],use=im['use'],
                    **summarize_state(prior[version]),**score(prior[version])))
    (SPECIAL/'states').mkdir(exist_ok=True)
    with gzip.open(SPECIAL/'states'/f'{code}.json.gz','wt',encoding='utf-8') as f:
        json.dump(dict(image=code,orders=orders,states=[dict(workers=list(key),automatic=compact(s)) for key,s in cache.items()]),f,ensure_ascii=False)
    pd.DataFrame(rows).to_csv(SPECIAL/f'{code}_trajectory.csv',index=False,encoding='utf-8-sig')
    save(SPECIAL/f'{code}_endpoints.json',endpoint_rows)
    return dict(image=code,path_states=len(rows),unique_subsets=len(cache))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--aggregate-only',action='store_true');args=parser.parse_args()
    SPECIAL.mkdir(parents=True,exist_ok=True)
    images=prepare()
    if not args.aggregate_only:
        with ProcessPoolExecutor(max_workers=2) as pool:
            for r in pool.map(run_image,images):print(json.dumps(r),flush=True)
    frame=pd.concat([pd.read_csv(p) for p in SPECIAL.glob('*_trajectory.csv')],ignore_index=True)
    frame.to_csv(SPECIAL/'trajectory_scores.csv',index=False,encoding='utf-8-sig')
    rows=[]
    for (image,k),g in frame.groupby(['image','k']):
        rows.append(dict(image=image,k=k,scene=g.scene.iloc[0],use=g.use.iloc[0],total_paths=len(g),
            full_WQ_paths=int(g.WQ.notna().sum()),IoU3D_paths=int(g.IoU3D100.notna().sum()),
            incomplete_paths=int(g.below_four.sum()),floor_evaluable_paths=int(g.complete_floor_evaluable.sum()),
            two_person_deferred_paths=int(g.k.eq(2).sum()),connection_missing_paths=int((~g.connection_available).sum()),
            WQ_mean=g.WQ.mean(),IoU3D100_mean=g.IoU3D100.mean(),unavailable_rate=float(g.WQ.isna().mean())))
    pd.DataFrame(rows).to_csv(SPECIAL/'by_image_k.csv',index=False,encoding='utf-8-sig')
    end=[r for p in SPECIAL.glob('*_endpoints.json') for r in read(p)]
    pd.DataFrame(end).to_csv(SPECIAL/'endpoints.csv',index=False,encoding='utf-8-sig')
    save(SPECIAL/'SUMMARY.json',dict(images=len(images),path_states=len(frame),status=frame.score_status.value_counts().to_dict()))
    pairs=[]
    for im in images:
        payload=json.load(gzip.open(SPECIAL/'states'/f"{im['image']}.json.gz",'rt',encoding='utf-8'))
        states={tuple(e['workers']):e['automatic'] for e in payload['states']}
        for pair in range(4):
            for k in range(1,len(im['records'])+1):
                a=states[tuple(sorted(payload['orders'][2*pair][:k]))]
                b=states[tuple(sorted(payload['orders'][2*pair+1][:k]))]
                pairs.append(dict(image=im['image'],pair=pair,k=k,**compare_outputs(a,b)))
    pd.DataFrame(pairs).to_csv(SPECIAL/'same_k_geometry.csv',index=False,encoding='utf-8-sig')
    from .wall_consensus_quality_20261015 import matched_changes
    changes=[r for lo,hi in [(1,8),(8,16)] for metric in ['WQ','IoU3D100','WQ_no_D'] for r in matched_changes(frame,lo,hi,metric)]
    pd.DataFrame(changes).to_csv(SPECIAL/'matched_changes.csv',index=False,encoding='utf-8-sig')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,3,figsize=(14,7))
    for ax,(code,g) in zip(axs.flat,pd.DataFrame(rows).groupby('image')):
        ax.plot(g.k,g.WQ_mean,'o-',ms=3,label='WQ');ax.plot(g.k,g.IoU3D100_mean,'s-',ms=3,label='3D IoU x100')
        ax.plot(g.k,100*g.floor_evaluable_paths/g.total_paths,':',color='gray',label='complete floor %')
        ax.set_title(code);ax.set_ylim(0,103);ax.grid(alpha=.2)
    axs.flat[0].legend(fontsize=8);fig.supxlabel('Number of workers');fig.tight_layout();fig.savefig(SPECIAL/'special_curves.png',dpi=160);plt.close(fig)


if __name__=='__main__':main()
