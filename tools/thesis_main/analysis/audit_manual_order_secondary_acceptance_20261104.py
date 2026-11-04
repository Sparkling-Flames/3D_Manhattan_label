"""Independent acceptance of existing same-room/composition/alliance/N/policy results.

This auditor does not invoke the previous manual-order producer, score geometry,
select teams, or fit classifications. It reconstructs the relevant arithmetic
from frozen rows and verifies every adopted replacement against saved consumers.
The audit writes only the new acceptance directory. The explicitly requested
--apply-format-repair action also fixes two existing composition CSV files and
their writer, without altering scientific values or the immutable prior ZIPs.
"""
from __future__ import annotations

import argparse
import ast
import csv
import difflib
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/fusion/manual_order_impact_20261104'
OUT = ROOT / 'research/fusion/manual_order_acceptance_20261104/secondary'
SRC = OUT / 'source'
COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
CHECKS: list[dict] = []
INPUTS: dict[str, dict] = {}
CONSUMERS: list[dict] = []
CONCLUSIONS: list[dict] = []
ATOL = 1e-8


def register(path):
    p = Path(path)
    key = str(p.relative_to(ROOT))
    if key not in INPUTS:
        INPUTS[key] = dict(path=key, bytes=p.stat().st_size,
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    return p


def read(path, **kwargs):
    # Re-read the producer's decimal CSV representation without changing the
    # binary floating-point value. Default parser rounding can break near ties
    # when a derived mean is ranked, despite unchanged substantive quantities.
    return pd.read_csv(register(path), low_memory=False, float_precision='round_trip', **kwargs)


def text(path):
    return register(path).read_text(encoding='utf-8-sig')


def write(frame, name):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    data = frame.to_csv(index=False).encode('utf-8-sig')
    p.write_bytes(gzip.compress(data, mtime=0) if p.suffix == '.gz' else data)


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer, np.bool_)):
        return obj.item()
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    return obj


def flag(module, check, passed, **details):
    CHECKS.append(dict(module=module, check=check, passed=bool(passed), **clean(details)))
    return bool(passed)


def numeric(module, check, actual, expected, atol=ATOL):
    a = np.asarray(pd.to_numeric(pd.Series(actual), errors='coerce'), dtype=float)
    e = np.asarray(pd.to_numeric(pd.Series(expected), errors='coerce'), dtype=float)
    if a.shape != e.shape:
        return flag(module, check, False, actual_shape=a.shape, expected_shape=e.shape)
    finite = np.isfinite(a) & np.isfinite(e)
    missing = int(np.sum(np.isfinite(a) != np.isfinite(e)))
    err = float(np.max(np.abs(a[finite] - e[finite]))) if finite.any() else 0.0
    passed = not missing and bool(np.allclose(a, e, rtol=1e-10, atol=atol, equal_nan=True))
    flag(module, check, passed, rows=len(a), missing_disagreements=missing,
         maximum_absolute_error=err, absolute_tolerance=atol)
    return passed


def equal_frame(module, check, actual, expected, keys, columns=None):
    a, e = actual.copy(), expected.copy()
    if a.duplicated(keys).any() or e.duplicated(keys).any():
        return flag(module, check, False, reason='duplicate comparison identities', keys=keys)
    a, e = a.set_index(keys).sort_index(), e.set_index(keys).sort_index()
    if not a.index.equals(e.index):
        return flag(module, check, False, reason='row identities differ',
                    actual_rows=len(a), expected_rows=len(e),
                    actual_only=len(a.index.difference(e.index)), expected_only=len(e.index.difference(a.index)))
    fields = columns or [c for c in e if c in a]
    bad, missing, maximum = [], 0, 0.0
    for c in fields:
        if pd.api.types.is_numeric_dtype(a[c]) or pd.api.types.is_numeric_dtype(e[c]):
            x, y = pd.to_numeric(a[c], errors='coerce').to_numpy(float), pd.to_numeric(e[c], errors='coerce').to_numpy(float)
            finite = np.isfinite(x) & np.isfinite(y)
            missing += int(np.sum(np.isfinite(x) != np.isfinite(y)))
            maximum = max(maximum, float(np.max(np.abs(x[finite]-y[finite]))) if finite.any() else 0.0)
            same = np.allclose(x, y, rtol=1e-10, atol=ATOL, equal_nan=True)
        else:
            same = a[c].fillna('').astype(str).equals(e[c].fillna('').astype(str))
        if not same:
            bad.append(c)
    return flag(module, check, not bad, rows=len(a), columns=len(fields),
                failed_fields='|'.join(bad), missing_disagreements=missing,
                maximum_absolute_error=maximum)


def truth(series):
    return series.fillna(False).astype(str).str.lower().isin(['true', '1', '1.0'])


def consumer(module, name, scope, result, evidence):
    CONSUMERS.append(dict(module=module, consumer=name, actual_scope=scope,
                          acceptance=result, evidence=evidence))


def conclusion(module, item, status, finding, evidence):
    CONCLUSIONS.append(dict(module=module, item=item, judgment=status, finding=finding, evidence=evidence))


def repair_composition_member_format():
    """Losslessly preserve the original pipe-list scalar contract, once.

    CSV cells are read as text; no floating-point parse/reformat occurs. The
    exact old files and code are retained in repairs/pre_acceptance. Repeated
    calls verify the already-applied repair without changing it again.
    """
    repair=OUT/'repairs';prior=repair/'pre_acceptance';prior.mkdir(parents=True,exist_ok=True)
    receipt_path=repair/'MEMBER_FIELD_FORMAT_REPAIR.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        for row in receipt['files']:
            assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['after_sha256'],row['path']
        return receipt
    def cells(path):
        b=path.read_bytes();raw=gzip.decompress(b)
        f=io.StringIO(raw.decode('utf-8-sig'),newline='');reader=csv.DictReader(f)
        return b,raw,list(reader.fieldnames),list(reader)
    _,_,_,original_rows=cells(BASE/'composition/affected_inputs/automatic_ENDPOINT_SCALARS.csv.gz')
    original={r['team_key']:r for r in original_rows}
    edited=[];files=[]
    for version in ['assisted_original_support','assisted_expanded']:
        path=BASE/'composition/affected_inputs'/(version+'_ENDPOINT_SCALARS.csv.gz')
        before,raw,columns,rows=cells(path)
        previous=[r.copy() for r in rows]
        for r in rows:
            for field in ['member_workers','member_object_ids']:
                old=r[field];wanted=original[r['team_key']][field]
                if old==wanted:
                    continue
                got=ast.literal_eval(old) if old.startswith('[') else old.split('|')
                expected=wanted.split('|')
                assert got==expected,(version,r['team_key'],field,'member identity/order mismatch')
                edited.append(dict(path=str(path.relative_to(ROOT)),team_key=r['team_key'],field=field,
                                   before=old,after=wanted,member_content_and_order_unchanged=True))
                r[field]=wanted
        assert [r['team_key'] for r in rows]==[r['team_key'] for r in previous]
        assert all(a[c]==b[c] for a,b in zip(rows,previous) for c in columns if c not in ['member_workers','member_object_ids'])
        f=io.StringIO(newline='');writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
        payload=f.getvalue().encode('utf-8')
        if raw.startswith(b'\xef\xbb\xbf'):
            payload=b'\xef\xbb\xbf'+payload
        after=gzip.compress(payload,mtime=0)
        (prior/path.name).write_bytes(before)
        path.write_bytes(after)
        _,_,after_columns,after_rows=cells(path)
        assert columns==after_columns and rows==after_rows
        files.append(dict(path=str(path.relative_to(ROOT)),before_sha256=hashlib.sha256(before).hexdigest(),
            after_sha256=hashlib.sha256(after).hexdigest(),rows=len(rows),columns=len(columns),
            field_order_unchanged=True,row_identity_and_order_unchanged=True,
            all_nonmember_cells_exact_text_unchanged=True,
            exact_pre_acceptance_copy=str((prior/path.name).relative_to(ROOT))))
    code=ROOT/'tools/thesis_main/analysis/evaluate_manual_order_composition_20261104.py'
    before=code.read_bytes();s=before.decode('utf-8')
    needle="        changed = merge_endpoint(row, auxiliary[row['team_key']]) if row['team_key'] in auxiliary else row.copy()\n"
    assert s.count(needle)==1
    insertion=("        # Preserve the original scalar member-list encoding as well as membership.\n"
               "        # The generic endpoint JSON uses lists; this CSV contract uses pipes.\n"
               "        for field in ('member_workers', 'member_object_ids'):\n"
               "            changed[field] = row[field]\n")
    updated=s.replace(needle,needle+insertion);ast.parse(updated)
    (prior/code.name).write_bytes(before);code.write_text(updated,encoding='utf-8')
    diff=''.join(difflib.unified_diff(s.splitlines(True),updated.splitlines(True),fromfile='a/'+str(code.relative_to(ROOT)),tofile='b/'+str(code.relative_to(ROOT))))
    (repair/'COMPOSITION_WRITER_FORMAT_FIX.patch').write_text(diff,encoding='utf-8')
    files.append(dict(path=str(code.relative_to(ROOT)),before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(code.read_bytes()).hexdigest(),
        changed_behavior='Keep member_workers and member_object_ids in the exact original scalar encoding',
        exact_pre_acceptance_copy=str((prior/code.name).relative_to(ROOT))))
    assert len(edited)==8,len(edited)
    write(pd.DataFrame(edited),'repairs/MEMBER_FIELD_CELL_CHANGES.csv')
    write(pd.DataFrame(files),'repairs/OVERLAY_FILES.csv')
    receipt=dict(repair='composition_member_field_serialization_only',source_commit=COMMIT,
        edited_cells=len(edited),csv_files=2,writer_files=1,member_content_and_order_unchanged=True,
        all_scientific_and_other_nonmember_CSV_cells_exact_text_unchanged=True,
        existing_member_consumer='aggregate_frozen_panels.py reads TEAM_REQUESTS.csv.gz, not endpoint scalar member strings',
        new_teams=0,new_fusions=0,new_scores=0,classification_selection_runs=0,scientific_aggregation_runs=0,
        immutable_prior_ZIPs_modified=False,files=files)
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt


