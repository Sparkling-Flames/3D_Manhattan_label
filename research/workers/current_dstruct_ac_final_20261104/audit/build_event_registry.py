"""Audit frozen historical AC membership under the current LOBO DSTRUCT K3 labels.

This program reads labels, members, design registration and pool identity only.
It does not read Q, annotation coordinates, GT coordinates, or recorded time.
The old event id, team keys, design links and reference identity are retained.
Current-label legality is separate from satisfying an old, more specific design.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import time

import pandas as pd


HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
REPO = STUDY.parents[2]
OLD = REPO / 'research/workers/personnel_ac_v21_20261030'
B12 = REPO / 'research/workers/mixture_patterns_and_c13_half_20261104/c13_half'
LABEL_PATH = REPO / 'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz'
CURRENT_CAP = REPO / 'research/workers/current_class_interpretation_20261104/basis/CLASS_CAPACITY_PER_POOL.csv.gz'
METHOD = 'TARGET_DSTRUCT_K3'
COMMIT = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
CLASSES = ['C1', 'C2', 'C3']
KEY_BUDGETS = [(6,3),(8,4),(10,5),(12,6),(14,7),(16,8),(18,9),(20,7),(20,10),(22,11),(24,12)]


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(enc(value).encode()).hexdigest()


def members(value):
    if value is None or pd.isna(value) or not str(value):
        return []
    return str(value).split('|')


def team_key(pid, workers):
    return pid + '__' + digest(sorted(workers))[:20]


def write_csv(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    if path.name.endswith('.gz'):
        with gzip.open(tmp, 'wt', encoding='utf-8', newline='') as stream:
            df.to_csv(stream, index=False)
    else:
        df.to_csv(tmp, index=False)
    tmp.replace(path)


def read_method(path, method=METHOD):
    parts = []
    for part in pd.read_csv(path, chunksize=60000, low_memory=False):
        parts.append(part[part.method == method])
    return pd.concat(parts, ignore_index=True)


def known_map(table):
    table = table[table.method == METHOD].copy()
    if table.duplicated(['heldout_building','worker_id']).any():
        raise ValueError('Duplicate worker/fold labels')
    return {(r.heldout_building, r.worker_id):
            str(r.class_id) if bool(r.known) and pd.notna(r.class_id) and str(r.class_id) in CLASSES else 'unknown'
            for r in table.itertuples()}


def counts(ws, lookup):
    return dict(sorted(Counter(lookup.get(w, 'unknown') for w in ws).items()))


def fair_class_sequence(groups, token):
    """The frozen registrar's quota rule, without reading or altering its RNG."""
    sizes = {k: len(v) for k,v in groups.items() if len(v)}
    N = sum(sizes.values())
    used = Counter()
    seq = []
    tie = {k: digest([token,k]) for k in sizes}
    for i in range(N):
        k = min((k for k in sizes if used[k] < sizes[k]),
                key=lambda k: (-(sizes[k]*(i+1)/N-used[k]), tie[k]))
        used[k] += 1
        seq.append(k)
    return seq


def groups_for(ws, lookup):
    groups = defaultdict(list)
    for w in ws:
        groups[lookup.get(w, 'unknown')].append(w)
    return groups


def quota_expected(remaining, lookup, token, n_D, profile, source, target):
    groups = groups_for(remaining, lookup)
    if profile in ('neutral_members_0','neutral_members_1'):
        seq = fair_class_sequence(groups, ['D_quota', token])
    elif profile in ('source_enriched','target_enriched'):
        focus = source if profile == 'source_enriched' else target
        other = {k:v for k,v in groups.items() if k != focus}
        seq = [focus]*len(groups.get(focus, [])) + fair_class_sequence(other, ['D_enriched_quota', token, focus])
    else:
        return None
    return dict(sorted(Counter(seq[:n_D]).items()))


