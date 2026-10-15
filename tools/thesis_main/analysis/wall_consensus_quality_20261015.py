"""Score saved wall-consensus states with the reviewed frozen WQ engine."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from .worker_wq_integration_20261015 import frozen_engine, read
from .wall_consensus_population_20261014 import prepare_input, summarize_state

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/wall_consensus_quality_20261015'
POP = ROOT/'research/wall_consensus_population_20261014'
BIND = ROOT/'research/difficulty_target_integration_20261015'
ARCHIVE = ROOT/'research/quality_joint_closeout_review_20261015/pro_closeout_delta.zip'
VERSION = 'WQ-LS08-20261014'


def save(path, data):
    def norm(v):
        if isinstance(v, dict): return {str(k): norm(x) for k,x in v.items()}
        if isinstance(v, (list, tuple, np.ndarray)): return [norm(x) for x in v]
        if isinstance(v, np.generic): return norm(v.item())
        if isinstance(v, float) and not np.isfinite(v): return None
        return v
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(norm(data), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def classify_output(k, nodes, connected, full_reference):
    if k == 2: return 'two_person_deferred'
    if nodes < 4: return 'below_four'
    if not connected: return 'no_connection'
    if not full_reference: return 'floor_only_reference'
    return 'candidate_full'


def measured(engine, state, reference):
    c = state['candidate']
    status = classify_output(state['n'], len(state['node_consensus']['nodes']),
                             c['points'] is not None, reference.get('points') is not None)
    result = dict(score_status=status, WQ=None, IoU3D100=None, floor_WQ_upper_bound=None)
    if status in ('two_person_deferred', 'no_connection'): return result
    floor = c.get('footprint')
    if floor is None: return dict(result, score_status=status if status=='below_four' else 'invalid_floor')
    vf=engine.valid.validate_footprint(floor)
    vg=engine.valid.validate_footprint(reference['floor'])
    if not vf['available'] or not vg['available']:
        return dict(result, score_status='invalid_floor', reasons=json.dumps([vf['errors'],vg['errors']]))
    a={'bottom3d':[[x,-1,z] for x,z in floor]}
    g={'bottom3d':[[x,-1,z] for x,z in reference['floor']]}
    areas=engine.au.area_metrics(a,g)
    m=dict(iou_2d=areas['iou'], S_bottom_deg=float(engine.sp.spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)),
           dir=float(engine.au.direction_residual(a,engine.au.direction_axis(a))),Hmean=None,Hcenter=None)
    scores=engine.score(m)
    result.update(m, omission=areas['omission'],extension=areas['extension'],floor_WQ_upper_bound=scores['floor_WQ'])
    if status in ('below_four','floor_only_reference'): return result
    if c.get('geometry_status')!='ok': return dict(result,score_status='invalid_full_geometry')
    measurement=engine.measure(engine.geometry(c['points']),engine.geometry(reference['points']))
    if measurement['status']!='complete':
        return dict(result,score_status='invalid_full_geometry',reasons=json.dumps(measurement.get('reasons')))
    result.update(measurement['metrics'])
    result.update({k:v for k,v in measurement['scores'].items() if k not in ('status','current','floor_current')})
    result.update(score_status='complete_conditional',IoU3D100=100*measurement['metrics']['iou_3d_corner_mean'])
    return result


def references(im, bindings):
    rows=bindings[bindings.image.eq(im['image'])]
    result=[]
    for r in im['references']:
        if r['version']=='difficulty_selected_floor': continue
        row=rows[rows.reference_kind.eq(r['version'])].iloc[0]
        result.append(dict(r,axis=r['version'],object_id=row.reference_object_id,full_target_match=bool(row.full_target_match)))
    selected=next(r for r in result if r['full_target_match']) if any(r['full_target_match'] for r in result) else next(r for r in im['references'] if r['version']=='difficulty_selected_floor')
    result.append(dict(selected,axis='selected_target',object_id=im['difficulty']['target_version'],full_target_match=selected.get('points') is not None))
    return result


def score_image(im):
    refs=references(im,pd.read_csv(BIND/'fusion_reference_bindings.csv'))
    payload=json.load(gzip.open(POP/'states'/f"{im['image']}.json.gz",'rt',encoding='utf-8'))
    gates={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    by_worker={r['worker']:r for r in im['records']}
    rows=[];cache={}
    with zipfile.ZipFile(ARCHIVE) as archive, frozen_engine(archive) as engine:
        for entry in payload['states']:
            state=entry['automatic']; members=sorted(entry['workers']); rs=[by_worker[w] for w in members]
            meta=dict(image=im['image'],image_id=im['image_id'],building=im['building'],panel=im['panel'],
                subset='|'.join(members),worker_ids='|'.join(sorted(gates[r['id']]['worker_id'] for r in rs)),
                member_record_ids='|'.join(sorted(r['id'] for r in rs)),member_object_ids='|'.join(sorted(gates[r['id']]['object_id'] for r in rs)),
                condition='manual',source_version='wall_consensus_population_20261014/input_snapshot.json',
                fusion_version='MV50_gap7.5_automatic',score_version=VERSION,reference_hold=im['reference_hold'],
                difficulty=im['difficulty']['current_class'],difficulty_version=im['difficulty_version'],
                original_holdout=any(gates[r['id']]['original_holdout'] for r in rs),
                restricted_members='|'.join(r['id'] for r in rs if gates[r['id']]['role']!='manual_development_candidate'),
                formal_eligibility_newly_granted=False,**summarize_state(state))
            for ref in refs:
                key=json.dumps([state['n']==2,len(state['node_consensus']['nodes'])<4,state['candidate'],ref.get('points'),ref['floor']],sort_keys=True)
                if key not in cache:cache[key]=measured(engine,state,ref)
                rows.append(dict(meta,reference_axis=ref['axis'],reference_id=ref['object_id'],full_target_match=ref['full_target_match'],**cache[key]))
    frame=pd.DataFrame(rows)
    (OUT/'scores').mkdir(parents=True,exist_ok=True)
    frame.to_csv(OUT/'scores'/f"{im['image']}.csv",index=False,encoding='utf-8-sig')
    save(OUT/'references'/f"{im['image']}.json",refs)
    return dict(image=im['image'],unique_subsets=len(payload['states']),rows=len(rows),measurements=len(cache))


def matched_changes(frame, low, high, metric='WQ'):
    rows=[]
    for (image,axis),g in frame.groupby(['image','reference_axis']):
        a=g[g.k.eq(low)][['path',metric]].rename(columns={metric:'low'})
        b=g[g.k.eq(high)][['path',metric]].rename(columns={metric:'high'})
        both=a.merge(b,on='path');valid=both.dropna()
        if len(both):rows.append(dict(image=image,reference_axis=axis,metric=metric,low_k=low,high_k=high,
            total_paths=len(both),matched_paths=len(valid),mean_low=valid.low.mean(),mean_high=valid.high.mean(),
            mean_change=(valid.high-valid.low).mean()))
    return rows


def aggregate():
    scores=pd.concat([pd.read_csv(p) for p in sorted((OUT/'scores').glob('*.csv'))],ignore_index=True)
    scores.to_csv(OUT/'subset_scores.csv',index=False,encoding='utf-8-sig')
    obs=pd.read_csv(POP/'observations.csv')
    frame=obs[['image','path','subset','k']].merge(scores,on=['image','subset','k'],validate='many_to_many')
    assert not frame.duplicated(['image','path','k','reference_axis']).any()
    frame.to_csv(OUT/'trajectory_scores.csv',index=False,encoding='utf-8-sig')
    rows=[]
    for (image,axis,k),g in frame.groupby(['image','reference_axis','k']):
        rows.append(dict(image=image,reference_axis=axis,k=k,panel=g.panel.iloc[0],difficulty=g.difficulty.iloc[0],
            total_paths=len(g),full_quality_paths=int(g.WQ.notna().sum()),unavailable_rate=float(g.WQ.isna().mean()),
            below_four_paths=int(g.below_four.sum()),two_person_deferred_paths=int(g.score_status.eq('two_person_deferred').sum()),
            floor_quality_paths=int(g.iou_2d.notna().sum()),WQ_mean=g.WQ.mean(),IoU3D100_mean=g.IoU3D100.mean(),
            floor_IoU_mean=g.iou_2d.mean(),S_bottom_deg_mean=g.S_bottom_deg.mean(),
            Hmean_mean=g.Hmean.mean(),Hcenter_mean=g.Hcenter.mean()))
    pd.DataFrame(rows).to_csv(OUT/'by_image_k.csv',index=False,encoding='utf-8-sig')
    changes=[r for lo,hi in [(1,8),(8,16),(16,24),(8,24)] for metric in ['WQ','IoU3D100'] for r in matched_changes(frame,lo,hi,metric)]
    pd.DataFrame(changes).to_csv(OUT/'matched_changes.csv',index=False,encoding='utf-8-sig')
    terminal=frame[frame.k.eq(frame.groupby('image').k.transform('max'))].drop_duplicates(['image','subset','reference_axis'])
    terminal.to_csv(OUT/'automatic_endpoints.csv',index=False,encoding='utf-8-sig')
    pairs=[]
    for (image,axis,k),g in frame.groupby(['image','reference_axis','k']):
        ordered=g.set_index('path')
        for p in range(12):
            a,b=ordered.loc[2*p],ordered.loc[2*p+1]
            pairs.append(dict(image=image,reference_axis=axis,k=k,pair=p,
                subset_a=a.subset,subset_b=b.subset,
                both_WQ_available=pd.notna(a.WQ) and pd.notna(b.WQ),
                abs_WQ_difference=abs(a.WQ-b.WQ),abs_IoU3D100_difference=abs(a.IoU3D100-b.IoU3D100)))
    pd.DataFrame(pairs).merge(pd.read_csv(POP/'same_k_pairs.csv'),on=['image','k','pair'],validate='many_to_one').to_csv(
        OUT/'same_k_scores.csv',index=False,encoding='utf-8-sig')
    selected=frame[frame.reference_axis.eq('selected_target')]
    save(OUT/'SUMMARY.json',dict(unique_subsets=scores[['image','subset']].drop_duplicates().shape[0],
        path_states=len(selected),selected_status=selected.score_status.value_counts().to_dict(),
        conditional_full_score_states=int(selected.WQ.notna().sum()),score_version=VERSION,
        reference_axes='original/manual_revision plus fixed selected target; no maximum-score selection'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(3,4,figsize=(16,10),sharex=True)
    for ax,(image,g) in zip(axs.flat,pd.DataFrame(rows).query("reference_axis=='selected_target'").groupby('image')):
        ax.plot(g.k,g.WQ_mean,'o-',ms=2,label='WQ');ax.plot(g.k,g.IoU3D100_mean,'s-',ms=2,label='3D IoU x100')
        ax.plot(g.k,100*(1-g.unavailable_rate),':',color='gray',label='available %')
        if g.WQ_mean.isna().all():ax.text(.5,.5,'Same-target floor only\nFull WQ / 3D IoU unavailable',ha='center',transform=ax.transAxes,fontsize=9)
        ax.set_title(image);ax.set_ylim(0,103);ax.grid(alpha=.2)
    axs.flat[0].legend(fontsize=8);fig.supxlabel('Number of workers');fig.tight_layout();fig.savefig(OUT/'quality_curves.png',dpi=160);plt.close(fig)


def endpoints_and_validation():
    snapshot=read(POP/'input_snapshot.json');bindings=pd.read_csv(BIND/'fusion_reference_bindings.csv')
    gates={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    rows=[];members=[]
    with zipfile.ZipFile(ARCHIVE) as archive,frozen_engine(archive) as engine:
        for im in snapshot['images']:
            for r in im['records']:
                members.append(dict(image=im['image'],public_worker=r['worker'],**gates[r['id']]))
            endpoint=read(POP/'endpoints'/f"{im['image']}.json")
            for version in ('current_automatic','prior_assisted'):
                state=endpoint[version]
                if state is None:continue
                for ref in references(im,bindings):
                    rows.append(dict(image=im['image'],version=version,reference_axis=ref['axis'],reference_id=ref['object_id'],
                        score_version=VERSION,input_same_as_1008=endpoint['endpoint_summary']['input_same_as_1008'],
                        interpretation=endpoint['endpoint_summary']['prior_assisted_interpretation'] if version=='prior_assisted' else 'current automatic terminal',
                        **summarize_state(state),**measured(engine,state,ref)))
    pd.DataFrame(rows).to_csv(OUT/'endpoint_comparison.csv',index=False,encoding='utf-8-sig')
    save(OUT/'member_registry.json',members)
    # Reuse already-scored exact member/reference cases as an integration check, not a second scorer.
    scores=pd.read_csv(OUT/'subset_scores.csv');prior=pd.read_csv(ROOT/'research/worker_wq_integration_20261015/cached_team_scores.csv')
    comparison=scores[~scores.reference_axis.eq('selected_target')].merge(prior,on=['image','subset','reference_id'],suffixes=('_new','_old'))
    comparison=comparison.dropna(subset=['WQ_new','WQ_old'])
    assert len(comparison)>0
    maximum=float((comparison.WQ_new-comparison.WQ_old).abs().max())
    assert maximum<1e-9
    assert (comparison.IoU3D100_new-comparison.IoU3D100_old).abs().max()<1e-9
    comparison[['image','subset','reference_id','WQ_new','WQ_old','IoU3D100_new','IoU3D100_old']].to_csv(OUT/'cache_crosscheck.csv',index=False,encoding='utf-8-sig')
    room_rows=[]
    for im in snapshot['images']:
        units={gates[r['id']]['original_room_group'] for r in im['records']}
        room_rows.append(dict(image=im['image'],image_id=im['image_id'],building=im['building'],
            room_groups='|'.join(sorted(units)),room_id_missing=any('missing_room' in x for x in units),
            pool_n=len(im['records']),reference_geometry_file=f"references/{im['image']}.json",
            input_geometry_file='../wall_consensus_population_20261014/input_snapshot.json'))
    pd.DataFrame(room_rows).to_csv(OUT/'image_registry.csv',index=False,encoding='utf-8-sig')
    save(OUT/'VALIDATION.json',dict(exact_cached_member_reference_comparisons=len(comparison),max_WQ_difference=maximum,
        input_snapshot_equal_fresh_preparation=True,score_engine='unaltered src/quality.py and engine in pro_closeout_delta.zip',
        no_fusion_recomputed_in_original_12=True))
    save(OUT/'FIELD_CONTRACT.json',dict(schema='wall_consensus_quality_20261015_v1',score_version=VERSION,
        unique_unit=['image','subset','reference_axis'],path_unit=['image','path','k','reference_axis'],
        source='saved actual member subsets; original12 automatic only',
        units={'WQ':'0..100 research work metric','IoU3D100':'0..100 vertex-mean-height prism proxy; not true room volume',
               'iou_2d':'0..1','S_bottom_deg':'degrees','dir':'own best orthogonal-axis residual degrees',
               'Hmean':'absolute perimeter-mean height ratio residual','Hcenter':'centered local height residual',
               'floor_WQ_upper_bound':'height-free upper bound, not complete quality'},
        missing='NA never zero; k=2 deferred; below4 excluded from full quality but valid floor diagnostics retained',
        validity='conditional research values, no new formal eligibility or semantic certification',
        denominator='by_image_k total_paths/full_quality_paths; matched_changes same paths at both k',
        same_room='image_registry room_groups preserve missing-room building fallbacks; do not treat fallback as confirmed same room'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--aggregate-only',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if not args.aggregate_only:
        snapshot=read(POP/'input_snapshot.json')
        assert snapshot==prepare_input(),'prepared input changed; do not relabel saved fusion states'
        with ProcessPoolExecutor(max_workers=3) as pool:
            for result in pool.map(score_image,snapshot['images']):print(json.dumps(result),flush=True)
    aggregate()
    endpoints_and_validation()


if __name__=='__main__':main()