def same_room():
    module = 'same_room'
    path = BASE / module
    old = read(path/'AUTOMATIC_CURRENT_EVENTS.csv.gz')
    new = read(path/'ASSISTED_CURRENT_EVENTS.csv.gz')
    identity = ['event_id', 'method_updated', 'updated_direction', 'n', 'm']
    new = new.set_index(identity).loc[old.set_index(identity).index].reset_index()
    old = old.reset_index(drop=True)
    end = read(BASE/'endpoints/ENDPOINT_SCORES.csv').set_index('team_key')
    keys = [f'team_key_{r}_{s}' for s in 'ab' for r in 'ABC']
    touched = old[keys].isin(set(end.index)).any(axis=1)
    scalar = read(path/'RECOVERED_AUTOMATIC_ENDPOINT_SCALARS.csv.gz').set_index('team_key')
    scorecols = [f'Q_{r}_{s}' for s in 'ab' for r in 'ABC']
    oq = np.isfinite(old[scorecols].to_numpy(float)).all(axis=1)
    nq = np.isfinite(new[scorecols].to_numpy(float)).all(axis=1)
    flag(module, 'current_event_keys_and_rows', len(old)==len(new)==1621 and not old.duplicated(identity).any())
    numeric(module, 'six_endpoint_support_automatic', old.Q_common6, oq)
    numeric(module, 'six_endpoint_support_assisted', new.Q_common6, nq)
    flag(module, 'no_lost_Q6_support', not np.any(oq & ~nq), old_Q6=int(oq.sum()), new_Q6=int(nq.sum()))
    flag(module, 'affected_physical_events', touched.sum()==54 and old.loc[touched,keys].drop_duplicates().shape[0]==23,
         method_rows=int(touched.sum()), physical_events=old.loc[touched,keys].drop_duplicates().shape[0],
         unique_manual_endpoints=len(set(old.loc[touched,keys].to_numpy().ravel()) & set(end.index)))
    flag(module, 'explicit_method_identity_preserved_as_separate_version',
         old.analysis_method_identity.eq('original_automatic').all()
         and new.analysis_method_identity.eq('fixed_nodes_human_order_auxiliary').all())
    untouched_columns = [c for c in old if c not in ['manual_endpoint_touched','analysis_method_identity']]
    equal_frame(module, 'all_fields_unchanged_unhit_events', new.loc[~touched], old.loc[~touched], identity, [c for c in untouched_columns if c not in identity])
    equal_frame(module, 'original_Q6_events_unchanged', new.loc[oq], old.loc[oq], identity, [c for c in untouched_columns if c not in identity])
    nohit = old.n.isin([12,14])
    flag(module, '12_6_and_14_7_have_no_direct_hit', not touched[nohit].any(), rows=int(nohit.sum()))
    equal_frame(module, '12_6_and_14_7_all_fields_unchanged', new.loc[nohit], old.loc[nohit], identity,
                [c for c in untouched_columns if c not in identity])

    # Independent reconstruction from saved scalar endpoints on every touched
    # event. No producer import or reuse of its transformation function.
    metric_fields = [c[:-8] for c in old if c.endswith('_common6') and c not in ['Q_common6','QT_common6','time_common6']]
    metric_fields = [m for m in metric_fields if m in scalar and m in end or m=='recorded_time_total_seconds']
    t = old.loc[touched].copy()
    updated = scalar.copy()
    mutable = [m for m in metric_fields if m not in ['recorded_time_total_seconds', 'nodes', 'identity_groups_n', 'minimum_support']]
    for key in set(t[keys].to_numpy().ravel()) & set(end.index):
        for f in ['reference_id','reference_version','pool_id']:
            flag(module, f'endpoint_identity/{key}/{f}', str(scalar.loc[key,f]) == str(end.loc[key,f]))
        for m in mutable:
            updated.loc[key,m] = end.loc[key,m]
    for version, frame, endpoint in [('automatic',old,scalar),('assisted',new,updated)]:
        for metric in metric_fields:
            arrays = {side: np.column_stack([pd.to_numeric(endpoint.loc[t[f'team_key_{r}_{side}'],metric],errors='coerce').to_numpy(float) for r in 'ABC']) for side in 'ab'}
            six = np.isfinite(np.column_stack(list(arrays.values()))).all(axis=1)
            if metric+'_common6' in frame:
                numeric(module, f'{version}/{metric}/six_support', frame.loc[touched,metric+'_common6'].to_numpy(),six)
            for side, matrix in arrays.items():
                a,b,c = matrix.T
                values = {'GA':abs(c-a)-abs(b-a), 'GS':(abs(c-a)+abs(c-b))/2-abs(b-a), 'CB':c-b,
                          'within':abs(b-a), 'cross':(abs(c-a)+abs(c-b))/2}
                for kind,value in values.items():
                    column = metric+'_'+kind+'_'+side
                    if column in frame:
                        numeric(module, f'{version}/{metric}/{kind}/{side}',frame.loc[touched,column].to_numpy(),np.where(six,value,np.nan))

    group = ['method_updated','n','m','updated_direction']
    pair_keys = group+['building','pair_key']
    summaries = read(path/'QUALITY_COMPONENT_REPETITION_SUMMARY.csv')
    support = read(path/'SUPPORT_CHANGES.csv')
    support_rows, stats_rows = [], []
    for vals,g in old.groupby(group,dropna=False):
        ids = g.index
        meta=dict(zip(group,vals))
        row=meta|dict(events=len(g),physical_events=g[keys].drop_duplicates().shape[0],
                      old_Q6=int(oq[ids].sum()),new_Q6=int(nq[ids].sum()),newly_Q6=int((nq[ids]&~oq[ids]).sum()),
                      old_pairs=g.loc[oq[ids],'pair_key'].nunique(),new_pairs=g.loc[nq[ids],'pair_key'].nunique(),
                      touched_method_rows=int(touched[ids].sum()),touched_pairs=g.loc[touched[ids],'pair_key'].nunique(),
                      remaining_unscored=int((~nq[ids]).sum()))
        support_rows.append(row)
    sr=pd.DataFrame(support_rows)
    equal_frame(module, 'reported_current_support',sr.rename(columns={'old_Q6':'automatic_common6','new_Q6':'assisted_common6','newly_Q6':'newly_common6','touched_method_rows':'touched_events','remaining_unscored':'still_unscoreable_events'}),support,group,
                ['events','physical_events','automatic_common6','assisted_common6','newly_common6','touched_events','touched_pairs','still_unscoreable_events'])

    versions={'automatic_original':old,'assisted_original_event_support':new.loc[oq],
              'assisted_expanded_support':new,'newly_scoreable_events_only':new.loc[nq&~oq]}
    metrics=list(dict.fromkeys(summaries.metric))
    all_stats_columns=list(dict.fromkeys([(kind+'_'+side if metric=='B8L2' else metric+'_'+kind+'_'+side)
                            for metric in metrics for kind in ['GA','GS','CB'] for side in 'ab']))
    for version,frame in versions.items():
        blocks=frame.groupby(pair_keys+['block'],dropna=False)[all_stats_columns].mean()
        pair_means=blocks.groupby(level=pair_keys).mean().reset_index()
        for vals,pair in pair_means.groupby(group,dropna=False):
            for metric in metrics:
                for kind in ['GA','GS','CB']:
                    cols=[(kind+'_'+side if metric=='B8L2' else metric+'_'+kind+'_'+side) for side in 'ab']
                    p=pair.dropna(subset=cols);a,b=p[cols[0]],p[cols[1]];z=(a+b)/2
                    stats_rows.append(dict(zip(group,vals))|dict(version=version,metric=metric,contrast=kind,
                        valid_pairs=len(p),valid_buildings=p.building.nunique(),view_a_mean=a.mean(),view_b_mean=b.mean(),pair_mean=z.mean(),
                        positive_pairs=int(z.gt(0).sum()),negative_pairs=int(z.lt(0).sum()),both_positive_pairs=int((a.gt(0)&b.gt(0)).sum()),
                        both_negative_pairs=int((a.lt(0)&b.lt(0)).sum()),
                        pearson_r=a.corr(b) if len(p)>=3 and a.nunique()>1 and b.nunique()>1 else np.nan,
                        spearman_r=a.corr(b,method='spearman') if len(p)>=3 and a.nunique()>1 and b.nunique()>1 else np.nan))
    stats=pd.DataFrame(stats_rows)
    equal_frame(module,'all_current_component_hierarchies',stats,summaries,group+['version','metric','contrast'],
        ['valid_pairs','valid_buildings','view_a_mean','view_b_mean','pair_mean','positive_pairs','negative_pairs','both_positive_pairs','both_negative_pairs','pearson_r','spearman_r'])
    write(sr,'SAME_ROOM_Q6_SUPPORT.csv');write(stats,'SAME_ROOM_RECOMPUTED_METRIC_SUMMARIES.csv.gz')
    # Diagnose a real reader-level reproducibility issue without altering any
    # scientific value or its producer. Only the affected 25 rank cells are
    # retained; the main B8L2 results have none of these differences.
    default_old=pd.read_csv(path/'AUTOMATIC_CURRENT_EVENTS.csv.gz',low_memory=False)
    default_new=pd.read_csv(path/'ASSISTED_CURRENT_EVENTS.csv.gz',low_memory=False)
    dq=truth(default_old.Q_common6);dn=truth(default_new.Q_common6)
    default_versions={'automatic_original':default_old,'assisted_original_event_support':default_new.loc[dq],
                      'assisted_expanded_support':default_new,'newly_scoreable_events_only':default_new.loc[dn&~dq]}
    rank_rows=[]
    target=stats.set_index(group+['version','metric','contrast'])
    expected=summaries.set_index(group+['version','metric','contrast'])
    for version,frame in default_versions.items():
        pairs=frame.groupby(pair_keys+['block'],dropna=False)[all_stats_columns].mean().groupby(level=pair_keys).mean().reset_index()
        for vals,p in pairs.groupby(group,dropna=False):
            for metric in metrics:
                for kind in ['GA','GS','CB']:
                    cols=[kind+'_'+side if metric=='B8L2' else metric+'_'+kind+'_'+side for side in 'ab']
                    pp=p.dropna(subset=cols);a,b=pp[cols[0]],pp[cols[1]]
                    default_rank=a.corr(b,method='spearman') if len(pp)>=3 and a.nunique()>1 and b.nunique()>1 else np.nan
                    key=(*vals,version,metric,kind);wanted=expected.loc[key,'spearman_r']
                    if not np.isclose(default_rank,wanted,atol=1e-8,equal_nan=True):
                        rank_rows.append(dict(zip(group,vals))|dict(version=version,metric=metric,contrast=kind,
                            valid_pairs=len(pp),spearman_default_read=default_rank,spearman_stored=wanted,
                            spearman_lossless_read=target.loc[key,'spearman_r'],
                            pearson_default_read=a.corr(b),pearson_lossless_read=target.loc[key,'pearson_r'],
                            pair_mean_default_read=((a+b)/2).mean(),pair_mean_lossless_read=target.loc[key,'pair_mean'],
                            main_B8L2_claim_hit=metric=='B8L2',classification='saved_CSV_default_float_parser_rank_tie_artifact'))
    ranks=pd.DataFrame(rank_rows)
    write(ranks,'SAME_ROOM_CSV_PARSE_SENSITIVITY.csv')
    flag(module,'CSV_rank_reader_differences_resolved_without_producer_change',len(ranks)==25 and not ranks.main_B8L2_claim_hit.any()
         and np.allclose(ranks.spearman_lossless_read,ranks.spearman_stored,atol=1e-12),
         reader_sensitive_cells=len(ranks),main_B8L2_affected=int(ranks.main_B8L2_claim_hit.sum()))

    # Q, geometry and labor retain different, explicitly reconstructed masks.
    go=read(path/'geometry/CURRENT_AUTOMATIC_EVENTS.csv.gz');gn=read(path/'geometry/CURRENT_ASSISTED_EVENTS.csv.gz')
    geometry_support=read(path/'geometry/CURRENT_SUPPORT.csv')
    labor_fields=[c for c in old if c.startswith(('recorded_time_total_seconds_','time_ratio_','time_logratio_'))]
    equal_frame(module,'recorded_labor_values_and_missingness',new,old,identity,labor_fields+['time_common6'])
    numeric(module,'assisted_joint_QT6_mask',new.QT_common6,truth(new.Q_common6)&truth(new.time_common6))
    separate=[]
    for vals,g in old.groupby(group,dropna=False):
        ids=g.index;geo_o=truth(go.loc[ids,'geometry_all_unique6']);geo_n=truth(gn.loc[ids,'geometry_all_unique6'])
        separate.append(dict(zip(group,vals))|dict(events=len(g),old_Q6=int(oq[ids].sum()),new_Q6=int(nq[ids].sum()),
            old_geometry6=int(geo_o.sum()),new_geometry6=int(geo_n.sum()),
            old_time6=int(truth(old.loc[ids,'time_common6']).sum()),new_time6=int(truth(new.loc[ids,'time_common6']).sum()),
            old_QT6=int(truth(old.loc[ids,'QT_common6']).sum()),new_QT6=int(truth(new.loc[ids,'QT_common6']).sum())))
    separate=pd.DataFrame(separate)
    equal_frame(module,'geometry_common_support_counts',separate.rename(columns={'old_geometry6':'automatic_unique6','new_geometry6':'assisted_unique6'}),geometry_support,group,['events','automatic_unique6','assisted_unique6'])
    geomcols=[c for c in go if c.startswith('geometry_') and c not in ['geometry_all_unique6','geometry_any_high_angle_warning']]
    geomgood=truth(go.geometry_all_unique6)
    equal_frame(module,'original_six_geometry_event_values',gn.loc[geomgood],go.loc[geomgood],identity,geomcols)
    write(separate,'SAME_ROOM_SEPARATE_SUPPORTS.csv')

    # Frozen registered event layer is a separate design, not another current
    # 1621-row denominator. Recheck its genuine 31-event intervention directly.
    fo=read(path/'frozen_registered/AUTOMATIC_EVENTS.csv.gz');fn=read(path/'frozen_registered/ASSISTED_EVENTS.csv.gz')
    native=read(path/'frozen_registered/AUTOMATIC_FULL_REGISTERED_SOURCE_AFFECTED_STRATA.csv.gz')
    equal_frame(module,'frozen_source_preserved_baseline',fo,native,['event_id'],[c for c in native if c!='event_id'])
    fh=fo[keys].isin(set(end.index)).any(axis=1);fq=truth(fo.Q_common6);nqf=truth(fn.Q_common6)
    flag(module,'frozen_affected_events_and_strata',len(fo)==2646 and int(fh.sum())==31,
         loaded_stratum_events=len(fo),touched_events=int(fh.sum()),newly_Q6=int((~fq & nqf).sum()))
    equal_frame(module,'frozen_original_Q6_unchanged',fn.loc[fq],fo.loc[fq],['event_id'],[c for c in fo if c!='event_id'])
    equal_frame(module,'frozen_unhit_events_unchanged',fn.loc[~fh],fo.loc[~fh],['event_id'],[c for c in fo if c!='event_id'])
    changes=read(path/'frozen_registered/native_results/CHANGED_CONFIGURATION_SUPPORT.csv')
    flag(module,'native_summary_39_support_cells_and_70_rows_retained',len(changes)==39 and len(read(path/'frozen_registered/native_results/UPDATED_SUMMARY_ROWS.csv'))==70,
         configuration_support_cells=len(changes))
    # Recreate the full 744 pair aggregates from the adopted 8198 configurations.
    cfg=read(path/'frozen_registered/native_results/CONFIGURATION_METRICS.csv.gz')
    pair=read(path/'frozen_registered/native_results/PAIR_METRICS.csv.gz')
    pk=['subset','pair_key','building','groups','method','condition'];counts=['attempted_events','common6_Q_events','complete6_events','joint_QT_events']
    measures=[c for c in pair.select_dtypes(include=['number','bool']) if c not in counts+['configurations']]
    derived=cfg.groupby(pk,dropna=False)[measures].mean().join(cfg.groupby(pk,dropna=False)[counts].sum()).reset_index()
    derived['configurations']=cfg.groupby(pk,dropna=False).size().to_numpy()
    equal_frame(module,'native_configuration_to_pair_all_consumers',derived,pair,pk,measures+counts+['configurations'])
    flag(module,'native_registered_denominator_preserved',len(cfg)==8198 and len(pair)==744,
         configuration_rows=len(cfg),pair_stratum_rows=len(pair))
    consumer(module,'当前事件、分项、图对、劳动、几何','1621 方法行；54 命中行 / 23 物理事件','独立重派生通过','SAME_ROOM_RECOMPUTED_METRIC_SUMMARIES.csv.gz; SAME_ROOM_SEPARATE_SUPPORTS.csv')
    consumer(module,'旧注册事件与配置→图对','2646 受影响标签层事件；31 直接事件；8198 配置 / 744 配对分层','旧来源和未命中行相符；全部配置→图对重新核对','CHECKS.csv; ../manual_order_impact_20261104/same_room/frozen_registered/native_results')
    consumer(module,'旧注册成员、历史 Q、原生几何','保持冻结选择域；前批已完成实际消费者，未新增选择','消费者文件存在；本轮未重新选择成员或历史 Q 域','../manual_order_impact_20261104/same_room/frozen_registered/native_member_sensitivity; native_history_q; native_geometry_summary')
    conclusion(module,'当前 K3 10/5 C2→C3','幅度变化','六端 Q 共同支持 295→318/322；GA、GS、CB 方向保持；19 对 CB 均值仍全正。无需新选队。','SAME_ROOM_Q6_SUPPORT.csv; SAME_ROOM_RECOMPUTED_METRIC_SUMMARIES.csv.gz')
    conclusion(module,'几何、劳动与质量分母','条件变化','几何六比较支持 240→240；原劳动六端 226→226，Q×劳动 201→222。人工排序时间未知。','SAME_ROOM_SEPARATE_SUPPORTS.csv')


