#!/usr/bin/env python3
"""Replay frozen raw geometry; no reprocessing and no fitting to human grades.

For additional frozen exports use score_dataset.py. This original36 replay
records its building groups before evaluation. No current image is a holdout.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import itertools
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from quality_v11 import score_geometry, scalar_score, load_parameters, Parameters, _plain


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(_plain(data), ensure_ascii=False, indent=2,
                                    allow_nan=False)+'\n', encoding='utf-8')


def csv(path, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False, encoding='utf-8-sig', float_format='%.12g')
    return frame


def band(score, config):
    if score is None or not np.isfinite(score):
        return '不可评价'
    t = config['thresholds']
    if score >= t['high']:
        return '高'
    if score >= t['good']:
        return '较好'
    if score >= t['fair']:
        return '一般'
    return '较差'


def flatten(out, identity, bands):
    row = {**identity, 'algorithm_version': out['algorithm_version'],
           'score_status': out['status'], 'quality_score': out['quality_score'],
           'quality_band': band(out['quality_score'], bands),
           'reason_codes': '|'.join(out['reason_codes']),
           'failure_classes': '|'.join(out['failure_classes'])}
    for role in ('annotation', 'reference'):
        val = out[role+'_validity']
        for key in ('valid_2d', 'valid_3d', 'spherical_boundary_available'):
            row[role+'_'+key] = val[key]
        row[role+'_warning_codes'] = '|'.join(x['code'] for x in val['warnings'])
        row[role+'_geometry_sha256'] = out[role+'_geometry_sha256']
    for key, value in out['metrics'].items():
        row[key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
    for key, value in out.get('height_diagnostics', {}).items():
        row[key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
    row.update({'availability_'+k: v for k, v in out['metric_availability'].items()})
    row['traditional_issues'] = '|'.join(out['traditional_issues'])
    row['auxiliary_issues'] = '|'.join(out.get('auxiliary_issues', []))
    return row


def parameters_sensitivity(frame, params, bands, outdir):
    """Nine two-scale stress configurations, not additional tuned winners."""
    rows, pairs, bandrows = [], [], []
    grid = list(itertools.product([3.5, 4., 4.5], [.4, .5, .6]))
    matrix = []
    for _, r in frame.iterrows():
        scores = []
        if r.score_status != 'available':
            continue
        for boundary, height in grid:
            p = replace(params, boundary_half_deg=boundary, height_relative_half=height)
            scores.append(scalar_score(r.iou, r.S_top_deg, r.S_bottom_deg,
                                       r.dir, r.flat, r.Hstar, p)['quality_score'])
        matrix.append(scores)
        b = [band(s, bands) for s in scores]
        rows.append({'review_id':r.review_id, 'image_code':r.image_code,
                     'frozen_score':r.quality_score, 'score_min':min(scores), 'score_max':max(scores),
                     'full_range':max(scores)-min(scores), 'frozen_band':r.quality_band,
                     'possible_bands':'|'.join(x for x in ['较差','一般','较好','高'] if x in b),
                     'band_unchanged_all9':len(set(b))==1})
        for shift in bands['sensitivity_threshold_shift_points']:
            cfg = {**bands, 'thresholds':{k:v+shift for k,v in bands['thresholds'].items()}}
            bandrows.append({'review_id':r.review_id, 'image_code':r.image_code,
                             'quality_score':r.quality_score, 'frozen_band':r.quality_band,
                             'threshold_shift_points':shift, 'shifted_band':band(r.quality_score,cfg)})
    available = frame[frame.score_status=='available'].reset_index(drop=True)
    mat = np.asarray(matrix)
    for i in range(len(available)):
        for j in range(i+1, len(available)):
            delta = mat[i]-mat[j]
            base = float(available.iloc[i].quality_score-available.iloc[j].quality_score)
            pairs.append({'id_a':available.iloc[i].review_id,'id_b':available.iloc[j].review_id,
                          'frozen_gap':base,'min_gap':delta.min(),'max_gap':delta.max(),
                          'ever_reversed':bool(np.any(delta*base < -1e-10))})
    csv(outdir/'parameter_sensitivity36.csv',rows)
    csv(outdir/'parameter_pair_sensitivity630.csv',pairs)
    csv(outdir/'threshold_sensitivity108.csv',bandrows)
    dump(outdir/'parameter_sensitivity_settings.json',{
        'purpose':'stress only; no configuration selected using ranks, bands or old ratings',
        'configurations':[{'boundary_half_deg':a,'height_relative_half':b} for a,b in grid],
        'other_parameters_fixed':{'direction_half_deg':5.,'flatness_half_deg':2.,'intrinsic_max_discount':.15},
        'intervals_are_not_confidence_intervals':True})


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    ap.add_argument('--v1-package',required=True)
    ap.add_argument('--audit',required=True)
    ap.add_argument('--height-results',required=True)
    ap.add_argument('--parameters',required=True)
    ap.add_argument('--bands',required=True)
    ap.add_argument('--out',required=True)
    args=ap.parse_args()
    source=Path(args.source); old=Path(args.v1_package); audit=Path(args.audit)
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    config=read(args.parameters); bands=read(args.bands); params=load_parameters(args.parameters)
    frozen=read(source/'inputs/frozen_geometry.json')
    # Use the original ratings file ONLY to recover its explicit target binding.
    # Quality labels/notes are attached in a separate final reporting step below.
    original_ratings=read(source/'inputs/review36_user_20261008.json')['ratings']
    bindings={r['reviewId']:(r['referenceId'],r['referenceVersion']) for r in original_ratings}
    groups=[]
    for im in frozen['images']:
        building=im.get('building')
        group='development_replay' if building in config['development_buildings'] else ('new_building_validation' if building else 'group_metadata_missing')
        groups.append({'image_code':im['code'],'building':building,'room':im.get('room') or None,
                       'evaluation_group':group,'prior_exposure':'known_historical_development' if group=='development_replay' else 'unknown',
                       'annotation_records':len(im['annotations'])})
    # Record groups and exact parameter hashes before any quality computation.
    csv(out/'evaluation_groups.csv',groups)
    dump(out/'run_start.json',{'started_unix':time.time(),
          'parameters_sha256':hashlib.sha256(Path(args.parameters).read_bytes()).hexdigest(),
          'bands_sha256':hashlib.sha256(Path(args.bands).read_bytes()).hexdigest(),
          'groups_written_before_scoring':True,'new_real_validation_images':sum(g['evaluation_group']=='new_building_validation' for g in groups)})
    full, flat, primary=[] ,[],[]
    for im, group in zip(frozen['images'],groups):
        for ann in im['annotations']:
            rid=ann['reviewId']
            for gt in im['groundtruths']:
                is_primary=(gt['id'],gt['version'])==bindings[rid]
                identity={'review_id':rid,'record_id':ann['id'],'image_code':im['code'],
                          'building':im.get('building'),'room':im.get('room') or None,
                          'evaluation_group':group['evaluation_group'],
                          'reference_id':gt['id'],'reference_version':gt['version'],
                          'is_rating_reference':is_primary,'pair_count':len(ann['bottom3d']),
                          'preprocessing_version':ann.get('preprocessing'),
                          'geometry_source':'source/inputs/frozen_geometry.json'}
                result=score_geometry(ann,gt,params)
                full.append({**identity,**result})
                row=flatten(result,identity,bands);flat.append(row)
                if is_primary:primary.append(dict(row))
        print('replayed',im['code'],flush=True)
    assert len(primary)==36 and len(flat)==48
    dump(out/'reference_specific_results48.json',full)
    csv(out/'reference_specific_scores48.csv',flat)
    primary=sorted(primary,key=lambda r:r['review_id'])
    frame=pd.DataFrame(primary)
    # A result copy is kept without any old grade for use in figure selection.
    csv(out/'scores36_geometry_only.csv',frame)
    parameters_sensitivity(frame,params,bands,out)
    # Old ratings are attached unchanged AFTER geometry scoring and stress tests.
    human={r['reviewId']:r for r in original_ratings}
    baseline=pd.read_csv(old/'deliverables/layout_quality_research_v1_scores36.csv') if (old/'deliverables/layout_quality_research_v1_scores36.csv').exists() else pd.read_csv(old/'results/scoring/research_scores36.csv')
    baseline_key='review_id' if 'review_id' in baseline else 'reviewId'
    v1=baseline.set_index(baseline_key).to_dict('index')
    for r in primary:
        h=human[r['review_id']]
        r.update(human_score_original=h['overallScore'],
                 human_scope_note_original=h.get('scopeNote',''),
                 human_geometry_note_original=h.get('geometryNote',''),
                 human_tags_original=json.dumps(h.get('tags',[]),ensure_ascii=False),
                 human_grade_role='imagewise pilot only; never optimized',
                 v1_original_score=v1[r['review_id']]['score_research_v1'])
        r['new_minus_v1']=r['quality_score']-r['v1_original_score'] if r['quality_score'] is not None else None
    final=csv(out/'scores36_with_original_ratings.csv',primary)
    # Complete geometry replay, including failures. Synthetic rows never count as images.
    controls=[]
    for path,group in [(old/'results/geometry/control_geometries.json','v1_control251'),
                       (old/'results/height_guard/large_room_uniform_height9_geometries.json','v1_height_control9'),
                       (audit/'numeric/independent_counterexample_geometries.json','new_audit8'),
                       (Path(args.height_results)/'new_height_control_geometries.json','new_height148')]:
        entries=read(path)
        for entry in entries:
            controls.append({**entry,'source_group':group,'source_file':str(path)})
    cfull,cflat=[],[]
    for k,c in enumerate(controls):
        cid=c.get('case_id',c.get('case'))
        ident={'case_id':cid,'source_group':c['source_group'],'family':c.get('family',''),
               'record_kind':'synthetic_control_NOT_new_image','geometry_source':c['source_file']}
        res=score_geometry(c['annotation'],c['reference'],params)
        cfull.append({**ident,**res});cflat.append(flatten(res,ident,bands))
        if (k+1)%100==0: print('controls',k+1,'/',len(controls),flush=True)
    dump(out/'control_replay_full.json',cfull)
    cf=csv(out/'control_replay.csv',cflat)
    # Keep unavailable records separate from poor quality.
    review=[]
    for r in [*full,*cfull]:
        if r['status']!='unavailable':continue
        review.append({'review_id':r.get('review_id'), 'case_id':r.get('case_id'),
           'record_id':r.get('record_id'),'image_code':r.get('image_code'),
           'record_kind':'real_annotation' if 'review_id' in r else 'synthetic_regression',
           'score_status':'unavailable','quality_score':None,'quality_band':'不可评价',
           'failure_classes':'|'.join(r['failure_classes']),'reason_codes':'|'.join(r['reason_codes']),
           'evidence_json':json.dumps(r['issues'],ensure_ascii=False),
           'geometry_source':r['geometry_source'],
           'action':'Inspect original coordinates and cited edge/vertex evidence; never auto-repair.'})
    csv(out/'unavailable_review_queue.csv',review)
    # Descriptive old-grade order check only; same grades are not equal-quality labels.
    oldchecks=[]
    for im,g in final.groupby('image_code',sort=False):
        for a,b in itertools.combinations(g.to_dict('records'),2):
            delta=a['human_score_original']-b['human_score_original']
            if not delta:continue
            oldchecks.append({'image_code':im,'building':a['building'],
                'id_a':a['review_id'],'id_b':b['review_id'],
                'old_grade_gap':delta,'new_score_gap':a['quality_score']-b['quality_score'],
                'agrees_old_imagewise_order':delta*(a['quality_score']-b['quality_score'])>0,
                'not_validation_labels':True})
    csv(out/'old_grade_auxiliary_pairs61.csv',oldchecks)
    counts=final.groupby(['image_code','building','quality_band'],dropna=False).size().reset_index(name='record_count')
    csv(out/'bands_by_image_selected_records_only.csv',counts)
    summary={'algorithm_version':config['algorithm_version'],'real_images':len(groups),
       'buildings':len({g['building'] for g in groups}),'real_annotations':len(final),
       'reference_specific_rows':len(flat),'new_validation_images':0,
       'real_available':int((final.score_status=='available').sum()),
       'real_unavailable':int((final.score_status!='available').sum()),
       'synthetic_replay_rows':len(cf),'synthetic_available':int((cf.score_status=='available').sum()),
       'synthetic_unavailable':int((cf.score_status!='available').sum()),
       'band_counts_selected_panel_only':final.quality_band.value_counts().to_dict(),
       'max_new_deduction_points':float((-final.new_minus_v1).max()),
       'median_new_deduction_points':float((-final.new_minus_v1).median()),
       'max_v1_recompute_error':float((final.score_v1_recomputed-final.v1_original_score).abs().max()),
       'original_UB_missing':int(final.U.isna().sum()),
       'old_imagewise_different_grade_pairs':len(oldchecks),
       'old_order_agreement_count':sum(r['agrees_old_imagewise_order'] for r in oldchecks),
       'claim_limit':'No additional image bytes were obtained. All 6 images are development/replay. Counts are annotation records, not unique people. No population image-quality/difficulty inference.'}
    dump(out/'replay_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
