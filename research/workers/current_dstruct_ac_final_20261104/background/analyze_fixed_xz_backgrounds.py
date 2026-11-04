"""Describe changes across already-computed D sets with exactly fixed X/Z.

No registration, fusion, label change, coordinate edit or outcome-based team
selection occurs here. Inputs are the 704 frozen capacity-gap AC comparisons.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
COHORT='current_capacity_gap_supplement'
EPS=1e-10
BASE=['image','building','pool_id','scope','condition','reference_id','reference_version','n','m','direction','class_pair']
DCOUNTS=['D_current_C1','D_current_C2','D_current_C3','D_current_unknown']


def write_csv(name,frame):
    frame.to_csv(HERE/name,index=False,float_format='%.17g')


def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(x) for x in value]
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(np.bool_,)):return bool(value)
    if isinstance(value,(float,np.floating)) and not np.isfinite(value):return None
    if isinstance(value,np.floating):return float(value)
    return value


def counts(values):
    return json.dumps({str(k):int(v) for k,v in values.value_counts(dropna=False).sort_index().items()},ensure_ascii=False,sort_keys=True)


def effect_stats(g):
    q=g.loc[g.common_Q]
    eligible=len(q)>=2
    out=dict(registered_backgrounds=len(g),common_Q_backgrounds=len(q),missing_common_Q_backgrounds=len(g)-len(q),
             eligible_D_variation=eligible,
             dQ_mean=q.dQ.mean(),dQ_min=q.dQ.min(),dQ_max=q.dQ.max(),
             dQ_range=q.dQ.max()-q.dQ.min() if eligible else np.nan,
             dQ_sample_sd=q.dQ.std(ddof=1) if eligible else np.nan,
             strict_positive_backgrounds=int(q.dQ.gt(EPS).sum()),strict_negative_backgrounds=int(q.dQ.lt(-EPS).sum()),
             practical_positive_backgrounds=int(q.dQ.gt(1).sum()),practical_negative_backgrounds=int(q.dQ.lt(-1).sum()),
             strict_sign_crossing=bool(q.dQ.min()<-EPS and q.dQ.max()>EPS) if eligible else None,
             practical_sign_crossing_pm1=bool(q.dQ.min()<-1 and q.dQ.max()>1) if eligible else None,
             common_Q_A_min=q.Q_A.min(),common_Q_A_max=q.Q_A.max(),common_Q_C_min=q.Q_C.min(),common_Q_C_max=q.Q_C.max(),
             distinct_D_class_vectors=g.D_class_signature.nunique(),
             score_state_changes_across_D=g.score_state_pair.nunique()>1,
             Q_evaluability_changes_across_D=g.Q_evaluability_pair.nunique()>1,
             score_state_pattern_counts=counts(g.score_state_pair),Q_evaluability_pattern_counts=counts(g.Q_evaluability_pair),
             A_unique_score_states=g.A_score_status.nunique(dropna=False),C_unique_score_states=g.C_score_status.nunique(dropna=False))
    if len(q):
        out.update(min_dQ_event_id=q.loc[q.dQ.idxmin(),'event_id'],max_dQ_event_id=q.loc[q.dQ.idxmax(),'event_id'])
    else:out.update(min_dQ_event_id=None,max_dQ_event_id=None)
    return out


def image_stats(g):
    eligible=g.loc[g.eligible_D_variation]
    return dict(registered_blocks=len(g),registered_pairs=int(g.registered_backgrounds.sum()),
                common_Q_pairs=int(g.common_Q_backgrounds.sum()),eligible_variation_blocks=len(eligible),
                insufficient_Q_variation_blocks=int((~g.eligible_D_variation).sum()),
                strict_sign_crossing_blocks=int(eligible.strict_sign_crossing.eq(True).sum()),
                practical_sign_crossing_pm1_blocks=int(eligible.practical_sign_crossing_pm1.eq(True).sum()),
                strict_crossing_fraction_of_eligible_blocks=eligible.strict_sign_crossing.eq(True).mean() if len(eligible) else np.nan,
                practical_crossing_fraction_of_eligible_blocks=eligible.practical_sign_crossing_pm1.eq(True).mean() if len(eligible) else np.nan,
                range_gt_5_blocks=int(eligible.dQ_range.gt(5).sum()),range_gt_10_blocks=int(eligible.dQ_range.gt(10).sum()),
                mean_block_dQ_range=eligible.dQ_range.mean(),median_block_dQ_range=eligible.dQ_range.median(),
                max_block_dQ_range=eligible.dQ_range.max(),block_equal_dQ_mean=g.dQ_mean.mean(),
                blocks_with_score_state_changes=int(g.score_state_changes_across_D.sum()),
                blocks_with_Q_evaluability_changes=int(g.Q_evaluability_changes_across_D.sum()))


def main():
    HERE.mkdir(exist_ok=True)
    auto_path=STUDY/'analysis/PHYSICAL_PAIRS_AUTOMATIC.csv.gz'
    aux_path=STUDY/'analysis/PHYSICAL_PAIRS_ASSISTED.csv.gz'
    events_path=STUDY/'supplement/EVENTS.csv.gz'
    blocks_path=STUDY/'supplement/BLOCKS.csv.gz'
    d=pd.read_csv(auto_path,low_memory=False)
    d=d.loc[d.analysis_cohort.eq(COHORT)].copy().sort_values(['image','n','m','direction','block_id','background_id']).reset_index(drop=True)
    events=pd.read_csv(events_path,low_memory=False)
    design=pd.read_csv(blocks_path,low_memory=False)
    failures=[]
    def check(condition,name,detail=None):
        if not condition:failures.append(dict(check=name,detail=detail))
    check(len(d)==704 and d.canonical_physical_pair_id.nunique()==704,'frozen_704_distinct_pairs')
    check(d.block_id.nunique()==290,'frozen_290_XZ_blocks')
    check(not d.duplicated(['block_id','background_id']).any(),'unique_registered_backgrounds')
    check((d.Q_A.notna()&d.Q_C.notna()).eq(d.common_Q).all(),'common_Q_matches_complete_endpoints')
    check(np.allclose(d.loc[d.common_Q,'dQ'],d.loc[d.common_Q,'Q_C']-d.loc[d.common_Q,'Q_A'],rtol=0,atol=1e-10),'dQ_endpoint_identity')
    # Compare the full frozen D/X/Z and team/reference identities, not only IDs.
    source=events.set_index(['block_id','background_id'])
    pairs=d.set_index(['block_id','background_id'])
    check(set(source.index)==set(pairs.index),'same_registered_events')
    for own,original in [('D_workers','D'),('X_workers','X'),('Z_workers','Z'),('A_team_key','A_team_key'),('C_team_key','C_team_key'),('reference_id','reference_id'),('reference_version','reference_version'),('n','n'),('m','m')]:
        check(pairs[own].eq(source.loc[pairs.index,original]).all(),'registered_identity_'+own)
    check(d[DCOUNTS].sum(axis=1).eq(d.n-d.m).all(),'D_class_counts_match_size')
    d['D_class_signature']=d.apply(lambda x:'|'.join(f'{c}:{int(x[col])}' for c,col in zip(['C1','C2','C3','unknown'],DCOUNTS)),axis=1)
    d['D_class_vector_json']=d.apply(lambda x:json.dumps({c:int(x[col]) for c,col in zip(['C1','C2','C3','unknown'],DCOUNTS)},sort_keys=True),axis=1)
    d['score_state_pair']=d.A_score_status.fillna('missing')+' → '+d.C_score_status.fillna('missing')
    d['Q_evaluability_pair']=np.select([d.Q_A.notna()&d.Q_C.notna(),d.Q_A.notna(),d.Q_C.notna()],['both_Q','A_Q_only','C_Q_only'],default='neither_Q')
    design=design.set_index('block_id')
    d['planned_backgrounds_per_XZ']=d.block_id.map(design.selected_D_count)
    d['background_team_size']=d.n-d.m
    aux=pd.read_csv(aux_path,usecols=['analysis_cohort','canonical_physical_pair_id','Q_A','Q_C','common_Q','approved_order_touched','A_score_status','C_score_status'])
    aux=aux.loc[aux.analysis_cohort.eq(COHORT)].set_index('canonical_physical_pair_id')
    ad=d.set_index('canonical_physical_pair_id')
    unchanged=all(np.allclose(ad[c],aux.loc[ad.index,c],rtol=0,atol=0,equal_nan=True) for c in ['Q_A','Q_C'])
    unchanged=unchanged and all(ad[c].eq(aux.loc[ad.index,c]).all() for c in ['common_Q','A_score_status','C_score_status'])
    check(unchanged,'supplement_automatic_equals_existing_assisted')
    check(not aux.approved_order_touched.any(),'no_manual_order_endpoint_in_this_supplement')
    write_csv('BACKGROUND_PAIR_RESULTS.csv.gz',d)
    rows=[]
    for block,g in d.groupby('block_id',sort=True):
        check(all(g[c].nunique(dropna=False)==1 for c in BASE+['X_workers','Z_workers']),'exact_fixed_XZ_context',block)
        check(len(g)==int(design.loc[block,'selected_D_count']),'planned_D_count',block)
        check(g.D_workers.nunique()==len(g),'distinct_D_members',block)
        first=g.iloc[0]
        row={c:first[c] for c in BASE}
        row.update(block_id=block,X_workers=first.X_workers,Z_workers=first.Z_workers,
                   planned_backgrounds_per_XZ=int(first.planned_backgrounds_per_XZ),background_team_size=int(first.background_team_size),
                   possible_backgrounds_per_XZ=str(design.loc[block,'possible_D_count']),
                   D_members_by_background=json.dumps(g[['background_id','D_workers','D_class_signature']].to_dict('records'),ensure_ascii=False))
        row.update(effect_stats(g));rows.append(row)
    blocks=pd.DataFrame(rows)
    write_csv('BLOCK_BACKGROUND_EFFECTS.csv.gz',blocks)
    image_rows=[]
    image_keys=BASE+['planned_backgrounds_per_XZ']
    for key,g in blocks.groupby(image_keys,sort=True,dropna=False):
        image_rows.append(dict(zip(image_keys,key))|image_stats(g))
    images=pd.DataFrame(image_rows)
    write_csv('IMAGE_BACKGROUND_EFFECTS.csv',images)
    summary_rows=[]
    summary_keys=['scope','condition','n','m','direction','class_pair','planned_backgrounds_per_XZ']
    for key,g in images.groupby(summary_keys,sort=True,dropna=False):
        row=dict(zip(summary_keys,key))
        row.update(registered_images=g.image.nunique(),registered_buildings=g.building.nunique(),registered_blocks=int(g.registered_blocks.sum()),
                   registered_pairs=int(g.registered_pairs.sum()),common_Q_pairs=int(g.common_Q_pairs.sum()),eligible_variation_blocks=int(g.eligible_variation_blocks.sum()),
                   eligible_variation_images=g.loc[g.eligible_variation_blocks.gt(0),'image'].nunique(),
                   strict_crossing_blocks=int(g.strict_sign_crossing_blocks.sum()),practical_crossing_pm1_blocks=int(g.practical_sign_crossing_pm1_blocks.sum()),
                   strict_crossing_images=g.loc[g.strict_sign_crossing_blocks.gt(0),'image'].nunique(),
                   practical_crossing_pm1_images=g.loc[g.practical_sign_crossing_pm1_blocks.gt(0),'image'].nunique(),
                   image_equal_mean_block_dQ_range=g.mean_block_dQ_range.mean(),
                   image_equal_mean_block_dQ=g.block_equal_dQ_mean.mean(),
                   building_equal_mean_block_dQ_range=g.groupby('building').mean_block_dQ_range.mean().mean(),
                   image_equal_strict_crossing_block_fraction=g.strict_crossing_fraction_of_eligible_blocks.mean(),
                   image_equal_practical_crossing_block_fraction=g.practical_crossing_fraction_of_eligible_blocks.mean(),
                   score_state_change_blocks=int(g.blocks_with_score_state_changes.sum()),
                   score_state_change_images=g.loc[g.blocks_with_score_state_changes.gt(0),'image'].nunique())
        row['orientation_sign']=1;row['reverse_is_independent_replication']=False
        summary_rows.append(row)
        reverse=row.copy();a,c=row['direction'].split('_to_');reverse.update(direction=c+'_to_'+a,orientation_sign=-1,image_equal_mean_block_dQ=-row['image_equal_mean_block_dQ'])
        summary_rows.append(reverse)
    summary=pd.DataFrame(summary_rows)
    write_csv('SIX_DIRECTION_BACKGROUND_SUMMARY.csv',summary)
    # A separately labelled descriptive subset holds D's class counts fixed as
    # well as X/Z, leaving concrete D membership to differ among observed teams.
    same_rows=[]
    for (block,signature),g in d.groupby(['block_id','D_class_signature'],sort=True):
        first=g.iloc[0];row={c:first[c] for c in BASE}
        row.update(block_id=block,D_class_signature=signature,planned_backgrounds_per_XZ=int(first.planned_backgrounds_per_XZ),
                   X_workers=first.X_workers,Z_workers=first.Z_workers,
                   D_members_by_background=json.dumps(g[['background_id','D_workers']].to_dict('records'),ensure_ascii=False))
        row.update(effect_stats(g));same_rows.append(row)
    same=pd.DataFrame(same_rows)
    write_csv('SAME_CLASS_VECTOR_BACKGROUND_VARIATION.csv.gz',same)
    # Outcome-chosen explanatory cases are explicitly labelled, never used to
    # select or regenerate teams. Full block tables are retained above.
    cases=[]
    eligible=blocks.loc[blocks.eligible_D_variation]
    def case(kind,row):
        if row is None:return
        block=row.block_id
        g=d.loc[d.block_id.eq(block)].copy()
        if kind=='same_D_class_vector_member_case':g=g.loc[g.D_class_signature.eq(row.D_class_signature)].copy()
        g['case_selection']=kind;cases.append(g)
    case('largest_observed_background_range',eligible.sort_values(['dQ_range','block_id'],ascending=[False,True]).iloc[0])
    case('smallest_observed_background_range',eligible.sort_values(['dQ_range','block_id'],ascending=[True,True]).iloc[0])
    s=same.loc[same.eligible_D_variation&same.practical_sign_crossing_pm1.eq(True)]
    if len(s):case('same_D_class_vector_member_case',s.sort_values(['dQ_range','block_id'],ascending=[False,True]).iloc[0])
    s=blocks.loc[blocks.score_state_changes_across_D]
    if len(s):case('observed_output_state_change',s.sort_values(['dQ_range','block_id'],ascending=[False,True],na_position='last').iloc[0])
    case_table=pd.concat(cases,ignore_index=True)
    write_csv('BACKGROUND_EXPLANATORY_CASES.csv.gz',case_table)
    same_eligible=same.loc[same.eligible_D_variation]
    illustrate=same_eligible.sort_values(['dQ_range','block_id','D_class_signature'],ascending=[False,True,True]).iloc[0]
    pool=d.loc[d.block_id.eq(illustrate.block_id)&d.D_class_signature.eq(illustrate.D_class_signature)&d.common_Q]
    low=pool.loc[pool.dQ.idxmin()];high=pool.loc[pool.dQ.idxmax()]
    columns=['event_id','source_event_id','canonical_physical_pair_id','block_id','background_id','bundle_id',
             'image','image_id','building','pool_id','scope','condition','reference_id','reference_version','n','m','direction','class_pair',
             'D_workers','X_workers','Z_workers','D_class_signature','D_class_vector_json']+DCOUNTS+[
             'A_team_key','C_team_key','A_workers','C_workers','Q_A','Q_C','dQ','A_score_status','C_score_status',
             'A_nodes','C_nodes','A_iou_2d','C_iou_2d','A_S_bottom_deg','C_S_bottom_deg','A_dir','C_dir','A_Hmean','C_Hmean','A_Hcenter','C_Hcenter']
    payload=dict(case_id='fixed_XZ_same_D_class_vector_q9_30_n14_m7_C2_C3',
                 selection_rule='Post-hoc largest observed dQ range among evaluated fixed-XZ, fixed-D-class-vector groups; explanatory only, no team selection or new computation.',
                 source_commit='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b',source_version='automatic',
                 source_metrics='analysis/PHYSICAL_PAIRS_AUTOMATIC.csv.gz',source_metrics_sha256=hashlib.sha256(auto_path.read_bytes()).hexdigest(),
                 native_endpoint_pool='supplement/endpoints/pools/'+str(low.pool_id)+'.json.gz',
                 fixed_block_id=illustrate.block_id,fixed_X_members=str(low.X_workers).split('|'),fixed_Z_members=str(low.Z_workers).split('|'),
                 fixed_D_class_counts={c:int(low[col]) for c,col in zip(['C1','C2','C3','unknown'],DCOUNTS)},
                 observed_dQ_range=float(high.dQ-low.dQ),
                 low_delta={c:low[c] for c in columns},high_delta={c:high[c] for c in columns})
    frozen=HERE/'ILLUSTRATIVE_FIXED_XZ_CASE.json'
    payload=clean(payload)
    if frozen.exists():
        check(json.loads(frozen.read_text(encoding='utf-8'))==payload,'frozen_illustrative_case_identity')
    else:frozen.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    def freeze_more(filename,content):
        content=clean(content);path=HERE/filename
        if path.exists():check(json.loads(path.read_text(encoding='utf-8'))==content,'frozen_case_identity_'+filename)
        else:path.write_text(json.dumps(content,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    stable=eligible.sort_values(['dQ_range','block_id'],ascending=[True,True]).iloc[0]
    sg=d.loc[d.block_id.eq(stable.block_id)&d.common_Q]
    lo=sg.loc[sg.dQ.idxmin()];hi=sg.loc[sg.dQ.idxmax()]
    stable_payload=dict(case_id='stable_fixed_XZ_e9_15_n20_m7_C1_C2',
        selection_rule='Post-hoc smallest observed dQ range across all evaluated fixed-XZ blocks; all two registered backgrounds retained, no team selection or new computation.',
        source_commit=payload['source_commit'],source_version='automatic',source_metrics=payload['source_metrics'],source_metrics_sha256=payload['source_metrics_sha256'],
        native_endpoint_pool='supplement/endpoints/pools/'+str(lo.pool_id)+'.json.gz',
        fixed_block_id=stable.block_id,fixed_X_members=str(lo.X_workers).split('|'),fixed_Z_members=str(lo.Z_workers).split('|'),
        fixed_D_class_counts={c:int(lo[col]) for c,col in zip(['C1','C2','C3','unknown'],DCOUNTS)},
        observed_dQ_range=float(hi.dQ-lo.dQ),low_delta={c:lo[c] for c in columns},high_delta={c:hi[c] for c in columns})
    check(sg.D_class_signature.nunique()==1,'stable_illustration_same_D_class_vector')
    freeze_more('ILLUSTRATIVE_STABLE_FIXED_XZ_CASE.json',stable_payload)
    state=blocks.loc[blocks.score_state_changes_across_D].sort_values(['dQ_range','block_id'],ascending=[False,True],na_position='last').iloc[0]
    sg=d.loc[d.block_id.eq(state.block_id)].sort_values('event_id')
    selected=sg.drop_duplicates('native_status_transition',keep='first')
    state_cols=columns+['native_status_transition','common_Q','Q_evaluability_pair']
    state_payload=dict(case_id='output_state_fixed_XZ_yq_27_n14_m7_C1_C3',
        selection_rule='Within the already selected state-changing block, sort existing event_id ascending and keep the first event for each native_status_transition, including first both_Q. No new draw or fusion.',
        source_commit=payload['source_commit'],source_version='automatic',source_metrics=payload['source_metrics'],source_metrics_sha256=payload['source_metrics_sha256'],
        native_endpoint_pool='supplement/endpoints/pools/'+str(sg.iloc[0].pool_id)+'.json.gz',
        fixed_block_id=state.block_id,fixed_X_members=str(sg.iloc[0].X_workers).split('|'),fixed_Z_members=str(sg.iloc[0].Z_workers).split('|'),
        fixed_D_class_counts={c:int(sg.iloc[0][col]) for c,col in zip(['C1','C2','C3','unknown'],DCOUNTS)},
        registered_backgrounds=len(sg),common_Q_backgrounds=int(sg.common_Q.sum()),
        full_common_Q_dQ_min=float(sg.loc[sg.common_Q,'dQ'].min()),full_common_Q_dQ_max=float(sg.loc[sg.common_Q,'dQ'].max()),
        native_state_counts=json.loads(counts(sg.native_status_transition)),selected_records=selected[state_cols].to_dict('records'))
    check(sg.D_class_signature.nunique()==1,'state_illustration_same_D_class_vector')
    freeze_more('ILLUSTRATIVE_OUTPUT_STATE_CASE.json',state_payload)
    receipt=dict(status='passed' if not failures else 'failed',source_cohort=COHORT,version='automatic',automatic_and_existing_assisted_identical=unchanged,
                 source_hashes={str(p.relative_to(STUDY)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [auto_path,aux_path,events_path,blocks_path]},
                 registered_pairs=len(d),unique_teams=len(set(d.A_team_key)|set(d.C_team_key)),images=d.image.nunique(),buildings=d.building.nunique(),
                 image_budget_direction_cells=len(images),fixed_XZ_blocks=len(blocks),common_Q_pairs=int(d.common_Q.sum()),
                 backgrounds_per_block_counts={int(k):int(v) for k,v in blocks.registered_backgrounds.value_counts().sort_index().items()},
                 eligible_variation_blocks=len(eligible),insufficient_Q_variation_blocks=len(blocks)-len(eligible),
                 strict_sign_crossing_blocks=int(eligible.strict_sign_crossing.eq(True).sum()),
                 practical_sign_crossing_pm1_blocks=int(eligible.practical_sign_crossing_pm1.eq(True).sum()),
                 strict_sign_crossing_images=eligible.loc[eligible.strict_sign_crossing.eq(True),'image'].nunique(),
                 practical_sign_crossing_pm1_images=eligible.loc[eligible.practical_sign_crossing_pm1.eq(True),'image'].nunique(),
                 score_state_change_blocks=int(blocks.score_state_changes_across_D.sum()),
                 score_state_change_images=blocks.loc[blocks.score_state_changes_across_D,'image'].nunique(),
                 same_D_class_vector_groups=len(same),same_D_class_vector_eligible_groups=len(same_eligible),
                 same_D_class_vector_eligible_blocks=same_eligible.block_id.nunique(),
                 same_D_class_vector_eligible_images=same_eligible.image.nunique(),
                 same_D_class_vector_eligible_buildings=same_eligible.building.nunique(),
                 same_D_class_vector_strict_crossing_groups=int(same_eligible.strict_sign_crossing.eq(True).sum()),
                 same_D_class_vector_practical_crossing_groups=int(same_eligible.practical_sign_crossing_pm1.eq(True).sum()),
                 same_D_class_vector_strict_crossing_images=same_eligible.loc[same_eligible.strict_sign_crossing.eq(True),'image'].nunique(),
                 same_D_class_vector_practical_crossing_images=same_eligible.loc[same_eligible.practical_sign_crossing_pm1.eq(True),'image'].nunique(),
                 same_D_class_vector_strict_crossing_blocks=same_eligible.loc[same_eligible.strict_sign_crossing.eq(True),'block_id'].nunique(),
                 same_D_class_vector_practical_crossing_blocks=same_eligible.loc[same_eligible.practical_sign_crossing_pm1.eq(True),'block_id'].nunique(),
                 max_background_dQ_range=eligible.dQ_range.max(),failures=failures,
                 interpretation=['All 704 teams comparisons were already registered and computed; no new team or fusion run.',
                   'Counts of 2, 4 and 32 backgrounds per XZ block remain separate. Range grows with opportunity to observe extremes.',
                   'Image summaries first average eligible XZ blocks within image; physical pairs and blocks are not independent images.',
                   'A block with fewer than two common-Q backgrounds has no evaluated range or sign-crossing claim.',
                   'Fixed D class-count subsets describe observed membership changes; no uniform population or causal background-ratio estimand is asserted.',
                   'Explanatory cases were selected after observing outcomes and do not determine team inclusion or primary means.'])
    (HERE/'BACKGROUND_REVIEW.json').write_text(json.dumps(clean(receipt),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(clean(receipt),ensure_ascii=False,indent=2,allow_nan=False))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