def composition():
    module='composition';path=BASE/module
    panels=read(path/'affected_inputs/PANELS_USED.csv')
    links=read(path/'affected_inputs/PANEL_TEAMS.csv.gz')
    members=read(path/'affected_inputs/TEAM_REQUESTS.csv.gz').set_index('team_key')
    labels=read(SRC/'composition_other_labels.csv.gz')
    conditions=read(SRC/'composition_other_conditions.csv').set_index('pool_id')
    allvar=read(path/'ALL_PANEL_VARIANCE.csv.gz')
    summary=read(path/'ALL_METHOD_COMPARISON.csv')
    variance=read(path/'AFFECTED_PANEL_VARIANCE.csv.gz')
    distributions=read(path/'AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz')
    config_counts=read(path/'AFFECTED_CONFIGURATION_COUNTS.csv.gz')
    methods=sorted(summary.method.unique())
    versions=['automatic','assisted_original_support','assisted_expanded']
    endpoints={v:read(path/'affected_inputs'/(v+'_ENDPOINT_SCALARS.csv.gz')).set_index('team_key') for v in versions}
    flag(module,'frozen_design_scope',len(panels)==2 and len(links)==len(members)==45 and len(methods)==11,
         panels=len(panels),teams=len(members),frozen_methods=len(methods))
    old,new=endpoints['automatic'],endpoints['assisted_expanded']
    newkeys=set(new.index[new.B8L2.notna() & old.B8L2.isna()])
    flag(module,'two_new_quality_endpoints_not_zero_improvements',len(newkeys)==2,
         newly_scorable=len(newkeys),original_Q_missing=bool(old.loc[list(newkeys),'B8L2'].isna().all()))
    fixed=['pool_id','image','image_id','building','condition','k','nodes','minimum_support','member_workers','member_object_ids','reference_id','reference_version']
    fixed += [c for c in old if 'time' in c]
    equal_frame(module,'fixed_design_reference_and_labor',new.reset_index(),old.reset_index(),['team_key'],[c for c in fixed if c in old and c in new])
    equal_frame(module,'all_nonintervened_endpoint_fields',new.loc[~new.index.isin(newkeys)].reset_index(),old.loc[~old.index.isin(newkeys)].reset_index(),['team_key'])

    labels=labels[labels.heldout_building.ne('ALL') & labels.method.isin(methods)].copy()
    duplicate=labels.groupby(['method','heldout_building','worker_id']).class_id.nunique()
    flag(module,'fixed_label_source_has_no_conflicts',duplicate.le(1).all())
    known=labels[truth(labels.known)&labels.class_id.notna()].drop_duplicates(['method','heldout_building','worker_id'],keep='last')
    maps={method:{(b,w):str(c) for b,w,c in d[['heldout_building','worker_id','class_id']].itertuples(index=False,name=None)} for method,d in known.groupby('method')}
    vector_rows=[]
    for panel in panels.itertuples(index=False):
        ll=links[links.panel_id.eq(panel.panel_id)]
        variable=str(panel.variable_workers).split('|')
        observed={tuple(sorted(str(x).split('|'))) for x in ll.selected_variable_workers}
        wanted=set(itertools.combinations(sorted(variable),int(panel.variable_choose)))
        flag(module,'finite_member_census/'+panel.pool_id,observed==wanted and len(wanted)==panel.expected_teams,
             observed_teams=len(observed),expected_teams=len(wanted))
        for method in methods:
            lm=maps[method];classes=sorted({c for (b,w),c in lm.items() if b==panel.building})
            for row in ll.itertuples(index=False):
                team=str(members.loc[row.team_key,'member_workers']).split('|')
                flag(module,'full_team_member_mapping/'+method+'/'+row.team_key,
                     set(team)==set(str(row.selected_variable_workers).split('|')) and len(team)==panel.n)
                ok=all((panel.building,w) in lm for w in team)
                shared=all((panel.building,w) in maps[mm] for mm in methods for w in team)
                counts='|'.join(f'{c}:{sum(lm.get((panel.building,w))==c for w in team)}' for c in classes) if ok else ''
                vector_rows.append(dict(panel_id=panel.panel_id,team_key=row.team_key,method=method,
                    heldout_building=panel.building,class_counts=counts,known=ok,shared_known=shared))
    vectors=pd.DataFrame(vector_rows)
    for method in methods:
        for version in versions:
            stored=read(path/'replay'/version/'by_method'/method/'TEAM_CLASS_VECTORS.csv.gz')
            equal_frame(module,'full_class_vectors/'+method+'/'+version,vectors[vectors.method.eq(method)],stored,['panel_id','team_key','method'])

    # Generate expected supports from the fixed design and label vectors, then
    # evaluate population variance and within-composition distributions.
    source_ast=ast.parse(text(SRC/'aggregate_frozen_panels.py'))
    declarations={n.targets[0].id:ast.literal_eval(n.value) for n in source_ast.body
                  if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
                  and n.targets[0].id in ['METRICS','TIME_METRICS']}
    time_metrics=declarations['TIME_METRICS']
    for version,end in endpoints.items():
        end['failure']=(~truth(end.complete_evaluable)).astype(float)
        if 'recorded_time_total_seconds' in end:
            time=pd.to_numeric(end.recorded_time_total_seconds,errors='coerce')
            ok=truth(end.recorded_time_eligible) if 'recorded_time_eligible' in end else time.gt(0)
            end['recorded_time_total_seconds']=time.where(ok & time.gt(0))
            end['log_recorded_time']=np.log(end.recorded_time_total_seconds)
    metrics=[m for m in declarations['METRICS'] if m in endpoints['automatic']]
    recomputed,distrows=[] ,[]
    for version,end in endpoints.items():
        for (panel_id,method),vv in vectors.groupby(['panel_id','method']):
            for support,flagfield in [('method_known','known'),('shared_known','shared_known')]:
                vv0=vv[vv[flagfield]].set_index('team_key')
                e=end.loc[vv0.index]
                grouping=vv0.class_counts
                timegroups=[('not_time',[m for m in metrics if m not in time_metrics],pd.Series(True,index=e.index))]
                kinds=e.time_source_kinds.fillna('unknown') if 'time_source_kinds' in e else pd.Series('source_unspecified',index=e.index)
                timegroups += [(kind,[m for m in metrics if m in time_metrics],kinds.eq(kind)) for kind in sorted(kinds.unique()) if kind and '|' not in str(kind)]
                for time_source,fields,which in timegroups:
                    for metric in fields:
                        y=pd.to_numeric(e.loc[which,metric],errors='coerce').astype(float).replace([np.inf,-np.inf],np.nan)
                        q=pd.DataFrame({'value':y,'class_counts':grouping.loc[y.index]})
                        valid=q.dropna(subset=['value'])
                        if len(valid):
                            fitted=valid.groupby('class_counts').value.transform('mean')
                            mean=valid.value.mean()
                            total=float(np.mean((valid.value-mean)**2));within=float(np.mean((valid.value-fitted)**2));between=float(np.mean((fitted-mean)**2))
                            conf=valid.groupby('class_counts').size()
                        else:
                            total=within=between=np.nan;conf=pd.Series(dtype=int)
                        meta=dict(panel_id=panel_id,method=method,support=support,version=version,metric=metric,time_source=time_source)
                        recomputed.append(meta|dict(valid_teams=len(valid),configurations=len(conf),singleton_configurations=int(conf.eq(1).sum()),
                            total_variance=total,within_variance=within,between_variance=between,between_share=between/total if total>1e-12 else np.nan))
                        for counts,g in q.groupby('class_counts'):
                            v=g.value.dropna().to_numpy();n=len(v)
                            pct=np.quantile(v,[0,.05,.25,.5,.75,.95,1]) if n else np.full(7,np.nan)
                            distrows.append(meta|dict(class_counts=counts,teams=len(g),valid_teams=n,missing_teams=len(g)-n,
                                mean=float(v.mean()) if n else np.nan,p05=pct[1],p25=pct[2],median=pct[3],p75=pct[4],p95=pct[5],minimum=pct[0],maximum=pct[6],
                                sd=float(np.std(v,ddof=0)) if n>1 else np.nan,iqr=pct[4]-pct[2] if n>1 else np.nan,
                                range=pct[6]-pct[0] if n>1 else np.nan,member_variation_estimable=n>1))
    vr=pd.DataFrame(recomputed);dr=pd.DataFrame(distrows)
    vk=['panel_id','method','support','metric','time_source','version']
    equal_frame(module,'all_affected_variance_decompositions',vr,variance,vk,[c for c in vr if c not in vk])
    equal_frame(module,'all_affected_configuration_distributions',dr,distributions,vk+['class_counts'],[c for c in dr if c not in vk+['class_counts']])
    single=dr[(dr.valid_teams<=1)]
    flag(module,'single_or_no_scorable_member_variation_unestimated',single[['sd','iqr','range']].isna().all().all(),distribution_cells=len(single))
    for p in panels.itertuples(index=False):
        x=variance[variance.panel_id.eq(p.panel_id)]
        for c in ['scope','difficulty','geometric_challenge','structural_condition']:
            source_field='official_difficulty' if c=='difficulty' else c
            expected=conditions.loc[p.pool_id,source_field]
            if c=='difficulty' and pd.isna(expected):
                expected='未分级'
            flag(module,'current_condition_binding/'+p.panel_id+'/'+c,x[c].astype(str).eq(str(expected)).all(),source_field=source_field)
        flag(module,'target_scope_not_primary/'+p.panel_id,x.scope.eq('other_admitted').all())

    # Full macro ratio is computed after panel -> pool -> image -> building
    # averaging, never by averaging each panel's percentage.
    fields=['total_variance','within_variance','between_variance']
    gcols=['method','condition','support','metric','time_source']
    macro_rows=[]
    for version,versionframe in allvar.groupby('version'):
        scopes=[('all','all',versionframe)]
        for c in ['scope','difficulty','n','source_domain','geometric_challenge']:
            scopes.extend((c,str(k),g) for k,g in versionframe.groupby(c,dropna=False))
        for axis,value,frame in scopes:
            valid=frame.dropna(subset=['total_variance'])
            pools=valid.groupby(gcols+['building','image','pool_id'],dropna=False)[fields].mean()
            images=pools.groupby(level=gcols+['building','image']).mean()
            buildings=images.groupby(level=gcols+['building']).mean()
            macro=buildings.groupby(level=gcols).mean()
            counts=valid.assign(constant=valid.total_variance.le(1e-12)).groupby(gcols,dropna=False).agg(
                panels=('panel_id','nunique'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),
                valid_team_links=('valid_teams','sum'),constant_panels=('constant','sum'))
            macro=macro.join(counts).reset_index()
            macro['between_share']=(macro.between_variance/macro.total_variance).where(macro.total_variance.gt(1e-12))
            macro['summary_axis']=axis;macro['summary_value']=value;macro['version']=version
            macro_rows.append(macro)
    macro=pd.concat(macro_rows,ignore_index=True)
    sk=gcols+['summary_axis','summary_value','version']
    equal_frame(module,'all_full_macro_hierarchies_and_counts',macro,summary,sk,[c for c in macro if c not in sk])
    avkey=['panel_id','method','support','metric','time_source']
    unaffected=~allvar.panel_id.isin(panels.panel_id)
    a=allvar[unaffected & allvar.version.eq('automatic')].drop(columns='version')
    b=allvar[unaffected & allvar.version.eq('assisted_expanded')].drop(columns='version')
    equal_frame(module,'unaffected_65_panels_preserved',b,a,avkey)
    formations={'failure','connection_available','order_tied','below_four','location_unresolved'}
    a=allvar[allvar.version.eq('automatic') & ~allvar.metric.isin(formations)].drop(columns='version')
    b=allvar[allvar.version.eq('assisted_original_support') & ~allvar.metric.isin(formations)].drop(columns='version')
    equal_frame(module,'all_original_common_metric_support_preserved',b,a,avkey)
    k3=dr[(dr.method=='TARGET_DSTRUCT_K3')&(dr.metric=='B8L2')&(dr.version=='assisted_expanded')]
    newconfig=vectors[(vectors.method=='TARGET_DSTRUCT_K3')&vectors.team_key.isin(newkeys)]
    newconfig=k3.merge(newconfig[['panel_id','class_counts','team_key']].drop_duplicates(),on=['panel_id','class_counts'])
    write(newconfig,'COMPOSITION_NEW_CONFIGURATIONS.csv')
    write(macro[(macro.method=='TARGET_DSTRUCT_K3')&(macro.metric=='B8L2')],'COMPOSITION_K3_MACRO_ACCEPTANCE.csv')
    write(vr[(vr.method=='TARGET_DSTRUCT_K3')&(vr.metric=='B8L2')],'COMPOSITION_K3_PANEL_ACCEPTANCE.csv')
    write(vectors[vectors.team_key.isin(newkeys)],'COMPOSITION_NEW_TEAM_LABEL_BINDINGS.csv')
    consumer(module,'有限面板、配置分布、配置方差与原完整宏统计','2 面板 / 45 原团队；11 固定标签；2 新可评端点','从固定标签和成员全集重派生所有受影响分项，并独立重算全部宏统计','COMPOSITION_NEW_CONFIGURATIONS.csv; COMPOSITION_K3_MACRO_ACCEPTANCE.csv; CHECKS.csv')
    conclusion(module,'有限配比与成员波动','幅度变化','两个其它目标面板的既有团队/参考/固定标签与主目标分开；K3 配比间宏占比 32.439565%→32.534050%，原共同支持不变。','COMPOSITION_K3_MACRO_ACCEPTANCE.csv')
    conclusion(module,'新增单队配比的成员稳定性','尚不能判断','rPc6-06 的 C1:2|C2:2|C3:0 与 uNb9-88 的 C1:0|C2:3|C3:0 均仅一可评队；SD/IQR/范围保持缺失。','COMPOSITION_NEW_CONFIGURATIONS.csv')


def alliance_rank(rows):
    results=[]
    for values,g in rows.groupby(['version','pool_id','unknown_background_included']):
        candidates=g[g.classes.isin(['C1','C2','C3']) & g.n.ge(3) & g.B8L2.notna()]
        full=g.iloc[np.argmax(g.n.to_numpy())]
        if pd.isna(full.B8L2) or not len(candidates):
            continue
        best=candidates.iloc[np.argmax(candidates.B8L2.to_numpy())]
        results.append(dict(zip(['version','pool_id','unknown_background_included'],values))|
            dict(image=full.image,building=full.building,scope=full.scope,condition=full.condition,
                 full_Q=full.B8L2,best_pure_Q=best.B8L2,full_minus_best_pure=full.B8L2-best.B8L2,
                 scoreable_pure_classes=len(candidates),full_team_key=full.team_key,best_pure_team_key=best.team_key))
    return pd.DataFrame(results)


def alliance_summary(ranks):
    # The original estimand is explicitly shared across frozen/updated label
    # snapshots. A scored pool in just one snapshot does not enter this table.
    poolkey=['pool_id','unknown_background_included']
    common=ranks.groupby(poolkey).version.nunique()
    shared=set(common.index[common.eq(2)])
    eligible=ranks[[tuple(x) in shared for x in ranks[poolkey].itertuples(index=False,name=None)]]
    out=[]
    for vals,g in eligible.groupby(['scope','condition','unknown_background_included','version']):
        image=g.groupby('image').full_minus_best_pure.mean()
        out.append(dict(zip(['scope','condition','unknown_background_included','version'],vals))|
                   dict(pools=len(g),images=len(image),mean_full_minus_best_pure=image.mean(),
                        pure_better_images=int(image.lt(-1e-8).sum()),full_better_images=int(image.gt(1e-8).sum()),tied_images=int(image.abs().le(1e-8).sum())))
    return pd.DataFrame(out),eligible


def alliances():
    module='alliances';path=BASE/module
    old=read(SRC/'ALLIANCE_RESULTS.csv');new=read(path/'ALLIANCE_RESULTS_ASSISTED.csv.gz')
    end=read(BASE/'endpoints/ENDPOINT_SCORES.csv').set_index(['team_key','reference_id','reference_version'])
    keys=['version','pool_id','classes','unknown_background_included']
    new=new.set_index(keys).loc[old.set_index(keys).index].reset_index()
    old=old.reset_index(drop=True)
    hit=pd.Series([tuple(r) in end.index for r in old[['team_key','reference_id','reference_version']].itertuples(index=False,name=None)])
    metrics=['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges','boundary_loss','direction_loss','height_loss','omission','extension']
    fixed=[c for c in old if c not in metrics+['complete_evaluable','status']+keys]
    equal_frame(module,'all_3160_identities_labels_members_labor',new,old,keys,fixed)
    equal_frame(module,'all_unhit_rows_unchanged',new.loc[~hit],old.loc[~hit],keys)
    equal_frame(module,'all_original_scorable_rows_unchanged',new.loc[old.B8L2.notna()],old.loc[old.B8L2.notna()],keys)
    flag(module,'19_references_12_teams_17_new_Q',int(hit.sum())==19 and old.loc[hit,'team_key'].nunique()==12 and new.loc[hit,'B8L2'].notna().sum()==17,
         references=int(hit.sum()),teams=old.loc[hit,'team_key'].nunique(),new_Q=int(new.loc[hit,'B8L2'].notna().sum()))
    flag(module,'all_intervened_old_Q_missing',old.loc[hit,'B8L2'].isna().all())
    expected=end.loc[[tuple(x) for x in old.loc[hit,['team_key','reference_id','reference_version']].itertuples(index=False,name=None)]]
    for metric in metrics:
        numeric(module,'correct_endpoint_component/'+metric,new.loc[hit,metric].to_numpy(),expected[metric].to_numpy())
    results={}
    for v,frame in [('automatic',old),('manual_assisted',new)]:
        ranks=alliance_rank(frame);summary,common=alliance_summary(ranks)
        equal_frame(module,v+'/all_pool_rankings',ranks,read(path/(v.upper()+'_FULL_VS_BEST_PURE.csv')),['version','pool_id','unknown_background_included'])
        equal_frame(module,v+'/image_equal_summary',summary,read(path/(v.upper()+'_FULL_VS_BEST_PURE_SUMMARY.csv')),['scope','condition','unknown_background_included','version'])
        results[v]=(ranks,summary,common)
        class_rows=[]
        for vals,g in frame.groupby(['version','scope','condition','unknown_background_included','classes']):
            for metric in metrics+['source_time_total_seconds','recorded_time_total_seconds']:
                image=g.groupby('image')[metric].mean().dropna()
                class_rows.append(dict(zip(['version','scope','condition','unknown_background_included','classes'],vals))|
                    dict(metric=metric,registered_pools=len(g),eligible_pools=int(g.n.ge(3).sum()),valid_images=len(image),mean=image.mean()))
        equal_frame(module,v+'/all_class_metric_consumers',pd.DataFrame(class_rows),read(path/(v.upper()+'_CLASS_METRIC_SUMMARY.csv')),
                    ['version','scope','condition','unknown_background_included','classes','metric'])
    # Selection support expands inside old pools as well as adding a comparison
    # pool. Fixed original candidates give exactly the original statistics.
    orig=results['automatic'][2];expanded=results['manual_assisted'][2]
    pkeys=['version','pool_id','unknown_background_included']
    oldset=set(orig[pkeys].itertuples(index=False,name=None))
    within=expanded[[tuple(x) in oldset for x in expanded[pkeys].itertuples(index=False,name=None)]]
    decomposition=[]
    for version,frame in [('automatic_original_candidates_original_pools',orig),
                          ('assisted_original_candidates_original_pools',orig),
                          ('assisted_expanded_candidates_original_pools',within),
                          ('assisted_expanded_candidates_expanded_pools',expanded)]:
        for vals,g in frame.groupby(['scope','condition','unknown_background_included','version']):
            im=g.groupby('image').full_minus_best_pure.mean()
            decomposition.append(dict(zip(['scope','condition','unknown_background_included','label_snapshot'],vals))|
                dict(comparison_condition=version,pools=len(g),images=len(im),mean_full_minus_best_pure=im.mean(),
                     pure_better_images=int(im.lt(-1e-8).sum()),full_better_images=int(im.gt(1e-8).sum()),tied_images=int(im.abs().le(1e-8).sum())))
    joined=results['automatic'][0].merge(results['manual_assisted'][0],on=pkeys,how='outer',suffixes=('_old','_new'),indicator=True)
    changed=joined[(joined._merge!='both') | joined.best_pure_team_key_old.ne(joined.best_pure_team_key_new) | ~np.isclose(joined.full_minus_best_pure_old,joined.full_minus_best_pure_new,atol=1e-8,equal_nan=True)]
    flag(module,'new_pool_and_ranking_changes_are_other_targets',changed.scope_new.eq('other_admitted').all(),
         new_label_snapshot_pool_rows=int(joined._merge.eq('right_only').sum()),
         changed_best_pure_on_original_pools=int((joined._merge.eq('both')&joined.best_pure_team_key_old.ne(joined.best_pure_team_key_new)).sum()),
         lost_pools=int(joined._merge.eq('left_only').sum()))
    primary_old=results['automatic'][1].query("scope=='primary'")
    primary_new=results['manual_assisted'][1].query("scope=='primary'")
    equal_frame(module,'primary_target_comparison_preserved',primary_new,primary_old,['scope','condition','unknown_background_included','version'])
    resolution=read(path/'ALLIANCE_414_RESOLUTION_ASSISTED.csv')
    resolved=new[new.version.eq('updated') & ~truth(new.unknown_background_included)].set_index(['pool_id','classes'])
    got=resolved.loc[list(resolution[['pool_id','classes']].itertuples(index=False,name=None))]
    numeric(module,'414_resolution_current_scores',resolution.assisted_B8L2,got.B8L2.to_numpy())
    flag(module,'414_resolution_identity_and_capacity',len(resolution)==414 and resolution.team_key.fillna('').equals(resolution.assisted_team_key.fillna(''))
         and resolution.assisted_team_key.fillna('').tolist()==got.team_key.fillna('').tolist()
         and int(resolution.assisted_status.eq('capacity_only').sum())==11,
         resolved_rows=len(resolution),executable=int(resolution.assisted_status.ne('capacity_only').sum()),capacity_only=int(resolution.assisted_status.eq('capacity_only').sum()))
    write(pd.DataFrame(decomposition),'ALLIANCE_SUPPORT_DECOMPOSITION.csv')
    write(changed,'ALLIANCE_NEW_SUPPORT_AND_RANK_CHANGES.csv')
    write(pd.concat([s.assign(connection_version=k) for k,(_,s,_) in results.items()],ignore_index=True),'ALLIANCE_RECOMPUTED_SUMMARIES.csv')
    consumer(module,'纯类/联盟每类分项与池内最佳纯类','3160 行、12 命中物理团队 / 19 引用','从 GitHub 原表独立对比并重建全部池内排名和图等权摘要','ALLIANCE_SUPPORT_DECOMPOSITION.csv; ALLIANCE_NEW_SUPPORT_AND_RANK_CHANGES.csv')
    consumer(module,'414 行联盟落实表','403 可执行 / 11 容量记录','每一落实团队键、分数与 updated 且无未知背景的实际行一致','CHECKS.csv')
    conclusion(module,'主目标纯类与联盟','保持','主目标 205 图的 full−best-pure、类别选择和图片方向计数均不变；不能与其它目标混合。','ALLIANCE_RECOMPUTED_SUMMARIES.csv')
    conclusion(module,'其它目标纯类与联盟','条件变化','updated 均值 −0.077642→+0.049069；frozen +1.200119→−0.548008。新增池与同池候选集合扩展分别列示，原团队 Q 未改变。','ALLIANCE_SUPPORT_DECOMPOSITION.csv; ALLIANCE_NEW_SUPPORT_AND_RANK_CHANGES.csv')


