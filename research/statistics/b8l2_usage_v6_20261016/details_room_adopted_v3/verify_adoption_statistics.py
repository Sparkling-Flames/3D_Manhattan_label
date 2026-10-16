"""只读独立复核已采用关系统计，不调用统计生成器。"""
import json
from pathlib import Path
from collections import Counter
import pandas as pd
import numpy as np

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
csv=lambda n:pd.read_csv(P/(n+'.csv'))
F=read(P/'RELATION_ADOPTION_INPUTS.json')
A=pd.read_csv(P.parent/'shared_records.csv')
checks={};rows_checked={}
def ok(name,condition):
    assert condition,name
    checks[name]=True
def equal(a,b):
    return pd.isna(a) and pd.isna(b) or (not pd.isna(a) and not pd.isna(b) and np.isclose(float(a),float(b),atol=1e-8,rtol=1e-10))
official=ROOT/'research/same_room/relation_adoption_20261016'
ok('relation_freeze_official_exact',F['manifest']==read(official/'CROSS_MODULE_RELATIONS.json') and F['groups']==read(official/'original_groups.json') and F['candidates']==read(official/'candidate_adoption.json') and F['relations']==read(official/'relations.json'))
registry=csv('room_group_registry');raw=csv('room_raw_group_evidence');pairs=csv('room_direct_pair_registry')
ok('259_working_260_raw_777_pairs',len(registry)==259 and len(raw)==260 and len(pairs)==777)
for row,g in zip(raw.to_dict('records'),F['groups']):
    assert row['review_code']==g['review_code'] and json.loads(row['raw_current'])==g['raw_current'] and row['viewed']
ok('raw_full_classification_allviewed_preserved',True)
candidate_by_id={c['candidate_id']:c for c in F['candidates']}
relation_by_key={tuple(sorted([r['image_a'],r['image_b']])):r for r in F['relations']}
definitions={}
for row in registry.to_dict('records'):
    c=candidate_by_id[row['candidate_id']]
    assert json.loads(row['image_ids'])==c['image_ids']
    tier='user_classified_comparable' if c['adopted_comparable'] else 'user_classified_other_scope' if c['physical_supported'] else 'not_supported' if any(g['raw_current']['physical_same']=='不支持' for g in F['groups'] if g['review_code'] in c['source_group_codes']) else 'physical_pending'
    assert row['relation_tier']==tier
    definitions[row['group_id']]=set(c['image_ids'])
for g in F['groups']:definitions['user_group:'+g['review_code']]=set(g['image_ids'])
for row in pairs.to_dict('records'):
    ids=json.loads(row['image_ids']);key=tuple(sorted(ids));assert key in relation_by_key and row['relation_tier']==relation_by_key[key]['tier']
    definitions[row['group_id']]=set(ids)
ok('registry_tiers_members_exact_official',True)
ok('lookup3152_unchanged',csv('record_lookup').equals(pd.read_csv(P.parent/'details/record_lookup.csv')))
for n in ['worker_inventory','image_inventory','worker_condition_stats','time_quality_focus','worker_usage_summary']:
    ok(n+'_unchanged',csv(n).equals(pd.read_csv(P.parent/'details'/(n+'.csv'))))
def dist_check(row,cell,ids):
    source=cell[cell.pool_analysis_eligible];scored=cell[cell.B8L2.notna()]
    expected={'n_inventory_records':len(cell),'n_inventory_images':cell.image_id.nunique(),'n_inventory_workers':cell.worker_id.nunique(),'n_source_records':len(source),'n_source_images':source.image_id.nunique(),'n_source_workers':source.worker_id.nunique(),'n_excluded_records':len(cell)-len(source),'n_quality_missing':len(source)-len(scored),'n_scored_images':scored.image_id.nunique(),'n_scored_workers':scored.worker_id.nunique()}
    for k,v in expected.items():assert row[k]==v,(k,row[k],v)
    for metric in ['B8L2','active_time_seconds','target_matched_time_seconds']:
        v=cell[metric].dropna();assert row[metric+'_n']==len(v)
        for stat,val in [('mean',v.mean()),('median',v.median()),('sd',v.std(ddof=1)),('q25',v.quantile(.25)),('q75',v.quantile(.75))]:assert equal(row[metric+'_'+stat],val),(metric,stat)
        assert equal(row[metric+'_image_equal_mean'],cell.groupby('image_id')[metric].mean().dropna().mean())
    for label,metric in [('source','active_time_seconds'),('target','target_matched_time_seconds')]:
        joint=cell[cell.B8L2.notna()&cell[metric].notna()];pre='quality_'+label+'_time_'
        for suffix,val in [('n',len(joint)),('images',joint.image_id.nunique()),('workers',joint.worker_id.nunique())]:assert row[pre+suffix]==val
        for name,column in [('B8L2','B8L2'),('seconds',metric)]:
            v=joint[column].dropna()
            for stat,val in [('mean',v.mean()),('median',v.median()),('sd',v.std(ddof=1)),('q25',v.quantile(.25)),('q75',v.quantile(.75))]:assert equal(row[pre+name+'_'+stat],val)
    if 'all_declared_views_have_records' in row:assert row['all_declared_views_have_records']==(cell.image_id.nunique()==len(ids))
    for label,metric in [('quality','B8L2'),('source_time','active_time_seconds'),('target_time','target_matched_time_seconds')]:
        k='n_'+label+'_workers_all_declared_views'
        if k in row and not pd.isna(row[k]):
            sets=[set(cell.loc[cell.image_id.eq(i)&cell[metric].notna(),'worker_id']) for i in ids]
            assert row[k]==len(set.intersection(*sets))
