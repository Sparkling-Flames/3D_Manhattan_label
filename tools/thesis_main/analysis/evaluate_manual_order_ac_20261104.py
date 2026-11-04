"""Patch the actual AC dependency closure using saved endpoints and frozen code.

No fusion, score calculation, class fitting, team selection or reference editing.
Original event and summary files are read-only.  Endpoint geometry and scalar
overlays are taken from the separately audited fixed-node assisted delivery.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
AC = ROOT / 'research/workers/personnel_ac_v21_20261030'
RESULT = ROOT / 'research/fusion/manual_order_impact_20261104'
OUT = RESULT / 'ac'
VERSION = 'v21_targeted_manual_order_assisted_20261104_v1'
TOLERANCE = 1e-7


def read_json(path):
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if str(path).endswith('.gz')
          else open(path, encoding='utf-8-sig')) as f:
        return json.load(f)


def iter_jsonl(path):
    with gzip.open(path, 'rt', encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Complete bytes first, then atomically replace; readers never see a
    # partially written gzip while later analysis phases start.
    payload=df.to_csv(index=False).encode('utf-8-sig')
    if str(path).endswith('.gz'):payload=gzip.compress(payload,mtime=0)
    temporary=path.with_name(path.name+'.writing')
    with temporary.open('wb') as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def jsave(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2,
                               allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modules():
    for path in (AC/'stage02_engine/code', AC/'code',
                 ROOT/'research/workers/personnel_v21_reselection_20261029/analysis'):
        sys.path.insert(0, str(path))
    import ac_measure_events as measure
    import summarize_ac_effects as summary
    from measure_registered_events import METRICS
    from legacy_geometry_diagnostics import geometry_metrics, refdiagnostic
    return measure, summary, METRICS, refdiagnostic, geometry_metrics


def normalized_text(s):
    return s.fillna('').astype(str).replace({'True':'true', 'False':'false',
                                            'nan':'', 'None':''})


def align(frame, keys):
    frame = frame.copy()
    for key in keys:
        # Frozen group identities are strings; retain blank NA identities.
        frame[key] = normalized_text(frame[key])
        if key in {'n','m','n_from','n_to','m_from','m_to','member_rep','n_condition','m_condition'}:
            frame[key]=frame[key].map(lambda x:format(float(x),'.12g') if x and x.replace('.','',1).isdigit() else x)
    assert not frame.duplicated(keys).any(), ('duplicate_identity', keys)
    return frame.set_index(keys).sort_index()


def compare(old, new, keys, context, require_same_fields=True):
    """Return every field's parity evidence; fail on any substantive difference."""
    a, b = align(old, keys), align(new, keys)
    assert a.index.equals(b.index), (context, 'identity_set', len(a), len(b))
    if require_same_fields:
        assert set(a)==set(b), (context, 'field_set', sorted(set(a)-set(b)), sorted(set(b)-set(a)))
    rows = []
    for field in sorted(set(a)&set(b)):
        x, y = a[field], b[field]
        missing = x.isna() ^ y.isna()
        nx, ny = pd.to_numeric(x, errors='coerce'), pd.to_numeric(y, errors='coerce')
        is_numeric = ((x.isna()|nx.notna()).all() and (y.isna()|ny.notna()).all()
                      and not (pd.api.types.is_bool_dtype(x) or pd.api.types.is_bool_dtype(y)))
        if is_numeric:
            diff = (nx-ny).abs()
            mismatch = missing | (diff>TOLERANCE)
            maximum = diff.max() if diff.notna().any() else 0.0
        else:
            # Readable CSV omits empty strings, which is the same missing value.
            mismatch = normalized_text(x).ne(normalized_text(y))
            maximum = None
        rows.append(dict(context=context, field=field, rows=len(x),
                         missing_disagreements=int(missing.sum()),
                         mismatches=int(mismatch.sum()), maximum_absolute_difference=maximum))
        if mismatch.any():
            samples = pd.DataFrame({'saved':x[mismatch], 'recomputed':y[mismatch]}).head(8)
            raise AssertionError((context, field, samples.to_dict('index')))
    return rows


def role_direction(d):
    d = d.copy()
    for field in ('source_role_rank', 'target_role_rank'):
        d[field] = pd.to_numeric(d[field], errors='coerce')
    d['role_direction'] = [f'{int(a)}->{int(b)}' if pd.notna(a) and pd.notna(b)
        else f'{x}->{y}' for a,b,x,y in zip(d.source_role_rank, d.target_role_rank,
                                          d.source_class, d.target_class)]
    return d


def pool_table(d, links, summary):
    links = links.reindex(columns=summary.LINK_COLS)
    selected = summary.views(role_direction(d), links)
    if selected.empty:
        return selected
    metrics = [c for c in summary.DELTA_METRICS+summary.ARM_METRICS if c in selected]
    return summary.stat_rows(selected, metrics)