def hierarchical_values(g,field,tolerance=None):
    valid=g[np.isfinite(pd.to_numeric(g[field],errors='coerce'))]
    image=valid.groupby(['image','building'],dropna=False)[field].mean().reset_index()
    building=image.groupby('building',dropna=False)[field].mean()
    x=image[field].to_numpy(float)
    out=dict(capacity_pools=g.pool_id.nunique(),capacity_images=g.image.nunique(),capacity_buildings=g.building.nunique(),
             valid_pools=valid.pool_id.nunique(),valid_images=len(image),valid_buildings=len(building),
             mean_pool_equal=valid[field].mean(),mean_image_equal=image[field].mean(),mean_building_equal=building.mean(),
             mean_absolute_image_value=np.mean(abs(x)) if len(x) else np.nan,
             image_p10=np.quantile(x,.1) if len(x) else np.nan,image_median=np.median(x) if len(x) else np.nan,image_p90=np.quantile(x,.9) if len(x) else np.nan,
             positive_images=int((x>1e-9).sum()),negative_images=int((x< -1e-9).sum()),zero_images=int((abs(x)<=1e-9).sum()))
    if tolerance is not None:
        out.update(tolerance=tolerance,greater_than_tolerance_images=int((x>tolerance+1e-9).sum()),
                   below_negative_tolerance_images=int((x< -tolerance-1e-9).sum()),within_tolerance_images=int((abs(x)<=tolerance+1e-9).sum()))
    if len(x) and np.abs(x).sum()>0:
        out.update(signed_change_cancellation_fraction=1-abs(x.mean())/np.abs(x).mean(),
                   top_decile_abs_change_share=np.sort(abs(x))[-max(1,int(math.ceil(.1*len(x)))):].sum()/np.abs(x).sum())
    else:
        out.update(signed_change_cancellation_fraction=np.nan,top_decile_abs_change_share=np.nan)
    return out


def changed_rows(old,new,keys,atol=1e-10):
    a=old.set_index(keys).sort_index();b=new.set_index(keys).reindex(a.index)
    mask=np.zeros(len(a),dtype=bool)
    for c in a.select_dtypes(include=['number','bool']):
        if c in b:
            mask |= ~np.isclose(pd.to_numeric(a[c]).to_numpy(float),pd.to_numeric(b[c]).to_numpy(float),rtol=0,atol=atol,equal_nan=True)
    return b.loc[mask].reset_index()


