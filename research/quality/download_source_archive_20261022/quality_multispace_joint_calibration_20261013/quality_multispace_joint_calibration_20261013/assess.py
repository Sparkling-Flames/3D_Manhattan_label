#!/usr/bin/env python3
"""Replay one actual record, or route a new 3D geometry to an admitted image.

python assess.py --record-id R00397
python assess.py --record-id R03197 --out assessed.json
python assess.py --geometry example_geometry.json --image-code uNb9QFRL6hY-67

External geometry: {"bottom3d":[[x,y,z],...],"top3d":[...]}. y=-1 is
the floor; camera height is the length unit. Optional raw input uses the exact
"before_preprocessing_points" and "links_zero_based" schema. Geometry must
already have a certified ring: this entry point never invents corner pairing.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, sys
from pathlib import Path
import numpy as np
from shapely.geometry import Point
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'routing'),str(ROOT/'calibration'),str(ROOT/'experiments'),str(ROOT/'integration')]
from router import prepare_reference_set,route_floor,strict_polygon,floor_metrics
from run_routing import engine,raw_x
from score import score_metrics,BASELINE
from run_impact import descriptor
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--record-id');g.add_argument('--geometry',type=Path)
    p.add_argument('--image-code');p.add_argument('--candidate');p.add_argument('--out',type=Path);a=p.parse_args()
    config=load(ROOT/'calibration/recommended_parameters.json');name=a.candidate or config['recommended']
    if name not in config['candidates']:p.error('Unknown candidate; use a name in calibration/recommended_parameters.json')
    c=config['candidates'][name]
    data=load(ROOT/'routing/inputs/prepared_input.json');frozen=load(ROOT/'baseline/inputs/calibration_records.json');latest=load(ROOT/'sources/main/research/quality_parallel_local_20261012/record_results.json')['rows'];cfg=load(ROOT/'routing/config.json')
    metadata=dict(config_name=name,config_sha256=sha(ROOT/'calibration/recommended_parameters.json'),calibration_input_sha256=sha(ROOT/'baseline/inputs/calibration_records.json'),routing_input_sha256=sha(ROOT/'routing/inputs/prepared_input.json'),source_main_commit='fdfc8a51ad668c83172ca4a9cf0105f417dac61c',input_geometry_repaired=False,quality_grade=None,formal_eligibility_newly_granted=False,spherical_samples=2048,height_samples=4096)
    manual=None;family=None;record=None;raw=None
    if a.record_id:
        record=next((r for r in data['records'] if r['record_id']==a.record_id),None)
        if record:
            image=next(im for im in data['candidate_images'] if im['image_id']==record['image_id']);geometry=record['geometry'];refs=[r for r in image['candidates'] if r['admitted_for_routing']]
            metadata.update(record_id=a.record_id,object_id=record['object_id'],image_code=record['image_code'],input_version=record['input_version'],current_points_sha256_canonical_v1=record['current_points_sha256_canonical_v1'],raw_points_sha256_canonical_v1=record['raw_points_sha256_canonical_v1'],qualification=record['current_eligibility_ledger'])
            manual=data['manual_overrides'].get(a.record_id);family=data['manual_family_directives'].get(a.record_id);raw=record['source_object']
        else:
            fr=next((r for r in frozen['rows'] if r['id']==a.record_id),None)
            if fr is None:
                led=load(ROOT/'sources/main/research/quality_parallel_local_20261012/eligibility_ledger.json')['records'];gate=next((r for r in led if r['record_id']==a.record_id),None)
                result=metadata|dict(status='unavailable',record_id=a.record_id,qualification=gate,reason='record_has_no_certified_scoring_geometry_in_delivered_inputs',score=None,floor_score=None);return output(result,a.out)
            geometry=frozen['geometries'][fr['object_id']];rg=frozen['geometries'][fr['reference_object_id']];refs=[dict(candidate_id=fr['reference_object_id'],reference_version=next(r for r in latest if r['record_id']==a.record_id)['reference_version'],full_reference_available=True,full_geometry=rg,floor_xz_h=np.asarray(rg['bottom3d'])[:,[0,2]].tolist(),admitted_for_routing=True,reference_points_sha256_from_calibration=fr['reference_points_sha256'])]
            # This reuses the frozen reference for a diagnostic score, not new scope admission.
            gate=next(r for r in latest if r['record_id']==a.record_id);metadata.update(record_id=a.record_id,object_id=fr['object_id'],image_code=fr['image_code'],legacy_input_version=gate['input_version'],current_formal_gate=gate['current_formal_gate'],qualification=gate['use_barriers'],conditional_personnel_eligible=gate['conditional_personnel_eligible'],current_points_sha256=fr['current_points_sha256'],reference_protocol='fixed frozen reference; no newly approved multi-space image');raw=next(r for r in load(ROOT/'baseline/input_quality/results/source_layers_922.json') if r['object_id']==fr['object_id'])
    else:
        if not a.image_code:p.error('--geometry requires --image-code of an already admitted image')
        image=next((im for im in data['candidate_images'] if im['image_code']==a.image_code),None)
        if image is None:p.error('This image has no admitted candidate registry in the deliverable; do not invent a new legal space')
        obj=load(a.geometry);geometry=obj.get('geometry',obj);refs=[r for r in image['candidates'] if r['admitted_for_routing']];raw=obj if 'before_preprocessing_points' in obj else None
        metadata.update(image_code=a.image_code,external_input_sha256=sha(a.geometry),qualification='external_not_adjudicated',conditional_personnel_eligible=False)
    try:metadata['raw_input_diagnostics']=raw_x(raw) if raw is not None else dict(status='unavailable',reason='raw_endpoint_and_pairing_layer_not_supplied')
    except (TypeError,ValueError,KeyError,IndexError) as e:metadata['raw_input_diagnostics']=dict(status='unavailable',reason='invalid_supplied_raw_input_layer: '+str(e))
    if geometry is None:return output(metadata|dict(status='unavailable',reason='certified_geometry_unavailable',score=None,floor_score=None),a.out)
    try:
        if not isinstance(geometry,dict):raise ValueError('geometry must be a JSON object')
        bottom=np.asarray(geometry['bottom3d'],float)
        if bottom.ndim!=2 or bottom.shape[1]!=3 or len(bottom)<3 or not np.isfinite(bottom).all():raise ValueError('bottom3d must be a finite N by 3 array with at least three vertices')
        if not np.allclose(bottom[:,1],-1,atol=1e-10,rtol=0):raise ValueError('expected floor y=-1 camera-height units')
        if geometry.get('top3d') is not None and len(geometry['top3d']):
            top=np.asarray(geometry['top3d'],float)
            if top.shape!=bottom.shape or not np.isfinite(top).all():raise ValueError('top3d must be a finite array with the same N by 3 shape as bottom3d')
        poly=strict_polygon(bottom[:,[0,2]])
        if not poly.contains(Point(0,0)):raise ValueError('camera_not_inside_preserved_floor_protocol')
    except (TypeError,ValueError,KeyError,IndexError) as e:return output(metadata|dict(status='unavailable',reason=str(e),score=None,floor_score=None),a.out)
    auto=route_floor(bottom[:,[0,2]],prepare_reference_set(refs,cfg));route=copy.deepcopy(auto)
    if family:
        route=route_floor(bottom[:,[0,2]],prepare_reference_set([r for r in refs if r['candidate_id'] in family['allowed_candidate_ids']],cfg));route['manual_family_source']=family
        route['route_reason']='manual_structural_family_then_'+route['route_reason']
    if manual:
        assert record and manual['object_id']==record['object_id'];route.update(candidate_id=manual['selected_candidate_id'],route_reason='explicit_user_reference_assignment',manual_source=manual,uncertainty='manual_directive_quality_and_confidence_not_inferred')
    ref=next(r for r in refs if r['candidate_id']==route['candidate_id']);au,sp,qv,ch,strict,hm=engine(ROOT/'baseline')
    rb=[[x,-1,z] for x,z in ref['floor_xz_h']];m=dict(I=floor_metrics(bottom[:,[0,2]],ref['floor_xz_h'])['I'],Sb=float(sp.spherical_sym_distance(geometry['bottom3d'],rb,2048)),D=float(au.direction_residual(geometry,au.direction_axis(geometry))),Hm=None,Hc=None)
    fullstatus='unavailable_top_pending';iou=None;reason=[]
    if ref['full_reference_available'] and geometry.get('top3d'):
        old=qv.score_geometry(geometry,ref['full_geometry'],spherical_samples=2048,height_samples=4096);fullstatus=old['status'];reason=old['reason_codes']
        if fullstatus=='available':m.update(Hm=old['metrics']['Hmean'],Hc=ch.centered_height_components(geometry,ref['full_geometry'],samples=4096,height_module=hm)['Hcenter']);iou=old['metrics']['iou_3d_corner_mean']
    d=descriptor(geometry,{name:c});new=score_metrics(m,c,d,reference_height_available=ref['full_reference_available']);old=score_metrics(m,BASELINE,d,reference_height_available=ref['full_reference_available'])
    result=metadata|dict(status=new['status'],route=route,automatic_route_before_manual=auto,selected_reference={k:ref.get(k) for k in ['candidate_id','reference_version','full_reference_available','points_sha256_canonical_v1','floor_sha256_canonical_v1','reference_points_sha256_from_calibration']},metrics=m,score=new['score'],floor_score=new['floor_score'],loss_decomposition=new,baseline=old,IoU3D_corner_mean=iou,full_metric_status=fullstatus,full_metric_reasons=reason,route_is_quality_acceptance=False)
    output(result,a.out)
def output(result,out):
    s=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if out:out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s,encoding='utf-8')
    else:print(s,end='')
if __name__=='__main__':main()