def read_selected_events(ids):
    frames = []
    for path in [AC/'stage01_registered/AC_EVENTS.csv.gz', AC/'stage01b_semi/AC_EVENTS.csv.gz']:
        for chunk in pd.read_csv(path, chunksize=30000, low_memory=False):
            frames.append(chunk[chunk.event_id.isin(ids)])
    frame = pd.concat(frames, ignore_index=True)
    assert set(frame.event_id)==ids and frame.event_id.is_unique
    return frame


def load_native(pid, needed):
    rows, provenance = {}, []
    for path in sorted((AC/'stage03_endpoints/pools'/pid).glob('part_*.jsonl.gz')):
        matched = 0
        file_sha = None
        for row in iter_jsonl(path):
            key = row['team_key']
            if key in needed:
                assert key not in rows, (key, 'duplicate_native_endpoint')
                rows[key] = row
                if file_sha is None:file_sha=sha(path)
                provenance.append(dict(team_key=key, pool_id=pid,
                    source=path.relative_to(ROOT).as_posix(), source_sha256=file_sha))
                matched += 1
        if set(rows)==needed:
            break
    assert set(rows)==needed, (pid, 'missing_saved_endpoints', sorted(needed-set(rows)))
    return rows, provenance


def overlay(old, assisted, metrics, raw_status):
    for field in ('team_key','pool_id','reference_id','reference_version','k','nodes'):
        assert old[field]==assisted[field], (field,old[field],assisted[field])
    def workers(v):
        return sorted(v if isinstance(v,list) else v.split('|'))
    assert workers(old['member_workers'])==workers(assisted['member_workers'])
    assert workers(old['member_object_ids'])==workers(assisted['member_object_ids'])
    result = deepcopy(old)
    fixed_metadata = {'source_time_total_seconds','recorded_time_total_seconds',
        'minimum_support','identity_groups_n','unselected_groups_n','half_vote_nodes',
        'selected_support_min','target_individual_B8L2_mean','target_individual_B8L2_min',
        'record_time_by_kind_json','endpoint_acquisition','semantic_identity'}
    for field in set(metrics+raw_status+['geometry'])-fixed_metadata:
        if field in assisted:
            result[field] = deepcopy(assisted[field])
    result['manual_order_analysis_version'] = VERSION
    result['manual_order_review_id'] = assisted['review_id']
    return result


def metric_support(old, new, metrics):
    a,b=align(old,['event_id']),align(new,['event_id'])
    rows=[]
    for metric in metrics:
        if metric not in a or metric not in b:
            continue
        x=pd.to_numeric(a[metric],errors='coerce').astype(float)
        y=pd.to_numeric(b[metric],errors='coerce').astype(float)
        common=x.notna()&y.notna();gained=x.isna()&y.notna();lost=x.notna()&y.isna()
        diff=(y-x).where(common)
        rows.append(dict(metric=metric, affected_events=len(a), original_valid=int(x.notna().sum()),
            assisted_valid=int(y.notna().sum()), common_valid=int(common.sum()), newly_valid=int(gained.sum()),
            lost_valid=int(lost.sum()), changed_on_common=int((diff.abs()>TOLERANCE).sum()),
            original_mean_on_common=x[common].mean(), assisted_mean_on_common=y[common].mean(),
            maximum_absolute_change_on_common=diff.abs().max(), new_support_mean=y[gained].mean()))
    return pd.DataFrame(rows)