def audit_event(row, pools, lookup_by_pool, teams):
    out = dict(row)
    pid = str(row['pool_id'])
    pool = pools.get(pid)
    structural = []
    reasons = []
    raw = {k: members(row.get(k+'_workers')) for k in ('A','C','D','X','Z')}
    ws = {k:set(v) for k,v in raw.items()}
    A,C,D,X,Z = [ws[k] for k in ('A','C','D','X','Z')]
    if any(len(raw[k]) != len(ws[k]) for k in raw): structural.append('duplicate_member_in_block')
    if pool is None: structural.append('unknown_pool')
    if D != A & C or X != A-C or Z != C-A or (D & X) or (D & Z) or (X & Z):
        structural.append('D_X_Z_not_exact_partition')
    if len(A) < 3 or len(C) < 3: structural.append('native_team_n_below_3')
    for field,actual in [('n_A',len(A)),('n_C',len(C)),('D_n',len(D)),('m_X',len(X)),('m_Z',len(Z))]:
        if field in row and pd.notna(row[field]) and float(row[field])!=actual:
            structural.append('registered_'+field+'_mismatch')
    if len(A)==len(C) and len(X)==len(Z):
        for field,actual in [('n',len(A)),('m',len(X))]:
            if field in row and pd.notna(row[field]) and float(row[field])!=actual:
                structural.append('registered_'+field+'_mismatch')
    for endpoint,S in [('A',A),('C',C)]:
        field='mv50_threshold_'+endpoint
        if field in row and pd.notna(row[field]) and float(row[field])!=math.ceil(len(S)/2):
            structural.append('registered_'+field+'_mismatch')
    if not X or not Z: reasons.append('empty_replacement_block')
    if len(A) != len(C) or len(X) != len(Z): reasons.append('unequal_n_or_m')
    if pool is not None:
        meta = pool['meta']
        if not A|C <= set(pool['workers']): structural.append('member_not_in_pool')
        if str(row['building']) != meta['building'] or str(row.get('heldout_building', row['building'])) != meta['building']:
            structural.append('heldout_building_mismatch')
        for col in ('image','condition','layer','reference_id','reference_version'):
            if str(row.get(col,'')) != str(meta.get(col,'')): structural.append(col+'_mismatch')
        if str(row.get('scope','')) != str(pool['scope']): structural.append('scope_mismatch')
    for endpoint, S in [('A',A),('C',C)]:
        key = str(row[endpoint+'_team_key'])
        if key != team_key(pid,S): structural.append(endpoint+'_team_key_mismatch')
        request = teams.get(key)
        if request is None:
            structural.append(endpoint+'_team_request_missing')
        else:
            if set(members(request['member_workers'])) != S: structural.append(endpoint+'_request_members_mismatch')
            if int(request['n']) != len(S): structural.append(endpoint+'_request_n_mismatch')
            for col in ('pool_id','reference_id','reference_version'):
                if str(request[col]) != str(row[col]): structural.append(endpoint+'_request_'+col+'_mismatch')
            if pool is not None:
                object_map = {m['worker_id']:str(m['object_id']) for m in pool['members']}
                expected = {object_map.get(w, '?') for w in S}
                if set(members(request['member_object_ids'])) != expected:
                    structural.append(endpoint+'_request_object_ids_mismatch')
    if structural:
        reasons.extend(structural)
    lookup = lookup_by_pool.get(pid,{})
    xcounts, zcounts = counts(X,lookup), counts(Z,lookup)
    cs = next(iter(xcounts)) if len(xcounts)==1 else '|'.join(sorted(xcounts))
    ct = next(iter(zcounts)) if len(zcounts)==1 else '|'.join(sorted(zcounts))
    if 'unknown' in xcounts: reasons.append('current_source_block_unknown')
    if 'unknown' in zcounts: reasons.append('current_target_block_unknown')
    if len(xcounts) > 1: reasons.append('current_source_block_mixed')
    if len(zcounts) > 1: reasons.append('current_target_block_mixed')
    if len(xcounts)==len(zcounts)==1 and cs==ct: reasons.append('same_current_class')
    if not cs or not ct:
        reasons.append('no_current_cross_class_direction')
    same = len(A)==len(C) and len(X)==len(Z)
    pure = len(xcounts)==len(zcounts)==1 and cs in CLASSES and ct in CLASSES and cs!=ct
    legal = not reasons and pure and same
    canonical_physical = digest([pid,sorted([str(row['A_team_key']),str(row['C_team_key'])])])[:24]
    if row.get('physical_pair_id') and str(row['physical_pair_id'])!=canonical_physical:
        structural.append('physical_pair_identity_mismatch');reasons.append('physical_pair_identity_mismatch');legal=False
    orientation = 1 if pure and cs<ct else -1 if pure and cs>ct else 0
    out.update({
        'current_source_class':cs,'current_target_class':ct,
        'current_direction':cs+'_to_'+ct if pure else '',
        'current_class_pair':'_'.join(sorted([cs,ct])) if pure else '',
        'current_ac_legal':legal,'audit_reason':'|'.join(sorted(set(reasons))) if reasons else 'legal_current_AC',
        'structural_identity_valid':not structural,
        'structural_identity_reason':'|'.join(sorted(set(structural))),
        'current_n':len(A) if same else None,'current_m':len(X) if same else None,
        'current_replacement_fraction':len(X)/len(A) if same and len(A) else None,
        'current_X_class_counts':enc(xcounts),'current_Z_class_counts':enc(zcounts),
        'current_direction_changed':pure and (cs!=str(row.get('source_class','')) or ct!=str(row.get('target_class',''))),
        'canonical_physical_pair_id':canonical_physical,'orientation_sign':orientation,
        'canonical_A_team_key':row['A_team_key'] if orientation>=0 else row['C_team_key'],
        'canonical_C_team_key':row['C_team_key'] if orientation>=0 else row['A_team_key'],
        'canonical_source_class':min(cs,ct) if pure else '',
        'canonical_target_class':max(cs,ct) if pure else '',
        'orientation_origin':'registered',
        'current_label_commit':COMMIT,'current_label_use':'target_building_excluded',
        'current_D_is_empty':len(D)==0,
        'current_D_is_mixed':len(counts(D,lookup))>1,
        'current_D_class_counts':enc(counts(D,lookup)),
        'current_A_class_counts':enc(counts(A,lookup)),
        'current_C_class_counts':enc(counts(C,lookup)),
        'current_source_available_n':sum(c==cs for c in lookup.values()) if pure else None,
        'current_target_available_n':sum(c==ct for c in lookup.values()) if pure else None,
        'current_whole_source':pure and X=={w for w,c in lookup.items() if c==cs},
        'current_whole_target':pure and Z=={w for w,c in lookup.items() if c==ct},
    })
    for k in ('D','X','Z'):
        cc=counts(ws[k],lookup)
        for cl in CLASSES+['unknown']:
            out[k+'_current_'+cl]=cc.get(cl,0)
            out[k+'_current_'+cl+'_workers']='|'.join(sorted(w for w in ws[k] if lookup.get(w,'unknown')==cl))
    return out


