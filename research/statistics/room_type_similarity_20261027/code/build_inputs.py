#!/usr/bin/env python3
"""Reconstruct minimal public-v2 room-purpose inputs without changing eligibility."""
import argparse, collections, gzip, hashlib, json, platform
from pathlib import Path
import numpy as np
import pandas as pd

COMMIT = 'b2b0898b90bd631df37f1f2e75e8380800a43cf8'
SOURCE_FILES = {
 'audit':'research/statistics/v2_evidence_audit_20261019/records.json.gz',
 'legacy_metadata':'research/data/processed_input_review_20261018/data.json.gz',
 'pool_conditions':'research/workers/personnel_composition_study_20261019/analysis/independent/POOL_IMAGE_CONDITIONS.csv',
 'features':'research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz',
 'reference_features':'research/difficulty/difficulty_mechanisms_v2_20261020/reference_conditions.csv',
}

def load_gz(p):
    with gzip.open(p,'rt',encoding='utf-8') as f: return json.load(f)

def jsonstr(v): return json.dumps(v, ensure_ascii=False, separators=(',',':'))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    records=load_gz(a.repo/SOURCE_FILES['audit'])['records']
    legacy=load_gz(a.repo/SOURCE_FILES['legacy_metadata'])
    legacy_images={i['image_id']:i for i in legacy['images']}
    pool=pd.read_csv(a.repo/SOURCE_FILES['pool_conditions'],low_memory=False)
    feat=pd.read_csv(a.repo/SOURCE_FILES['features'],dtype={'object_id':str},low_memory=False)
    assert not feat.object_id.duplicated().any()
    ref=pd.read_csv(a.repo/SOURCE_FILES['reference_features'])
    rows=[]; geometry=[]; labels={}; mismatches=[]
    base_fields=['object_id','worker_id','image_id','room_id','condition','origin','data_release','quality_usable','quality_use','pool_analysis_eligible','independent_vote_eligible','cleaning_disposition','geometry_status','reference_id','reference_version','binding_status','reference_full_available','raw_original_available','calculation_class','point_count','declared_pair_count','ring_confirmed','order_status']
    scalar_fields=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','iou_3d_corner_mean','IoU3D100']
    for r in records:
        im=r.get('image_evidence') or {}; old=legacy_images.get(r['image_id'],{})
        purpose=(im.get('room_spatial_classification') or {}).get('coarse_type')
        old_p=(old.get('room_spatial_classification') or {}).get('coarse_type')
        if purpose!=old_p: mismatches.append({'image_id':r['image_id'],'audit':purpose,'legacy':old_p})
        purpose_status='missing' if purpose in [None,''] else ('explicit_unknown' if purpose=='无法判断' else ('multifunction' if purpose=='开放复合空间' else 'recorded_purpose'))
        d={k:r.get(k) for k in base_fields}; d['object_id']=str(d['object_id'])
        d.update(image=r['image_code'],image_code=r['image_code'],building=r['building_id'],building_id=r['building_id'],
                 image_key=r['image_code']+'__'+r['condition'],room_type=purpose,room_type_status=purpose_status,
                 room_type_model=purpose if purpose else '__MISSING__',difficulty=r.get('current_class'),
                 is_oos=bool(r.get('is_oos')),is_doorway=bool(r.get('is_doorway')))
        d['layer']='oos' if d['is_oos'] else ('doorway' if d['is_doorway'] else ('ordinary' if d['quality_use']=='ordinary_primary' else 'other_or_hold'))
        d['formal_quality']=bool(r.get('quality_usable'))
        d['Q']=r.get('B8L2') if d['formal_quality'] else None
        d['B8L2']=d['Q'];d['D10']=r.get('D10') if d['formal_quality'] else None
        d['quality_exclusion_reasons_json']=jsonstr(r.get('quality_exclusion_reasons'))
        t=r.get('time_evidence') or {}
        d.update(source_time_seconds=t.get('source_active_time_seconds'),target_time_seconds=t.get('target_matched_time_seconds'),
                 time_source=t.get('source_kind'),time_source_status=t.get('source_status'),time_binding=t.get('source_binding'),
                 time_source_file=t.get('source_file'),time_missing_reason=t.get('source_missing_reason'),
                 time_target_missing_reason=t.get('target_missing_reason'))
        d['time_positive']=isinstance(d['source_time_seconds'],(int,float)) and np.isfinite(d['source_time_seconds']) and d['source_time_seconds']>0
        d['log_time']=np.log(d['source_time_seconds']) if d['time_positive'] else None
        meas=(r.get('measurements') or {}).get('same_reference_measurements') or {}
        for k in scalar_fields: d[k]=meas.get(k)
        scope=r.get('scope_evidence') or {}; excl=r.get('exclusion_attribution') or {}
        d.update(scope_response=scope.get('response'),scope_response_recorded=scope.get('response_recorded'),
                 scope_judgement_opportunity=scope.get('judgement_opportunity'),scope_correct=scope.get('correct'),
                 personal_exclusion_category=excl.get('category'),specific_person_error_candidate=excl.get('specific_person_error_candidate'),
                 historical_worker_exclusion=excl.get('historical_worker_exclusion'))
        rows.append(d)
        labels[r['image_id']]={'image_id':r['image_id'],'image':r['image_code'],'building':r['building_id'],
           'room_type':purpose,'room_type_status':purpose_status,'room_classification_sources_json':jsonstr(old.get('room_classification_sources')),
           'functions_json':jsonstr((im.get('room_spatial_classification') or {}).get('functions')),
           'focus_json':jsonstr((im.get('room_spatial_classification') or {}).get('focus')),
           'boundary_json':jsonstr((im.get('room_spatial_classification') or {}).get('boundary')),
           'main_visual_space':im.get('main_visual_space'),'expected_annotation_extent':im.get('expected_annotation_extent'),
           'difficulty':r.get('current_class'),'is_oos':bool(r.get('is_oos')),'is_doorway':bool(r.get('is_doorway')),
           'label_primary_source':SOURCE_FILES['audit']+'#image_evidence.room_spatial_classification.coarse_type',
           'label_source_metadata':SOURCE_FILES['legacy_metadata']+'#images.room_classification_sources'}
        geometry.append({k:r.get(k) for k in ['object_id','worker_id','image_id','image_code','condition','reference_id','reference_version','quality_usable','quality_use','cleaning_disposition','geometry_status','original_points','received_processed_points','preprocessed_points','points_1024x512','reference_evidence','coordinate_evidence']})
    df=pd.DataFrame(rows)
    feature_cols=[c for c in feat if c not in df.columns and c not in ['R5','H2','Rnew2']]
    df=df.merge(feat[['object_id']+feature_cols],on='object_id',how='left',validate='one_to_one')
    # Reference measurements retain their exact original reference IDs. No reference switching.
    for c in ref.columns:
        if c=='reference_id':continue
        lookup=ref.set_index('reference_id')[c]
        if c not in df: df[c]=df.reference_id.map(lookup)
        else: df[c]=df[c].fillna(df.reference_id.map(lookup))
    df['turn_delta']=df.get('annotation_turn5')-df.get('ref_turn5')
    df['actual_simplification']=np.where(df.annotation_turn5.notna()&df.ref_turn5.notna(),(df.annotation_turn5<df.ref_turn5).astype(float),np.nan)
    pcols=['pool_id','image_id','condition','layer','pool_n']
    ps=pool[pcols].rename(columns={'layer':'historical_pool_layer','pool_n':'historical_pool_n'})
    assert not ps[['image_id','condition']].duplicated().any()
    df=df.merge(ps,on=['image_id','condition'],how='left',validate='many_to_one')
    assert not df.object_id.duplicated().any()
    df.to_csv(a.out/'annotations.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(labels.values()).sort_values('image').to_csv(a.out/'image_labels.csv',index=False)
    image_rows=[]
    for key,g in df.groupby('image_key',sort=True):
        first=g.iloc[0]; q=g[g.formal_quality & g.Q.notna()]
        f=q.iloc[0] if len(q) else first
        d={c:f[c] for c in ['image_key','image','image_code','image_id','building','building_id','condition','room_type','room_type_model','room_type_status','difficulty','is_oos','is_doorway','pool_id','historical_pool_layer','historical_pool_n']}
        d.update(layer='oos' if f.is_oos else ('doorway' if f.is_doorway else ('ordinary' if len(q) and (q.quality_use=='ordinary_primary').all() else 'other_or_hold')),
                 n_records=len(g),n_formal=len(q),n_people=q.worker_id.nunique(),n_reference_ids=q.reference_id.nunique(),
                 reference_id=q.reference_id.iloc[0] if q.reference_id.nunique()==1 else None,
                 reference_version=q.reference_version.iloc[0] if q.reference_version.nunique()==1 else None,
                 mean_Q=q.Q.mean(),median_Q=q.Q.median(),sd_Q=q.Q.std(ddof=1),p10_Q=q.Q.quantile(.1),
                 mean_D10=q.D10.mean(),sd_D10=q.D10.std(ddof=1),
                 low_Q50=(q.Q<50).mean() if len(q) else None,low_Q60=(q.Q<60).mean() if len(q) else None,
                 workers_json=jsonstr(sorted(q.worker_id.unique())),object_ids_json=jsonstr(q.object_id.tolist()))
        for c in [x for x in ref.columns if x!='reference_id']:
            vals=q[c].dropna().unique()
            d[c]=vals[0] if len(vals)==1 else None
        for c in ['annotation_turn5','pair_n','near_straight_nodes_5deg','short_turn_edges','turn_delta','actual_simplification','omission','extension','bottom_bias_9','S_bottom_deg','dir','Hmean','height_mean_ratio','log_area_ratio','unmatched_ref_9','iou_2d']:
            d['mean_'+c]=q[c].mean() if c in q else None
            d['sd_'+c]=q[c].std(ddof=1) if c in q else None
            d['n_'+c]=int(q[c].notna().sum()) if c in q else 0
        image_rows.append(d)
    images=pd.DataFrame(image_rows)
    images.to_csv(a.out/'images.csv',index=False)
    # Small public geometry dependency, only anonymous exact records; no free-text review copying.
    with gzip.open(a.out/'annotation_geometry.jsonl.gz','wt',encoding='utf-8') as f:
        for x in geometry:f.write(jsonstr(x)+'\n')
    coverage=[]
    for (cond,layer),g in df.groupby(['condition','layer']):
        q=g[g.formal_quality & g.Q.notna()]
        coverage.append({'condition':cond,'layer':layer,'records':len(g),'formal_records':len(q),'formal_images':q.image.nunique(),'formal_buildings':q.building.nunique(),'formal_people':q.worker_id.nunique()})
    pd.DataFrame(coverage).to_csv(a.out/'coverage.csv',index=False)
    purposes=[]
    for (cond,layer,purpose),g in images[images.n_formal>0].groupby(['condition','layer','room_type_model']):
        sub=df[df.image_key.isin(g.image_key)&df.formal_quality&df.Q.notna()]
        purposes.append({'condition':cond,'layer':layer,'room_type':purpose,'images':len(g),'buildings':g.building.nunique(),'people':sub.worker_id.nunique(),'records':len(sub),'mean_Q_image_equal':g.mean_Q.mean(),'mean_D10_image_equal':g.mean_D10.mean(),'mean_Q_record_equal':sub.Q.mean(),'mean_person_sd':g.sd_Q.mean(),'simple_images':int((g.difficulty=='简单').sum()),'medium_images':int((g.difficulty=='中等').sum()),'hard_images':int((g.difficulty=='困难').sum())})
    pd.DataFrame(purposes).to_csv(a.out/'purpose_coverage.csv',index=False)
    pd.DataFrame(mismatches,columns=['image_id','audit','legacy']).drop_duplicates().to_csv(a.out/'purpose_source_mismatches.csv',index=False)
    checks={'source_commit':COMMIT,'records':len(df),'image_condition_rows':len(images),'image_labels':len(labels),
      'purpose_source_mismatches':len({x['image_id'] for x in mismatches}),
      'ordinary_manual_formal':int(((df.condition=='manual')&(df.layer=='ordinary')&df.formal_quality&df.Q.notna()).sum()),
      'ordinary_semi_formal':int(((df.condition=='semi')&(df.layer=='ordinary')&df.formal_quality&df.Q.notna()).sum()),
      'duplicate_object_ids':int(df.object_id.duplicated().sum()),
      'formal_Q_D10_mismatch_n':int((df.formal_quality & (df.Q.notna()!=df.D10.notna())).sum()),
      'source_files':[{ 'role':k,'path':v,'bytes':(a.repo/v).stat().st_size,'sha256':hashlib.sha256((a.repo/v).read_bytes()).hexdigest()} for k,v in SOURCE_FILES.items()],
      'requested_unavailable':['research/data/releases/v2/analysis_input/data.json.gz'],
      'upstream_scoping_now_available':'research/statistics/room_type_similarity_scoping_20261027/',
      'reconstruction':'Public v2 evidence contains adopted purpose; legacy effective manifest supplies source provenance only, never replaces v2 quality or geometry.',
      'same_physical_room_policy':'All primary source-target tests use different buildings; no invented room clustering or transitive relation expansion.',
      'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}
    (a.out/'INPUT_RECEIPT.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    print(pd.DataFrame(coverage).to_string(index=False))
    print(pd.DataFrame(purposes).to_string(index=False))

if __name__=='__main__':main()
