"""Active-time log loading and lookup for analyze_quality."""

from collections import defaultdict
from datetime import datetime
import json
import os

from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files


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


def _parse_active_time_key(value):
    parts = str(value or '').split('|')
    if len(parts) != 4:
        return None
    return tuple(part.strip() for part in parts)


def _annotation_owner(annotation_owner_map, project_id, task_id, annotation_id):
    if not annotation_owner_map or not annotation_id or annotation_id == 'unknown_annotation':
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
                    ann_id = str(data.get('annotation_id', '') or '').strip()
                    alias_from = _parse_active_time_key(data.get('active_time_alias_from'))
                    alias_reason = str(data.get('active_time_alias_reason', '') or '').strip()
                    late_status = str(data.get('late_binding_status', '') or '').strip()
                    owner = _annotation_owner(annotation_owner_map, p_id, t_id, ann_id)
                    if not _same_or_unknown_owner(annotation_owner_map, p_id, t_id, ann_id, a_id):
                        continue
                    if calibration and ann_id and ann_id != 'unknown_annotation' and owner != a_id:
                        continue

                    event = {
                        'project_id': p_id,
                        'task_id': t_id,
                        'annotator_id': a_id,
                        'annotation_id': ann_id,
                        'session_id': s_id,
                        'seconds': sec,
                        'source_file': os.path.basename(fpath),
                        'alias_from': alias_from,
                        'alias_reason': alias_reason,
                        'late_status': late_status,
                        'event_dt': event_dt,
                    }
                    parsed_events.append(event)
                    if ann_id and ann_id != 'unknown_annotation':
                        actual_annotations_by_context[(p_id, t_id, a_id, s_id)].add(ann_id)
                    elif ann_id == 'unknown_annotation':
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
            if calibration and event['annotation_id'] == 'unknown_annotation':
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
    for event in parsed_events:
        context = (event['project_id'], event['task_id'], event['annotator_id'])
        if event['annotation_id'] == 'unknown_annotation':
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
            'active_time_exclusion_reason': 'unknown_annotation_audit_only' if unknown_sessions else '',
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
            'active_time_exclusion_reason': 'unknown_annotation_audit_only',
            'audit_only': True,
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