def summarize(frame, grouping, include_reasons=False):
    rows=[]
    for key,g in frame.groupby(grouping,dropna=False,sort=True):
        key=key if isinstance(key,tuple) else (key,)
        legal=g[g.current_ac_legal]
        item=dict(zip(grouping,key))
        item.update(original_events=len(g),current_legal_events=len(legal),excluded_events=len(g)-len(legal),
                    original_images=g.image.nunique(),original_buildings=g.building.nunique(),
                    current_legal_images=legal.image.nunique(),current_legal_buildings=legal.building.nunique(),
                    original_pools=g.pool_id.nunique(),current_legal_pools=legal.pool_id.nunique(),
                    original_unique_teams=len(set(g.A_team_key)|set(g.C_team_key)),
                    current_legal_unique_teams=len(set(legal.A_team_key)|set(legal.C_team_key)),
                    original_physical_pairs=g.canonical_physical_pair_id.nunique(),
                    current_legal_physical_pairs=legal.canonical_physical_pair_id.nunique(),
                    current_legal_direction_changed=int(legal.current_direction_changed.sum()),
                    current_legal_mixed_D_events=int(legal.current_D_is_mixed.sum()))
        if 'original_design_current_valid' in g:
            item['original_specific_design_still_valid_events']=int(g.original_design_current_valid.sum())
        if include_reasons:
            item['excluded_reasons_json']=enc(g.loc[~g.current_ac_legal,'audit_reason'].value_counts().to_dict())
        rows.append(item)
    return pd.DataFrame(rows)