def natural():
    module='natural';path=BASE/module;source=SRC/'frozen_inputs/natural'
    pools=['rPc6DW4iMge-06__manual__other_space_10','uNb9QFRL6hY-88__manual__other_space_22']
    endpoint=read(BASE/'endpoints/ENDPOINT_SCORES.csv').set_index('team_key')
    actuals=[];pathcounts=[]
    for pid in pools:
        old=read(SRC/(pid+'.csv.gz'));new=read(path/'normalized_assisted'/(pid+'.csv.gz'))
        keys=['replicate_id','k'];new=new.set_index(keys).loc[old.set_index(keys).index].reset_index()
        manualkeys=set(old.team_key)&set(endpoint.index)
        hit=old.team_key.isin(manualkeys)
        equal_frame(module,'all_other_normalized_rows/'+pid,new.loc[~hit],old.loc[~hit],keys)
        fixed=['pool_id','image','building','condition','domain','target_id','reference_id','reference_version','N','replicate_id','origin_stratum','team_key','member_workers','member_object_ids','k']
        equal_frame(module,'path_team_reference_identity/'+pid,new,old,keys,[c for c in fixed if c not in keys])
        flag(module,'only_extra_target_scope/'+pid,old.domain.eq('ordinary_manual_extra_target').all() and int(hit.sum()) in [8,25]
             and len(manualkeys)==1,unique_teams=len(manualkeys),path_references=int(hit.sum()))
        oldgood=old.B8L2.notna()
        equal_frame(module,'original_scorable_path_values/'+pid,new.loc[oldgood],old.loc[oldgood],keys)
        for metric in ['B8L2','D10','IoU3D100']:
            numeric(module,'endpoint_scalar_reuse/'+pid+'/'+metric,new.loc[hit,metric].to_numpy(),endpoint.loc[old.loc[hit,'team_key'],metric].to_numpy())
        n=int(old.N.iloc[0]);k=int(old.loc[hit,'k'].iloc[0])
        pathcounts.append(dict(pool_id=pid,N=n,k=k,path_rows=len(old),replicates=old.replicate_id.nunique(),
                               affected_path_rows=int(hit.sum()),affected_unique_teams=len(manualkeys),target_domain=old.domain.iloc[0]))
        for label,frame,dirname in [('automatic',old,'automatic'),('manual_assisted',new,'manual_assisted')]:
            stored=read(path/dirname/'by_pool'/pid/'POOL_K_STATISTICS.csv.gz').set_index('k')
            for kk,g in frame.groupby('k'):
                for metric in ['B8L2','D10','IoU3D100']:
                    finite=g[metric].dropna().to_numpy(float);nn=len(finite)
                    stats=dict(valid_n=nn,mean=finite.mean() if nn else np.nan,median=np.median(finite) if nn else np.nan,
                               p10=np.quantile(finite,.1,method='linear') if nn else np.nan,p90=np.quantile(finite,.9) if nn else np.nan,
                               p10_inverse_cdf=np.sort(finite)[max(0,math.ceil(.1*nn)-1)] if nn else np.nan,
                               sd=np.std(finite,ddof=1) if nn>1 else np.nan,sd_population=np.std(finite,ddof=0) if nn else np.nan,
                               minimum=finite.min() if nn else np.nan,maximum=finite.max() if nn else np.nan,
                               unique_valid_teams=g.loc[g[metric].notna(),'team_key'].nunique())
                    numeric(module,f'path_frequency_statistics/{pid}/{label}/{kk}/{metric}',list(stats.values()),
                            [stored.loc[kk,metric+'_'+field] for field in stats])
                    if kk==k:
                        actuals.append(dict(pool_id=pid,version=label,N=n,k=kk,metric=metric,paths=len(g),unique_teams=g.team_key.nunique(),**stats))
            # All paired windows touching a restored prefix are recomputed from
            # matching replicate ids; an unscored end is never a zero score.
            pair=read(path/dirname/'by_pool'/pid/'PATH_CHANGE_SUMMARY.csv.gz')
            checks=[]
            for row in pair[pair.metric.isin(['B8L2','D10','IoU3D100'])].itertuples(index=False):
                a=frame[frame.k.eq(row.k_from)].set_index('replicate_id')[row.metric]
                b=frame[frame.k.eq(row.k_to)].set_index('replicate_id')[row.metric].reindex(a.index)
                va,vb=a.notna(),b.notna();both=va&vb;delta=b[both]-a[both]
                checks.append(dict(pool_id=pid,k_from=row.k_from,k_to=row.k_to,metric=row.metric,
                    both_valid_n=int(both.sum()),from_only_valid_n=int((va&~vb).sum()),to_only_valid_n=int((~va&vb).sum()),neither_valid_n=int((~va&~vb).sum()),
                    paired_from_mean=a[both].mean(),paired_to_mean=b[both].mean(),mean_delta=delta.mean(),mean_abs_delta=delta.abs().mean(),
                    positive_paths=int(delta.gt(1e-9).sum()),negative_paths=int(delta.lt(-1e-9).sum()),near_zero_paths=int(delta.abs().le(1e-9).sum())))
            equal_frame(module,'paired_existing_windows/'+label+'/'+pid,pd.DataFrame(checks),pair[pair.metric.isin(['B8L2','D10','IoU3D100'])],
                        ['pool_id','k_from','k_to','metric'],[c for c in checks[0] if c not in ['pool_id','k_from','k_to','metric']])
    flag(module,'33_references_are_two_teams',sum(x['affected_path_rows'] for x in pathcounts)==33 and sum(x['affected_unique_teams'] for x in pathcounts)==2)
    write(pd.DataFrame(pathcounts),'NATURAL_FROZEN_PATH_SUPPORT.csv');write(pd.DataFrame(actuals),'NATURAL_RECOMPUTED_PATH_STATISTICS.csv')

    # Verify every combined changed pool replacement and unchanged non-target
    # slice against freshly retrieved original files from the frozen commit.
    names={'POOL_K_STATISTICS.csv.gz':['pool_id','k'],'STATUS_BY_K.csv.gz':['pool_id','k','status_class'],
           'PATH_CHANGE_SUMMARY.csv.gz':['pool_id','k_from','k_to','metric'],'TAIL_ENVELOPES.csv.gz':['pool_id','metric','k'],
           'PLATEAU_SENSITIVITY.csv.gz':['pool_id','metric','tolerance','minimum_valid_paths']}
    combined_path_changes=None;onset_grid=None
    for name,key in names.items():
        old=read(source/name);new=read(path/'stage03_response/manual'/name)
        equal_frame(module,'stage03_unhit_pools/'+name,new[~new.pool_id.isin(pools)],old[~old.pool_id.isin(pools)],key)
        target=pd.concat([read(path/'manual_assisted/by_pool'/pid/name) for pid in pools],ignore_index=True)
        equal_frame(module,'stage03_all_affected_pool_rows/'+name,new[new.pool_id.isin(pools)],target,key)
        consumer(module,'stage03/'+name,'仅两个其它目标池','原其它池逐格保持；实际新池行完整接入',str((path/'stage03_response/manual'/name).relative_to(ROOT)))
        if name=='PATH_CHANGE_SUMMARY.csv.gz':
            combined_path_changes=new[[c for c in ['pool_id','domain','image','building','interval_labels','metric','mean_delta','mean_abs_delta','both_valid_n','from_only_valid_n','to_only_valid_n','neither_valid_n'] if c in new]].copy()
        if name=='PLATEAU_SENSITIVITY.csv.gz':
            onset_grid=new
    for name in ['TRANSIENT_FLAT_THEN_CHANGE.csv.gz','REUSED_BAND_ESTIMATE_CHECKS.csv.gz']:
        old=read(source/name);new=read(path/'stage03_response/manual'/name)
        flag(module,'empty_target_contribution/'+name,not old.pool_id.isin(pools).any() and not new.pool_id.isin(pools).any())
        # These two consumers receive no rows from the small target pools;
        # keep original row order as well as all numeric and text fields.
        equal_frame(module,'unchanged_empty_target_consumer/'+name,new.assign(audit_row=np.arange(len(new))),old.assign(audit_row=np.arange(len(old))),['audit_row'])
        consumer(module,'stage03/'+name,'两个其它目标池原/新贡献均为空','完整非目标表保持；不创造置信带或短暂平台案例',name)
    changes=combined_path_changes[combined_path_changes.interval_labels.str.contains('fixed_',na=False)].copy()
    changes=changes.assign(window=changes.interval_labels.str.split('|')).explode('window')
    changes=changes[changes.window.str.startswith('fixed_')]
    windows=[]
    for values,g in changes.groupby(['domain','window','metric'],dropna=False):
        valid=g[g.mean_delta.notna()];im=valid.groupby(['image','building']).mean_delta.mean().reset_index();bd=im.groupby('building').mean_delta.mean();a=im.mean_delta.to_numpy(float)
        windows.append(dict(zip(['domain','window','metric'],values))|dict(capacity_pools=len(g),capacity_images=g.image.nunique(),capacity_buildings=g.building.nunique(),
            valid_pools=len(valid),valid_images=len(im),valid_buildings=len(bd),mean_delta_pool_equal=valid.mean_delta.mean(),mean_delta_image_equal=im.mean_delta.mean(),mean_delta_building_equal=bd.mean(),
            mean_abs_path_delta_pool_equal=valid.mean_abs_delta.mean(),positive_images=int((a>1e-9).sum()),negative_images=int((a< -1e-9).sum()),near_zero_images=int((abs(a)<=1e-9).sum()),
            image_delta_p10=np.quantile(a,.1) if len(a) else np.nan,image_delta_median=np.median(a) if len(a) else np.nan,image_delta_p90=np.quantile(a,.9) if len(a) else np.nan,
            paired_valid_path_rows=int(g.both_valid_n.sum()),unavailable_endpoint_path_rows=int((g.from_only_valid_n+g.to_only_valid_n+g.neither_valid_n).sum())))
    windows=pd.DataFrame(windows)
    equal_frame(module,'all_stage03_fixed_window_domains',windows,read(path/'stage03_response/manual/FIXED_WINDOW_DOMAIN_SUMMARY.csv'),['domain','window','metric'])
    write(windows[windows.domain.eq('ordinary_manual_extra_target')],'NATURAL_RECOMPUTED_FIXED_WINDOW_SUMMARY.csv')
    primary=read(path/'stage03_response/manual/PRIMARY_SMALL_CHANGE_ONSETS.csv')
    equal_frame(module,'primary_onset_rows_from_declared_grid',primary,onset_grid[truth(onset_grid.primary_rule)],['pool_id','metric'])
    consumer(module,'stage03/FIXED_WINDOW_DOMAIN_SUMMARY 与主平台表','原域与窗口声明保持','从完整路径变化行和平台网格独立重建，正式门槛未放宽','NATURAL_RECOMPUTED_FIXED_WINDOW_SUMMARY.csv; CHECKS.csv')

    curves=read(path/'stage03_response/manual/POOL_K_STATISTICS.csv.gz')
    index=read(source/'POOL_INDEX.csv')
    members=read(source/'FIXED_PANEL_MEMBERS.csv')
    stage07_keys={'FIXED_PANEL_CURVES.csv.gz':['panel','domain','stratum_dimension','stratum','k','metric'],
                  'PER_IMAGE_MARGINAL_CHANGES.csv.gz':['pool_id','window','metric'],
                  'FIXED_PANEL_CHANGE_SUMMARY.csv.gz':['panel','domain','stratum_dimension','stratum','window','metric']}
    differences={}
    for name,key in stage07_keys.items():
        old=read(source/name);new=read(path/'stage07_summary/manual'/name)
        equal_frame(module,'stage07_main_and_other_unhit_domains/'+name,new[new.domain.ne('ordinary_manual_extra_target')],old[old.domain.ne('ordinary_manual_extra_target')],key)
        differences[name]=changed_rows(old,new,key)
        flag(module,'stage07_changes_confined_to_other_targets/'+name,differences[name].domain.eq('ordinary_manual_extra_target').all(),changed_rows=len(differences[name]))
    marginal=read(path/'stage07_summary/manual/PER_IMAGE_MARGINAL_CHANGES.csv.gz')
    ci=curves.set_index(['pool_id','k'])
    derived=[]
    for row in marginal[marginal.pool_id.isin(pools)].itertuples(index=False):
        a,b=ci.loc[(row.pool_id,row.k_from)],ci.loc[(row.pool_id,row.k_to)]
        count=row.metric[:-5]+'_valid_n' if row.metric.endswith('_rate') else row.metric.rsplit('_',1)[0]+'_valid_n'
        x,y=a[row.metric],b[row.metric];good=a[count]>=64 and b[count]>=64 and pd.notna(x) and pd.notna(y)
        derived.append(dict(pool_id=row.pool_id,window=row.window,metric=row.metric,from_value=x,to_value=y,
                            from_valid_paths=int(a[count]),to_valid_paths=int(b[count]),paired_image_metric_valid=good,
                            delta=y-x if good else np.nan,abs_delta=abs(y-x) if good else np.nan))
    equal_frame(module,'stage07_actual_marginal_values',pd.DataFrame(derived),marginal[marginal.pool_id.isin(pools)],['pool_id','window','metric'],[c for c in derived[0] if c not in ['pool_id','window','metric']])

    def eligible_ids(row):
        ids=set(members.loc[members.panel.eq(row.panel)&members.domain.eq(row.domain),'pool_id'])
        ii=index[index.pool_id.isin(ids)]
        if row.stratum_dimension=='frozen_difficulty':
            ii=ii[ii.difficulty_en.astype(str).eq(str(row.stratum))]
        elif row.stratum_dimension=='has_short':
            ii=ii[ii.has_short.astype('Int64').astype(str).eq(str(row.stratum))]
        elif row.stratum_dimension=='reference_turn_band':
            bands=pd.cut(ii.ref_turn5,bins=[-np.inf,4,6,8,np.inf],labels=['at_most_4','5_to_6','7_to_8','9_or_more'])
            ii=ii[bands.astype(str).eq(str(row.stratum))]
        else:
            assert row.stratum_dimension=='all',row.stratum_dimension
        return set(ii.pool_id)

    rebuilt=[]
    for row in differences['FIXED_PANEL_CURVES.csv.gz'].itertuples(index=False):
        g=curves[curves.pool_id.isin(eligible_ids(row))&curves.k.eq(row.k)].copy()
        count=row.metric[:-5]+'_valid_n' if row.metric.endswith('_rate') else row.metric.rsplit('_',1)[0]+'_valid_n'
        g.loc[g[count].lt(64),row.metric]=np.nan
        meta={c:getattr(row,c) for c in stage07_keys['FIXED_PANEL_CURVES.csv.gz']}
        rebuilt.append(meta|dict(valid_path_rows=int(g.loc[g[count]>=64,count].sum()),**hierarchical_values(g,row.metric)))
    rebuilt=pd.DataFrame(rebuilt)
    equal_frame(module,'stage07_changed_curve_weighting_and_support',rebuilt,differences['FIXED_PANEL_CURVES.csv.gz'],stage07_keys['FIXED_PANEL_CURVES.csv.gz'],[c for c in rebuilt if c not in stage07_keys['FIXED_PANEL_CURVES.csv.gz']])
    rebuilt_changes=[]
    for row in differences['FIXED_PANEL_CHANGE_SUMMARY.csv.gz'].itertuples(index=False):
        g=marginal[marginal.pool_id.isin(eligible_ids(row))&marginal.window.eq(row.window)&marginal.metric.eq(row.metric)]
        meta={c:getattr(row,c) for c in stage07_keys['FIXED_PANEL_CHANGE_SUMMARY.csv.gz']}
        rebuilt_changes.append(meta|hierarchical_values(g,'delta',row.tolerance))
    rebuilt_changes=pd.DataFrame(rebuilt_changes)
    equal_frame(module,'stage07_changed_contrast_weighting_and_support',rebuilt_changes,differences['FIXED_PANEL_CHANGE_SUMMARY.csv.gz'],stage07_keys['FIXED_PANEL_CHANGE_SUMMARY.csv.gz'],[c for c in rebuilt_changes if c not in stage07_keys['FIXED_PANEL_CHANGE_SUMMARY.csv.gz']])
    write(rebuilt,'NATURAL_RECOMPUTED_CHANGED_FIXED_PANEL_CURVES.csv')
    write(rebuilt_changes,'NATURAL_RECOMPUTED_CHANGED_FIXED_PANEL_CONTRASTS.csv')
    po=read(path/'aggregate_automatic/PRIMARY_SMALL_CHANGE_ONSETS.csv');pn=read(path/'stage03_response/manual/PRIMARY_SMALL_CHANGE_ONSETS.csv')
    equal_frame(module,'formal_onsets_keep_same_support_and_values',pn,po,['pool_id','metric'],['onset_k'])
    small=pn[pn.pool_id.isin(pools)]
    flag(module,'N5_N7_formal_platforms_still_unestimated',small.onset_k.isna().all(),rows=len(small))
    late=read(source/'LATE_PATH_JUMP_SENSITIVITY.csv.gz')
    flag(module,'late_jump_design_has_no_small_pool_hit',not late.pool_id.isin(pools).any())
    original_facts=json.loads(text(source/'RESULT_FACTS.json'));new_facts=json.loads(text(path/'stage07_summary/manual/RESULT_FACTS.json'))
    # The producer's declared JSON contract compares numbers at absolute 1e-10,
    # while keys, list shape, strings and missing values must remain exact.
    # CSV read/write roundoff must not be mislabeled as a changed research fact.
    facts_rounding=[];facts_structure_errors=[]
    def compare_facts(a,b,location='root'):
        if isinstance(a,dict) and isinstance(b,dict):
            if set(a)!=set(b):
                facts_structure_errors.append(dict(path=location,reason='keys differ'));return
            for k in a:compare_facts(a[k],b[k],location+'/'+str(k))
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):
                facts_structure_errors.append(dict(path=location,reason='list lengths differ'));return
            for i,(x,y) in enumerate(zip(a,b)):compare_facts(x,y,location+'/'+str(i))
        elif isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool):
            if a!=b:
                facts_rounding.append(dict(path=location,automatic=a,manual_assisted=b,
                                           delta=b-a,absolute_difference=abs(b-a)))
        elif type(a) is not type(b) or a!=b:
            facts_structure_errors.append(dict(path=location,reason='non-numeric value or type differs',automatic=a,manual_assisted=b))
    compare_facts(original_facts,new_facts)
    rounding=pd.DataFrame(facts_rounding,columns=['path','automatic','manual_assisted','delta','absolute_difference'])
    maximum_facts_error=float(rounding.absolute_difference.max()) if len(rounding) else 0.
    write(rounding,'NATURAL_RESULT_FACTS_NUMERIC_PARITY.csv')
    contract='tools/thesis_main/analysis/evaluate_manual_order_natural_20261104.py'
    register(ROOT/contract)
    flag(module,'stage07_result_facts_unchanged',not facts_structure_errors and maximum_facts_error<1e-10,
         numeric_rounding_cells=len(rounding),maximum_absolute_error=maximum_facts_error,
         absolute_tolerance=1e-10,structure_or_nonnumeric_errors=facts_structure_errors,
         producer_contract=contract+'::json_numeric_parity',scientific_recalculation_required=False)
    for name in stage07_keys:
        consumer(module,'stage07/'+name,'原固定面板成员/难度；仅其它目标域变化','原其它域保持；全部真实变化的值与池→图→楼权重重新计算',name)
    consumer(module,'main-only 几何、结构分项、P10/finite-tail、连续结构与诊断','两个被处理池均为 ordinary_manual_extra_target','未命中原 ordinary_manual_main 域；不重新运行',str((path/'DOWNSTREAM_CONSUMERS.csv').relative_to(ROOT)))
    conclusion(module,'人数两其它目标小池','幅度变化','两队分别复用 8/25 条原路径；Q 均值和尾部分位数按路径频数更新，主目标消费者逐格不变。','NATURAL_FROZEN_PATH_SUPPORT.csv; NATURAL_RECOMPUTED_PATH_STATISTICS.csv')
    conclusion(module,'正式平台人数/停止人数','尚不能判断','N=5/7 未满足原后续观察门槛；正式 onset_k 仍缺失。两个 ungated 诊断格不等同正式平台前移。','CHECKS.csv; ../../manual_order_impact_20261104/natural/AGGREGATE_NUMERIC_CHANGES.csv.gz')


POLICY_COMPONENTS=['B8_floor_block','B8_direction_block','B8_height_block','iou_2d','S_bottom_deg','dir','Hmean']
POLICY_METRICS=['paired_Q_delta','paired_D10_delta','Q_p10_delta_common','Q_sd_delta_common_ddof1','failure_delta','incomplete_delta',
                'Q_loss_gt5_rate','Q80_reached_delta','Q90_reached_delta','labor_ratio_legal','QT_paired_Q_delta','nodes_delta','turn5_delta']
POLICY_METRICS += [x+'_delta' for x in POLICY_COMPONENTS]
POLICY_STATES=['actual_consensus_failure','output_generated_unscorable','reference_unavailable','other_unscored']
POLICY_METRICS += [x+'_delta' for x in POLICY_STATES]
POLICY_PHASES=['early_3_to_half','low_3_to_6','late_20_to_Nminus1','full']
POLICY_NAMES=['joint_highq_first','structure_moreturn_first','joint_fast_first','structure_dominant_first']


def policy_legal(raw):
    d=raw[raw.base_batch.isin(['old8','prior_new8','new16'])].copy()
    def kind(v):
        if pd.isna(v):return ''
        s=str(v)
        if s.startswith('['):
            x=json.loads(s);return str(x[0]) if len(x)==1 else ''
        return '' if '|' in s or ',' in s else s
    d['labor_kind']=d.time_source_kinds.fillna(d.get('time_source_kinds_json',pd.Series(index=d.index,dtype=object))).map(kind)
    eligible=d.source_time_known_n.eq(d.k)&d.source_time_total_seconds.gt(0)&d.labor_kind.ne('')
    d.loc[~eligible,'source_time_total_seconds']=np.nan
    active=d.k.ne(2)&d.B8L2.isna();status=d.score_status.fillna('')
    d['actual_consensus_failure']=active & status.isin(['fusion_exception','below_four','no_connection'])
    d['output_generated_unscorable']=active & status.isin(['measurement_exception','invalid_floor','invalid_full_geometry'])
    d['reference_unavailable']=active & status.isin(['floor_only_reference','missing_reference'])
    d['other_unscored']=active & ~(d.actual_consensus_failure|d.output_generated_unscorable|d.reference_unavailable)
    return d


def policy_k_statistics(frame):
    rows=[]
    for version in ['old16','new16','pooled32']:
        d=frame if version=='pooled32' else frame[frame.base_batch.eq('new16') if version=='new16' else frame.base_batch.isin(['old8','prior_new8'])]
        for policy in POLICY_NAMES:
            nat=d[d.policy.eq('natural_random')].set_index(['base_path_id','k'])
            pol=d[d.policy.eq(policy)].set_index(['base_path_id','k']).reindex(nat.index)
            assert not nat.index.duplicated().any() and nat.index.equals(pol.index)
            for k in sorted(d.k.unique()):
                nn=nat.xs(k,level='k');pp=pol.xs(k,level='k')
                valid=nn.B8L2.notna()&pp.B8L2.notna()
                n,p=nn.loc[valid],pp.loc[valid];delta=p.B8L2-n.B8L2
                time=(nn.source_time_total_seconds.gt(0)&pp.source_time_total_seconds.gt(0)&nn.labor_kind.eq(pp.labor_kind))
                ratio=(pp.source_time_total_seconds/nn.source_time_total_seconds).where(time)
                both=int(valid.sum())
                out=dict(version=version,policy=policy,k=int(k),base_paths=len(nn),both_Q_paths=both,legal_QT_paths=int((valid&time).sum()),
                    paired_Q_delta=delta.mean(),paired_D10_delta=(p.D10-n.D10).mean(),
                    Q_p10_delta_common=p.B8L2.quantile(.1)-n.B8L2.quantile(.1) if both else np.nan,
                    Q_sd_delta_common_ddof1=p.B8L2.std(ddof=1)-n.B8L2.std(ddof=1) if both>1 else np.nan,
                    failure_delta=(pp.score_failure_nonpolicy.astype(float)-nn.score_failure_nonpolicy.astype(float)).mean(),
                    incomplete_delta=(pp.incomplete_nonpolicy.astype(float)-nn.incomplete_nonpolicy.astype(float)).mean(),
                    Q_loss_gt5_rate=delta.lt(-5).mean() if both else np.nan,
                    Q80_reached_delta=(pp.B8L2.ge(80).astype(float)-nn.B8L2.ge(80).astype(float)).mean(),
                    Q90_reached_delta=(pp.B8L2.ge(90).astype(float)-nn.B8L2.ge(90).astype(float)).mean(),
                    labor_ratio_legal=ratio[valid].mean(),QT_paired_Q_delta=(pp.B8L2-nn.B8L2).where(time).mean(),
                    nodes_delta=(pp.nodes-nn.nodes).mean(),turn5_delta=(pp.floor_turn5_n-nn.floor_turn5_n).mean())
                out.update({c+'_delta':(p[c]-n[c]).mean() for c in POLICY_COMPONENTS})
                out.update({c+'_delta':(pp[c].astype(float)-nn[c].astype(float)).mean() for c in POLICY_STATES})
                if k==2:
                    out.update({c:np.nan for c in POLICY_METRICS})
                rows.append(out)
    return pd.DataFrame(rows)


