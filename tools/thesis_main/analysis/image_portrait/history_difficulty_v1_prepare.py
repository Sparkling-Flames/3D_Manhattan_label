"""Missing-aware input preparation; immutable raw inputs, no legacy difficulty.

A missing count on an invalid response stays missing. The 106 explicit user tags
are read only from the confirmed selection-record namespace and stored apart.
"""
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *


def run():
    from tools.thesis_main.analysis.image_portrait.build_bundle import verify_bundle
    OUT.mkdir(parents=True,exist_ok=True);check=verify_bundle(B)
    raw=read(B/'human/responses.jsonl.gz');rawmap={r['canonical_annotation_id']:r for r in raw}
    p=OLD/'foundation/human/response_metrics.csv.gz';df=pd.read_csv(p)
    assert len(df)==len(rawmap)==2501
    missing=[]
    for r in df.to_dict('records'):
        z=rawmap[r['canonical_annotation_id']]
        assert (r['image_id'],r['worker_id'],r['raw_condition'])==(z['image_id'],z['worker_id'],z['raw_condition'])
        if pd.notna(r['effective_point_count']):assert int(r['effective_point_count'])==len(z['effective_points_1024x512'])
        else:
            assert not r['geometry_valid']
            missing.append(dict(canonical_annotation_id=r['canonical_annotation_id'],image_id=r['image_id'],worker_id=r['worker_id'],raw_condition=r['raw_condition'],raw_effective_length=len(z.get('effective_points_1024x512') or []),action='retain missing count and invalid status; never zero-impute'))
        assert bool(r['main_worker_included'])==(z['worker_id'] not in ('W019','W026'))
    fields=['canonical_annotation_id','image_id','worker_id','raw_condition','effective_point_count','geometry_valid','geometry_failure','imputed_point','main_worker_included','quality','active_seconds','top_signed_pixels','floor_signed_pixels','band_width_bias_pixels']
    rows=df[[c for c in fields if c in df]].copy();rows['building']=rows.image_id.str.split('_').str[0]
    choices={}
    for cid,r in rawmap.items():
        sc=[v for c in r.get('choices',[]) if str(c.get('from_name','')).lower()=='scope' for v in c.get('choices',[])]
        choices[cid]=scope_collapse(sc[0]) if len(sc)==1 else 'unknown'
    rows['scope']=rows.canonical_annotation_id.map(choices)
    assert not rows.duplicated(['image_id','raw_condition','worker_id']).any()
    csv('inputs/response_metrics_sanitized.csv.gz',rows);csv('inputs/missing_count_audit.csv',missing)
    sp={r['image_id']:r for r in read(B/'metadata/spatial_history.jsonl.gz')};ims=pd.DataFrame(read(B/'metadata/images.jsonl'))
    whitelist=['image_id','building','source_split','scene_category','scene_source','main_space_raw','main_space_safe','main_space_source','main_space_basis','main_space_human','main_space_human_source','fine_human','fine_ai','doorway','room_id','room_status','main_function_primary','main_function_primary_source','main_semantic_key',*TRAITS,*[t+'_recheck' for t in TRAITS],'resolution_rechecked']
    oldmeta=MAINSPACE/'images/metadata_all648.csv';header=pd.read_csv(oldmeta,nrows=0).columns
    whitelist += [c for c in header if c.startswith('position_') or c in ['main_sleep','main_bathroom','main_kitchen','main_dining','main_living','main_work','main_circulation','main_storage','main_special','main_empty']]
    meta=pd.read_csv(oldmeta,usecols=[c for c in whitelist if c in header],keep_default_na=False)
    assert len(meta)==648 and set(meta.image_id)==set(ims.image_id)
    conflicts=[]
    for r in meta.to_dict('records'):
        s=sp[r['image_id']];c=s.get('spatial_classification') or {};u=s.get('spatial_prior_user') or {}
        expected=c.get('coarse_type') or u.get('user_type') or 'unknown'
        if r['scene_category'] and expected!='unknown' and r['scene_category']!=expected:
            conflicts.append(dict(image_id=r['image_id'],field='scene_category',cached=r['scene_category'],original=expected,action='not silently reconciled; original source remains authoritative'))
        text=(s.get('new_spatial_review') or {}).get('main_space') or s.get('main_visual_space') or ''
        assert str(r['main_space_raw'])==str(text)
    csv('inputs/metadata_source_conflicts.csv',conflicts)
    assert not conflicts,'Classification source conflict requires explicit review'
    csv('inputs/image_metadata_whitelist.csv',meta)
    original_path=ROOT/'analysis_results/candidate_selection_review_20260913_v2/用户审查原始记录.json'
    original=read(original_path) if original_path.exists() else {}
    groupnotes={r.get('group'):r.get('note','') for r in original.get('groups',[])}
    # Mapping is identity-only: group identifiers never enter prediction features.
    oldgroups=pd.read_csv(oldmeta,usecols=['image_id','selection_display_group'],keep_default_na=False).set_index('image_id').selection_display_group.to_dict()
    tags=[]
    for i,s in sp.items():
        v=s.get('latest_selection_record') or {};tag=v.get('difficulty')
        if tag not in ('简单','中等','困难'):continue
        note={k:v[k] for k in ('note','notes','comment','comments','reason') if k in v}
        group=v.get('group',v.get('display_group',v.get('review_code',oldgroups.get(i,''))))
        tags.append(dict(image_id=i,expert_tag=tag,comment_json=json.dumps(note,ensure_ascii=False),selection_record_json=json.dumps(v,ensure_ascii=False),display_group=group,group_comment=groupnotes.get(group,''),source='metadata/spatial_history.jsonl.gz#/latest_selection_record',use='independent contrast only; never tiers or predictors'))
    td=csv('expert/independent_tags106.csv',tags)
    assert td.expert_tag.value_counts().to_dict()=={'简单':49,'中等':41,'困难':16}
    js('expert/original_group_comments.json',[dict(group=k,comment=v) for k,v in groupnotes.items()])
    geo=rows[rows.main_worker_included & rows.raw_condition.isin(['manual','semi'])];targetids=sorted(geo.image_id.unique());js('inputs/historical_ids.json',targetids)
    counts=[]
    for arm,g in rows[rows.main_worker_included].groupby('raw_condition'):
        counts.append(dict(condition=arm,responses=len(g),images=g.image_id.nunique(),workers=g.worker_id.nunique(),valid_responses=int(g.geometry_valid.sum()),valid_images=g[g.geometry_valid].image_id.nunique()))
    csv('inputs/response_coverage.csv',counts)
    oos=rows[rows.main_worker_included & ~rows.raw_condition.isin(['manual','semi'])].copy()
    if len(oos):
        oos['condition']='oos';oos=oos.drop(columns=['raw_condition']);csv('oos/unified_rule_responses.csv',oos)
        csv('oos/unified_image_results.csv',oos.groupby('image_id').agg(n_people=('worker_id','nunique'),oos_choices=('scope',lambda a:(a=='oos').sum()),in_scope_choices=('scope',lambda a:(a=='in_scope').sum()),unknown_choices=('scope',lambda a:(a=='unknown').sum())).reset_index())
    artifacts=['human/responses.jsonl.gz','metadata/spatial_history.jsonl.gz','evaluation/folds.jsonl.gz','evaluation/config.json','visual/visual_traits.json']
    artifacts += [str(p.relative_to(B)) for p in (OLD/'process').glob('*') if p.is_file()]
    hashes=[dict(path=p,sha256=hashlib.sha256((B/p).read_bytes()).hexdigest()) for p in artifacts]
    js('inputs/source_manifest.json',dict(input_commit=BASE,execution_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),bundle_check=check,actual_historical_images=len(targetids),expert_tag_images=len(td),overlap_images=len(set(targetids)&set(td.image_id)),old_experimental_difficulty_used=False,scope_subtypes_collapsed=True,early_k_supersedes_old_prompt=list(range(2,9)),artifacts=hashes,missing_invalid_counts=len(missing),metadata_source_conflicts=conflicts,notes=['No original images, model weights or visual inference.','Expert tags/comments excluded from tier generation and pure image features.','Finite-person old replays are reused as evidence, not new data or chronology.']))
    print('PREPARE',json.dumps(safe(counts),ensure_ascii=False),'historical',len(targetids),'overlap',len(set(targetids)&set(td.image_id)),flush=True)

if __name__=='__main__':run()
