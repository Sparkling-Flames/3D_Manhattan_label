"""Active-time log loading and lookup for analyze_quality."""

from collections import defaultdict
from datetime import datetime
import json
import os

from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files


def is_unknown_annotation_id(value) -> bool:
    return value is None or str(value).strip().casefold() in {"", "unknown", "unknown_annotation", "none", "null"}


def _is_explicit_false(value) -> bool:
    return value is False or str(value).strip().casefold() in {"false", "0"}


def _parse_cli_datetime(value, *, is_end=False):
    """Parse an ISO date/datetime CLI bound for active-log filtering."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        suffix = "T23:59:59.999999" if is_end else "T00:00:00"
        text = f"{text}{suffix}"
    text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _parse_active_log_event_time(data):
    """Return server event time, falling back to client timestamp milliseconds."""
    server_received_at = data.get("server_received_at")
    if server_received_at:
        try:
            text = str(server_received_at).strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except Exception:
            return None
    timestamp = data.get("timestamp")
    if timestamp not in (None, ""):
        try:
            value = float(timestamp)
            if value > 10_000_000_000:
                value = value / 1000.0
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    return None


def cumulative_active_intervals(events):
    """Allocate only monotone adjacent cumulative deltas with one stable annotation."""
    ordered = sorted((row for row in events if row.get("event_time")), key=lambda row: row["event_time"])
    intervals = []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.get("annotation_id") != current.get("annotation_id"):
            continue
        if any(str(row.get("page_gate_reason") or "").strip() not in {"", "eligible"} for row in (previous, current)):
            continue
        before, after = float(previous.get("active_seconds") or 0), float(current.get("active_seconds") or 0)
        delta = after - before
        if delta <= 0:
            continue
        end = datetime.fromisoformat(current["event_time"])
        intervals.append((end.timestamp() - delta, end.timestamp()))
    return intervals


def merged_interval_seconds(intervals):
    total, end = 0.0, None
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += stop - start
            end = stop
        elif stop > end:
            total += stop - end
            end = stop
    return total


def _parse_active_time_key(value):
    parts = str(value or '').split('|')
    if len(parts) != 4:
        return None
    return tuple(part.strip() for part in parts)


def _annotation_owner(annotation_owner_map, project_id, task_id, annotation_id):
    if not annotation_owner_map or is_unknown_annotation_id(annotation_id):
        return None
    for key in (
        (project_id, task_id, annotation_id),
        (task_id, annotation_id),
        annotation_id,
    ):
        if key in annotation_owner_map:
            owner = str(annotation_owner_map[key] or '').strip()
            return owner or None
    return None


def _same_or_unknown_owner(annotation_owner_map, project_id, task_id, annotation_id, annotator_id):
    owner = _annotation_owner(annotation_owner_map, project_id, task_id, annotation_id)
    return owner is None or owner == str(annotator_id)


def _event_key(event, annotation_id=None):
    return (
        event['project_id'],
        event['task_id'],
        event['annotator_id'],
        event['annotation_id'] if annotation_id is None else annotation_id,
        event['session_id'],
    )


def _is_short_bootstrap_alias(event):
    return (
        event['alias_from']
        and event['alias_reason'] in {'short_unknown_bootstrap', 'unknown_annotation_late_bound'}
        and event['late_status'] in {'short_unknown_bootstrap_merged', 'single_actual_annotation'}
    )


def load_active_logs(log_dir, start_time=None, end_time=None, annotation_owner_map=None, policy='general'):
    """
    Load active time logs from a directory of JSONL files.
    Logic: max within a session, sum across sessions.

    Returns:
      dict[(project_id, task_id, annotator_id)] -> {
        active_time_value,
        active_time_source_file,
        active_time_session_count,
        active_time_event_count,
      }

      When logs include annotation_id, annotation-level keys are also emitted:
      dict[(project_id, task_id, annotator_id, annotation_id)] -> same fields.

      For backward compatibility, a legacy (task_id, annotator_id) key is also
      emitted only when the pair maps to exactly one project_id. If the same
      pair appears under multiple projects, the legacy key is deliberately
      omitted and an ("__ambiguous__", task_id, annotator_id) audit marker is
      emitted instead.
    """
    session_maxes = defaultdict(float)
    session_files = defaultdict(set)
    session_events = defaultdict(int)
    alias_superseded_session_keys = set()
    actual_annotations_by_context = defaultdict(set)
    unknown_events_by_context = defaultdict(list)
    parsed_events = []
    calibration = policy == 'calibration'
    start_dt = _parse_cli_datetime(start_time) if start_time else None
    end_dt = _parse_cli_datetime(end_time, is_end=True) if end_time else None

    if not log_dir or not os.path.exists(log_dir):
        return {}

    resolved_dir, resolved_files = resolve_active_log_files(log_dir)
    files = [str(path) for path in resolved_files]
    print(f"Found {len(files)} log files in {resolved_dir or log_dir}")

    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    event_dt = _parse_active_log_event_time(data)
                    if start_dt or end_dt:
                        if event_dt is None:
                            continue
                        if start_dt and event_dt < start_dt:
                            continue
                        if end_dt and event_dt > end_dt:
                            continue

                    t_id = str(data.get('task_id'))
                    a_id = str(data.get('annotator_id', 'unknown'))
                    s_id = str(data.get('session_id', 'default'))
                    p_id = str(data.get('project_id', '') or '').strip()
                    sec = float(data.get('active_seconds', 0))
                    annotation_present = 'annotation_id' in data
                    raw_ann_id = data.get('annotation_id')
                    annotation_unknown = annotation_present and is_unknown_annotation_id(raw_ann_id)
                    ann_id = 'unknown_annotation' if annotation_unknown else str(raw_ann_id or '').strip()
                    alias_from = _parse_active_time_key(data.get('active_time_alias_from'))
                    alias_reason = str(data.get('active_time_alias_reason', '') or '').strip()
                    late_status = str(data.get('late_binding_status', '') or '').strip()
                    owner = _annotation_owner(annotation_owner_map, p_id, t_id, ann_id)
                    if not _same_or_unknown_owner(annotation_owner_map, p_id, t_id, ann_id, a_id):
                        continue
                    if calibration and ann_id and not annotation_unknown and owner != a_id:
                        continue

                    event = {
                        'project_id': p_id,
                        'task_id': t_id,
                        'annotator_id': a_id,
                        'annotation_id': ann_id,
                        'annotation_unknown': annotation_unknown,
                        'session_id': s_id,
                        'seconds': sec,
                        'source_file': os.path.basename(fpath),
                        'alias_from': alias_from,
                        'alias_reason': alias_reason,
                        'late_status': late_status,
                        'event_dt': event_dt,
                        'page_gate_eligible': data.get('page_gate_eligible'),
                        'page_gate_reason': str(data.get('page_gate_reason', '') or '').strip(),
                        'page_gate_sources': str(data.get('page_gate_sources', '') or '').strip(),
                        'script_version': str(data.get('script_version', '') or '').strip(),
                        'location_path': str(data.get('location_path', '') or '').strip(),
                        'route_task_id': str(data.get('resolved_route_task_id', '') or '').strip(),
                        'dom_task_id': str(data.get('resolved_dom_task_id', '') or '').strip(),
                        'store_task_ids': str(data.get('store_task_ids', '') or '').strip(),
                        'store_task_match_status': str(data.get('store_task_match_status', '') or '').strip(),
                        'store_mismatch_present': data.get('store_mismatch_present'),
                        'labeling_root_present': data.get('labeling_root_present'),
                        'editor_dom_present': data.get('annotation_editor_dom_present'),
                        'main_view_dom_present': data.get('annotation_main_view_dom_present'),
                    }
                    parsed_events.append(event)
                    if ann_id and not annotation_unknown:
                        actual_annotations_by_context[(p_id, t_id, a_id, s_id)].add(ann_id)
                    else:
                        unknown_events_by_context[(p_id, t_id, a_id, s_id)].append(event)
                except Exception:
                    pass

    def can_merge_short_unknown(event):
        if not _is_short_bootstrap_alias(event):
            return False
        alias_p, alias_t, alias_a, alias_ann = event['alias_from']
        if alias_ann != 'unknown_annotation':
            return False
        if (alias_p, alias_t, alias_a) != (event['project_id'], event['task_id'], event['annotator_id']):
            return False
        if event['seconds'] > 5 or event['event_dt'] is None:
            return False
        context = (event['project_id'], event['task_id'], event['annotator_id'], event['session_id'])
        if actual_annotations_by_context[context] != {event['annotation_id']}:
            return False
        if not _same_or_unknown_owner(
            annotation_owner_map,
            event['project_id'],
            event['task_id'],
            event['annotation_id'],
            event['annotator_id'],
        ):
            return False
        unknown_events = unknown_events_by_context.get(context, [])
        if not unknown_events:
            return event['alias_reason'] == 'short_unknown_bootstrap'
        for unknown_event in unknown_events:
            if unknown_event['event_dt'] is None:
                continue
            delta = (event['event_dt'] - unknown_event['event_dt']).total_seconds()
            if 0 <= delta <= 10 and unknown_event['seconds'] <= 5:
                return True
        return False

    for event in parsed_events:
        try:
            if calibration and event['annotation_unknown']:
                continue
            key = _event_key(event)
            if not calibration and _is_short_bootstrap_alias(event):
                alias_p, alias_t, alias_a, alias_ann = event['alias_from']
                if can_merge_short_unknown(event):
                    alias_superseded_session_keys.add((alias_p, alias_t, alias_a, alias_ann, event['session_id']))
                else:
                    key = _event_key(event, alias_ann)
            if event['seconds'] > session_maxes[key]:
                session_maxes[key] = event['seconds']
            session_files[key].add(event['source_file'])
            session_events[key] += 1
        except Exception:
            pass

    final_logs = defaultdict(lambda: {
        'active_time_value': 0.0,
        'active_time_source_file': set(),
        'active_time_session_count': 0,
        'active_time_event_count': 0,
        'active_time_project_ids': set(),
    })
    unknown_audit = defaultdict(lambda: {'seconds_by_session': defaultdict(float), 'event_count': 0, 'known_sessions': set()})
    page_gate_audit = defaultdict(lambda: {
        'reasons': set(),
        'sources': set(),
        'script_versions': set(),
        'ineligible_events': 0,
        'location_paths': set(),
        'route_task_ids': set(),
        'dom_task_ids': set(),
        'store_task_ids': set(),
        'store_match_statuses': set(),
        'store_mismatch_events': 0,
        'labeling_root_missing_events': 0,
        'editor_missing_events': 0,
        'main_view_missing_events': 0,
    })
    for event in parsed_events:
        context = (event['project_id'], event['task_id'], event['annotator_id'])
        gate_audit = page_gate_audit[context]
        if event['page_gate_reason']:
            gate_audit['reasons'].add(event['page_gate_reason'])
        if event['page_gate_sources']:
            gate_audit['sources'].add(event['page_gate_sources'])
        if event['script_version']:
            gate_audit['script_versions'].add(event['script_version'])
        if _is_explicit_false(event['page_gate_eligible']):
            gate_audit['ineligible_events'] += 1
        if event['location_path']:
            gate_audit['location_paths'].add(event['location_path'])
        if event['route_task_id']:
            gate_audit['route_task_ids'].add(event['route_task_id'])
        if event['dom_task_id']:
            gate_audit['dom_task_ids'].add(event['dom_task_id'])
        if event['store_task_ids']:
            gate_audit['store_task_ids'].update(
                task_id.strip()
                for task_id in event['store_task_ids'].split(';')
                if task_id.strip()
            )
        if event['store_task_match_status']:
            gate_audit['store_match_statuses'].add(event['store_task_match_status'])
        if _is_explicit_false(event['store_mismatch_present']):
            pass
        elif event['store_mismatch_present'] is not None:
            gate_audit['store_mismatch_events'] += 1
        if _is_explicit_false(event['labeling_root_present']):
            gate_audit['labeling_root_missing_events'] += 1
        if _is_explicit_false(event['editor_dom_present']):
            gate_audit['editor_missing_events'] += 1
        if _is_explicit_false(event['main_view_dom_present']):
            gate_audit['main_view_missing_events'] += 1
        if event['annotation_unknown']:
            audit = unknown_audit[context]
            audit['seconds_by_session'][event['session_id']] = max(audit['seconds_by_session'][event['session_id']], event['seconds'])
            audit['event_count'] += 1
        else:
            unknown_audit[context]['known_sessions'].add(event['session_id'])
    for (p_id, t_id, a_id, ann_id, _s_id), max_sec in session_maxes.items():
        if (p_id, t_id, a_id, ann_id, _s_id) in alias_superseded_session_keys:
            continue
        bucket = final_logs[(p_id, t_id, a_id)]
        bucket['active_time_value'] += max_sec
        bucket['active_time_source_file'].update(session_files[(p_id, t_id, a_id, ann_id, _s_id)])
        bucket['active_time_session_count'] += 1
        bucket['active_time_event_count'] += session_events[(p_id, t_id, a_id, ann_id, _s_id)]
        if p_id:
            bucket['active_time_project_ids'].add(p_id)

        if ann_id:
            ann_bucket = final_logs[(p_id, t_id, a_id, ann_id)]
            ann_bucket['active_time_value'] += max_sec
            ann_bucket['active_time_source_file'].update(session_files[(p_id, t_id, a_id, ann_id, _s_id)])
            ann_bucket['active_time_session_count'] += 1
            ann_bucket['active_time_event_count'] += session_events[(p_id, t_id, a_id, ann_id, _s_id)]
            if p_id:
                ann_bucket['active_time_project_ids'].add(p_id)

    serialized = {}
    for key, value in final_logs.items():
        context = key[:3]
        audit = unknown_audit[context]
        gate_audit = page_gate_audit[context]
        unknown_sessions = set(audit['seconds_by_session'])
        serialized[key] = {
            'active_time_value': float(value['active_time_value']),
            'active_time_source_file': ";".join(sorted(value['active_time_source_file'])),
            'active_time_session_count': int(value['active_time_session_count']),
            'active_time_event_count': int(value['active_time_event_count']),
            'active_time_project_ids': ";".join(sorted(value['active_time_project_ids'])),
            'unassigned_active_time_seconds': float(sum(audit['seconds_by_session'].values())),
            'unknown_annotation_event_count': int(audit['event_count']),
            'unknown_annotation_session_count': len(unknown_sessions),
            'known_unknown_oscillation_flag': bool(unknown_sessions & audit['known_sessions']),
            'unassigned_audit_present': bool(unknown_sessions),
            'unassigned_active_time_exclusion_reason': 'unknown_annotation_audit_only' if unknown_sessions else '',
            'active_time_page_gate_reasons': ';'.join(sorted(gate_audit['reasons'])),
            'active_time_page_gate_sources': ';'.join(sorted(gate_audit['sources'])),
            'active_time_script_versions': ';'.join(sorted(gate_audit['script_versions'])),
            'active_time_page_gate_ineligible_event_count': int(gate_audit['ineligible_events']),
            'active_time_location_paths': ';'.join(sorted(gate_audit['location_paths'])),
            'active_time_route_task_ids': ';'.join(sorted(gate_audit['route_task_ids'])),
            'active_time_dom_task_ids': ';'.join(sorted(gate_audit['dom_task_ids'])),
            'active_time_store_task_ids': ';'.join(sorted(gate_audit['store_task_ids'])),
            'active_time_store_match_statuses': ';'.join(sorted(gate_audit['store_match_statuses'])),
            'active_time_store_mismatch_event_count': int(gate_audit['store_mismatch_events']),
            'active_time_labeling_root_missing_event_count': int(gate_audit['labeling_root_missing_events']),
            'active_time_editor_missing_event_count': int(gate_audit['editor_missing_events']),
            'active_time_main_view_missing_event_count': int(gate_audit['main_view_missing_events']),
        }

    for context, audit in unknown_audit.items():
        unknown_sessions = set(audit['seconds_by_session'])
        if not unknown_sessions:
            continue
        serialized[("__unknown_audit__", *context)] = {
            'unassigned_active_time_seconds': float(sum(audit['seconds_by_session'].values())),
            'unknown_annotation_event_count': int(audit['event_count']),
            'unknown_annotation_session_count': len(unknown_sessions),
            'known_unknown_oscillation_flag': bool(unknown_sessions & audit['known_sessions']),
            'unassigned_audit_present': True,
            'unassigned_active_time_exclusion_reason': 'unknown_annotation_audit_only',
            'audit_only': True,
            'active_time_page_gate_reasons': ';'.join(sorted(page_gate_audit[context]['reasons'])),
            'active_time_page_gate_sources': ';'.join(sorted(page_gate_audit[context]['sources'])),
            'active_time_script_versions': ';'.join(sorted(page_gate_audit[context]['script_versions'])),
            'active_time_page_gate_ineligible_event_count': int(page_gate_audit[context]['ineligible_events']),
            'active_time_location_paths': ';'.join(sorted(page_gate_audit[context]['location_paths'])),
            'active_time_route_task_ids': ';'.join(sorted(page_gate_audit[context]['route_task_ids'])),
            'active_time_dom_task_ids': ';'.join(sorted(page_gate_audit[context]['dom_task_ids'])),
            'active_time_store_task_ids': ';'.join(sorted(page_gate_audit[context]['store_task_ids'])),
            'active_time_store_match_statuses': ';'.join(sorted(page_gate_audit[context]['store_match_statuses'])),
            'active_time_store_mismatch_event_count': int(page_gate_audit[context]['store_mismatch_events']),
            'active_time_labeling_root_missing_event_count': int(page_gate_audit[context]['labeling_root_missing_events']),
            'active_time_editor_missing_event_count': int(page_gate_audit[context]['editor_missing_events']),
            'active_time_main_view_missing_event_count': int(page_gate_audit[context]['main_view_missing_events']),
        }

    by_legacy_pair = defaultdict(list)
    for key, value in final_logs.items():
        if len(key) != 3:
            continue
        p_id, t_id, a_id = key
        by_legacy_pair[(t_id, a_id)].append((p_id, value))

    for (t_id, a_id), project_values in by_legacy_pair.items():
        project_ids = sorted({p_id for p_id, _value in project_values if p_id})
        if len(project_ids) <= 1:
            p_id, _value = project_values[0]
            serialized[(t_id, a_id)] = serialized[(p_id, t_id, a_id)]
        else:
            serialized[("__ambiguous__", t_id, a_id)] = {
                'active_time_project_ids': ";".join(project_ids),
                'active_time_value': 0.0,
                'active_time_source_file': "",
                'active_time_session_count': 0,
                'active_time_event_count': 0,
            }
    return serialized


def lookup_active_log_entry(active_times, project_id, task_id, annotator_id, annotation_id=None, allow_task_level_fallback=True):
    """Return a project-safe active log match and its match status."""
    p_id = str(project_id or '').strip()
    t_id = str(task_id)
    a_id = str(annotator_id)
    ann_id = str(annotation_id or '').strip()

    if p_id:
        if ann_id:
            exact_annotation = active_times.get((p_id, t_id, a_id, ann_id))
            if exact_annotation:
                return exact_annotation, 'project+task+annotator+annotation'
            if not allow_task_level_fallback:
                return None, 'annotation_missing_task_level_ambiguous'

        if not allow_task_level_fallback:
            return None, 'annotation_missing_task_level_ambiguous'

        exact = active_times.get((p_id, t_id, a_id))
        if exact:
            return exact, 'project+task+annotator'

        ambiguous = active_times.get(("__ambiguous__", t_id, a_id))
        if ambiguous:
            return None, 'project_mismatch_ambiguous_active_log'

        legacy = active_times.get((t_id, a_id))
        legacy_projects = str((legacy or {}).get('active_time_project_ids', '') or '').strip()
        if legacy and not legacy_projects:
            return legacy, 'task+annotator_legacy_no_project'
        if legacy:
            return None, 'project_mismatch_no_direct_log'
        return None, 'missing'

    legacy = active_times.get((t_id, a_id))
    if legacy:
        return legacy, 'task+annotator_unique_project_fallback'
    if active_times.get(("__ambiguous__", t_id, a_id)):
        return None, 'ambiguous_project_log_no_match'
    return None, 'missing'


def lookup_unknown_active_time_audit(active_times, project_id, task_id, annotator_id):
    return active_times.get(("__unknown_audit__", str(project_id or '').strip(), str(task_id), str(annotator_id)), {})
