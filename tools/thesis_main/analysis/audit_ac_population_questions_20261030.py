"""Targeted AC audit: actual class unions, native case endpoints, main contrasts.

Reads the archived AC files through their package path map; does not fuse,
rescore, change references or import the author's analysis implementation.
"""
from pathlib import Path
import gzip
import json
import csv
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/personnel_ac_review_20261030'
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / 'research/workers/personnel_ac_v21_20261030'
with (BASE / 'SOURCE_PATH_MAP.csv').open(encoding='utf-8-sig', newline='') as f:
    SOURCE_MAP = list(csv.DictReader(f))

def z(name):
    package = 'HOHONET_v21_AC_' + name + '.zip'
    paths = {r['member']: BASE / r['path'] for r in SOURCE_MAP if r['package'] == package}
    assert paths and all(p.is_file() for p in paths.values()), package
    return paths

def read(zf, name, **kwargs):
    return pd.read_csv(zf[name], compression='gzip' if name.endswith('.gz') else None,
                       low_memory=False, **kwargs)

def members(value):
    return set(str(value).split('|')) if pd.notna(value) and value else set()

capacity = z('stage01_capacity_and_sources')
design = z('stage02_frozen_design_clean')
sens = z('stage05_member_background_sensitivity')
labels = read(capacity, 'stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz')
lm = {(r.method, r.heldout_building, r.worker_id): r.class_id
      for r in labels[labels.known.eq(True)].itertuples()}
