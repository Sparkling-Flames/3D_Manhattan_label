"""Independent inventory/evidence analysis of the commit-pinned v2 records.

Adopted provenance flags are retained as flags, not upgraded to newly adjudicated
gold. Event identifiers and unknown states remain explicit; no personnel score.
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import csv,gzip,hashlib,json,math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT/'repo_main_20261019'
OUT=ROOT/'work_v2_20261019/audit'
STRICT_VERDICTS={'usable','invalid','undetermined','representation_pending','repair_needed'}

def load(path):
    if str(path).endswith('.gz'):
        with gzip.open(path,'rt',encoding='utf-8-sig') as f:return json.load(f)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def save(name,value):
    def norm(x):
        if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [norm(v) for v in x]
        if isinstance(x,np.generic):return norm(x.item())
        if isinstance(x,float) and not math.isfinite(x):return None
        return x
    (OUT/name).write_text(json.dumps(norm(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def csvout(name,rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')

def boolcount(rows,field):return sum(x.get(field) is True for x in rows)

def image_building(rows):
    return dict(n=len(rows),images=len({x['image_id'] for x in rows}),buildings=len({x['building_id'] for x in rows}),workers=len({x['worker_id'] for x in rows}))

def same_multiset(a,b):
    if a is None or b is None or len(a)!=len(b):return None
    return sorted(tuple(round(float(v),6) for v in p) for p in a)==sorted(tuple(round(float(v),6) for v in p) for p in b)

def make_record(r):
    e=r['exclusion_attribution'];s=r['semi_evidence'];scope=r['scope_evidence'];t=r['time_evidence'];rv=r['review_evidence']
    diff=r['image_evidence']['difficulty_record']
    x={k:r[k] for k in ['object_id','worker_id','image_id','image_code','building_id','room_id','origin','condition','quality_usable','quality_use','calculation_class','cleaning_disposition','pool_analysis_eligible','independent_vote_eligible','B8L2','D10','reference_id','reference_version','source_active_time_seconds','target_matched_time_seconds','is_doorway','is_oos','point_count']}
    x.update(difficulty=r['current_class'],difficulty_target_match=r['reference_id']==diff.get('target_version'),
        review_verdict=rv['verdict'],individual_verdict_recorded=rv['verdict'] in STRICT_VERDICTS,
        current_comment_recorded=bool(rv.get('current_comment') or rv.get('current_decision_comment')),
        source_kind=t['source_kind'],source_missing_reason=t['source_missing_reason'],target_missing_reason=t['target_missing_reason'],
        exact_initialization_bound=s.get('exact_initialization_bound',False),
        old_confirmed_opportunity=s.get('confirmed_error_opportunity',False),
        new_reported_opportunity=s.get('reported_error_opportunity',False),
        old_confirmed_unchanged=s.get('known_error_unchanged'),new_reported_unchanged=s.get('reported_known_error_unchanged'),
        initialization_edited=s.get('edited'),error_specific_state=s.get('error_specific_state'),
        error_specific_corrected_confirmed=s.get('corrected_confirmed'),
        initial_equals_raw_coordinate_multiset_6dec=same_multiset(s.get('initialization_points'),s.get('raw_final_points')),
        paired_initial_scores_adopted=s.get('paired_scores_current_adopted',False),qualified_net_gain=s.get('current_qualified_gain_available',False),
        worker_attributable_gain=s.get('worker_attributable_gain_available',False),
        scope_response=scope['response'],scope_judgement_opportunity=scope['judgement_opportunity'],scope_correct=scope['correct'],
        scope_compatible_gold=scope['compatible_gold'],scope_missing_reason=scope['judgement_missing_reason'],
        exclusion_category=e['category'],legacy_explicit_person_error=e['legacy_explicit_person_error'],
        specific_person_error_candidate=e['specific_person_error_candidate'],
        independently_confirmed_severe_error=e['independently_confirmed_severe_error'],
        severity_status=e['severity_status'],attribution_pending=e['attribution_pending'],
        historical_worker_exclusion=e['historical_worker_exclusion'],broad_reviewer_nonacceptance=e['broad_reviewer_nonacceptance'])
    for k,v in e['context_factors'].items():x['context_'+k]=v
    for metric in ['B8L2','D10','IoU3D100']:
        x['initial_'+metric]=(s.get('current_initial_scores') or {}).get(metric)
        x['project_gain_'+metric]=(s.get('current_project_gain') or {}).get(metric)
        x['worker_gain_'+metric]=(s.get('current_worker_attributable_gain') or {}).get(metric)
    x['adverse_event_labels']='|'.join(label for label,yes in [
        ('legacy_person_exclusion',e['legacy_explicit_person_error']),
        ('specific_exclusion_candidate',e['specific_person_error_candidate']),
        ('old_confirmed_initial_error_unchanged',s.get('known_error_unchanged') is True),
        ('new_reported_initial_error_unchanged',s.get('reported_known_error_unchanged') is True),
        ('compatible_scope_incorrect',scope['correct'] is False)] if yes)
    return x

def summarize_person(d):
    def support(mask,prefix):
        z=d.loc[mask];return {prefix+'_n':len(z),prefix+'_images':z.image_id.nunique(),prefix+'_buildings':z.building_id.nunique()}
    x=dict(worker_id=d.worker_id.iloc[0],origin='|'.join(sorted(d.origin.unique())),inventory=len(d),images=d.image_id.nunique(),buildings=d.building_id.nunique())
    for prefix,mask in [('quality',d.quality_usable),('ordinary_manual',d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')),
        ('full_diagnostic',d.calculation_class.eq('full')),('source_time',d.source_active_time_seconds.notna()),('target_time',d.target_matched_time_seconds.notna()),
        ('explicit_individual_verdict',d.individual_verdict_recorded),('semi',d.condition.eq('semi')),
        ('old_confirmed_opportunity',d.old_confirmed_opportunity),('new_reported_opportunity',d.new_reported_opportunity),
        ('old_known_error_unchanged',d.old_confirmed_unchanged.eq(True)),('new_reported_error_unchanged',d.new_reported_unchanged.eq(True)),
        ('qualified_gain',d.qualified_net_gain),('worker_attributable_gain',d.worker_attributable_gain),
        ('scope_response',d.scope_response.notna()),('scope_compatible_gold',d.scope_judgement_opportunity),
        ('scope_incorrect',d.scope_correct.eq(False)),('legacy_person_error',d.legacy_explicit_person_error),
        ('specific_person_candidate',d.specific_person_error_candidate),('adverse_event_union',d.adverse_event_labels.ne(''))]:x.update(support(mask,prefix))
    for prefix,num,den in [('old_persistent',x['old_known_error_unchanged_n'],x['old_confirmed_opportunity_n']),('new_reported_persistent',x['new_reported_error_unchanged_n'],x['new_reported_opportunity_n'])]:
        x[prefix+'_rate_among_observed_opportunities']=num/den if den else None
        x[prefix+'_denominator_note']='targeted_opportunities_not_random_population_sample'
    x['no_new_severity_gold']=True
    return x

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    records=load(REPO/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    contract=load(REPO/'research/statistics/v2_evidence_audit_20261019/COVERAGE.json')
    assert len({x['object_id'] for x in records})==len(records)
    quality=[x for x in records if x['quality_usable']]
    ordinary=[x for x in quality if x['condition']=='manual' and x['quality_use']=='ordinary_primary']
    flat=[make_record(r) for r in records];d=pd.DataFrame(flat)
    counts=dict(inventory=len(records),people=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique(),
        origins=dict(Counter(d.origin)),calculation=dict(Counter(d.calculation_class)),quality_rows=len(quality),quality_workers=len({x['worker_id'] for x in quality}),quality_images=len({x['image_id'] for x in quality}),
        source_time_available=int(d.source_active_time_seconds.notna().sum()),target_matched_time_available=int(d.target_matched_time_seconds.notna().sum()),
        semi_inventory=int(d.condition.eq('semi').sum()),semi_exact_initialization_bound=int(d.exact_initialization_bound.sum()),
        semi_confirmed_error_opportunities=int(d.old_confirmed_opportunity.sum()),semi_reported_error_opportunities=int(d.new_reported_opportunity.sum()),
        semi_current_paired_scores=int(d.paired_initial_scores_adopted.sum()),semi_current_qualified_gains=int(d.qualified_net_gain.sum()),semi_qualified_worker_attributable_gains=int(d.worker_attributable_gain.sum()),
        scope_responses=int(d.scope_response.notna().sum()),scope_compatible_judgement_opportunities=int(d.scope_judgement_opportunity.sum()),scope_correct=int(d.scope_correct.eq(True).sum()),
        specific_person_error_candidates=int(d.specific_person_error_candidate.sum()),legacy_explicit_person_error_records=int(d.legacy_explicit_person_error.sum()))
    mismatches={k:{'expected':contract[k],'observed':v} for k,v in counts.items() if k in contract and contract[k]!=v}
    assert not mismatches,mismatches
    assert all((r['B8L2'] is not None)==r['quality_usable'] and (r['D10'] is not None)==r['quality_usable'] for r in records)
    assert not any(r['quality_usable'] and r['is_oos'] for r in records)
    assert not d.source_active_time_seconds.dropna().le(0).any()
    assert not d.target_matched_time_seconds.dropna().le(0).any()
    assert not any(r['time_evidence']['lead_time_used'] for r in records)
    assert not d.loc[d.old_confirmed_unchanged.eq(True),'initial_equals_raw_coordinate_multiset_6dec'].eq(False).any()
    csvout('records_evidence.csv',flat)
    csvout('person_evidence_62.csv',[summarize_person(g) for _,g in d.groupby('worker_id')])
    for name,mask in [('semi_records',d.condition.eq('semi')),('scope_opportunities',d.scope_judgement_opportunity),('exclusion_records',d.cleaning_disposition.ne('retained')),('unique_adverse_events',d.adverse_event_labels.ne(''))]:
        csvout(name+'.csv',d.loc[mask])
    evidence_details=[{k:r[k] for k in ['object_id','worker_id','image_id','image_code','building_id','origin','condition','quality_use','cleaning_disposition','exclusion_attribution','review_evidence','comments','image_comments']} for r in records if r['exclusion_attribution']['specific_person_error_candidate'] or r['exclusion_attribution']['legacy_explicit_person_error']]
    save('PERSONAL_EXCLUSION_EVIDENCE_25.json',evidence_details)
    # No transitive closure: preserve the authoritative direct links and overlapping named groups.
    tables=load(REPO/'research/statistics/v2_integrated_analysis_20261019/tables.json.gz')['tables']
    table_contract=load(REPO/'research/statistics/v2_integrated_analysis_20261019/CONSUMER_INTERFACE.json')
    row_count_checks={t['id']:dict(expected=t['rows'],observed=len(tables[t['id']]),pass_=t['rows']==len(tables[t['id']])) for t in table_contract['tables']}
    assert all(v['pass_'] for v in row_count_checks.values())
    published=pd.DataFrame(tables['quality__shared_records']).set_index('object_id')
    for field in ['B8L2','D10','source_active_time_seconds','target_matched_time_seconds']:
        expected=d.set_index('object_id').loc[published.index,field].to_numpy(float)
        assert np.allclose(expected,published[field].to_numpy(float),atol=1e-9,rtol=0,equal_nan=True),field
    for table in ['statistics__direct_relation_registry','statistics__room_registry','statistics__room_memberships']:
        with gzip.open(OUT/(table+'.json.gz'),'wt',encoding='utf-8') as f:json.dump(tables[table],f,ensure_ascii=False,allow_nan=False)
    csvout('time_coverage_by_source_condition.csv',d.groupby(['origin','source_kind','condition','quality_usable'],dropna=False).agg(
        records=('object_id','size'),source_n=('source_active_time_seconds','count'),target_n=('target_matched_time_seconds','count'),source_median=('source_active_time_seconds','median'),source_p90=('source_active_time_seconds',lambda x:x.quantile(.9)),source_p99=('source_active_time_seconds',lambda x:x.quantile(.99))).reset_index())
    # Standardized event flag is a further descriptor, never a Q penalty.
    # Comparisons using it must restrict BOTH baseline and candidate to the same
    # source-kind audited pool, preserving absent opportunity as unknown.
    behavior=[]
    for heldout in sorted(d.building_id.unique()):
        train=d[d.building_id.ne(heldout)]
        for worker,g in train.groupby('worker_id'):
            z=g[g.old_confirmed_opportunity|g.new_reported_opportunity]
            level='confirmed_frozen_initialization' if len(z) and z.old_confirmed_opportunity.any() else 'user_reported_flags' if len(z) else 'unknown'
            n=len(z);b=z.building_id.nunique();miss=int((z.old_confirmed_unchanged.eq(True)|z.new_reported_unchanged.eq(True)).sum())
            supported=n>=3 and b>=2
            state='repeated_retention_observed' if supported and miss>=2 else 'one_retention_observed' if supported and miss==1 else 'no_retention_reported_on_observed_opportunities_correction_unknown' if supported else 'insufficient_opportunity'
            behavior.append(dict(heldout_building=heldout,worker_id=worker,evidence_level=level,opportunities=n,opportunity_images=z.image_id.nunique(),opportunity_buildings=b,
                retained_error_events=miss,supported=supported,retention_fraction=miss/n if supported else None,behavior_type=state,
                legacy_person_exclusion_count=int(g.legacy_explicit_person_error.sum()),specific_person_candidate_count=int(g.specific_person_error_candidate.sum()),
                scope_opportunities=int(g.scope_judgement_opportunity.sum()),scope_false=int(g.scope_correct.eq(False).sum())))
    csvout('fold_behavior_profiles.csv',behavior)
    # Frozen image difficulty provenance: reviewers were not newly blinded here.
    images={r['image_id']:r['image_evidence']['difficulty_record'] for r in records}
    provenance=[]
    for image,x in sorted(images.items()):
        provenance.append(dict(image_id=image,image_code=x.get('image'),difficulty=x.get('current_class'),
            target_version=x.get('target_version'),classification_basis=x.get('classification_basis'),review_method=x.get('review_method'),
            basis_before_user_adoption=x.get('basis_before_user_adoption'),reviewed=x.get('reviewed'),user_grade_adopted=x.get('user_grade_adopted'),
            latest_user_review=json.dumps(x.get('latest_user_review'),ensure_ascii=False),difficulty_analysis_eligible=x.get('difficulty_analysis_eligible')))
    csvout('difficulty_provenance_261.csv',provenance)
    manifested=load(REPO/'research/workers/pro_personnel_v2_20261019/INPUT_MANIFEST.json')
    sizes=[]
    for x in manifested['files']:
        data=(REPO/x['path']).read_bytes();newlines=data.count(b'\n')
        sizes.append(dict(path=x['path'],declared_bytes=x['bytes'],git_bytes=len(data),match=x['bytes']==len(data),
            explained_by_crlf_to_lf=x['bytes']==len(data)+newlines,sha256=hashlib.sha256(data).hexdigest()))
    csvout('input_manifest_size_audit.csv',sizes)
    unknown_judge=sum(r['scope_evidence']['correct'] is None for r in records)
    summary=dict(verified_counts=counts,ordinary_manual=image_building(ordinary),ordinary_difficulty=dict(Counter(r['current_class'] for r in ordinary)),
        quality_strata={k:image_building([r for r in quality if r['condition']+'|'+r['quality_use']==k]) for k in sorted({r['condition']+'|'+r['quality_use'] for r in quality})},
        review_verdicts_by_origin={origin:dict(Counter(d.loc[d.origin.eq(origin),'review_verdict'])) for origin in ['v1','new']},
        target_source_overlap=int((d.target_matched_time_seconds.notna()&d.source_active_time_seconds.notna()).sum()),
        target_source_value_disagreements=int((d.loc[d.target_matched_time_seconds.notna(),'source_active_time_seconds']-d.loc[d.target_matched_time_seconds.notna(),'target_matched_time_seconds']).abs().gt(1e-9).sum()),
        scope_retained_opportunities=int((d.scope_judgement_opportunity&d.cleaning_disposition.eq('retained')).sum()),scope_unknown_judgement=unknown_judge,
        old_unchanged_all=int((d.exact_initialization_bound&d.initialization_edited.eq(False)).sum()),old_bad_unchanged=int(d.old_confirmed_unchanged.eq(True).sum()),
        new_unchanged_all=int((d.origin.eq('new')&d.condition.eq('semi')&d.initialization_edited.eq(False)).sum()),new_reported_bad_unchanged=int(d.new_reported_unchanged.eq(True).sum()),
        corrected_true=int(d.error_specific_corrected_confirmed.eq(True).sum()),corrected_false=int(d.error_specific_corrected_confirmed.eq(False).sum()),
        adverse_unique_records=int(d.adverse_event_labels.ne('').sum()),adverse_label_occurrences=int(d.adverse_event_labels.map(lambda x:len(x.split('|')) if x else 0).sum()),
        specific_person_candidate_includes_legacy=bool((~d.legacy_explicit_person_error|d.specific_person_error_candidate).all()),
        severe_error_gold_performed=False,
        provenance_review_methods=dict(Counter(x['review_method'] for x in provenance)),
        table_row_count_checks=row_count_checks,manifest_text_size_differences=[x for x in sizes if not x['match']],
        qualification_rebuilt=False,acquisition_replayed=False,statistical_source_columns_read=True,
        notes=['25 existing specific-person candidates include 10 historical explicit flags; no new severity adjudication.',
        'scope response, compatible judgment, actual spatial choice are separate; 93 gold opportunities are all in-scope.',
        'Old and new Semi evidence tiers never pooled into one success rate. Editing does not confirm error correction.',
        'Adverse events are deduplicated by object_id; legacy and candidate flags are nested, not two punishments.',
        'Whole-inventory errors or exclusion rates are NOT estimates from a random audit sample.',
        'Preserved 777 direct image relations and overlapping named groups without graph transitive closure.'])
    save('EVIDENCE_AUDIT_CHECKS.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['table_row_count_checks','manifest_text_size_differences','review_verdicts_by_origin']},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