def main():
    started=time.monotonic()
    registry=STUDY/'registry';registry.mkdir(exist_ok=True,parents=True)
    current=pd.read_csv(LABEL_PATH,low_memory=False)
    previous=pd.read_csv(OLD/'stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz',low_memory=False)
    lm=known_map(current);old_lm=known_map(previous)
    changed=[]
    for key in sorted(set(lm)|set(old_lm)):
        a,b=old_lm.get(key,'missing'),lm.get(key,'missing')
        changed.append(dict(heldout_building=key[0],worker_id=key[1],old_class=a,current_class=b,label_changed=a!=b))
    crosswalk=pd.DataFrame(changed)
    write_csv(crosswalk,HERE/'LABEL_CROSSWALK_ALL_LOBO.csv.gz')
    write_csv(crosswalk[crosswalk.label_changed],HERE/'CHANGED_WORKER_FOLDS.csv')
    score_blind=json.loads((OLD/'stage01_capacity/SCORE_BLIND_POOL_INPUTS.json').read_text(encoding='utf-8'))
    pools={p['pool_id']:p for p in score_blind['pools']}
    lookup_by_pool={pid:{w:lm.get((p['meta']['building'],w),'unknown') for w in p['workers']} for pid,p in pools.items()}
    old_lookup_by_pool={pid:{w:old_lm.get((p['meta']['building'],w),'unknown') for w in p['workers']} for pid,p in pools.items()}
    pool_rows=[];member_rows=[]
    for pid,p in pools.items():
        meta=p['meta'];lookup=lookup_by_pool[pid]
        if meta['condition']!='manual' or meta['layer']!='ordinary_manual':continue
        rr={k:meta.get(k,'') for k in ('image','image_id','building','condition','layer','reference_id','reference_version','difficulty')}
        rr.update(pool_id=pid,scope=p['scope'],pool_n=len(p['workers']),workers='|'.join(sorted(p['workers'])))
        for cl in CLASSES+['unknown']:
            ws=sorted(w for w,c in lookup.items() if c==cl);rr[cl+'_n']=len(ws);rr[cl+'_workers']='|'.join(ws)
        pool_rows.append(rr)
        for m in p['members']:
            worker=m['worker_id'];cl=lookup[worker]
            member_rows.append(dict(pool_id=pid,image=meta['image'],building=meta['building'],scope=p['scope'],condition=meta['condition'],
                                    layer=meta['layer'],worker_id=worker,object_id=m['object_id'],current_class=cl,
                                    old_class=old_lookup_by_pool[pid].get(worker,'unknown'),reference_id=meta['reference_id'],
                                    reference_version=meta['reference_version'],heldout_building=meta['building']))
    pool_frame=pd.DataFrame(pool_rows)
    write_csv(pool_frame,registry/'CURRENT_POOL_INVENTORY.csv.gz')
    write_csv(pd.DataFrame(member_rows),registry/'CURRENT_POOL_MEMBERS.csv.gz')
    write_csv(current[current.method==METHOD],registry/'CURRENT_DSTRUCT_LOBO_LABELS.csv.gz')
    pool_compat=[]
    cap_previous=pd.read_csv(CURRENT_CAP,low_memory=False)
    cap_previous=cap_previous[cap_previous.method==METHOD]
    for pid,g in cap_previous.groupby('pool_id'):
        p=pools.get(pid);ws=set()
        for value in g.members:ws.update(members(value))
        pool_compat.append(dict(pool_id=pid,present_in_historical_capacity=p is not None,
            members_identical=p is not None and ws==set(p['workers']),
            reference_identical=p is not None and str(g.reference_id.iloc[0])==str(p['meta']['reference_id']) and str(g.reference_version.iloc[0])==str(p['meta']['reference_version'])))
    pool_compat=pd.DataFrame(pool_compat)
    write_csv(pool_compat,HERE/'POOL_COMPATIBILITY_WITH_BATCH08_12.csv.gz')
    events=read_method(OLD/'stage01_registered/AC_EVENTS.csv.gz')
    links=read_method(OLD/'stage01_registered/DESIGN_LINKS.csv.gz')
    needed=set(events.A_team_key)|set(events.C_team_key)
    team_parts=[]
    for part in pd.read_csv(OLD/'stage01_registered/TEAM_REQUESTS.csv.gz',chunksize=60000,low_memory=False):
        team_parts.append(part[part.team_key.isin(needed)])
    team_frame=pd.concat(team_parts,ignore_index=True)
    if team_frame.duplicated('team_key').any():raise ValueError('Duplicate historical team requests')
    teams={r['team_key']:r for r in team_frame.to_dict('records')}
    write_csv(team_frame,registry/'LEGACY_TARGET_TEAM_REQUESTS.csv.gz')
    audited=[]
    for row in events.to_dict('records'):
        row.update(analysis_source='legacy_target_stock_current_label_conditional',source_event_id=row['event_id'],source_leg='AC',
                   source_registry='personnel_ac_v21_20261030/stage01_registered/AC_EVENTS.csv.gz',
                   sampling_interpretation='conditional_analysis_of_historical_registered_teams')
        rr=audit_event(row,pools,lookup_by_pool,teams)
        old_lookup=old_lookup_by_pool[row['pool_id']]
        original_failures=[]
        for block,col in [('X','source_class'),('Z','target_class')]:
            expected='|'.join(sorted(set(old_lookup.get(w,'unknown') for w in members(row[block+'_workers']))))
            registered='' if pd.isna(row.get(col)) else str(row[col])
            if expected!=registered:original_failures.append(col+'_does_not_match_old_LOBO')
        for block in ('A','C','D'):
            if json.loads(row[block+'_class_counts'])!=counts(members(row[block+'_workers']),old_lookup):
                original_failures.append(block+'_class_counts_do_not_match_old_LOBO')
        rr['original_label_metadata_valid']=not original_failures
        rr['original_label_metadata_reason']='|'.join(original_failures)
        audited.append(rr)
    audit=pd.DataFrame(audited)
    event_map={r['event_id']:r for r in audited}
    print('EVENT_AUDIT',len(audit),'legal',int(audit.current_ac_legal.sum()),flush=True)
    # Background requirements are assessed per design link, not imposed on generic AC.
    link_rows=[]
    for row in links.to_dict('records'):
        r=event_map[row['event_id']];pid=r['pool_id'];p=pools[pid];lookup=lookup_by_pool[pid]
        D,X,Z=[set(members(r[k+'_workers'])) for k in ('D','X','Z')]
        sign=int(row['input_orientation_sign']);ox,oz=(X,Z) if sign==1 else (Z,X)
        cs=r['current_source_class'] if sign==1 else r['current_target_class']
        ct=r['current_target_class'] if sign==1 else r['current_source_class']
        profile='' if pd.isna(row.get('background_profile')) else str(row['background_profile'])
        family=str(row['design_family']);rule='mixed_background_allowed';bgpass=True;quota_match=None
        q_expected=None
        if profile.startswith('outside_swapped_classes_'):
            rule='D_outside_both_current_swapped_classes'
            bgpass=all(lookup.get(w,'unknown') not in (cs,ct) for w in D)
        elif family=='F_strict_common_n_bridge':
            rule='inherited_exact_strict_ABC_common_background_may_mix_classes'
        elif profile in ('neutral_members_0','neutral_members_1','source_enriched','target_enriched'):
            token=[pid,sorted(ox),sorted(oz)]
            q_expected=quota_expected(set(p['workers'])-X-Z,lookup,token,len(D),profile,cs,ct)
            quota_match=q_expected==counts(D,lookup)
            rule='frozen_profile_counts_under_current_labels'
            bgpass=quota_match
        specific=bool(r['current_ac_legal']) and bgpass
        specific_reasons=[]
        if not r['current_ac_legal']:specific_reasons.append('not_current_generic_AC')
        if not bgpass:specific_reasons.append('current_background_rule_not_met')
        whole_required=family in ('B_equal_whole_class','B_unequal_equal_size_anchor')
        whole_pass=not whole_required or bool(r['current_whole_source'] or r['current_whole_target'])
        if not whole_pass:specific=False;specific_reasons.append('no_longer_contains_entire_current_class')
        if family=='B_unequal_equal_size_anchor' and r['current_source_available_n']==r['current_target_available_n']:
            specific=False;specific_reasons.append('current_full_classes_no_longer_unequal')
        if family=='C_complete_class_alliances':
            # This link is historical context only: whole current class census is
            # not asserted by the generic AC eligibility audit.
            specific=False;specific_reasons.append('alliance_identity_retained_historical_only')
        row.update(current_ac_legal=bool(r['current_ac_legal']),current_direction=r['current_direction'],
                   current_class_pair=r['current_class_pair'],canonical_physical_pair_id=r['canonical_physical_pair_id'],
                   current_n=r['current_n'],current_m=r['current_m'],current_D_class_counts=r['current_D_class_counts'],
                   background_rule_current=rule,background_rule_current_pass=bgpass,
                   background_quota_current_match=quota_match,
                   expected_current_background_counts=enc(q_expected) if q_expected is not None else '',
                   whole_class_required=whole_required,whole_class_current_pass=whole_pass,
                   original_design_current_valid=specific,
                   original_design_current_reason='|'.join(specific_reasons) if specific_reasons else 'specific_membership_requirements_met',
                   sampling_interpretation='conditional_analysis_of_historical_registered_teams')
        link_rows.append(row)
    link_audit=pd.DataFrame(link_rows)
    valid_link=link_audit.groupby('event_id').original_design_current_valid.any().to_dict()
    profs=link_audit.groupby('event_id').background_profile.agg(lambda s:'|'.join(sorted(set(str(v) for v in s if pd.notna(v))))).to_dict()
    audit['original_design_current_valid']=audit.event_id.map(valid_link).fillna(False)
    audit['historical_background_profiles']=audit.event_id.map(profs).fillna('')
    audit['original_specific_link_count']=audit.event_id.map(link_audit.groupby('event_id').size()).fillna(0).astype(int)
    audit['current_valid_specific_link_count']=audit.event_id.map(link_audit[link_audit.original_design_current_valid].groupby('event_id').size()).fillna(0).astype(int)
    write_csv(audit,registry/'LEGACY_TARGET_EVENTS_AUDIT.csv.gz')
    write_csv(link_audit,registry/'LEGACY_TARGET_DESIGN_LINKS_AUDIT.csv.gz')
    legal=audit[audit.current_ac_legal].copy()
    write_csv(legal,registry/'LEGAL_CURRENT_AC_EVENTS.csv.gz')
    write_csv(link_audit[link_audit.current_ac_legal],registry/'LEGAL_CURRENT_AC_DESIGN_LINKS.csv.gz')
    write_csv(summarize(audit,['scope','condition','source_class','target_class','n','m'],True),HERE/'LEGACY_REUSE_BY_ORIGINAL_CONDITION.csv.gz')
    write_csv(summarize(audit,['scope','condition','design_family','source_class','target_class','n','m'],True),HERE/'LEGACY_REUSE_BY_ORIGINAL_DESIGN.csv.gz')
    write_csv(summarize(audit,['scope','condition','current_source_class','current_target_class','current_n','current_m'],True),HERE/'LEGACY_REUSE_BY_CURRENT_CONDITION.csv.gz')
    reason_rows=[]
    for reason,g in audit.groupby('audit_reason'):
        reason_rows.append(dict(reason=reason,events=len(g),images=g.image.nunique(),buildings=g.building.nunique(),pools=g.pool_id.nunique(),
                                unique_teams=len(set(g.A_team_key)|set(g.C_team_key))))
    write_csv(pd.DataFrame(reason_rows),HERE/'EXCLUSION_AND_RETENTION_REASONS.csv')
    # Every original member/fold consulted is traceable independently of an event.
    member_changes=[]
    for r in audited:
        pid=r['pool_id'];old_lookup=old_lookup_by_pool[pid];lookup=lookup_by_pool[pid]
        for block in ('D','X','Z'):
            for worker in members(r[block+'_workers']):
                if old_lookup.get(worker,'unknown')!=lookup.get(worker,'unknown'):
                    member_changes.append(dict(event_id=r['event_id'],pool_id=pid,image=r['image'],building=r['building'],block=block,
                                               worker_id=worker,old_class=old_lookup.get(worker,'unknown'),current_class=lookup.get(worker,'unknown'),
                                               current_ac_legal=r['current_ac_legal'],current_direction=r['current_direction']))
    write_csv(pd.DataFrame(member_changes),HERE/'AFFECTED_EVENT_MEMBERS.csv.gz')
    # Batch 12: both AC and BC are real direct replacement legs. The original
    # ABC event and its non-uniform, strict-capacity selection remain explicit.
    b12_events=pd.read_csv(B12/'design/EVENTS.csv.gz',low_memory=False)
    b12_req=pd.read_csv(B12/'design/REQUESTS.csv.gz',low_memory=False)
    b12_teams={r['team_key']:r for r in b12_req.to_dict('records')}
    b12_rows=[]
    for r in b12_events.to_dict('records'):
        for leg,outgoing in [('AC','A'),('BC','B')]:
            row=dict(r)
            row.update(source_event_id=r['event_id'],event_id=r['event_id']+'::'+leg,source_leg=leg,
                       A_team_key=r[outgoing+'_team_key'],A_workers=r[outgoing+'_workers'],
                       D_workers=r['D'],X_workers=r['X'] if outgoing=='A' else r['Y'],Z_workers=r['Z'],
                       heldout_building=r['building'],condition='manual',layer='ordinary_manual',scope='primary',
                       n_A=r['n'],n_C=r['n'],m_X=r['m'],m_Z=r['m'],D_n=r['n']-r['m'],
                       source_commit=COMMIT,registration_source='batch12_C13_strict_half',design_family='batch12_'+r['study']+'_strict_ABC_'+leg,
                       source_registry='mixture_patterns_and_c13_half_20261104/c13_half/design/EVENTS.csv.gz',
                       analysis_source='batch12_strictABC_reused_direct_leg',sampling_interpretation='conditional_analysis_of_strict_ABC_registered_teams')
            rr=audit_event(row,pools,lookup_by_pool,b12_teams)
            rr['original_design_current_valid']=bool(rr['current_ac_legal'])
            rr['historical_background_profiles']='strict_ABC_registered_D'
            b12_rows.append(rr)
    b12_audit=pd.DataFrame(b12_rows)
    write_csv(b12_audit,registry/'BATCH12_C13_AC_BC_LEGS_AUDIT.csv.gz')
    reused=pd.concat([legal,b12_audit[b12_audit.current_ac_legal]],ignore_index=True,sort=False)
    write_csv(reused,registry/'REUSED_CURRENT_AC_REGISTRY.csv.gz')
    # One row per physical pair, with aliases rather than duplicated outcomes.
    pair_rows=[]
    for physical,g in reused.groupby('canonical_physical_pair_id',sort=True):
        rr=g.iloc[0]
        if g[['pool_id','reference_id','reference_version','current_n','current_m','current_class_pair']].drop_duplicates().shape[0]!=1:
            raise ValueError('Inconsistent physical pair aliases: '+physical)
        pair_rows.append(dict(canonical_physical_pair_id=physical,pool_id=rr.pool_id,image=rr.image,building=rr.building,scope=rr.scope,
            condition=rr.condition,layer=rr.layer,reference_id=rr.reference_id,reference_version=rr.reference_version,
            n=int(rr.current_n),m=int(rr.current_m),replacement_fraction=float(rr.current_replacement_fraction),
            current_class_pair=rr.current_class_pair,canonical_source_class=rr.canonical_source_class,canonical_target_class=rr.canonical_target_class,
            canonical_A_team_key=rr.canonical_A_team_key,canonical_C_team_key=rr.canonical_C_team_key,
            registered_event_alias_count=len(g),source_event_count=g.source_event_id.nunique(),
            event_ids='|'.join(g.event_id.astype(str)),analysis_sources='|'.join(sorted(set(g.analysis_source))),
            has_legacy_stock=bool((g.analysis_source=='legacy_target_stock_current_label_conditional').any()),
            has_batch12_leg=bool((g.analysis_source=='batch12_strictABC_reused_direct_leg').any())))
    pair_frame=pd.DataFrame(pair_rows)
    write_csv(pair_frame,registry/'REUSED_CURRENT_AC_PHYSICAL_PAIRS.csv.gz')
    # Fully enumerated capacity catalog, including infeasible directions. No
    # labels, workers or budgets are selected by an outcome.
    # Include every equal-size historical budget, even if all its events lose
    # current-label eligibility, so zero support is visible rather than omitted.
    budgets={(int(r.current_n),int(r.current_m)) for r in audit.itertuples()
             if pd.notna(r.current_n) and pd.notna(r.current_m) and r.current_m>0}
    budgets.update(KEY_BUDGETS)
    capacity=[];frontier=[]
    stock_counts=legal.groupby(['pool_id','current_class_pair','current_n','current_m']).size().to_dict()
    reused_counts=pair_frame.groupby(['pool_id','current_class_pair','n','m']).size().to_dict()
    for pool in pool_rows:
        N=pool['pool_n']
        for s,t in itertools.permutations(CLASSES,2):
            pair='_'.join(sorted([s,t]));ns=pool[s+'_n'];nt=pool[t+'_n']
            maxhalf=min(ns,nt,N//3)
            frontier.append(dict(pool_id=pool['pool_id'],image=pool['image'],building=pool['building'],scope=pool['scope'],source_class=s,target_class=t,
                direction=s+'_to_'+t,pool_n=N,source_n=ns,target_n=nt,unknown_n=pool['unknown_n'],
                max_equal_block_m=min(ns,nt),max_half_m=maxhalf if maxhalf>=2 else 0,max_half_n=2*maxhalf if maxhalf>=2 else 0))
            for n,m in sorted(budgets):
                why=[]
                if n<3:why.append('native_n_below_3')
                if m<1 or m>n:why.append('invalid_m')
                if ns<m:why.append('source_class_capacity_below_m')
                if nt<m:why.append('target_class_capacity_below_m')
                if N<n+m:why.append('union_capacity_below_n_plus_m')
                feasible=not why
                capacity.append(dict(pool_id=pool['pool_id'],image=pool['image'],building=pool['building'],scope=pool['scope'],condition=pool['condition'],
                    direction=s+'_to_'+t,source_class=s,target_class=t,current_class_pair=pair,n=n,m=m,replacement_fraction=m/n,D_n=n-m,
                    pool_n=N,source_available_n=ns,target_available_n=nt,unknown_n=pool['unknown_n'],feasible=feasible,
                    infeasible_reason='|'.join(why),possible_XZ_blocks=str(math.comb(ns,m)*math.comb(nt,m)) if feasible else '0',
                    possible_D_per_XZ=str(math.comb(N-2*m,n-m)) if feasible else '0',
                    legacy_legal_method_events=stock_counts.get((pool['pool_id'],pair,n,m),0),
                    reused_unique_physical_pairs=reused_counts.get((pool['pool_id'],pair,n,m),0),
                    missing_reused_support=feasible and reused_counts.get((pool['pool_id'],pair,n,m),0)==0,
                    capacity_rule='source>=m; target>=m; N>=n+m; D may mix known and unknown classes',
                    reverse_view_is_same_physical_support=True))
    cap=pd.DataFrame(capacity);fr=pd.DataFrame(frontier)
    write_csv(cap,registry/'CURRENT_AC_POOL_N_M_DIRECTION_CAPACITY.csv.gz')
    write_csv(fr,registry/'CURRENT_AC_MAXIMUM_HALF_CAPACITY.csv.gz')
    cs=[]
    for (scope,direction,n,m),g in cap.groupby(['scope','direction','n','m']):
        f=g[g.feasible];old=f[f.legacy_legal_method_events>0];re=f[f.reused_unique_physical_pairs>0]
        cs.append(dict(scope=scope,direction=direction,n=n,m=m,replacement_fraction=m/n,candidate_pools=len(g),
            feasible_pools=f.pool_id.nunique(),feasible_images=f.image.nunique(),feasible_buildings=f.building.nunique(),
            legacy_supported_pools=old.pool_id.nunique(),legacy_supported_images=old.image.nunique(),legacy_supported_buildings=old.building.nunique(),
            reused_supported_pools=re.pool_id.nunique(),reused_supported_images=re.image.nunique(),reused_supported_buildings=re.building.nunique(),
            uncovered_feasible_pools=len(f)-len(re),
            support_status='no_feasible_support' if not len(f) else 'sparse_capacity' if f.image.nunique()<5 else 'feasible_support',
            reverse_view_is_not_an_independent_sample=True))
    cap_summary=pd.DataFrame(cs)
    write_csv(cap_summary,HERE/'CURRENT_CAPACITY_AND_REUSE_BY_CONDITION.csv.gz')
    write_csv(cap_summary[[tuple(x) in KEY_BUDGETS for x in cap_summary[['n','m']].itertuples(index=False,name=None)]],HERE/'KEY_BUDGET_CAPACITY_AND_REUSE.csv')
    missing=cap[(cap.scope=='primary')&(cap.n.isin([14,20]))&(cap.m==7)&(cap.source_class<cap.target_class)&cap.missing_reused_support].copy()
    missing=missing.merge(pool_frame[['pool_id','workers','reference_id','reference_version','image_id']+[c+'_workers' for c in CLASSES+['unknown']]],on='pool_id',how='left',validate='many_to_one')
    write_csv(missing,HERE/'CORE_BUDGET_MISSING_POOLS_BEFORE_SUPPLEMENT.csv')
    # Detailed old design requirement summary; all denominators refer to links,
    # and the unique event/team counts remain available separately.
    lsum=link_audit.groupby(['design_family','background_profile','background_rule_current'],dropna=False).agg(
        original_links=('link_id','size'),original_events=('event_id','nunique'),generic_current_legal_links=('current_ac_legal','sum'),
        background_current_rule_pass_links=('background_rule_current_pass','sum'),specific_current_design_valid_links=('original_design_current_valid','sum')).reset_index()
    write_csv(lsum,HERE/'OLD_SPECIFIC_DESIGN_REQUIREMENTS.csv')
    stats={
        'status':'passed' if audit.structural_identity_valid.all() and audit.original_label_metadata_valid.all() and b12_audit.structural_identity_valid.all() and pool_compat.members_identical.all() and pool_compat.reference_identical.all() else 'failed',
        'source_commit':COMMIT,'method':METHOD,'outcome_reads':0,'geometry_reads':0,'time_reads':0,'fusion_calls':0,
        'labels_worker_fold_rows':len(crosswalk),'changed_worker_folds':int(crosswalk.label_changed.sum()),
        'changed_lobo_worker_folds':int(crosswalk[(crosswalk.heldout_building!='ALL')].label_changed.sum()),
        'legacy_target_events':len(audit),'legacy_target_design_links':len(link_audit),'legacy_target_unique_teams':len(team_frame),
        'legacy_current_ac_legal_events':len(legal),'legacy_current_ac_legal_unique_physical_pairs':legal.canonical_physical_pair_id.nunique(),
        'legacy_current_ac_legal_unique_teams':len(set(legal.A_team_key)|set(legal.C_team_key)),
        'legacy_current_ac_legal_images':legal.image.nunique(),'legacy_current_ac_legal_buildings':legal.building.nunique(),
        'legacy_legal_direction_changed_events':int(legal.current_direction_changed.sum()),
        'legacy_current_ac_mixed_D_events':int(legal.current_D_is_mixed.sum()),
        'legacy_current_ac_unknown_D_events':int((legal.D_current_unknown>0).sum()),
        'legacy_structural_identity_failures':int((~audit.structural_identity_valid).sum()),
        'legacy_original_label_metadata_failures':int((~audit.original_label_metadata_valid).sum()),
        'batch12_original_ABC_events':len(b12_events),'batch12_AC_BC_leg_aliases':len(b12_audit),
        'batch12_legal_leg_aliases':int(b12_audit.current_ac_legal.sum()),
        'batch12_unique_physical_direct_pairs':b12_audit[b12_audit.current_ac_legal].canonical_physical_pair_id.nunique(),
        'reused_total_aliases':len(reused),'reused_unique_physical_pairs':len(pair_frame),
        'ordinary_manual_capacity_pools':len(pool_frame),'ordinary_manual_primary_pools':int((pool_frame.scope=='primary').sum()),
        'ordinary_manual_other_pools':int((pool_frame.scope=='other_admitted').sum()),
        'prior_delivery_pool_identity_comparisons':len(pool_compat),
        'core_missing_budget_cells':len(missing),'core_missing_pool_pairs':len(missing[['pool_id','current_class_pair']].drop_duplicates()),
        'core_missing_images':missing.image.nunique(),
        'elapsed_seconds':time.monotonic()-started,
        'stock_interpretation':'Conditional analysis of old selected teams under current labels; no claim of a new uniform current-label sample.',
        'reverse_interpretation':'Six directed displays share three physical pair contrasts; swapping A/C negates the signed difference, without new evidence.',
    }
    (HERE/'REGISTRY_VALIDATION.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    schema=pd.DataFrame([{'file':'LEGACY_TARGET_EVENTS_AUDIT.csv.gz','column':c,'dtype':str(audit[c].dtype)} for c in audit.columns])
    write_csv(schema,registry/'REGISTRY_SCHEMA.csv')
    print(json.dumps(stats,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
