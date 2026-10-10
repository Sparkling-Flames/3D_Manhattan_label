#!/usr/bin/env python3
"""Evaluate additional already-frozen geometry with explicit groups and targets.

No pairing, winding, repair or raw-point reconstruction is attempted. Each
image uses one explicit default reference or each record has a pre-frozen
binding. Scores are never used to select a reference or a building split.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import pandas as pd

from quality_v11 import score_geometry, load_parameters
from run_replay import read, dump, csv, flatten


def load_reference_bindings(path):
    """Read target identities only; human grades/notes are never consumed.

    Accept the unchanged original review JSON (``ratings``), or an export
    containing ``bindings``. Every item must identify the image and record.
    """
    if path is None:
        return {}, None
    path=Path(path); data=read(path)
    entries=data.get('bindings',data.get('ratings')) if isinstance(data,dict) else data
    if not isinstance(entries,list):
        raise ValueError('Reference bindings require a bindings/ratings array or an array')
    bindings={}
    for entry in entries:
        image=entry.get('image_code',entry.get('imageCode'))
        record=entry.get('record_id',entry.get('recordId'))
        ref=entry.get('reference_id',entry.get('referenceId'))
        version=entry.get('reference_version',entry.get('referenceVersion'))
        if any(not isinstance(v,str) or not v for v in (image,record,ref,version)):
            raise ValueError('Each binding requires nonempty image, record, reference ID and version')
        key=(image,record)
        if key in bindings:
            raise ValueError('Duplicate record in explicit reference bindings')
        bindings[key]=(ref,version)
    return bindings,hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frozen-geometry',required=True)
    ap.add_argument('--parameters',required=True)
    ap.add_argument('--bands',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--reference-bindings',help='Fixed image/record to reference ID/version sidecar; accepts unchanged original review JSON without using grades')
    ap.add_argument('--allow-image-default-with-multiple-references',action='store_true',
                    help='Explicitly authorize already-fixed per-image defaults when multiple GT versions exist; original36 must use its original reference-bindings sidecar instead')
    ap.add_argument('--inventory-only',action='store_true')
    args=ap.parse_args()
    path=Path(args.frozen_geometry); data=read(path); config=read(args.parameters)
    params=load_parameters(args.parameters); bands=read(args.bands)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    bindings,bindings_hash=load_reference_bindings(args.reference_bindings)
    images=data.get('images')
    if not isinstance(images,list):raise ValueError('Frozen export requires an images array')
    groups=[];identities=[];jobs=[]
    used_ids=set()
    for im in images:
        if not isinstance(im.get('code'),str):raise ValueError('Each image requires an explicit code')
        building=im.get('building') or None
        split=('development_replay' if building in config['development_buildings'] else
               'new_building_validation' if building else 'group_metadata_missing')
        historical=im.get('historical_exposure','unknown')
        if split=='development_replay':historical='known_historical_development'
        groups.append({'image_code':im['code'],'building':building,'room':im.get('room') or None,
          'evaluation_group':split,'historical_exposure':historical,
          'not_used_for_current_parameter_choice':split=='new_building_validation',
          'independent_blind_test_claimed':False,
          'image_path':im.get('imagePath'),
          'raw_annotation_records':len(im.get('annotations',[]))})
        references={}
        for g in im.get('groundtruths',[]):
            key=(g.get('id'),g.get('version'))
            if key in references:raise ValueError('Duplicate fixed-reference ID/version within image')
            references[key]=g
        for ann in im.get('annotations',[]):
            aid=ann.get('id')
            if not aid:raise ValueError('Each record requires its original stable ID')
            if (im['code'],aid) in used_ids:raise ValueError('Duplicate original record in frozen export')
            used_ids.add((im['code'],aid))
            identity_key=(im['code'],aid)
            binding_problem=None
            record_has_binding=('referenceId' in ann or 'referenceVersion' in ann)
            if identity_key in bindings:
                binding=bindings[identity_key]; binding_source='explicit_sidecar'
                if record_has_binding and binding!=(ann.get('referenceId'),ann.get('referenceVersion')):
                    binding_problem='Conflicting record and sidecar reference bindings; no target selected.'
            elif record_has_binding:
                binding=(ann.get('referenceId'),ann.get('referenceVersion'))
                binding_source='explicit_record'
            else:
                binding=(im.get('defaultReferenceId'),im.get('defaultReferenceVersion'))
                binding_source='fixed_image_default'
                if len(references)>1 and not args.allow_image_default_with_multiple_references:
                    binding_problem='Multiple reference versions without explicit record/sidecar binding; image default not silently substituted.'
            gt=references.get(binding)
            if binding_problem is not None:gt=None
            identity={'review_id':ann.get('reviewId',aid),'record_id':aid,
                      'image_code':im['code'],'building':building,'room':im.get('room') or None,
                      'evaluation_group':split,'historical_exposure':historical,
                      'reference_id':binding[0],'reference_version':binding[1],
                      'reference_binding_source':binding_source,
                      'reference_binding_issue':binding_problem,
                      'geometry_source':str(path),'geometry_source_sha256':source_hash,
                      'preprocessing_version':ann.get('preprocessing'),
                      'pairing_and_order_reused_without_changes':True,
                      'original_scope_response':ann.get('scopeResponse')}
            identities.append({**identity,'has_top3d':ann.get('top3d') is not None,
                              'has_bottom3d':ann.get('bottom3d') is not None,
                              'fixed_reference_found':gt is not None})
            policy=im.get('targetApplicability','conditional_geometry')
            reason=im.get('targetInapplicabilityReason')
            if gt is None:
                gt={}
                policy='data_missing'
                reason=binding_problem or 'No matching pre-frozen reference ID/version; no replacement reference chosen.'
            jobs.append((ann,gt,identity,policy,reason))
    # These artifacts are committed before the first call to score_geometry.
    csv(out/'image_groups_before_scoring.csv',groups)
    csv(out/'record_inventory_before_scoring.csv',identities)
    dump(out/'evaluation_contract_before_scoring.json',{
        'created_unix':time.time(),'geometry_sha256':source_hash,
        'reference_bindings_sha256':bindings_hash,
        'allow_image_default_with_multiple_references':args.allow_image_default_with_multiple_references,
        'parameters_sha256':hashlib.sha256(Path(args.parameters).read_bytes()).hexdigest(),
        'bands_sha256':hashlib.sha256(Path(args.bands).read_bytes()).hexdigest(),
        'parameter_definition_frozen_at':config['frozen_at_utc'],
        'selection_policy':'all supplied records retained; all supplied images evaluated when required frozen geometry exists',
        'group_policy':'whole buildings, no cross-view random split; missing building IDs remain unresolved',
        'historical_blind_status':'not inferred from a new building ID',
        'post_validation_change_policy':'any groups used to change the method become development; record version change',
        'inventory_only':args.inventory_only})
    if args.inventory_only:
        print(json.dumps({'images':len(groups),'records':len(jobs),'scored':0},ensure_ascii=False));return
    rows=[];full=[]
    for index,(ann,gt,identity,policy,reason) in enumerate(jobs):
        result=score_geometry(ann,gt,params,target_applicability=policy,
                              target_inapplicability_reason=reason)
        rows.append(flatten(result,identity,bands))
        # Preserve the exact submitted arrays, raw points and provenance,
        # including invalid or incomplete originals, in the local results file.
        full.append({**identity,**result,'original_annotation':ann,'frozen_reference':gt})
        if (index+1)%100==0:print('processed',index+1,'/',len(jobs),flush=True)
    frame=pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        'review_id','record_id','image_code','building','room','evaluation_group',
        'reference_id','reference_version','score_status','quality_score','quality_band',
        'reason_codes','failure_classes'])
    csv(out/'all_records_scores.csv',frame)
    dump(out/'all_records_with_original_geometry.json',full)
    csv(out/'unavailable_manual_review.csv',frame.loc[frame.score_status=='unavailable'])
    csv(out/'groups_and_status_counts.csv',frame.groupby(
        ['evaluation_group','building','score_status','quality_band'],dropna=False).size().reset_index(name='record_count'))
    new_groups=[g for g in groups if g['evaluation_group']=='new_building_validation']
    available_new=frame[(frame.score_status=='available') & (frame.evaluation_group=='new_building_validation')]
    summary={'images':len(groups),'original_records':len(rows),
             'available_records':int((frame.score_status=='available').sum()),
             'unavailable_records':int((frame.score_status=='unavailable').sum()),
             'new_building_validation_attempted_images':len(new_groups),
             'new_building_validation_images_with_evaluable_scores':int(available_new.image_code.nunique()),
             'new_building_validation_evaluable_records':len(available_new),
             'new_buildings_attempted':len({g['building'] for g in new_groups}),
             'new_buildings_with_evaluable_scores':int(available_new.building.nunique()),
             'parameters_modified_after_viewing_results':False,
             'historically_unseen_claimed':False,
             'geometry_source_sha256_unchanged':hashlib.sha256(path.read_bytes()).hexdigest()==source_hash}
    dump(out/'evaluation_summary.json',summary);print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
