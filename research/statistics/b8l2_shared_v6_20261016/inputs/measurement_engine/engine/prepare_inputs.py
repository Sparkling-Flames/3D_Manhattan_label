"""Build a frozen, task-minimal source snapshot from authenticated source files.

This script is a one-time source extraction. run_routing.py only needs the
included prepared_input.json and pinned metric engine, not the full loader.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parent
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def dump(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def geometry(points):
    a=np.asarray(points,float)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)%2 or len(a)<6 or not np.isfinite(a).all():raise ValueError('paired_points_unavailable')
    bottom=a[1::2];top=a[0::2];u=(bottom[:,0]/1024-.5)*2*np.pi;v=(bottom[:,1]/512-.5)*np.pi
    if np.any(v<=0) or np.any(v>=np.pi/2):raise ValueError('bottom_not_below_horizon')
    radius=1/np.tan(v);x=radius*np.sin(u);z=-radius*np.cos(u)
    height=-radius*np.tan((top[:,1]/512-.5)*np.pi)
    return {'bottom3d':np.column_stack((x,np.full(len(x),-1.),z)).tolist(),
            'top3d':np.column_stack((x,height,z)).tolist()}
def floor_of(points):return np.asarray(geometry(points)['bottom3d'])[:,[0,2]].tolist()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--main',type=Path,default=ROOT.parent/'sources/main');ap.add_argument('--routing-sources',type=Path,default=ROOT.parent/'sources/routing');ap.add_argument('--out',type=Path,default=ROOT/'inputs/prepared_input.json');a=ap.parse_args()
    sources={}
    def load(path):
        path=Path(path);b=path.read_bytes();sources[str(path.resolve())]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};return json.loads(b)
    regpath=a.routing_sources/'research/quality_scope_review_complete_20261010/data'
    registry=load(regpath/'reference_registry.json');overlay=load(regpath/'normalized_confirmation_overlay.json');raw=load(regpath/'raw_scope_receipt.json');bindings=load(regpath/'source_bindings.json');oldmetrics=load(regpath/'record_metrics.json')
    loader=load(a.source/'inputs/current_formal_loader_data.json');ex=load(a.routing_sources/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json')
    decisions=load(a.routing_sources/'research/quality_calibration_pro_handoff_20261011/USER_DECISIONS.json')
    four=load(a.routing_sources/'research/quality_four_space_recompute_20261011/results/reference_ledger.json')
    oldlocal=load(a.routing_sources/'research/quality_four_space_recompute_20261011/results/local_structure_20.json')
    rawfour=load(a.source/'inputs/previous_raw_receipts/空间范围人工审核_2026-10-11.json')
    reviews=load(a.source/'inputs/previous_raw_receipts/quality_review30_receipt.json')
    selection=load(a.routing_sources/'research/quality_review30_20261011/results/selection_private.json')
    eligibility=load(a.main/'research/quality_parallel_local_20261012/eligibility_ledger.json')
    cal=load(a.source/'inputs/calibration_records.json')
    byobj={r['object_id']:r for r in loader['objects']};images={r['image_code']:r for r in loader['images']};gates={r['object_id']:r for r in eligibility['records']};byover={r['image_code']:r for r in overlay['records']};bybind={r['image_code']:r for r in bindings['records']};rawby={r['image_code']:r for r in raw['records']};calby={r['object_id']:r for r in cal['rows']}
    issues={}
    for group in ['confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine']:
        for r in ex[group]:issues[r['image_code']]={'registry_group':group,**r}
    candidate_images=[];assert len(registry['records'])==35
    confirmation_checks=[]
    for rr in registry['records']:
        code=rr['image_code'];ov=byover[code];source=rawby[code];bind=bybind[code];orig=ov['historical_original_GT_points_1024x512'];original_floor=floor_of(orig);selected=ov['editing_reference_points_1024x512'];selected_floor=floor_of(selected)
        receipt_region=source['space_regions']['regions'][0];confirmed=receipt_region['confirmed_version'];floor=confirmed['polygon'];assert floor==ov['cropped_floor_xz_h']==rr['floor_xz_h'];assert confirmed['floor_region_confirmed']
        floor_source_sha=hashlib.sha256(json.dumps(floor,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        # The original registry uses ordered canonical points with sort_keys;
        # list payload makes the two canonical conventions identical.
        assert floor_source_sha==rr['floor_polygon_sha256']==bind['receipt_floor_sha256']
        qorig=Polygon(original_floor);qfloor=Polygon(floor);different=qorig.symmetric_difference(qfloor).area>1e-8*max(qorig.area,qfloor.area)
        oid=ov['historical_original_GT_object_id'];orig_obj=byobj.get(oid);origin_geom=geometry(orig)
        problem=issues.get(code);original_allowed=not bool(problem)
        ori={'candidate_id':code+':A','space_label':'A','candidate_kind':'historical_original_GT',
             'reference_object_id':oid,'reference_version':orig_obj.get('object_kind') if orig_obj else 'recovered_original_equivalent_snapshot',
             'points_1024x512':orig,'points_sha256_canonical_v1':digest(orig),'floor_xz_h':original_floor,
             'floor_sha256_canonical_v1':digest(original_floor),'full_geometry':origin_geom,
             'full_reference_available':True,'top_status':'existing_original_top_no_new_ceiling_validation',
             'admitted_for_routing':original_allowed,'restriction':problem,
             'human_confirmation_source':{'current_user_instruction':'original GT and confirmed drawn space are admitted alternatives, subject to latest exclusions','source_binding':bind},
             'aliases':[]}
        candidates=[ori];floor_alias=rr['reference_id']
        selected_same_as_orig=Polygon(selected_floor).symmetric_difference(qorig).area<=1e-8*max(qorig.area,Polygon(selected_floor).area)
        if different:
            full_existing=byobj.get(ov['editing_reference_object_id'])
            matches_selected=qfloor.symmetric_difference(Polygon(selected_floor)).area<=1e-8*max(qfloor.area,Polygon(selected_floor).area)
            full=geometry(selected) if matches_selected and full_existing is not None else None
            cr={'candidate_id':code+':B','space_label':'B','candidate_kind':'user_confirmed_floor',
                'reference_object_id':ov['editing_reference_object_id'] if full is not None else floor_alias,
                'reference_version':full_existing.get('object_kind') if full is not None else 'user_confirmed_floor_only',
                'points_1024x512':selected if full is not None else None,
                'points_sha256_canonical_v1':digest(selected) if full is not None else None,
                'floor_xz_h':floor,'floor_sha256_canonical_v1':digest(floor),'full_geometry':full,
                'full_reference_available':full is not None,
                'top_status':'existing_selected_GT_top_not_grafted' if full is not None else 'top_pending',
                'admitted_for_routing':True,'restriction':None,'confirmed_at':confirmed['confirmed_at'],
                'confirmation_id':floor_alias,'human_confirmation_source':rr['confirmation_provenance'],'aliases':[]}
            candidates.append(cr)
        else:
            ori['aliases'].append({'confirmation_id':floor_alias,'reason':'same_floor_geometry_within_1e-8_area_tolerance','full_top_newly_confirmed':False,'human_confirmation_source':rr['confirmation_provenance']})
        if code==four['image_code']:
            rawfour_regions={x['region_id']:x for x in rawfour['records'][0]['space_regions']['regions']}
            for sp in four['spaces']:
                label=sp['space_label'];fp=sp['polygon_xz_h']
                if label in ['C','D']:
                    original_confirmation=rawfour_regions[sp['region_id']]['confirmed_version']
                    assert original_confirmation is not None and original_confirmation['floor_region_confirmed']
                    assert original_confirmation['polygon']==fp
                    assert original_confirmation['confirmed_at']==sp['confirmed_at']
                if label in ['A','B']:
                    existing=next(c for c in candidates if c['space_label']==label)
                    assert Polygon(existing['floor_xz_h']).symmetric_difference(Polygon(fp)).area<1e-10
                    existing['four_space_version_binding']={'receipt_sha256':four['receipt_sha256'],'acceptance_source':sp['acceptance_source'],'confirmed_at':sp.get('confirmed_at')}
                else:
                    candidates.append({'candidate_id':code+':'+label,'space_label':label,'candidate_kind':'user_confirmed_floor',
                        'reference_object_id':code+':'+sp['region_id']+':floor:'+digest(fp)[:16],
                        'reference_version':'four_space_confirmed_floor_only','points_1024x512':None,'points_sha256_canonical_v1':None,
                        'floor_xz_h':fp,'floor_sha256_canonical_v1':digest(fp),'full_geometry':None,'full_reference_available':False,
                        'top_status':'top_pending','admitted_for_routing':True,'restriction':None,'confirmed_at':sp['confirmed_at'],
                        'human_confirmation_source':{'receipt_sha256':four['receipt_sha256'],'receipt_library_id':four['receipt_library_id'],'acceptance_source':sp['acceptance_source']},'aliases':[]})
        im=images.get(code)
        candidate_images.append({'image_code':code,'image_id':rr['image_id'],'building_id':code.split('-')[0],
           'room_id':im.get('room_id') if im else None,'image_conditions_and_comments':im,
           'in_formal_corpus':rr['in_current_formal_corpus'],'reference_only_reason':rr['reference_only_reason'],
           'scope_confirmation_changed_displayed_GT':rr['new_floor_geometry'],
           'confirmed_floor_differs_from_historical_original_GT':different,'scope_confirmation_top_pending':True,
           'original_reference_candidate':code+':A','previous_fixed_selected_reference_candidate':code+(':B' if different and not selected_same_as_orig else ':A'),
           'candidates':candidates,'original_reference_restriction':problem,
           'source_reference_registry_entry':rr})
        confirmation_checks.append({'image_code':code,'raw_confirmation_matches_normalized_and_registry':True,'source_floor_hash_verified':True,
            'declared_changed_displayed_GT':rr['new_floor_geometry'],'actual_differs_historical_original_GT':different})
    records=[]
    for old in oldmetrics:
        obj=byobj[old['object_id']];gate=gates[obj['object_id']];r={'record_id':old['record_id'],'object_id':obj['object_id'],'image_id':obj['image_id'],'image_code':obj['image_code'],'worker_id':obj.get('worker_id'),'condition':obj.get('condition'),
            'room_id':obj.get('room_id'),'building_id':obj.get('building_id'),'input_version':{'loader_contract':loader['contract_version'],'order_revision':loader['order_update_revision'],'quality_revision':loader['quality_update_revision'],'source_main':'fdfc8a51ad668c83172ca4a9cf0105f417dac61c','calibration_archive_source_main':cal['main_sha']},
            'source_object':obj,'source_object_sha256_canonical_v1':digest(obj),'current_points_sha256_canonical_v1':digest(obj.get('points_1024x512')),
            'raw_points_sha256_canonical_v1':digest(obj.get('before_preprocessing_points')),
            'current_eligibility_ledger':gate,'old_scope_metrics':old,'calibration_pool_row':calby.get(obj['object_id'])}
        try:r['geometry']=geometry(obj.get('points_1024x512'));r['reconstruction_reason']=None
        except (ValueError,TypeError) as e:r['geometry']=None;r['reconstruction_reason']=str(e)
        records.append(r)
    cases={r['case_id']:r for r in selection['records']};overrides={};review_evidence=[]
    latest={x['case_id']:x for x in decisions['decisions'] if x.get('case_id')}
    for ans in reviews['answers']:
        cid=ans['case_id'];case=cases[cid]
        if case['case_type']!='single_floor_space_compatibility':continue
        rid=case['selection_private']['record_id'];target=None;src=None
        if ans['space_compatibility']=='仅 A 可匹配':target='A';src='original_30_receipt'
        if ans['space_compatibility']=='仅 B 可匹配':target='B';src='original_30_receipt'
        if latest.get(cid,{}).get('reference_label'):target=latest[cid]['reference_label'];src='latest_USER_DECISIONS'
        if target:
            overrides[rid]={'record_id':rid,'object_id':case['object_id'],'image_code':case['image_code'],
                'selected_candidate_id':case['image_code']+':'+target,'case_id':cid,'source':src,
                'source_evidence':latest[cid] if src=='latest_USER_DECISIONS' else ans,
                'source_points_hash':case['current_points_sha256'],'all_30_confidence_unknown_not_invented':True}
        review_evidence.append({'case_id':cid,'record_id':rid,'image_code':case['image_code'],'raw_answer':ans,'latest_clarification':latest.get(cid),'effective_target':target,'used_as_development_evidence':True,'independent_validation':False})
    family_directives={}
    for d in decisions['decisions']:
        if d.get('protruding_region_included_user_confirmed'):
            rid=d['record_id'];rec=next(r for r in records if r['record_id']==rid)
            family_directives[rid]={'record_id':rid,'image_code':rec['image_code'],'allowed_candidate_ids':[rec['image_code']+':A',rec['image_code']+':B'],
                'reason':'user_confirmed_protruding_region_present_exact_A_or_B_not_decided','source_evidence':d,
                'source_historical_local_evidence':next(x for x in oldlocal['rows'] if x['record_id']==rid)}
    out={'schema':'multispace_routing_input_v1','source_files':sources,'coordinate_frame':'camera_height_normalized_xz; ERP1024x512',
         'geometry_preprocessing':'retain original and before_preprocessing points; geometry uses supplied ordered pair-mean-x points without new repair',
         'candidate_images':candidate_images,'records':records,'manual_overrides':overrides,'manual_family_directives':family_directives,
         'development_space_review_evidence':review_evidence,'reference_confirmation_checks':confirmation_checks,'old_T30_local_evidence':oldlocal,
         'source_receipt_hashes':{'scope_35':hashlib.sha256((regpath/'raw_scope_receipt.json').read_bytes()).hexdigest(),'four_space':four['receipt_sha256']},
         'floor_confirmation_does_not_validate_ceiling':True,'formal_eligibility_unchanged':True,
         'counts':{'confirmed_images':35,'raw_receipt_rows':len(raw['records']),'new_floor_geometry_vs_displayed':sum(x['scope_confirmation_changed_displayed_GT'] for x in candidate_images),
            'different_vs_historical_original':sum(x['confirmed_floor_differs_from_historical_original_GT'] for x in candidate_images),
            'candidate_count_including_restricted':sum(len(x['candidates']) for x in candidate_images),
            'admitted_unique_candidate_count':sum(c['admitted_for_routing'] for x in candidate_images for c in x['candidates']),
            'images_with_multiple_admitted_unique_candidates':sum(sum(c['admitted_for_routing'] for c in x['candidates'])>1 for x in candidate_images),
            'formal_corpus_images':sum(x['in_formal_corpus'] for x in candidate_images),'records':len(records),
            'records_in_calibration922':sum(r['calibration_pool_row'] is not None for r in records),
            'manual_explicit_routes':len(overrides),'manual_family_only':len(family_directives)}}
    dump(a.out,out);dump(a.out.parent/'source_extraction_manifest.json',{'sources':sources,'confirmation_checks':confirmation_checks,'prepared_input_sha256':hashlib.sha256(a.out.read_bytes()).hexdigest(),'counts':out['counts']});print(json.dumps(out['counts'],indent=2))
if __name__=='__main__':main()
