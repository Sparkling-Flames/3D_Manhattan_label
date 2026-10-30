#!/usr/bin/env python3
"""Independent targeted review of half-team scalars, identities and local votes.

Does not import the generating aggregators or mutate the half-team module.
"""
import gzip,itertools,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'stage01_half_team'
OUT=ROOT/'stage03_speed_difficulty/cross_review';OUT.mkdir(exist_ok=True)
e=pd.read_csv(P/'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz',low_memory=False)
s=pd.read_csv(P/'SAVED_ENDPOINT_SCALARS.csv.gz',low_memory=False).set_index('team_key')
h=e[e.n.eq(14)].copy();q={a:h[a+'_team_key'].map(s.B8L2) for a in 'ABC'}
ok=pd.concat(q,axis=1).notna().all(axis=1);bc=q['B'].notna()&q['C'].notna()
h['GA_check']=((q['C']-q['A']).abs()-(q['B']-q['A']).abs()).where(ok)
h['GS_check']=(((q['C']-q['A']).abs()+(q['C']-q['B']).abs())/2-(q['B']-q['A']).abs()).where(ok)
h['CB_check']=(q['C']-q['B']).where(bc)
columns=['GA_check','GS_check','CB_check']
keys=['building','image','pool_id','block_id','background_id']
a=h.groupby(keys,dropna=False)[columns].mean().reset_index()
for k in [keys[:-1],keys[:-2],keys[:2]]:a=a.groupby(k,dropna=False)[columns].mean().reset_index()
saved=pd.read_csv(P/'ALL_IMAGE_RESULTS.csv.gz');saved=saved[saved.n.eq(14)].set_index('image')
errors={}
for field,old in zip(columns,['gap_A','gap_sym','CB']):
    actual=a.set_index('image')[field];expected=saved[old].reindex(actual.index)
    assert np.allclose(actual,expected,equal_nan=True,atol=1e-12)
    errors[field]=float((actual-expected).abs().max())
assert set(a.loc[a.GS_check.le(0),'image'])==set(pd.read_csv(P/'LATEST_HALF_SYMMETRIC_NONPOSITIVE_21.csv').image)
links=pd.read_csv(P/'EXACT_XYZ_14_7_TO_20_7.csv');ev=e.set_index('event_id')
for r in links.to_dict('records'):
    x=ev.loc[r['event_id_14']];y=ev.loc[r['event_id_20']]
    for block in ['X','Y','Z']:assert set(x[block].split('|'))==set(y[block].split('|'))
    assert (set(x.D.split('|'))<=set(y.D.split('|')))==r['D14_subset_D20']
events=pd.read_csv(P/'ALL_EXCEPTION_EVENTS_AND_20_7_CONTEXT.csv.gz')
facts=pd.read_csv(P/'mechanism_tables/ARM_MECHANISM_FACTS.csv').set_index(['event_id','arm'])
checked=0
for r in events.to_dict('records'):
    blocks={k:set(r[k].split('|')) for k in 'DXYZ'}
    for arm,block in zip('ABC','XYZ'):
        with gzip.open(P/'trace_endpoints'/(r[arm+'_team_key']+'.json.gz'),'rt') as file:tr=json.load(file)
        state=tr['full_state'];groups=state['identity_groups'];threshold=state['minimum_support']
        assert threshold==int(np.ceil(r['n']/2))
        support={g['feature_id']:set(z['worker'] for z in g['members']) for g in groups if g['selected']}
        old=facts.loc[(r['event_id'],arm)]
        expected={'selected_groups':len(support),'all_groups':len(groups),
            'unselected_groups':sum(not g['selected'] for g in groups),
            'exact_threshold_selected_groups':sum(g['selected'] and g['support']==threshold for g in groups),
            'one_vote_below_groups':sum(g['support']==threshold-1 for g in groups),
            'replacement_alone_reaches_groups':sum(len(v&blocks[block])>=threshold for v in support.values()),
            'background_alone_reaches_groups':sum(len(v&blocks['D'])>=threshold for v in support.values()),
            'selected_disjoint_support_pairs':sum(not x&y for x,y in itertools.combinations(support.values(),2))}
        for key,value in expected.items():assert int(old[key])==value,(r['event_id'],arm,key)
        for g in groups:
            assert g['support']==len(set(z['worker'] for z in g['members']))
            assert g['selected']==(g['support']>=threshold)
        checked+=1
report=dict(status='targeted independent checks passed',events_14_7=len(h),registered_images=h.image.nunique(),
    joint_ABC_scored_events=int(ok.sum()),BC_scored_events=int(bc.sum()),
    BC_additional_when_A_unscored=h.loc[bc&~ok,['event_id','image','CB']].to_dict('records'),
    image_results={field:dict(valid=int(a[field].notna().sum()),positive=int(a[field].gt(0).sum()),
        nonpositive=int(a[field].le(0).sum()),mean=float(a[field].mean())) for field in columns},
    maximum_image_error=errors,GS_nonpositive_list_exact=True,all_exception_images=len(pd.read_csv(P/'ALL_36_CASE_READING_INDEX.csv')),
    exact_XYZ_links=len(links),exact_XYZ_images=links.image_14.nunique(),nested_D_links=int(links.D14_subset_D20.sum()),
    complete_arms_checked=checked,local_vote_counts_and_threshold_checks=True,
    mechanism_wording_review='Nearest-reference distances are explicitly diagnostic. Disjoint supporters are not equated with physical mutually exclusive walls. D/block-alone counts are conditional on the saved endpoint groups, not separate D-alone fusion experiments.',
    denominator_note='GA/GS use 185 ABC-scoreable events; C-B uses 187 BC-scoreable events. Their image denominator is 83 in both cases, but the event support is different.',
    source_hashes={file:hashlib.sha256((P/file).read_bytes()).hexdigest() for file in ['EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz','ALL_36_CASE_READING_INDEX.csv','EXACT_XYZ_14_7_TO_20_7.csv','mechanism_tables/ARM_MECHANISM_FACTS.csv']})
(OUT/'HALF_TEAM_INDEPENDENT_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
a.to_csv(OUT/'HALF_TEAM_INDEPENDENT_IMAGE_VALUES.csv',index=False,encoding='utf-8-sig')
print(json.dumps(report,ensure_ascii=False,indent=2))