tables=['room_group_summary','user_original_group_summary','room_worker_groups','user_original_worker_groups','room_group_views','user_original_group_views','room_direct_pair_summary','room_worker_direct_pairs']
for name in tables:
    frame=csv(name)
    for row in frame.to_dict('records'):
        ids=definitions[row['group_id']];cell=A[A.image_id.isin(ids)&A.condition.eq(row['condition'])&A.analysis_layer.eq(row['analysis_layer'])]
        if 'worker_id' in row:cell=cell[cell.worker_id.eq(row['worker_id'])]
        if 'image_id' in row:cell=cell[cell.image_id.eq(row['image_id'])]
        dist_check(row,cell,ids)
    rows_checked[name]=len(frame);ok(name+'_all_stats',True)
    print('checked',name,len(frame),flush=True)
working_summary=csv('room_group_summary');original_summary=csv('user_original_group_summary')
ok('96_zero_inventory_working_groups',working_summary.n_inventory_records.eq(0).sum()==96 and working_summary.group_id.nunique()==259)
ok('all260_original_groups_represented',original_summary.group_id.nunique()==260)
for n in ['room_group_summary','user_original_group_summary']:
    d=csv(n);z=d[d.n_inventory_records.eq(0)];assert z.B8L2_n.eq(0).all() and z.B8L2_mean.isna().all() and z.active_time_seconds_mean.isna().all()
ok('noobs_n0_estimates_null',True)
current=set(A.image_id);expected_pairs={'pair:'+r['image_a']+'|'+r['image_b'] for r in F['relations'] if {r['image_a'],r['image_b']}<=current}
ok('pairsummary_only_both_current_ends',set(csv('room_direct_pair_summary').group_id)==expected_pairs)
unlinked=csv('room_unlinked_images');covered=set().union(*(set(c['image_ids']) for c in F['candidates']))
ok('23_working_outside_exact',set(unlinked.image_id)==current-covered and len(unlinked)==23)
ok('outside1_still_original_classified',sum(bool(json.loads(s)) for s in unlinked.original_user_group_ids)==1 and unlinked.loc[unlinked.original_user_group_ids.ne('[]'),'room_evidence_status'].eq('outside_retained_working_subgroups; original_group_available').all())
ok('OOS_normal_mask_from_parent',A.loc[A.is_oos,'B8L2'].isna().all() and not (A.is_oos&A.quality_usable).any())
result=dict(version='adoption_statistics_independent_audit_20261016_v2',relation_adoption_version=F['version'],checks=checks,rows_recomputed=rows_checked,total_rows_recomputed=sum(rows_checked.values()),relation_tier_counts=dict(Counter(r['tier'] for r in F['relations'])),zero_inventory_working=int(working_summary.n_inventory_records.eq(0).sum()),zero_inventory_original=int(original_summary.n_inventory_records.eq(0).sum()),unlinked_original_classified=unlinked[unlinked.original_user_group_ids.ne('[]')].to_dict('records'),case_summaries=working_summary[working_summary.group_id.isin(['candidate:G095-S1','candidate:G095-S2','candidate:G155'])][['group_id','condition','analysis_layer','n_inventory_records','B8L2_n','B8L2_mean','quality_source_time_n']].replace({np.nan:None}).to_dict('records'))
(P/'ADOPTION_STATISTICS_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