def policy():
    module='policy';path=BASE/module;source=SRC/'frozen_inputs/policy'
    pid='x8F5xyUWy9e-08__manual__0b13997fd3';key=pid+'__fb261248c4a2c1b66d0b'
    pol='structure_dominant_first';phase='late_20_to_Nminus1'
    old=read(SRC/(pid+'.csv.gz'));new=read(path/'PREFIX_VALUES_ASSISTED.csv.gz')
    identity=['pool_id','path_id','k'];new=new.set_index(identity).loc[old.set_index(identity).index].reset_index()
    hit=old.team_key.eq(key)
    equal_frame(module,'all_unhit_prefix_fields',new.loc[~hit],old.loc[~hit],identity)
    equal_frame(module,'old_scored_prefix_values',new.loc[old.B8L2.notna()],old.loc[old.B8L2.notna()],identity)
    fixed=['team_key','base_path_id','base_batch','policy','member_workers','member_object_ids','reference_id','reference_version',
           'pool_n','worker_order','base_worker_order','method','nodes']+[c for c in old if 'time' in c]
    equal_frame(module,'fixed_prefix_members_order_reference_and_labor',new,old,identity,[c for c in fixed if c in old and c not in identity])
    flag(module,'one_existing_legacy_prefix_only',hit.sum()==1 and old.loc[hit,'k'].eq(28).all() and old.loc[hit,'base_batch'].eq('new16').all()
         and old.loc[hit,'policy'].eq(pol).all() and old.loc[hit,'method'].eq('V3_BEHAVIOR').all(),affected_prefixes=int(hit.sum()))
    flag(module,'old_Q_missing_not_zero_and_labor_unmodified',old.loc[hit,'B8L2'].isna().all()
         and new.loc[hit,'B8L2'].notna().all() and new.loc[hit,'source_time_total_seconds'].equals(old.loc[hit,'source_time_total_seconds']))
    per_k={}
    for version,raw in [('automatic',old),('manual_assisted',new)]:
        part=path/version/'analysis_policy26/parts'/pid
        calculated=policy_k_statistics(policy_legal(raw));stored=read(part/'POLICY_IMAGE_K.csv.gz')
        per_k[version]=calculated
        equal_frame(module,version+'/all_affected_pool_k_metrics',calculated,stored,['version','policy','k'],[c for c in calculated if c not in ['version','policy','k']])
        fixed=read(part/'FIXED_SUPPORT.csv.gz')
        kk=calculated.set_index(['version','policy','k'])
        values=[]
        for row in fixed.itertuples(index=False):
            ks=[int(x) for x in str(row.matched_k_list).split('|') if x and x!='nan']
            expected=float(np.mean([kk.loc[(row.version,row.policy,k),row.metric] for k in ks])) if ks else np.nan
            values.append(expected)
        numeric(module,version+'/all_fixed_k_phase_means',fixed.point,values)
        phases=read(part/'POLICY_IMAGE_PHASE.csv').set_index(['version','policy','phase'])
        numeric(module,version+'/fixed_support_to_phase_consumers',
                [phases.loc[(r.version,r.policy,r.phase),r.metric] for r in fixed.itertuples(index=False)],fixed.point)
    fkeys=['pool_id','version','policy','phase','metric']
    fo=read(path/'automatic/analysis_policy26/parts'/pid/'FIXED_SUPPORT.csv.gz')
    fn=read(path/'manual_assisted/analysis_policy26/parts'/pid/'FIXED_SUPPORT.csv.gz')
    equal_frame(module,'adopted_k_support_and_path_design_preserved',fn,fo,fkeys,['candidate_k','adopted_old16_k','matched_k','lost_k','matched_k_list'])
    # Each global consumer consists of the old unhit pools plus the exact
    # replacement for the one hit pool; no unrelated cohort is substituted.
    consumer_keys={'POLICY_IMAGE_K.csv.gz':['pool_id','version','policy','k'],
                   'POLICY_IMAGE_PHASE.csv':['pool_id','version','policy','phase'],
                   'FIXED_SUPPORT.csv.gz':fkeys}
    global_frames={}
    for name,ks in consumer_keys.items():
        a=read(source/name);b=read(path/('ASSISTED_'+name));replacement=read(path/'manual_assisted/analysis_policy26/parts'/pid/name)
        equal_frame(module,'all_unhit_pool_consumers/'+name,b[b.pool_id.ne(pid)],a[a.pool_id.ne(pid)],ks)
        equal_frame(module,'affected_pool_replacement/'+name,b[b.pool_id.eq(pid)],replacement,ks)
        global_frames[name]=(a,b)
        consumer(module,name,'唯一 N35/k28 的 new16 旧角色策略前缀','原 152 未命中池逐格保持；命中池完整替换并重算 k/phase 均值',name)
    precision_old=read(source/'POLICY_PRECISION_SUMMARY.csv');precision_new=read(path/'POLICY_PRECISION_SUMMARY_ASSISTED.csv')
    summarykeys=['version','policy','difficulty','phase','metric','weighting']
    mask_old=precision_old.policy.eq(pol)&precision_old.version.isin(['new16','pooled32'])&precision_old.phase.eq(phase)
    mask_new=precision_new.policy.eq(pol)&precision_new.version.isin(['new16','pooled32'])&precision_new.phase.eq(phase)
    equal_frame(module,'all_unhit_precision_summary_rows',precision_new[~mask_new],precision_old[~mask_old],summarykeys)
    late=read(path/'LATE_GLOBAL_COMPARISON.csv')
    equal_frame(module,'all_affected_precision_summary_rows',precision_new[mask_new],late[late.connection_version.eq('manual_assisted')],summarykeys)
    equal_frame(module,'frozen_late_baseline',precision_old[mask_old],late[late.connection_version.eq('automatic')],summarykeys)

    # Reuse saved complete-path draws. This checks propagation and both interval
    # definitions without generating any new path/team/scoring experiment.
    meta=read(source/'COMMON_IMAGES.csv').sort_values('pool_id').reset_index(drop=True)
    flag(module,'original_primary_cohort_preserved',len(meta)==153 and meta.building.nunique()==21)
    zpath=register(path/'LATE_PATH_BOOTSTRAP_AUTOMATIC.npz')
    with np.load(zpath) as z:cached={v:z[v] for v in ['new16','pooled32']}
    partpath=register(path/'manual_assisted/analysis_policy26/parts'/pid/'PATH_BOOTSTRAP_CACHE.npz')
    with np.load(partpath) as z:replacement={v:z[pol+'__'+v+'__boot'][:,2,:] for v in ['new16','pooled32']}
    own_position=int(meta.index[meta.pool_id.eq(pid)][0]);globalrows=[]
    def interval(values):
        a=values[np.isfinite(values)]
        return tuple(np.quantile(a,[.025,.975])) if len(a) else (np.nan,np.nan)
    for connection,source_phase in zip(['automatic','manual_assisted'],global_frames['POLICY_IMAGE_PHASE.csv']):
        for version in ['new16','pooled32']:
            rows=source_phase[source_phase.policy.eq(pol)&source_phase.version.eq(version)].set_index(['pool_id','phase'])
            points=np.empty((len(meta),4,len(POLICY_METRICS)))
            for ph,phname in enumerate(POLICY_PHASES):
                points[:,ph,:]=rows.loc[[(p,phname) for p in meta.pool_id],POLICY_METRICS].to_numpy(float)
            boots=cached[version].copy()
            if connection=='manual_assisted':boots[own_position]=replacement[version]
            rng=np.random.default_rng(np.random.SeedSequence([2026102603,999,3,['old16','new16','pooled32'].index(version)]))
            for difficulty,g in [('全部',meta)]+list(meta.groupby('difficulty')):
                ids=g.index.to_numpy()
                for ph,phname in enumerate(POLICY_PHASES):
                    for mi,metric in enumerate(POLICY_METRICS):
                        x=points[ids,ph,mi];good=np.isfinite(x);pos=ids[good];x=x[good]
                        if not len(x):continue
                        b=meta.loc[pos,'building'].to_numpy();unique=np.unique(b)
                        bv=np.array([np.mean(x[b==u]) for u in unique]);counts=np.array([(b==u).sum() for u in unique])
                        weights=rng.multinomial(len(unique),np.repeat(1/len(unique),len(unique)),size=2000)
                        if phname!=phase:continue
                        draws=boots[pos,:,mi];bdraws=np.array([np.mean(draws[b==u],axis=0) for u in unique])
                        building_image_draw=(weights@(bv*counts))/(weights@counts)
                        building_equal_draw=(weights@bv)/len(unique)
                        for weighting,estimate,pdra,bdra in [('image_equal',x.mean(),np.mean(draws,axis=0),building_image_draw),
                                                            ('building_equal',bv.mean(),np.mean(bdraws,axis=0),building_equal_draw)]:
                            pl,phigh=interval(pdra);bl,bhigh=interval(bdra);nvalid=int(np.isfinite(pdra).sum())
                            globalrows.append(dict(connection_version=connection,version=version,policy=pol,difficulty=difficulty,phase=phase,metric=metric,weighting=weighting,
                                estimate=estimate,images=len(x),candidate_images=len(g),buildings=len(unique),positive_images=int((x>1e-9).sum()),negative_images=int((x< -1e-9).sum()),nearzero_images=int((abs(x)<=1e-9).sum()),
                                path_lo=pl,path_hi=phigh,path_valid_replicates=nvalid,path_invalid_replicates=2000-nvalid,
                                path_interval_status='unavailable' if nvalid==0 else 'conditional_on_estimable_draws' if nvalid<2000 else 'complete_support_all_draws',
                                building_lo=bl,building_hi=bhigh,bootstrap_replicates=2000))
    recalculated=pd.DataFrame(globalrows)
    equal_frame(module,'all_late_estimates_and_cached_path_building_intervals',recalculated,late,['connection_version']+summarykeys)
    write(recalculated,'POLICY_RECOMPUTED_LATE_SUMMARY.csv')
    oldlate=late[late.connection_version.eq('automatic')].drop(columns='connection_version')
    newlate=late[late.connection_version.eq('manual_assisted')].drop(columns='connection_version')
    paired=oldlate.merge(newlate,on=summarykeys,suffixes=('_old','_new'),validate='one_to_one')
    def zclass(lo,hi):
        return np.where(lo.gt(0),'positive',np.where(hi.lt(0),'negative','contains_zero'))
    paired['estimate_direction_same']=np.sign(paired.estimate_old)==np.sign(paired.estimate_new)
    paired['path_interval_zero_relation_same']=zclass(paired.path_lo_old,paired.path_hi_old)==zclass(paired.path_lo_new,paired.path_hi_new)
    paired['building_interval_zero_relation_same']=zclass(paired.building_lo_old,paired.building_hi_old)==zclass(paired.building_lo_new,paired.building_hi_new)
    flag(module,'all_352_point_and_interval_directions_preserved',len(paired)==352 and paired[['estimate_direction_same','path_interval_zero_relation_same','building_interval_zero_relation_same']].all().all(),
         summary_groups=len(paired),changed_point_estimates=int((~np.isclose(paired.estimate_old,paired.estimate_new,rtol=0,atol=1e-10)).sum()))
    write(paired,'POLICY_DIRECTION_AND_INTERVAL_ACCEPTANCE.csv')
    consumer(module,'POLICY_PRECISION_SUMMARY','new16 与 pooled32 的既有 late_20_to_Nminus1 摘要','全 352 组点值、保存路径抽样和建筑区间独立复核；其余摘要保持','POLICY_RECOMPUTED_LATE_SUMMARY.csv; POLICY_DIRECTION_AND_INTERVAL_ACCEPTANCE.csv')
    conclusion(module,'旧策略单一前缀与实际消费者','幅度变化','唯一 x8-08、N35/k28、new16 的历史 V3_BEHAVIOR structure_dominant_first 前缀已接续；352 组点估计/区间相对 0 判定均保持。','POLICY_DIRECTION_AND_INTERVAL_ACCEPTANCE.csv')
    conclusion(module,'当前 DSTRUCT 策略与更大策略实验','保持','旧角色策略不等同当前 DSTRUCT；未增加政策、团队或 replacement 规模，未命中条件不重跑。','CHECKS.csv')