pools = {}
for name in ['pools', 'admitted_space_extension/pools']:
    data = json.loads((ROOT / 'research/data/releases/v2.1' / name / 'INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))
    pools.update({p['pool_id']: p for p in data['images']})
unions = read(capacity, 'stage01_capacity/ALL_CLASS_ALLIANCE_TEAMS.csv.gz')
for r in unions.itertuples():
    p = pools[r.pool_id]
    assert r.heldout_building == p['meta']['building']
    classes = members(r.alliance_classes)
    expected = set()
    for rec in p['records']:
        cls = lm.get((r.method, r.heldout_building, rec['worker']))
        if cls in classes or (cls is None and r.unknown_background_included):
            expected.add(rec['worker'])
    assert expected == members(r.members) and len(expected) == r.n, (r.pool_id, r.method, r.alliance_classes)
print('Class union members checked:', len(unions), flush=True)

coal = read(sens, 'stage05_sensitivity/results_v1/COMPLETE_COALITIONS.csv.gz')
planned = read(capacity, 'stage01_capacity/ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz')
def coalition_key(r, a, c):
    return (r.pool_id,r.method,bool(r.unknown_background_included),tuple(sorted((a,c))))
expected_keys={coalition_key(r,r.A_alliance,r.C_alliance) for r in planned[planned.condition.eq('manual')&planned.both_n_at_least3.eq(True)].itertuples()}
actual_keys={coalition_key(r,r.raw_input_A_alliance,r.raw_input_C_alliance) for r in coal[coal.condition.eq('manual')].itertuples()}
assert expected_keys==actual_keys
events = read(design, 'stage01_registered/AC_EVENTS.csv.gz')
links = read(design, 'stage01_registered/DESIGN_LINKS.csv.gz', usecols=[
    'event_id', 'design_family', 'background_profile', 'input_orientation_sign', 'complete_coalition_census'])
assert events.event_id.is_unique
ei = events.set_index('event_id')
assert set(coal.event_id) <= set(ei.index)
for r in coal.itertuples():
    e = ei.loc[r.event_id]
    assert {r.input_A_team_key,r.input_C_team_key} == {e.A_team_key,e.C_team_key}
    # Coalition results already orient both endpoint columns to the stated direction.
    assert (pd.isna(r.B8L2_CA) and (pd.isna(r.A_B8L2) or pd.isna(r.C_B8L2))) or abs(r.B8L2_CA - (r.C_B8L2-r.A_B8L2)) < 1e-9
cov = coal.groupby(['scope','condition','method']).agg(
    directional_rows=('event_id','size'), unique_events=('event_id','nunique'),
    pools=('pool_id','nunique'), images=('image','nunique')).reset_index()
cov.to_csv(OUT/'COALITION_COVERAGE.csv',index=False)
print('Coalitions:', len(coal), 'rows;', coal.event_id.nunique(), 'unique events', flush=True)

# Independently compare the seven unions to saved native outputs for four images.
cases = read(sens, 'stage05_sensitivity/preselected_four_complete/PRESELECTED_8_17_10_TEAMS.csv.gz')
assert len(cases) == 28
native = z('stage03_native_part02')
needed = set(cases.team_key)
found = {}
for n in native:
    if n.endswith('.jsonl.gz') and any('/'+pid+'/' in n for pid in cases.pool_id.unique()):
        with gzip.open(native[n],'rt',encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                if r['team_key'] in needed:
                    assert r['team_key'] not in found
                    found[r['team_key']] = r
assert set(found) == needed
for r in cases.itertuples():
    e = found[r.team_key]
    assert set(e['member_workers']) == members(r.member_workers)
    assert abs(e['B8L2']-r.B8L2)<1e-9 and e['nodes']==r.nodes and e['k']==r.n
    p = pools[r.pool_id]
    assert e['reference_id']==p['meta']['reference_id'] and e['reference_version']==p['meta']['reference_version']
    cset=members(r.alliance_classes)
    assert members(r.member_workers)=={a['worker'] for a in p['records'] if lm.get((r.method,r.building,a['worker'])) in cset}
cases.to_csv(OUT/'SEVEN_COALITIONS_VERIFIED.csv',index=False,encoding='utf-8-sig')
print(cases.pivot(index='image',columns='alliance_classes',values='B8L2').round(3).to_string(), flush=True)

# Select actual registered neutral-background events; do not reuse summary values.
neutral=links[links.background_profile.eq('neutral_members_0')]
assert neutral.input_orientation_sign.eq(1).all()
selections=[]
base=events[events.scope.eq('primary')&events.layer.eq('ordinary_manual')&events.equal_team_size.eq(True)&events.pure_cross_class_blocks.eq(True)]
for method,n,m,s,t in [('TARGET_DSTRUCT_K3',20,7,2,3),('OPPJOINT_K3',20,10,1,2),('V21_DSTRUCT_RAW3_K3',23,12,1,2)]:
    ids=set(neutral[neutral.design_family.eq('A_equal_AC')].event_id)
    a=base[base.event_id.isin(ids)&base.method.eq(method)&base.n.eq(n)&base.m.eq(m)&base.source_role_rank.eq(s)&base.target_role_rank.eq(t)].copy()
    a['contrast']=f'{method}_{n}_{m}_{s}_to_{t}'
    selections.append(a)
ids=set(neutral[neutral.design_family.eq('B_equal_whole_class')].event_id)
a=base[base.event_id.isin(ids)&base.method.eq('TARGET_DSTRUCT_K3')&base.n.eq(20)&base.source_role_rank.eq(2)&base.target_role_rank.eq(3)&base.whole_target.eq(True)].copy()
a['contrast']='TARGET_whole_target_n20';selections.append(a)
selected=pd.concat(selections,ignore_index=True)
metrics=[]
for part in [1,2]:
    mz=z(f'stage04_metrics_part0{part}')
    for n in mz:
        if not n.startswith('stage04_metrics/metric_shards/') or not n.endswith('.csv.gz'):
            continue
        pid=n.split('/')[-1][:-7]
        ids=set(selected.loc[selected.pool_id.eq(pid),'event_id'])
        if not ids:continue
        a=read(mz,n,usecols=['event_id','A_team_key','C_team_key','A_B8L2','C_B8L2','B8L2_CA','A_D10','C_D10','D10_CA','A_nodes','C_nodes','fusion_turn_n_CA','A_output_state','C_output_state'])
        metrics.append(a[a.event_id.isin(ids)])
data=pd.concat(metrics,ignore_index=True)
assert data.event_id.is_unique and set(data.event_id)==set(selected.event_id)
for metric in ['B8L2','D10']:
    delta=data['C_'+metric]-data['A_'+metric]
    assert delta.isna().equals(data[metric+'_CA'].isna())
    assert (delta-data[metric+'_CA']).abs().max()<1e-9
j=selected.merge(data,on='event_id',validate='many_to_one',suffixes=('','_metric'))
assert j.A_team_key.eq(j.A_team_key_metric).all() and j.C_team_key.eq(j.C_team_key_metric).all()
j['abs_delta']=j.B8L2_CA.abs()
im=j.groupby(['contrast','pool_id','image','building'])[['B8L2_CA','abs_delta','D10_CA','fusion_turn_n_CA']].mean().reset_index()
out=[]
for contrast,g in im.groupby('contrast'):
    a=j[j.contrast.eq(contrast)];b=g.groupby('building').B8L2_CA.mean()
    out.append(dict(contrast=contrast,registered=len(a),valid=int(a.B8L2_CA.notna().sum()),images=len(g),Q=g.B8L2_CA.mean(),absQ=g.abs_delta.mean(),positive=int((g.B8L2_CA>1e-9).sum()),D10=g.D10_CA.mean(),buildings=len(b),building_Q=b.mean(),positive_buildings=int((b>1e-9).sum()),turn_increase_images=int((g.fusion_turn_n_CA>1e-9).sum())))
pd.DataFrame(out).to_csv(OUT/'MAIN_EFFECTS_RECOMPUTED.csv',index=False)
im.to_csv(OUT/'MAIN_EFFECTS_BY_IMAGE.csv',index=False)
print(pd.DataFrame(out).to_string(index=False),flush=True)
bg=read(sens,'stage05_sensitivity/results_v1/BACKGROUND_CHANGES.csv.gz',usecols=[
    'image','building','scope','condition','method','role_direction','n','m','block_id',
    'same_background_class_counts','B8L2_CA__baseline','B8L2_CA__changed','B8L2_CA__effect_difference'])
bg=bg[bg.scope.eq('primary')&bg.condition.eq('manual')&bg.method.eq('TARGET_DSTRUCT_K3')&bg.role_direction.eq('2->3')&bg.n.eq(20)&bg.m.eq(7)&bg.same_background_class_counts.eq(True)].copy()
bg['effect_change']=bg.B8L2_CA__changed-bg.B8L2_CA__baseline
assert (bg.effect_change-bg.B8L2_CA__effect_difference).abs().max()<1e-9
bg['absolute_effect_change']=bg.effect_change.abs()
bi=bg.groupby(['image','building','block_id'])[['effect_change','absolute_effect_change']].mean().groupby(['image','building']).mean()
bi.to_csv(OUT/'BACKGROUND_SAME_COMPOSITION_RECOMPUTED.csv')
checks=dict(union_members_checked=len(unions),manual_coalition_plan_actual_exact_equal=True,manual_coalition_comparisons=len(actual_keys),coalition_rows=len(coal),coalition_unique_events=int(coal.event_id.nunique()),native_case_endpoints_checked=len(found),selected_events_checked=int(data.event_id.nunique()),native_fusion_rerun=False)
checks.update(background_comparisons=len(bg),background_images=len(bi),background_mean_effect_change=float(bi.effect_change.mean()),background_mean_absolute_effect_change=float(bi.absolute_effect_change.mean()))
(OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