def run_events(out, measure, summary, metrics, refdiagnostic, geometry_metrics):
    aux = {r['team_key']:r for r in iter_jsonl(RESULT/'endpoints/ENDPOINTS.jsonl.gz')}
    links = pd.read_csv(AC/'stage01_registered/DESIGN_LINKS.csv.gz',
                        usecols=summary.LINK_COLS, low_memory=False)
    pools = {p['pool_id']:p for fn in [ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
        ROOT/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
        for p in read_json(fn)['images']}
    original_shards, affected_ids = {}, set()
    for path in sorted((AC/'stage04_metrics/metric_shards').glob('*.csv.gz')):
        d = pd.read_csv(path, low_memory=False)
        impacted = d.A_team_key.isin(aux)|d.C_team_key.isin(aux)
        if impacted.any():
            original_shards[path.name[:-7]] = d
            affected_ids.update(d.loc[impacted,'event_id'])
    expected = pd.read_csv(RESULT/'endpoints/ENDPOINT_REFERENCE_BINDINGS.csv')
    expected = expected[expected.module.eq('ac_registered')]
    assert affected_ids==set(expected.event_id) and len(affected_ids)==339
    events=read_selected_events(affected_ids)
    parity, provenance, old_pools, new_pools, before, after = [], [], [], [], [], []
    for pid, old_shard in original_shards.items():
        event=events[events.pool_id.eq(pid)].reset_index(drop=True)
        wanted=set(event.A_team_key)|set(event.C_team_key)
        old_rows, sources=load_native(pid,wanted);provenance.extend(sources)
        original=measure.compute(event,deepcopy(old_rows),pools[pid],metrics,refdiagnostic,geometry_metrics)
        saved=old_shard[old_shard.event_id.isin(event.event_id)]
        parity.extend(compare(saved,original,['event_id'],'saved_events:'+pid,require_same_fields=False))
        new_rows={key:overlay(row,aux[key],metrics,measure.RAW_STATUS) if key in aux else deepcopy(row)
                  for key,row in old_rows.items()}
        assisted=measure.compute(event,new_rows,pools[pid],metrics,refdiagnostic,geometry_metrics)
        # Patch only measured fields of affected rows; all frozen event metadata,
        # context assignments, old labels, and unimpacted rows remain untouched.
        patched=old_shard.set_index('event_id').copy()
        overlay_fields=[c for c in assisted if c in patched and c not in events.columns]
        patched.loc[assisted.event_id,overlay_fields]=assisted.set_index('event_id')[overlay_fields]
        patched=patched.reset_index()[old_shard.columns]
        unchanged=~old_shard.event_id.isin(event.event_id)
        parity.extend(compare(old_shard[unchanged],patched[unchanged],['event_id'],'untouched_events:'+pid))
        save(patched,out/'metric_shards'/(pid+'.csv.gz'))
        before.append(saved);after.append(patched[patched.event_id.isin(event.event_id)])
        own_links=links[links.pool_id.eq(pid)]
        old_pools.append(pool_table(old_shard,own_links,summary))
        new_pools.append(pool_table(patched,own_links,summary))
        save(pd.DataFrame(parity),out/'EVENT_AND_UNTOUCHED_PARITY.csv')
        save(pd.DataFrame(provenance),out/'SAVED_ENDPOINT_PROVENANCE.csv')
        save(pd.concat(old_pools,ignore_index=True),out/'AFFECTED_POOLS_AUTOMATIC.csv.gz')
        save(pd.concat(new_pools,ignore_index=True),out/'AFFECTED_POOLS_ASSISTED.csv.gz')
        print(json.dumps({'phase':'AC event patch','pool_id':pid,'affected_events':len(event),
                          'saved_endpoints':len(old_rows),'old_valid_Q':int(saved.AC_scored.sum()),
                          'new_valid_Q':int(assisted.AC_scored.sum())}),flush=True)
    before,after=pd.concat(before,ignore_index=True),pd.concat(after,ignore_index=True)
    save(before,out/'AFFECTED_EVENT_METRICS_AUTOMATIC.csv.gz')
    save(after,out/'AFFECTED_EVENT_METRICS_ASSISTED.csv.gz')
    save(metric_support(before,after,summary.DELTA_METRICS+summary.ARM_METRICS),
         out/'AFFECTED_EVENT_SUPPORT_BY_METRIC.csv')
    save(pd.DataFrame(provenance),out/'SAVED_ENDPOINT_PROVENANCE.csv')
    save(pd.DataFrame(parity),out/'EVENT_AND_UNTOUCHED_PARITY.csv')
    old_pool,new_pool=pd.concat(old_pools,ignore_index=True),pd.concat(new_pools,ignore_index=True)
    save(old_pool,out/'AFFECTED_POOLS_AUTOMATIC.csv.gz')
    save(new_pool,out/'AFFECTED_POOLS_ASSISTED.csv.gz')
    return old_pool,new_pool,sorted(original_shards),before,after


def run_main(out, summary, old_local, new_local):
    source=AC/'stage05_main'
    old=pd.read_csv(source/'POOL_CONDITION_EFFECTS.csv.gz',low_memory=False,
                    dtype={k:str for k in summary.GROUP})
    for d in (old_local,new_local):
        for c in summary.GROUP:d[c]=d[c].astype(str)
    keys=summary.GROUP+['pool_id','image','building']
    selected=old[old.pool_id.isin(set(old_local.pool_id))]
    parity=compare(selected,old_local,keys,'original_pool_aggregation')
    a,b=align(old_local,keys),align(new_local,keys)
    # Only groups with changed scalar/support values require reaggregation.
    numeric=list(old_local.select_dtypes(include=['number','bool']).columns)
    changed=((a[numeric].isna()^b[numeric].isna()) |
             ((a[numeric]-b[numeric]).abs()>TOLERANCE)).any(axis=1)
    changed_keys=a.index[changed]
    changed_local=new_local.set_index(keys).loc[changed_keys].reset_index()
    changed_groups=changed_local[summary.GROUP].drop_duplicates()
    save(changed_local,out/'CHANGED_POOL_CONDITIONS.csv.gz')
    target=old.merge(changed_groups,on=summary.GROUP,how='inner',validate='many_to_one')
    target_patched=target.set_index(keys).copy()
    target_patched.loc[changed_keys,:]=b.loc[changed_keys,target_patched.columns]
    target_patched=target_patched.reset_index()[target.columns]
    original_dir=out/'main_automatic_reproduced'
    assisted_dir=out/'main_assisted_affected_conditions'
    original_dir.mkdir(parents=True,exist_ok=True);assisted_dir.mkdir(parents=True,exist_ok=True)
    summary.aggregate(target,original_dir)
    summary.aggregate(target_patched,assisted_dir)
    for file,extra in [('IMAGE_CONDITION_EFFECTS.csv.gz',['image','building']),
                       ('BUILDING_CONDITION_EFFECTS.csv.gz',['building']),
                       ('CONDITION_METRIC_SUMMARY.csv.gz',['metric'])]:
        base=pd.read_csv(source/file,low_memory=False,dtype={k:str for k in summary.GROUP})
        selected=base.merge(changed_groups,on=summary.GROUP,how='inner',validate='many_to_one')
        recomputed=pd.read_csv(original_dir/file,low_memory=False,dtype={k:str for k in summary.GROUP})
        parity.extend(compare(selected,recomputed,summary.GROUP+extra,'original_'+file))
    save(pd.DataFrame(parity),out/'MAIN_AGGREGATION_PARITY.csv')
    old_summary=pd.read_csv(original_dir/'CONDITION_METRIC_SUMMARY.csv.gz',dtype={k:str for k in summary.GROUP})
    new_summary=pd.read_csv(assisted_dir/'CONDITION_METRIC_SUMMARY.csv.gz',dtype={k:str for k in summary.GROUP})
    k=summary.GROUP+['metric'];a,b=align(old_summary,k),align(new_summary,k)
    numeric=list(a.select_dtypes(include=['number','bool']).columns)
    changed=((a[numeric].isna()^b[numeric].isna())|((a[numeric]-b[numeric]).abs()>TOLERANCE)).any(axis=1)
    diff=a[changed].add_prefix('automatic_').join(b[changed].add_prefix('assisted_')).reset_index()
    for field in ['image_mean','image_balanced_mean_absolute','building_balanced_mean','valid_pairs','valid_pools','valid_images','valid_buildings']:
        diff[field+'_change']=diff['assisted_'+field]-diff['automatic_'+field]
    diff['effect_relation']=np.where(diff.valid_pairs_change.ne(0),'support_extension_or_change','change_on_original_metric_support')
    save(diff,out/'MAIN_SUMMARY_CHANGES.csv.gz')
    save(changed_groups,out/'MAIN_AFFECTED_GROUP_IDENTITIES.csv')
    return {'affected_pool_condition_rows':len(changed_keys),'affected_condition_groups':len(changed_groups),
            'changed_condition_metric_rows':len(diff),'original_pool_rows':len(old),
            'scope':'only changed condition groups reaggregated; untouched published rows remain authoritative'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--phase',choices=['events','main','all'],default='all')
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    measure,summary,metrics,refdiagnostic,geometry_metrics=modules()
    receipt={'analysis_version':VERSION,'source_repository_commit':'ac395e703d1fef573d1ef3e105df0286d62a0468',
        'new_fusions':0,'new_endpoint_scores':0,'new_class_fits':0,'reference_changes':0,
        'original_files_modified':False,'missing_Q_imputed':False}
    if args.phase in ('all','events'):
        old,new,pools,before,after=run_events(out,measure,summary,metrics,refdiagnostic,geometry_metrics)
        receipt.update(affected_events=len(before),affected_pools=len(pools),
            affected_endpoint_identities=11,saved_endpoint_identities=pd.read_csv(out/'SAVED_ENDPOINT_PROVENANCE.csv').team_key.nunique(),
            automatic_valid_Q_events=int(before.AC_scored.sum()),assisted_valid_Q_events=int(after.AC_scored.sum()))
    else:
        old=pd.read_csv(out/'AFFECTED_POOLS_AUTOMATIC.csv.gz',low_memory=False,dtype={k:str for k in summary.GROUP})
        new=pd.read_csv(out/'AFFECTED_POOLS_ASSISTED.csv.gz',low_memory=False,dtype={k:str for k in summary.GROUP})
        path=out/'AC_IMPACT_RECEIPT.json'
        if path.exists():receipt.update(read_json(path))
    if args.phase in ('all','main'):
        receipt['main_aggregation']=run_main(out,summary,old,new)
    jsave(out/'AC_IMPACT_RECEIPT.json',receipt)
    print(json.dumps(clean(receipt),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