def coordinate_candidate():
    module='coordinate_candidate';path=BASE/module
    rows=json.loads(gzip.decompress(register(path/'CANDIDATE_FULL_STATE.json.gz').read_bytes()))
    fixed,candidate=rows
    key=fixed['score']['team_key']
    assert candidate['score']['team_key']==key
    endpoint=read(BASE/'endpoints/ENDPOINT_SCORES.csv').set_index('team_key')
    flag(module,'main_fixed_coordinate_result_not_promoted',len(endpoint)==57 and int(endpoint.B8L2.notna().sum())==56
         and pd.isna(endpoint.loc[key,'B8L2']) and endpoint.loc[key,'score_status']=='invalid_floor',
         main_endpoints=len(endpoint),main_scored=int(endpoint.B8L2.notna().sum()))
    flag(module,'unchanged_source_members_reference_order',fixed['source_records']==candidate['source_records']
         and fixed['reference']==candidate['reference'] and fixed['manual_feature_order']==candidate['manual_feature_order'])
    oldnodes={n['feature_id']:n for n in fixed['nodes']};newnodes={n['feature_id']:n for n in candidate['nodes']}
    edits=[]
    flag(module,'all_node_identities_and_supports_preserved',set(oldnodes)==set(newnodes) and len(oldnodes)==9
         and all({k:v for k,v in oldnodes[n].items() if k!='points'}=={k:v for k,v in newnodes[n].items() if k!='points'} for n in oldnodes))
    for name in oldnodes:
        a=np.array(oldnodes[name]['points']);b=np.array(newnodes[name]['points'])
        for i,j in np.argwhere(a!=b):
            edits.append(dict(feature_id=name,point=int(i),axis='x' if j==0 else 'y',before=a[i,j],after=b[i,j]))
    changes=pd.DataFrame(edits)
    flag(module,'exactly_four_requested_x_edits',len(edits)==4 and set(changes.feature_id)=={'node_001','node_010'}
         and changes.axis.eq('x').all() and changes.after.eq(438.8037).all(),changed_scalars=len(edits))
    def planar_check(points):
        p=np.asarray(points,float);n=len(p);area=float(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1))/2)
        def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])
        crosses=[]
        for i in range(n):
            a,b=p[i],p[(i+1)%n]
            for j in range(i+1,n):
                if j in [i,(i+1)%n] or (j+1)%n==i:continue
                c,d=p[j],p[(j+1)%n]
                s=[cross(b-a,c-a),cross(b-a,d-a),cross(d-c,a-c),cross(d-c,b-c)]
                if s[0]*s[1]< -1e-24 and s[2]*s[3]< -1e-24:crosses.append([i,j])
        halfplanes=[np.sign(area)*cross(p[(i+1)%n]-p[i],-p[i]) for i in range(n)]
        return dict(signed_area_h2=area,proper_nonadjacent_crossings=crosses,
                    camera_satisfies_all_interior_halfplanes=bool(min(halfplanes)>=-1e-12),
                    minimum_camera_halfplane_margin=float(min(halfplanes)))
    geom_old=planar_check(fixed['geometry_audit']['floor']);geom_new=planar_check(candidate['geometry_audit']['floor'])
    flag(module,'independent_planar_crossing_and_kernel_check',len(geom_old['proper_nonadjacent_crossings'])==1
         and not geom_new['proper_nonadjacent_crossings'] and abs(geom_new['signed_area_h2'])>1e-10
         and not geom_new['camera_satisfies_all_interior_halfplanes'])
    order=candidate['manual_feature_order'];floor=np.asarray(candidate['geometry_audit']['floor'])
    distance=float(np.linalg.norm(floor[order.index('node_001')]-floor[order.index('node_010')]))
    flag(module,'F2_F9_remain_two_distinct_floor_nodes',distance>1e-12,floor_separation_h=distance)
    numeric(module,'candidate_scores_remain_separately_labeled',[candidate['score']['B8L2'],candidate['score']['D10']], [39.61561918763198,41.30578782236161])
    flag(module,'conditional_candidate_is_not_a_global_coordinate_rule',candidate['score']['score_status']=='complete_conditional'
         and candidate['geometry_audit']['camera_in_visible_kernel'] is False)
    references=read(path/'ACTUAL_DOWNSTREAM_REFERENCES.csv')
    flag(module,'52_actual_references_two_modules',len(references)==52 and references.module.value_counts().to_dict()=={'ac_registered':50,'changed_alliances':2})
    ac=read(BASE/'ac/AFFECTED_EVENT_METRICS_ASSISTED.csv.gz')
    ac_refs=0
    for arm in ['A','C']:
        hit=ac[arm+'_team_key'].eq(key);ac_refs+=int(hit.sum())
        flag(module,'main_AC_'+arm+'_candidate_not_adopted',ac.loc[hit,arm+'_B8L2'].isna().all(),references=int(hit.sum()))
    flag(module,'main_AC_references_covered',ac_refs==50,actual_references=ac_refs)
    alliance=read(BASE/'alliances/ALLIANCE_RESULTS_ASSISTED.csv.gz')
    a=alliance[alliance.team_key.eq(key)]
    flag(module,'main_alliance_candidate_not_adopted',len(a)==2 and a.B8L2.isna().all())
    candidate_dir=BASE/'alliances/coordinate_candidate'
    candidate_support=[]
    for name,keys in [('FULL_VS_BEST_PURE.csv',['version','pool_id','unknown_background_included']),
                      ('FULL_VS_BEST_PURE_SUMMARY.csv',['scope','condition','unknown_background_included','version'])]:
        x=read(candidate_dir/('MANUAL_ASSISTED_FIXED_COORDINATES_'+name));y=read(candidate_dir/('COORDINATE_CANDIDATE_NOT_ADOPTED_'+name))
        fields=[c for c in x if c not in keys+['scoreable_pure_classes']]
        equal_frame(module,'candidate_alliance_Q_and_selection_unchanged/'+name,y,x,keys,fields)
        if 'scoreable_pure_classes' in x:
            joined=x.merge(y,on=keys,suffixes=('_fixed','_candidate'),validate='one_to_one')
            changed=joined[joined.scoreable_pure_classes_fixed.ne(joined.scoreable_pure_classes_candidate)]
            flag(module,'candidate_adds_two_snapshot_class_support_counts',len(changed)==2
                 and changed.pool_id.eq('pa4otMbVnkk-18__manual__bbb972aaa9').all()
                 and (changed.scoreable_pure_classes_candidate-changed.scoreable_pure_classes_fixed).eq(1).all())
            candidate_support=changed[keys+['scoreable_pure_classes_fixed','scoreable_pure_classes_candidate','full_Q_fixed','full_Q_candidate','best_pure_Q_fixed','best_pure_Q_candidate']]
    write(candidate_support,'CANDIDATE_ALLIANCE_SUPPORT_COUNTS.csv')
    # Full-vs-best is only one consumer: the candidate also expands the C1
    # conditional class mean's image support, without changing the main branch.
    class_acceptance=[]
    for version,stem in [('fixed_coordinates','MANUAL_ASSISTED_FIXED_COORDINATES'),
                         ('coordinate_candidate_not_adopted','COORDINATE_CANDIDATE_NOT_ADOPTED')]:
        frame=alliance.copy()
        if version=='coordinate_candidate_not_adopted':
            frame.loc[frame.team_key.eq(key),'B8L2']=candidate['score']['B8L2']
        frame=frame[frame.scope.eq('primary')&frame.condition.eq('manual')&frame.classes.eq('C1')&~truth(frame.unknown_background_included)]
        derived=[]
        for label,g in frame.groupby('version'):
            image=g.groupby('image').B8L2.mean().dropna()
            derived.append(dict(version=label,scope='primary',condition='manual',unknown_background_included=False,
                                classes='C1',metric='B8L2',registered_pools=len(g),eligible_pools=int(g.n.ge(3).sum()),
                                valid_images=len(image),mean=image.mean()))
        stored=read(candidate_dir/(stem+'_CLASS_METRIC_SUMMARY.csv'))
        stored=stored[stored.scope.eq('primary')&stored.condition.eq('manual')&stored.classes.eq('C1')&stored.metric.eq('B8L2')&~truth(stored.unknown_background_included)]
        equal_frame(module,'candidate_C1_class_mean_and_support/'+version,pd.DataFrame(derived),stored,
                    ['version','scope','condition','unknown_background_included','classes','metric'])
        class_acceptance.extend(dict(connection_version=version,**r) for r in derived)
    write(pd.DataFrame(class_acceptance),'CANDIDATE_C1_CLASS_METRIC_ACCEPTANCE.csv')
    write(changes,'CANDIDATE_EXACT_COORDINATE_EDITS.csv')
    (OUT/'CANDIDATE_ISOLATION.json').write_text(json.dumps(clean(dict(team_key=key,
        fixed_coordinate_audit=geom_old,candidate_audit=geom_new,F2_F9_floor_distance_h=distance,
        candidate_not_adopted=True,main_scored=56,main_registered=57,actual_AC_references=ac_refs,
        actual_alliance_references=len(a),additional_coordinate_experiment=False)),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    consumer(module,'主端点、AC、联盟及单列候选摘要','1 候选 / 52 引用；主分支 56/57','候选四个 x 标量编辑精确；未混入主评分或主下游','CANDIDATE_ISOLATION.json; CHECKS.csv')
    conclusion(module,'F2/F9 候选','保持','仅保留该四人团队的独立坐标候选；主分支仍 invalid_floor。候选消除严格自交，但相机不在可见核，未据此开展坐标规则实验。','CANDIDATE_ISOLATION.json; CANDIDATE_EXACT_COORDINATE_EDITS.csv')
    conclusion(module,'F2/F9 候选的联盟条件摘要','条件变化','候选未采用；单列分支 full-vs-best 的 Q、最佳纯类及比较支持保持，pa4 可评纯类数各加1；C1 类图均 Q 的 frozen/updated 支持分别150→151、166→167，均值相应变化，不能声称整个联盟模块仅计数改变。','CANDIDATE_ALLIANCE_SUPPORT_COUNTS.csv; CANDIDATE_C1_CLASS_METRIC_ACCEPTANCE.csv')


def audit_format_repair():
    module='composition_format_repair'
    receipt=json.loads(text(OUT/'repairs/MEMBER_FIELD_FORMAT_REPAIR.json'))
    changes=read(OUT/'repairs/MEMBER_FIELD_CELL_CHANGES.csv')
    flag(module,'eight_member_format_cells',len(changes)==8 and truth(changes.member_content_and_order_unchanged).all())
    for record in receipt['files']:
        actual=register(ROOT/record['path']).read_bytes()
        before=register(ROOT/record['exact_pre_acceptance_copy']).read_bytes()
        flag(module,'before_after_hashes/'+Path(record['path']).name,
             hashlib.sha256(actual).hexdigest()==record['after_sha256'] and hashlib.sha256(before).hexdigest()==record['before_sha256'])
        if record['path'].endswith('.csv.gz'):
            def strings(blob):
                reader=csv.reader(io.StringIO(gzip.decompress(blob).decode('utf-8-sig'),newline=''))
                rows=list(reader);return rows[0],rows[1:]
            ac,ar=strings(actual);bc,br=strings(before)
            mutable={ac.index('member_workers'),ac.index('member_object_ids')}
            token_equal=ac==bc and len(ar)==len(br) and all(x[i]==y[i] for x,y in zip(ar,br) for i in range(len(ac)) if i not in mutable)
            for x,y in zip(ar,br):
                for i in mutable:
                    normalize=lambda s:ast.literal_eval(s) if s.startswith('[') else s.split('|')
                    token_equal &= normalize(x[i])==normalize(y[i])
            flag(module,'all_other_text_tokens_and_member_order/'+Path(record['path']).name,token_equal,
                 rows=len(ar),columns=len(ac),numeric_tokens_reparsed=False)
    conclusion(module,'有限配比标量成员字段合同','需改写','已修正两份辅助标量表共8格的列表字符串格式，并修正写入脚本；实际成员、顺序和所有其它CSV单元文本保持，原统计无需重跑。','repairs/MEMBER_FIELD_FORMAT_REPAIR.json; repairs/MEMBER_FIELD_CELL_CHANGES.csv; repairs/OVERLAY_FILES.csv')
    consumer(module,'后续读取辅助标量成员列表的消费者','2 文件 / 8 字符串单元格','原管道分隔合同已恢复；现有聚合器读取固定 TEAM_REQUESTS，数值不受影响','repairs/MEMBER_FIELD_FORMAT_REPAIR.json')


def markdown_table(rows,columns):
    def cell(value):
        if isinstance(value,(float,np.floating)):
            return '—' if pd.isna(value) else f'{value:.6f}'
        return str(value).replace('|','\\|').replace('\n',' ')
    return '| '+' | '.join(columns)+' |\n| '+' | '.join(['---']*len(columns))+' |\n'+'\n'.join('| '+' | '.join(cell(r.get(c,'')) for c in columns)+' |' for r in rows)


def report():
    checks=pd.DataFrame(CHECKS);failed=checks[~checks.passed]
    scope=read(OUT/'SAME_ROOM_SEPARATE_SUPPORTS.csv')
    sr=scope[(scope.method_updated=='TARGET_DSTRUCT_K3')&(scope.n==10)&scope.updated_direction.eq('C2→C3')].iloc[0]
    ss=read(OUT/'SAME_ROOM_RECOMPUTED_METRIC_SUMMARIES.csv.gz')
    ss=ss[(ss.method_updated=='TARGET_DSTRUCT_K3')&(ss.n==10)&ss.updated_direction.eq('C2→C3')&(ss.metric=='B8L2')]
    room=[]
    for contrast in ['GA','GS','CB']:
        g=ss[ss.contrast.eq(contrast)].set_index('version')
        room.append({'指标':contrast,'原自动原支持':g.loc['automatic_original','pair_mean'],
            '辅助原事件共同支持':g.loc['assisted_original_event_support','pair_mean'],
            '辅助扩展支持':g.loc['assisted_expanded_support','pair_mean'],
            '扩展后正均值图对':str(int(g.loc['assisted_expanded_support','positive_pairs']))+'/19'})
    alliance=read(OUT/'ALLIANCE_RECOMPUTED_SUMMARIES.csv')
    alliance=alliance[alliance.condition.eq('manual')&~truth(alliance.unknown_background_included)]
    ar=[]
    for vals,g in alliance.groupby(['scope','version']):
        g=g.set_index('connection_version');a,b=g.loc['automatic'],g.loc['manual_assisted']
        ar.append({'目标范围':vals[0],'标签快照':vals[1],'原池数→辅助池数':f'{int(a.pools)}→{int(b.pools)}','图数':int(b.images),
                   '原 full−best-pure':a.mean_full_minus_best_pure,'辅助 full−best-pure':b.mean_full_minus_best_pure,
                   '辅助纯类/全员较好/持平图':f'{int(b.pure_better_images)}/{int(b.full_better_images)}/{int(b.tied_images)}'})
    ns=read(OUT/'NATURAL_RECOMPUTED_PATH_STATISTICS.csv');nr=[]
    for pid,g in ns[ns.metric.eq('B8L2')].groupby('pool_id'):
        g=g.set_index('version');a,b=g.loc['automatic'],g.loc['manual_assisted']
        nr.append({'图片/N/k':f'{pid.split("__")[0]}/{int(b.N)}/{int(b.k)}','可评路径':f'{int(a.valid_n)}→{int(b.valid_n)}',
                   '原Q均值':a['mean'],'辅助Q均值':b['mean'],'原P10':a.p10,'辅助P10':b.p10,'原SD':a.sd,'辅助SD':b.sd})
    pp=read(OUT/'POLICY_RECOMPUTED_LATE_SUMMARY.csv');pr=[]
    for vals,g in pp[(pp.difficulty=='全部')&(pp.metric=='paired_Q_delta')].groupby(['version','weighting']):
        g=g.set_index('connection_version');a,b=g.loc['automatic'],g.loc['manual_assisted']
        pr.append({'路径批次':vals[0],'计权':vals[1],'原效应':a.estimate,'辅助效应':b.estimate,
                   '辅助建筑重抽区间':f'[{b.building_lo:.6f}, {b.building_hi:.6f}]','支持图/楼':f'{int(b.images)}/{int(b.buildings)}'})
    facts_rounding=read(OUT/'NATURAL_RESULT_FACTS_NUMERIC_PARITY.csv')
    class_candidate=read(OUT/'CANDIDATE_C1_CLASS_METRIC_ACCEPTANCE.csv');cr=[]
    for label,g in class_candidate.groupby('version'):
        g=g.set_index('connection_version');a,b=g.loc['fixed_coordinates'],g.loc['coordinate_candidate_not_adopted']
        cr.append({'C1 标签快照':label,'原固定坐标支持图数':int(a.valid_images),'未采用候选支持图数':int(b.valid_images),
                   '原固定坐标图均Q':a['mean'],'未采用候选图均Q':b['mean']})
    modulecounts=checks.groupby('module').passed.agg(['size','sum']).reset_index()
    mt=[{'模块':r.module,'检查项':int(r['size']),'通过':int(r['sum'])} for _,r in modulecounts.iterrows()]
    content=f'''# HOHONET v2.1：同房、配比、联盟、人数、旧策略和坐标候选独立验收

## 结论与本轮实际补充

**这些模块不需要新增团队、扩大人数/替换规模或开展新一轮坐标实验。** 本轮从冻结输入及逐事件/逐路径表重新构造关键计算，确认前批辅助结果的支持、计权、配置映射和实际汇总接续。发现的真实缺口是**有限配比辅助标量表中 8 个成员字段的序列化格式**；已经完成两份 CSV 和写入脚本的最小修正。没有改变成员、参考、坐标、类别、评分或统计值。

本报告是当前人工辅助分支的再次验收。下列“原→辅助”数字仍表示原自动实验与固定节点人工顺序分支的差异，**不表示本轮又产生了一轮新效果**。原自动失败继续保留为缺失 Q，未补为 0。

审查基线为 GitHub `Sparkling-Flames/3D_Manhattan_label` 的 `{COMMIT}`。本次来源与运行输入逐文件见 [INPUT_MANIFEST.json](INPUT_MANIFEST.json)，新补取的原始代码/表均保留来源标识和哈希。共 **{len(checks)} 项核查，{int(checks.passed.sum())} 项通过，{len(failed)} 项未通过**；一项表级核查可能覆盖数千行或多个字段，检查项数不是实验样本数。

{markdown_table(mt,['模块','检查项','通过'])}

### 已修正的真实格式缺口

两份 `composition/affected_inputs` 辅助标量表中，rPc6-06 与 uNb9-88 两队的 `member_workers`、`member_object_ids` 原本被写成 Python 列表字符串；原标量契约是管道分隔字符串。两队、两个字段、两个辅助版本，共 8 格。成员内容和排列本来相同，当前配置聚合器实际从固定 `TEAM_REQUESTS.csv.gz` 读取成员，因此该格式问题没有进入前批配置或方差计算。

本轮已把字段恢复为原表达，并修改 `evaluate_manual_order_composition_20261104.py` 的 `prepare`，明确保留这两个原标量字段。修正采用 CSV 文本单元直接替换，**没有浮点再解析**：所有其它数值/字符串单元、列序、行身份与行序逐格一致；不可变的前五批 ZIP 未改动。见 [8 格明细](repairs/MEMBER_FIELD_CELL_CHANGES.csv)、[前后哈希及修正回执](repairs/MEMBER_FIELD_FORMAT_REPAIR.json)、[必须覆盖的三个路径](repairs/OVERLAY_FILES.csv)、[写入脚本补丁](repairs/COMPOSITION_WRITER_FORMAT_FIX.patch)。精确修正前文件保留在 `repairs/pre_acceptance/`。

## 1. 同房 ABC：六端共同支持和分项接续通过

当前 1621 个方法行中，57 端点清单命中 54 行、对应 23 个物理事件与 24 个物理端点；这些复用行不能视为独立新案例。所有受影响事件的每个分项已从原标量和辅助端点重新构造；全表 2610 个版本×条件×指标摘要沿用“事件→XYZ 成员块→物理图对等权”重新核对。

主层为 TARGET_DSTRUCT_K3、C2→C3、10/5。Q 六端共同支持 {int(sr.old_Q6)}→{int(sr.new_Q6)}/{int(sr.events)}，仍为 19 个图对；原已可评事件保持。结果如下。

{markdown_table(room,['指标','原自动原支持','辅助原事件共同支持','辅助扩展支持','扩展后正均值图对'])}

CB 19/19 图对均值为正；跨视角双正仍为 18/19。几何六比较支持 **{int(sr.old_geometry6)}→{int(sr.new_geometry6)}**，原记录劳动六端支持 **{int(sr.old_time6)}→{int(sr.new_time6)}**，Q 与记录劳动联合六端支持 **{int(sr.old_QT6)}→{int(sr.new_QT6)}**。三个分母的含义不同。人工排序耗时未记录，无法评价含该劳动后的完整效率。

12/6 和 14/7 均无端点命中，数值与支持保持。旧注册层保留 62964 事件的原总设计；本轮检查已提取的 2646 个受影响标签层事件、31 个直接命中事件，并从已更新的 8198 配置独立聚合到全部 744 个配对分层。未重新选队。

来源：[Q6 支持](SAME_ROOM_Q6_SUPPORT.csv)、[分项重新计算](SAME_ROOM_RECOMPUTED_METRIC_SUMMARIES.csv.gz)、[三个支持口径](SAME_ROOM_SEPARATE_SUPPORTS.csv)、[核查明细](CHECKS.csv)。

### CSV 浮点读取约定

独立验收最初使用 Pandas 默认浮点 CSV 解析时，25 个非 B8L2 分项 Spearman 单元因近乎并列值的最后几位变化，与原保存摘要不同。换成 `float_precision="round_trip"` 读取**已经写出的 CSV**，这 25 格均与原保存值一致。主 B8L2 指标命中 0 格。证据见 [读取敏感单元](SAME_ROOM_CSV_PARSE_SENSITIVITY.csv)，同时保留默认读取值、无损读取值与原值。

这是验收读回保存文件时的精度问题，不是新队伍进入支持、生产评分改变或新的科学翻向。本轮只规定验收器无损读取，不修改原生产输入读取器，不以这些最后几位的秩差要求重跑实验。

## 2. 有限配比和纯类/联盟：配置、排名、方差通过

有限配比固定两个其它目标面板的 35+10 个原团队和 11 种原冻结标签。逐成员重新构造完整团队类别计数，复核 `method_known` 与 `shared_known`。难度分层取当前目标条件表的 `official_difficulty`，不能误用该表留存的旧 `difficulty` 字段。两新队均属于 `other_admitted`，没有进入主目标域。

所有受影响方差和配置分布已由端点标量重新计算；全体 67 面板的宏统计继续按“面板→池→图→楼”，在宏观方差汇总后形成比例。TARGET_DSTRUCT_K3 配比间方差占比为 **32.439565%→32.534050%**，原可评共同支持保持。新增两个 K3 配比各只有一可评队，SD、IQR 和范围继续缺失；不能以其 0 个成员差异推断配比稳定。

来源：[新团队标签与配置绑定](COMPOSITION_NEW_TEAM_LABEL_BINDINGS.csv)、[新增配比](COMPOSITION_NEW_CONFIGURATIONS.csv)、[面板重算](COMPOSITION_K3_PANEL_ACCEPTANCE.csv)、[宏统计重算](COMPOSITION_K3_MACRO_ACCEPTANCE.csv)。

联盟从 GitHub 原 3160 行表独立核对至辅助全表，逐池重新挑选可评最佳纯类，再按图片等权汇总。当前 414 行落实表仍为 403 可执行、11 容量记录。原可评团队分数、劳动、标签与成员保持；12 个新增处理团队有 19 个引用，其中 17 行新可评，pa4 两个引用在主分支仍无 Q。

{markdown_table(ar,['目标范围','标签快照','原池数→辅助池数','图数','原 full−best-pure','辅助 full−best-pure','辅助纯类/全员较好/持平图'])}

其它目标的翻向必须分清两个机制：uNb9-88 为两个标签快照各增加一个比较池，仍是原 23 张图；wc2-26 的 frozen 快照在原池内扩大可评纯类候选集合，改变最佳纯类选择。原候选集合、原池支持上的结果保持。详见 [分步支持分解](ALLIANCE_SUPPORT_DECOMPOSITION.csv)、[新池与排名变化](ALLIANCE_NEW_SUPPORT_AND_RANK_CHANGES.csv)。updated 的轻微正均值不足以改写为全员稳定占优。

## 3. 人数：两个其它目标小池的实际消费者通过

rPc6-06 的 N=7/k=4 与 uNb9-88 的 N=5/k=3 分别出现于 8 与 25 条既有路径；总计 33 个引用来自两个物理团队。各池 256 条路径、原团队和顺序保持。独立核对使用原路径频数、线性 P10、样本 SD（ddof=1），没有以有限团队等权替换路径分布。

{markdown_table(nr,['图片/N/k','可评路径','原Q均值','辅助Q均值','原P10','辅助P10','原SD','辅助SD'])}

逐 k 表、配对窗口、五个有目标行的 stage03 合表，两个没有目标行的短暂平台/复用置信带合表，以及固定窗口域摘要已核对。stage07 固定面板与每图边际变化中，所有实际变化行的池、图、楼权重重新计算；主目标及其它未命中域逐格保持。`RESULT_FACTS.json` 的结构与非数值字段精确一致；{len(facts_rounding)} 个数值末位差的最大绝对值为 {facts_rounding.absolute_difference.max():.3g}，低于原生产器 `json_numeric_parity` 约定的 1e-10。科学事实保持，无需改写事实表。逐项证据见 [JSON 数值一致性](NATURAL_RESULT_FACTS_NUMERIC_PARITY.csv)。正式 `onset_k` 仍为空；两个 ungated 诊断格的 4→3 不构成平台人数提前的证据。

来源：[路径分母](NATURAL_FROZEN_PATH_SUPPORT.csv)、[逐路径统计](NATURAL_RECOMPUTED_PATH_STATISTICS.csv)、[固定窗口](NATURAL_RECOMPUTED_FIXED_WINDOW_SUMMARY.csv)、[固定面板](NATURAL_RECOMPUTED_CHANGED_FIXED_PANEL_CURVES.csv)、[面板对照](NATURAL_RECOMPUTED_CHANGED_FIXED_PANEL_CONTRASTS.csv)。main-only 几何、结构分项、P10/finite-tail、连续结构和诊断均未扩跑。

## 4. 旧策略：一个前缀及全部实际消费者通过

唯一命中 x8-08 的 N35/k28、new16、`structure_dominant_first` 前缀。其方法身份仍为历史 V3_BEHAVIOR；不能当作当前 DSTRUCT 策略实验。原前缀表、记录劳动、固定 k 支持和路径批次保持；其余 152 池和未命中汇总行逐格保持。

本轮独立重算受影响池的全部 k 指标和固定 k 相位均值，并直接复用前批保存的完整路径抽样，核对 704 行原/辅助后段摘要的点值、路径区间和建筑重抽区间。没有再次运行全库路径抽样、融合或评分。

{markdown_table(pr,['路径批次','计权','原效应','辅助效应','辅助建筑重抽区间','支持图/楼'])}

对应 352 个后段条件组，104 个点值有数值改变；点估计方向、路径区间与建筑区间相对 0 的判定均保持。new16 图片等权区间仍跨 0，pooled32 图片等权区间仍全负，不能互换口径。来源：[重算摘要](POLICY_RECOMPUTED_LATE_SUMMARY.csv)、[逐条件方向/区间验收](POLICY_DIRECTION_AND_INTERVAL_ACCEPTANCE.csv)。

## 5. F2/F9：单独案例隔离通过

独立比较原固定节点与候选状态，仅发现 F2/F9 上下点共 4 个 x 标量改为 438.8037；y、节点身份、支持数、成员、源记录、参考和已确认顺序不变。独立平面检查复核原 1 个严格交叉变为 0、面积非零，但相机仍不满足全部可见核半平面。F2/F9 在底面仍是两个不同节点。

主分支仍为 **56/57 可评分**，pa4 主分支仍 `invalid_floor`。候选 B8L2=39.615619、D10=41.305788 只存在于单列条件分支。50 个 AC 引用和 2 个联盟引用均未把候选混入主结果。对 **full-vs-best-pure 池表及其总体比较**，候选使 pa4 两个标签快照的可评纯类数各增加 1，其 full/best-pure Q、最佳纯类身份和比较支持均保持。

此外，C1 类的条件图均 Q 摘要会因新增可评图而变化。这是另一个真实消费者，不能把前述 full-vs-best-pure 表的有限不变性推广为“整个联盟模块仅计数变化”。本轮分别从固定坐标结果与单列候选分数重新推导这四行：

{markdown_table(cr,['C1 标签快照','原固定坐标支持图数','未采用候选支持图数','原固定坐标图均Q','未采用候选图均Q'])}

来源：[隔离与几何核对](CANDIDATE_ISOLATION.json)、[四个坐标编辑](CANDIDATE_EXACT_COORDINATE_EDITS.csv)、[候选池内纯类支持](CANDIDATE_ALLIANCE_SUPPORT_COUNTS.csv)、[C1 条件图均 Q](CANDIDATE_C1_CLASS_METRIC_ACCEPTANCE.csv)。该候选不成为全库近邻 x 约束或预处理规则，未新增坐标实验。

## 判定、复现和剩余边界

逐条“保持、幅度变化、条件变化、需改写、尚不能判断”见 [CONCLUSIONS.csv](CONCLUSIONS.csv)；真实消费者清单见 [CONSUMER_ACCEPTANCE.csv](CONSUMER_ACCEPTANCE.csv)。本次需要落地的修正已在上文完成，未发现要求增加同房团队、扩大策略池或坐标约束实验的证据。人工排序劳动未记录、57 组定向案例不能代表全体无环结果，这两个限制继续保留。

在前批结果与本补充覆盖层均解压至仓库根目录后运行：

```bash
python -m tools.thesis_main.analysis.audit_manual_order_secondary_acceptance_20261104
```

脚本默认只生成独立验收目录。若从修正前的两份标量与原写入脚本开始复现格式修正，可使用同脚本 `--apply-format-repair`；它仅执行已记录的 8 格与写入规则修正，不重评分。全部新源码、冻结原始文件和必要旧结果的实际读取清单见 [REPRODUCE_INPUTS.csv](REPRODUCE_INPUTS.csv)。
'''
    (OUT/'REPORT_ZH.md').write_text(content,encoding='utf-8')


def save_acceptance(completed_modules,complete=True):
    """Persist evidence after a full run or a targeted acceptance correction."""
    if complete:
        report()
    checks=pd.DataFrame(CHECKS)
    write(checks,'CHECKS.csv');write(pd.DataFrame(CONSUMERS),'CONSUMER_ACCEPTANCE.csv');write(pd.DataFrame(CONCLUSIONS),'CONCLUSIONS.csv')
    register(Path(__file__))
    # Reports may re-read a newly regenerated audit table. Refresh hashes after
    # all writes, retaining the actual input set and its current saved bytes.
    for key in list(INPUTS):
        INPUTS.pop(key)
        register(ROOT/key)
    manifest=pd.DataFrame(INPUTS.values()).sort_values('path')
    manifest['source_class']=np.where(manifest.path.str.contains('/secondary/source/'),'frozen_source_cache',
                              np.where(manifest.path.str.contains('/secondary/repairs/'),'format_repair_evidence',
                              np.where(manifest.path.str.contains('/manual_order_impact_20261104/'),'prior_delivery_or_explicit_format_overlay','audit_code_or_results')))
    write(manifest,'REPRODUCE_INPUTS.csv')
    failed=[x for x in CHECKS if not x['passed']]
    summary=dict(version='v21_manual_order_secondary_independent_acceptance_20261104_v1',source_commit=COMMIT,
        completed_modules=list(completed_modules),checks=len(CHECKS),passed=len(CHECKS)-len(failed),failed=len(failed),
        status='PASS' if not failed else 'FAIL',failed_checks=failed,
        producer_recalculation_required=False,new_teams=0,new_fusions=0,new_geometry_scores=0,new_classification_selection_runs=0,
        format_repair={'csv_files':2,'writer_files':1,'text_cells':8,'all_nonmember_tokens_unchanged':True},
        CSV_float_parser='round_trip; production input readers unchanged',numpy_version=np.__version__,pandas_version=pd.__version__)
    (OUT/'CHECKS.json').write_text(json.dumps(clean(summary),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'INPUT_MANIFEST.json').write_text(json.dumps(dict(source_commit=COMMIT,files=manifest.to_dict('records')),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'README.md').write_text('''# v2.1 次级消费者独立验收

结论、数据与边界见 [REPORT_ZH.md](REPORT_ZH.md)。逐条判定见 [CONCLUSIONS.csv](CONCLUSIONS.csv)，实际消费者见 [CONSUMER_ACCEPTANCE.csv](CONSUMER_ACCEPTANCE.csv)。

- `CHECKS.csv` / `CHECKS.json`：独立数值、支持、计权、版本与原共同支持核查。
- `SAME_ROOM_*`：六端分母、全部分项重派生及保存 CSV 的无损读取证据。
- `COMPOSITION_*` / `ALLIANCE_*`：固定标签/成员、有限面板、池内排名和分层方差。
- `NATURAL_*` / `POLICY_*`：现有路径频数、固定 k、真实汇总消费者与原重抽区间核对。
- `CANDIDATE_*`：F2/F9 候选四个坐标编辑与主分支隔离。
- `repairs/`：8 格成员字段格式修正、三个覆盖路径、前后哈希和精确修正前副本。
- `source/`：冻结 GitHub 原始源文件与来源说明；为离线复现保留。
- `REPRODUCE_INPUTS.csv`：脚本实际读取路径与 SHA-256。需要前五批结果及本补充覆盖层。

运行：`python -m tools.thesis_main.analysis.audit_manual_order_secondary_acceptance_20261104`。本补充不选新队、不重新排序、不重新融合或评分，不进行分类选型。
''',encoding='utf-8')
    print(json.dumps(clean(summary),ensure_ascii=False,indent=2),flush=True)
    if failed:
        raise SystemExit(1)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply-format-repair',action='store_true')
    ap.add_argument('--module',choices=['same_room','composition','alliances','natural','policy','coordinate_candidate'])
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.apply_format_repair:
        repair_composition_member_format()
    # Record the source contracts consulted when deriving these independent
    # formulae, without importing or invoking the original producers.
    for p in [SRC/'aggregate_frozen_panels.py',SRC/'analyze_response.py',SRC/'summarize_response.py',
              SRC/'adopted_policy_functions_20261025.py',SRC/'frozen_inputs/policy/analyze_policy32.py']:
        register(p)
    functions=[same_room,composition,alliances,natural,policy,coordinate_candidate]
    if args.module:
        functions=[f for f in functions if f.__name__==args.module]
    for fn in functions:
        start=len(CHECKS);print('audit',fn.__name__,flush=True);fn()
        current=CHECKS[start:]
        (OUT/(fn.__name__.upper()+'_INDEPENDENT_CHECKS.json')).write_text(json.dumps(clean(current),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(fn.__name__,'checks',len(current),'failed',sum(not x['passed'] for x in current),flush=True)
    if not args.module:
        audit_format_repair()
    save_acceptance([f.__name__ for f in functions],complete=not args.module)


if __name__=='__main__':
    main()






