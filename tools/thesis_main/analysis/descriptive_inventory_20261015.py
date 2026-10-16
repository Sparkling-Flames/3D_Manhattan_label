"""读取当前人员库存并绑定冻结的有效时间，不重建输入、不修改历史秒数。"""
import math
from pathlib import Path

import pandas as pd

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from .worker_behavior_time_20260910 import adjusted_time_keys, clean_time
from .worker_classification_progress_20261014 import historical_worker

ROOT = Path(__file__).resolve().parents[3]
TIME_FACTS = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts'


def inventory_rows(objects, timing_rows, spine_rows, adjusted_keys):
    """按项目/运行任务/人员连接；历史 canonical 身份另核对图、建筑及条件。"""
    spine = {r['canonical_annotation_id']: r for r in spine_rows}
    if len(spine) != len(spine_rows):
        raise ValueError('duplicate historical canonical annotation')
    times = {}
    for row in timing_rows:
        key = (row['project_id'], row['runtime_task_id'], historical_worker(row['worker_id']))
        if key in times:
            raise ValueError('duplicate historical task/person timing key')
        if row['canonical_annotation_id'] not in spine:
            raise ValueError('historical time missing annotation spine')
        times[key] = row
    frame = pd.DataFrame(timing_rows)
    if timing_rows:
        frame['active_time_seconds'] = pd.to_numeric(frame.active_time_seconds.replace('', float('nan')))
    flags = clean_time(frame).tolist() if timing_rows else []
    eligible = {r['canonical_annotation_id']: bool(flag) for r, flag in zip(timing_rows, flags)}
    result, seen = [], set()
    for obj in objects:
        if obj['object_kind'] != 'annotation':
            continue
        oid = obj['object_id']
        if oid in seen:
            raise ValueError('duplicate inventory object_id')
        seen.add(oid)
        source = obj['source']
        key = (str(source['project']), str(source['task']), obj['worker_id'])
        old = times.get(key)
        time = dict(active_time_seconds=None, raw_active_time_seconds=None,
            time_status=('new_collection_time_unfrozen' if oid.startswith('new_')
                         else 'not_in_historical_table'), time_source='', timing_status='',
            time_source_file='', time_rule_version='', time_stage='', time_binding='unbound',
            historical_canonical_annotation_id='')
        if old is not None:
            identity = spine[old['canonical_annotation_id']]
            if (identity['image_id'], identity['building_id'], historical_worker(identity['worker_id']),
                identity['raw_condition'], identity['project_id'], identity['runtime_task_id']) != (
                obj['image_id'], obj['building_id'], obj['worker_id'], obj['condition'], *key[:2]):
                raise ValueError('time identity mismatch: ' + oid)
            raw = old['active_time_seconds']
            seconds = float(raw) if raw != '' else None
            raw_key = (key[0], key[1], str(int(obj['worker_id'][1:])))
            status = ('known_manual_adjustment' if raw_key in adjusted_keys else
                      'lead_time_fallback' if old['active_time_source'] == 'lead_time_fallback' else
                      'usable' if eligible[old['canonical_annotation_id']] else 'historical_time_ineligible')
            if status == 'usable' and (not old['active_time_source_file'] or seconds is None
                                       or not math.isfinite(seconds) or seconds <= 0):
                raise ValueError('invalid usable active time source: ' + oid)
            time = dict(active_time_seconds=seconds if status == 'usable' else None,
                raw_active_time_seconds=seconds if seconds is not None and math.isfinite(seconds) else None,
                time_status=status, time_source=old['active_time_source'], timing_status=old['timing_status'],
                time_source_file=old['active_time_source_file'], time_rule_version=old['timing_rule_version'],
                time_stage=old['stage'], time_binding='project_task_worker_and_image_matched',
                historical_canonical_annotation_id=old['canonical_annotation_id'])
        collection=obj.get('collection_active_time')
        if collection and collection['adopted']:
            expected=f"{source['project']}|{source['task']}|{source['source_account_id']}"
            if old is not None or str(source['project'])!='98' or collection['identity_key']!=expected:
                raise ValueError('admitted time identity mismatch: '+oid)
            seconds=collection['seconds']
            if not math.isfinite(seconds) or seconds<=0:raise ValueError('invalid admitted active time: '+oid)
            time.update(active_time_seconds=seconds,raw_active_time_seconds=seconds,time_status='usable',
                time_source='active_log_v10_admitted',timing_status='project+task+annotator',
                time_source_file=collection['source_audit'],time_rule_version=collection['rule'],
                time_stage='project98_admitted',time_binding='project_task_worker_and_image_matched')
        result.append(dict(record_id=oid, object_id=oid, **{k: obj[k] for k in (
            'image_id', 'image_code', 'worker_id', 'building_id', 'room_id', 'condition',
            'canonical_unit', 'person_image_unit', 'independent_vote_eligible', 'independent_vote_reasons',
            'cleaning_disposition', 'worker_quality_gate', 'main_quality_gate', 'main_consensus_gate',
            'preprocessing_status', 'ring_confirmed')}, geometry_status=obj['geometry']['status'],
            project_id=key[0], runtime_task_id=key[1], raw_annotation_id=str(source['annotation']),
            source_path=source['path'], time_context_source=collection['source_audit'] if collection and collection['adopted'] else str(TIME_FACTS.relative_to(ROOT) / 'active_time_context.csv.gz'),
            **time))
    return result


def load_inventory(bundle=None):
    """返回全部人员记录；有效时间与原秒数分列，缺失及不合格不补0。"""
    if bundle is None:
        bundle = load_current_bundle()
    dtype = {'worker_id': str, 'project_id': str, 'runtime_task_id': str}
    timing = pd.read_csv(TIME_FACTS / 'active_time_context.csv.gz', keep_default_na=False, dtype=dtype)
    spine = pd.read_csv(TIME_FACTS / 'annotation_spine.csv.gz', keep_default_na=False, dtype=dtype)
    return inventory_rows(bundle['data']['objects'], timing.to_dict('records'),
                          spine.to_dict('records'), adjusted_time_keys())
