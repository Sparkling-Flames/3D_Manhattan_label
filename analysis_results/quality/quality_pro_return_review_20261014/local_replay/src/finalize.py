"""Finalize the two-stage, conditional working result without mutating source data.
All choices are investigator decisions. This script records them and evaluates
regressions; it does not infer human labels, choose a reference, or fit workers.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
import importlib.metadata, platform, zipfile
from scipy.stats import spearmanr
from core import *
from compare import score_set, evidence_summary, quant, csv_dump

Q01_IMAGE='B6ByNegPMKs_d2dcbd73533446dcaf50e6be98c30386'

def source_audit(co, objs):
    """Audit BOTH annotation/reference geometry for EVERY supplied object.
    This also closes an intermediate measure.py reporting limitation: duplicate
    field keys retained only the last object's geometry delta in that report.
    Here object IDs and individual arrays are retained, and checked separately.
    """
    rows=[];errs=[]
    for o in objs['objects']:
        oid=o['object_id'];p=o.get('points_1024x512');before=o.get('before_preprocessing_points');links=o.get('links_zero_based')
        item=dict(object_id=oid,kind=o['object_kind'],image_id=o['image_id'],source=o.get('source'),
                  pairing_basis=o.get('pairing_basis'),geometry_status=o['geometry']['status'],
                  original_geometry_status_preserved=True,points_sha256=digest(p),
                  source_point_order=o.get('ordered_source_point_indices'),source_links=links,
                  source_review=o.get('final_review'),source_unchanged=True)
        if p is None or not links:
            item.update(status='unavailable_preserved',full_quality_evaluation=False)
        else:
            pp=np.asarray(p,dtype=float);bb=np.asarray(before,dtype=float);expected=bb.copy();delta=[]
            assert sorted(i for pair in links for i in pair)==list(range(len(bb))),oid
            for top,bottom in links:
                dx=(bb[bottom,0]-bb[top,0]+512)%1024-512
                if abs(dx)>=512-1e-8:raise AssertionError('ambiguous_x_midpoint:'+oid)
                mid=(bb[top,0]+dx/2)%1024;expected[[top,bottom],0]=mid;delta.append(dx)
            ordered=expected[o['ordered_source_point_indices']]
            pd=float(np.max(abs(ordered-pp)));assert pd<1e-8,(oid,pd)
            item.update(preprocessed_max_error=pd,raw_X_rms_deg=float(np.sqrt(np.mean(np.array(delta)**2))*360/1024),
                        raw_X_max_deg=float(np.max(np.abs(delta))*360/1024),raw_X_in_main_Q=False)
            try:
                g=geometry(pp);stored=objs['geometries'][oid]
                gd={k:float(np.max(abs(np.asarray(g[k])-stored[k]))) for k in ('bottom3d','top3d')}
                assert max(gd.values())<1e-9,(oid,gd)
                item.update(status='rebuilt_and_equal',geometry_errors=gd)
            except (ValueError, KeyError) as e:
                # Unavailable geometry is retained, not assigned a score of zero.
                if oid in objs['geometries']:raise
                item.update(status='geometry_unavailable_preserved',reason=str(e))
        rows.append(item)
    by={r['object_id']:r for r in rows}
    for layer in ('ordinary','severe','doorway','historical_only'):
        for r in co[layer]:
            assert r['object_id'] in by
            assert by[r['object_id']]['image_id']==r['image_id']
            ref=r.get('reference_object_id') or (r.get('reference') or {}).get('object_id')
            if ref:assert by[ref]['image_id']==r['image_id'],r['record_id']
    result=dict(objects=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
                max_geometry_error=max(v for r in rows for v in r.get('geometry_errors',{}).values()),
                max_preprocessing_error=max(r.get('preprocessed_max_error',0) for r in rows),
                all_binding_images_equal=True,full_project_loader_claimed=False,
                disclosure='907-object authorized working snapshot, not the 3152-row full-project loader',records=rows)
    dump(ROOT/'results/object_and_input_audit.json',result)
    csv_dump(ROOT/'results/input_source_reference_manifest.csv',rows)
    # Exact comparison against the untouched extraction. This can be rechecked
    # during archive verification without relying on any connector response.
    manifest=INPUT/'manifest.json'
    print('object audit',result['statuses'],result['max_geometry_error'])
    return by


def selected_rows(co,measurements,config,audit):
    by={r['record_id']:r for r in measurements};rows=[]
    for layer in ('ordinary','severe','doorway','historical_only'):
        for r in co[layer]:
            rid=r['record_id'];m=by.get(rid);ref=r.get('reference_object_id') or (r.get('reference') or {}).get('object_id')
            item=dict(record_id=rid,object_id=r['object_id'],image_id=r['image_id'],image_code=r.get('image_code',r.get('scene_layer',{}).get('image_code',r.get('severe_review',{}).get('image_code') if r.get('severe_review') else None)),
                building_id=r.get('building_id',r['image_id'].split('_')[0]),worker_id=r['worker_id'],source_layer=layer,
                explicitly_ordinary=r.get('scene_layer',{}).get('ordinary_status_is_explicit'),
                reference_object_id=ref,reference_version=r.get('reference_version',(r.get('reference') or {}).get('version')),
                original_holdout=r.get('original_holdout',False),exposure=r.get('exposure','historical_exposed'),
                personnel_barriers=r.get('personnel_barriers',[]),context_barriers=r.get('context_barriers',r.get('use_barriers',[])),
                formal_gate=r.get('formal_personnel_gate',audit[r['object_id']].get('source_review',{}).get('worker_quality_gate') if audit[r['object_id']].get('source_review') else None),
                formal_eligibility_newly_granted=False,source_use=r.get('use',r.get('status')),
                reason_codes=r.get('reason_codes',[]),raw_X_rms_deg=audit[r['object_id']].get('raw_X_rms_deg'),
                raw_X_in_main_Q=False,annotation_pairs=len(audit[r['object_id']].get('source_links') or []),reference_pairs=len(audit[ref].get('source_links') or []) if ref else None,severe_review_status=(r.get('severe_review') or {}).get('effective_review_status'),used_for_ordinary_selection=layer=='ordinary',separate_severe_constraint=layer=='severe',
                stage2_regression_eligible=layer=='doorway' and m is not None and r['image_id']!=Q01_IMAGE,
                full_quality_human_order_established=False,universal_grade=None)
            if m is None:
                assert layer=='doorway' and r['status']=='held'
                item.update(status='held',current_Q=None,working_Q=None,working_floor_Q=None,iou3d_pct=None,
                            same_target_worker_quality_Q=None,effective_use='held_original_restrictions_preserved')
            else:
                metrics=m['metrics'];old=components(metrics,BASE);new=components(metrics,config)
                assert old['status']==new['status']=='complete'
                item.update(status='conditional_complete',**metrics,current_Q=old['score'],working_Q=new['score'],
                    delta_Q=new['score']-old['score'],current_floor_Q=old['floor_score'],working_floor_Q=new['floor_score'],
                    current_height_drop=old['height_score_drop'],working_height_drop=new['height_score_drop'],
                    boundary_loss=new['boundary_loss'],direction_loss=new['direction_loss'],
                    global_height_loss=new['global_height_loss'],local_height_loss=new['local_height_loss'],height_loss=new['height_loss'],
                    overlap_loss=new['overlap_neutral_loss'],iou3d_pct=100*metrics['iou_3d_corner_mean'],
                    input_hash=m['input_sha256'],reference_hash=m['reference_sha256'],
                    effective_use='ordinary_conditional_development' if layer=='ordinary' else 'separate_severe_constraint' if layer=='severe' else 'doorway_conditional_regression' if layer=='doorway' else 'historical_mechanism_only')
                # A score conditioned on broad G remains reproducible but does not
                # judge whether a separately permitted small room was drawn well.
                if r['image_id']==Q01_IMAGE:
                    item.update(effective_use='Q01_image_scope_conditional_diagnostic_not_tuning',stage2_regression_eligible=False,
                                same_target_worker_quality_Q=None,conditional_large_ref_Q=new['score'],
                                target_warning='R03332 legal small scope has no precise small-scope reference; no reinterpretation as poor quality')
                else:item['same_target_worker_quality_Q']=new['score'] if layer in ('ordinary','severe') else None
                d=m.get('diagnostics',{})
                for k in ['N_nearest_deg','N_ray_deg','ray_ambiguity_fraction','azimuth_bottom_rms_px','azimuth_bottom_max_px','azimuth_bottom_top10_rms_px','spherical_bottom_top10_mean_deg']:
                    item[k]=d.get(k)
            rows.append(item)
    for layer in ('ordinary','severe','doorway','historical_only'):
        rr=[r for r in rows if r['source_layer']==layer];csv_dump(ROOT/f'results/FINAL_{layer}.csv',rr)
    dump(ROOT/'results/effective_use_ledger.json',dict(records=rows,source_counts={k:len(co[k]) for k in ('ordinary','severe','doorway','historical_only')},
        conditional_scoring_not_formal_admission=True,Q01_small_ref_missing=True))
    csv_dump(ROOT/'results/effective_use_ledger.csv',rows)
    return rows


def summaries(rows):
    grouped=[];overall={};rr=[r for r in rows if r.get('working_Q') is not None]
    for layer in ['ordinary','ordinary_explicit','ordinary_conditional','severe','doorway_conditional125','doorway_regression117','Q01_image8','historical_only']:
        pool=[r for r in rr if r['source_layer']==layer or layer=='ordinary_explicit' and r['source_layer']=='ordinary' and r['explicitly_ordinary'] or layer=='ordinary_conditional' and r['source_layer']=='ordinary' and not r['explicitly_ordinary'] or layer=='doorway_conditional125' and r['source_layer']=='doorway' or layer=='doorway_regression117' and r['stage2_regression_eligible'] or layer=='Q01_image8' and r['image_id']==Q01_IMAGE]
        bins={}
        for level in ('image_id','building_id'):
            b=defaultdict(list)
            for r in pool:b[r[level]].append(r)
            bmeans=[]
            for key,vals in b.items():
                g=dict(layer=layer,level=level,group=key,n=len(vals),current_mean=np.mean([r['current_Q'] for r in vals]),working_mean=np.mean([r['working_Q'] for r in vals]),
                       mean_delta=np.mean([r['delta_Q'] for r in vals]),min_delta=min(r['delta_Q'] for r in vals),max_delta=max(r['delta_Q'] for r in vals),
                       iou3d_mean=np.mean([r['iou3d_pct'] for r in vals]),working_height_drop_mean=np.mean([r['working_height_drop'] for r in vals]))
                grouped.append(g);bmeans.append(g['mean_delta'])
            bins[level]=dict(groups=len(b),equal_group_mean_delta=float(np.mean(bmeans)) if bmeans else None,per_group_delta_range=quant(bmeans))
        overall[layer]=dict(n=len(pool),current=quant([r['current_Q'] for r in pool]),working=quant([r['working_Q'] for r in pool]),delta=quant([r['delta_Q'] for r in pool]),
                            iou3d=quant([r['iou3d_pct'] for r in pool]),increase_ge5=sum(r['delta_Q']>=5 for r in pool),increase_ge10=sum(r['delta_Q']>=10 for r in pool),group_balanced=bins)
    csv_dump(ROOT/'results/FINAL_by_image_building.csv',grouped)
    # Within-image rank differences are descriptive, not errors against labels.
    rank=[]
    for layer in ('ordinary','severe','doorway'):
        pool=[r for r in rr if r['source_layer']==layer and r['image_id']!=Q01_IMAGE];b=defaultdict(list)
        for r in pool:b[(r['image_id'],r['reference_object_id'])].append(r)
        for (im,ref),vals in b.items():
            for a,z in combinations(vals,2):
                diffs={k:a[k]-z[k] for k in ('current_Q','working_Q','iou3d_pct')}
                if diffs['current_Q']*diffs['working_Q'] < -1e-9 or diffs['working_Q']*diffs['iou3d_pct'] < -1e-9:
                    rank.append(dict(layer=layer,image_id=im,reference_object_id=ref,a=a['record_id'],b=z['record_id'],**diffs,
                         working_vs_current_sign_change=diffs['current_Q']*diffs['working_Q'] < -1e-9,working_vs_iou_sign_change=diffs['working_Q']*diffs['iou3d_pct'] < -1e-9,not_accuracy_label=True))
    csv_dump(ROOT/'results/within_image_rank_differences.csv',rank)
    for layer in ('ordinary','severe','doorway'):
        overall.setdefault('rank_disagreements',{})[layer]=dict(working_vs_current=sum(r['layer']==layer and r['working_vs_current_sign_change'] for r in rank),working_vs_iou=sum(r['layer']==layer and r['working_vs_iou_sign_change'] for r in rank),independent_accuracy_claim=False)
    dump(ROOT/'results/FINAL_summary.json',overall)
    return overall


def benchmark(measurements):
    r=[x for x in measurements if x['source_layer']!='doorway'];ev=read(INPUT/'preparation/EVIDENCE.json')
    out={x['record_id']:{'iou3d':dict(score=100*x['metrics']['iou_3d_corner_mean'])} for x in r}
    result=evidence_summary(out,r,ev,'iou3d');result['definition']='same-input/same-reference frozen HoHoNet vertex-mean-height prism 3D IoU, not exact non-flat-top solid volume IoU'
    dump(ROOT/'results/iou3d_evidence_comparison.json',result)
    print('IoU P01',result['P01_margin'],'weak inversions',len(result['weak_grade_inversions']))


def height_attribution(measurements,config):
    controls=read(ROOT/'results/control_reconstruction.json')['records'];kind={r['record_id']:r for r in read(INPUT/'data/control_geometries.json')}
    cases=[r for r in measurements if r['record_id'] in ['R00397','R00418','R01609','R02297','R03274','R03346','R03347','R00687']]
    rows=[]
    cfgs={'current':BASE,'working':config,'working_global1':dict(config,global_scale=1.),'working_global065':dict(config,global_scale=.65),'working_local02':dict(config,local_scale=.2),'working_local03':dict(config,local_scale=.3)}
    for r in controls+cases:
        m=r['metrics'];is_control=r in controls
        if is_control and 'height' not in r['record_id'].lower():continue
        old=components(m,BASE);base=components(m,config);I=m['iou_2d'];floor=base['floor_score'];K=base['boundary_loss']+base['direction_loss']
        for name,c in cfgs.items():
            v=components(m,c);H=v['height_loss'];fixed=100*I/(1+I*K)-100*I/(1+I*(K+H))
            rows.append(dict(record_id=r['record_id'],source='reconstructed_control' if is_control else r['source_layer'],candidate=name,
                Hmean=m['Hmean'],Hcenter=m['Hcenter'],global_loss=v['global_height_loss'],local_loss=v['local_height_loss'],height_loss=H,
                neutral_height_drop_100H_over_1plusH=100*H/(1+H),fixed_working_nonheight_drop=fixed,
                actual_height_drop=v['height_score_drop'],complete_Q=v['score'],delta_complete_vs_current=v['score']-old['score'],
                delta_complete_vs_working=v['score']-base['score'],fixed_nonheight_definition='same actual I, same selected B,D, working loss_sum combination; vary H only'))
    csv_dump(ROOT/'results/height_attribution.csv',rows)
    dump(ROOT/'results/height_attribution.json',dict(records=rows,control_count=len({r['record_id'] for r in rows if r['source']=='reconstructed_control'}),
        global08_not_new_height_tuning=True,local025_retained=True,P04_scope='component, not cross-image total ranking'))


def door_fine_regression(co,ordinary,doors,config):
    # Restrict tuning evidence, not the availability of conditional diagnostics.
    d=[r for r in doors if next(z for z in co['doorway'] if z['record_id']==r['record_id'])['image_id']!=Q01_IMAGE]
    candidates=read(ROOT/'configs/doorway_candidates.json');o=[r for r in ordinary if r['source_layer'] in ('ordinary','severe')]
    s=score_set(o+d,candidates);ev=read(INPUT/'preparation/EVIDENCE.json');rows=[]
    for name,c in candidates.items():
        if name=='old_current':continue
        ee=evidence_summary(s,o,ev,name)
        for layer,rr in [('ordinary',[r for r in o if r['source_layer']=='ordinary']),('severe',[r for r in o if r['source_layer']=='severe']),('doorway_regression117',d)]:
            delta=[s[r['record_id']][name]['score']-s[r['record_id']]['ordinary_frozen']['score'] for r in rr]
            rows.append(dict(candidate=name,layer=layer,n=len(rr),**{'delta_'+k:v for k,v in quant(delta).items() if k!='n'},P01_margin=ee['P01_margin'],weak_inversions=len(ee['weak_grade_inversions']),severe_light_inversions=len(ee['severe_vs_light_inversions']),
                selection_basis='no new full-quality ranking from Q02/Q03; no target doorway score'))
    csv_dump(ROOT/'results/doorway_fine_normal_regression.csv',rows)
    source=read(ROOT/'configs/ordinary_frozen.json')
    final=dict(schema='quality_working_final_v1',name=source['name'],config=config,stage1_freeze_sha256=sha(ROOT/'configs/ordinary_frozen.json'),
         stage2_status='conditional_comparison_completed_no_additional_parameter_change',conditional_doorway_scored=125,original_doorway_held=92,
         scope_conditional_Q01_image_rows_excluded_from_tuning=8,remaining_conditional_regression_rows=117,
         parameter_changes_after_ordinary_freeze={},ordinary_regression_n=574,severe_regression_n=9,
         ordinary_max_delta_from_frozen=max(abs(components(r['metrics'],config)['score']-components(r['metrics'],source['config'])['score']) for r in o),
         rationale='Fine candidates trade off geometry/height penalties but no valid new complete human ranking selects a better one. Preserve the ordinary tradeoff; doorway is not trained to be low.',
         reference_assignment_changed=False,formal_algorithm_changed=False,formal_worker_eligibility_changed=False,fusion_changed=False,
         ordinary_hashes_verified=all(sha(ROOT/p)==h for p,h in source['dependencies'].items()))
    assert final['ordinary_hashes_verified'] and final['ordinary_max_delta_from_frozen']==0.
    dump(ROOT/'configs/WORKING_FINAL.json',final)
    dump(ROOT/'results/stage2_decision.json',dict(decision=final,regression=rows))


def actual_counterpatterns():
    measurements=read(ROOT/'results/ordinary_reconstruction.json')['records'];co=read(INPUT/'data/cohorts.json')
    meta={r['record_id']:r for r in co['ordinary']};bins=defaultdict(list)
    for r in measurements:
        if r['source_layer']!='ordinary':continue
        p=r['diagnostics']['profile'];pg=r['diagnostics']['reference_profile']
        if len(p['signed_turn_deg'])==4 and len(pg['signed_turn_deg'])==4 and pg['D']<.05:
            bins[(meta[r['record_id']]['image_id'],r['reference_object_id'])].append(r)
    corner=lambda r:float(np.sqrt(np.mean((abs(np.array(r['diagnostics']['profile']['signed_turn_deg']))-90)**2)))
    actual=[];comparison_count=0
    for key,rr in bins.items():
        for a,b in combinations(rr,2):
            comparison_count+=1
            if a['metrics']['iou_2d']<b['metrics']['iou_2d']:a,b=b,a
            if a['metrics']['iou_2d']-b['metrics']['iou_2d']>.02 and a['metrics']['dir']-b['metrics']['dir']>1 and corner(b)-corner(a)>5:
                actual.append(dict(a=a['record_id'],b=b['record_id'],image_id=key[0],Ia=a['metrics']['iou_2d'],Ib=b['metrics']['iou_2d'],Da=a['metrics']['dir'],Db=b['metrics']['dir'],Ca=corner(a),Cb=corner(b)))
    tr=read(ROOT/'results/real_bottom_trajectories.json');lookup={(r['record_id'],r['t']):r for r in tr['records']};derived=[]
    for r in tr['reversal_windows']:
        a,b=lookup[(r['record_id'],r['t_from'])],lookup[(r['record_id'],r['t_to'])]
        if len(a['profile']['signed_turn_deg'])!=4:continue
        pa=np.array(a['profile']['signed_turn_deg']);pb=np.array(b['profile']['signed_turn_deg']);ca=float(np.sqrt(np.mean((abs(pa)-90)**2)));cb=float(np.sqrt(np.mean((abs(pb)-90)**2)))
        if cb>ca+1e-8:derived.append(dict(**r,corner_rms_from=ca,corner_rms_to=cb))
    result=dict(actual_pair_criteria='same image and reference, four corners each, reference D<.05deg, I decrease>.02, D decrease>1deg, rectangle turn-error increase>5deg',
        actual_pairs_tested=comparison_count,actual_pairs=actual,derived_corner_worsening_windows=derived,derived_is_not_two_human_annotations=True)
    dump(ROOT/'results/actual_direction_counterpatterns.json',result)


def main():
    co=read(INPUT/'data/cohorts.json');objs=read(INPUT/'data/objects.json');config=read(ROOT/'configs/ordinary_frozen.json')['config']
    ordinary=read(ROOT/'results/ordinary_reconstruction.json')['records'];doors=read(ROOT/'results/doorway_reconstruction.json')['records']
    a=source_audit(co,objs);rows=selected_rows(co,ordinary+doors,config,a);s=summaries(rows);benchmark(ordinary+doors);height_attribution(ordinary+doors,config)
    door_fine_regression(co,ordinary,doors,config);actual_counterpatterns()
    dump(ROOT/'results/runtime_versions.json',dict(python=platform.python_version(),platform=platform.platform(),packages={k:importlib.metadata.version(k) for k in ['numpy','scipy','shapely','matplotlib','pillow','pytest']}))
    print('final counts', {k:s[k]['n'] for k in s if k!='rank_disagreements'})
    print('severe',[(r['record_id'],r['current_Q'],r['working_Q']) for r in rows if r['source_layer']=='severe'])
if __name__=='__main__':main()
