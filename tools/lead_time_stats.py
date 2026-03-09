# 示例   整个目录
#   python tools/lead_time_stats.py export.json --active-log . 
# 增加了 --project 参数，允许你只统计特定项目的工时：
#   python tools/lead_time_stats.py export.json --active-log . --project 15
"""Utility to compute Label Studio lead_time for HoHoNet experiments.

Usage:
  python tools/lead_time_stats.py path/to/manual.json path/to/semiauto.json
  python tools/lead_time_stats.py /path/to/dir   # process all json files in dir

This script is resilient to Label Studio export layout differences: it will try
both `annotations` and `completions` fields when searching for `lead_time`.
"""
import json
import statistics
from pathlib import Path
from typing import Iterable, List
from collections import defaultdict


def _iter_json_files(paths: Iterable[Path]) -> Iterable[Path]:
    """Expand the provided paths into a list of JSON files.

    For directories, yield all .json files inside. For files, yield the file
    itself if it ends with .json.
    """
    for p in paths:
        if p.is_dir():
            for child in sorted(p.glob("*.json")):
                yield child
        elif p.is_file() and p.suffix.lower() == ".json":
            yield p
        else:
            # Allow non-json file paths but skip them
            continue


def _collect_lead_time_from_task(task: dict) -> List[float]:
    """Return a list of lead_time values found in a task object.

    Label Studio exports may use `annotations` or `completions`. We try both.
    """
    times = []
    for k in ("annotations", "completions"):
        for ann in task.get(k, []):
            lt = ann.get("lead_time")
            if isinstance(lt, (int, float)):
                times.append(lt)
    return times


def avg_lead_time(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and data.get("tasks"):
        tasks = data.get("tasks")
    else:
        # Label Studio exports usually produce a list of tasks at top-level
        tasks = data

    times = []
    for task in tasks:
        times += _collect_lead_time_from_task(task)

    if not times:
        raise RuntimeError(f"No lead_time entries found in {path}")
    
    # also return the mapping task_id -> lead_time (take sum if multiple annotations?)
    task_lead_map = {}
    task_ids = []
    for task in tasks:
        t_id = task.get('id')
        # prefer 'annotations' then 'completions'
        vals = []
        for k in ('annotations', 'completions'):
            for ann in task.get(k, []):
                lt = ann.get('lead_time')
                if isinstance(lt, (int, float)):
                    vals.append(lt)
        if vals:
            # take latest/last one as representative (or sum?) -> choose last
            task_lead_map[str(t_id)] = vals[-1]
        task_ids.append(str(t_id))

    return {
        "count": len(times),
        "total_seconds": sum(times),
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
        "min": min(times),
        "max": max(times),
        "raw_times": times,
        "task_map": task_lead_map,
        "task_ids": task_ids,
    }


def parse_active_log(paths: List[Path], filter_project: str = None):
    """Parse newline-delimited JSON log files and return task_id -> active_seconds.

    Aggregation logic (consistent with analyze_quality.py:load_active_logs):
      1. Per (task_id, annotator_id, session_id) take max active_seconds
         (because the script reports cumulative seconds, not increments).
      2. Per (task_id, annotator_id) sum across sessions
         (to capture multi-session work on the same task).
      3. Per task_id take the *first* annotator's value
         (this script is mainly for quick per-task stats; for multi-annotator
         analysis, use analyze_quality.py:load_active_logs directly).

    If filter_project is provided, only entries with matching project_id are used.
    """
    # Step 1: (task_id, annotator_id, session_id) -> max seconds
    session_maxes = defaultdict(int)

    for path in paths:
        if not path.exists():
            continue
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    o = json.loads(line)
                    tid = str(o.get('task_id', ''))
                    secs = o.get('active_seconds')
                    pid = o.get('project_id')
                    aid = str(o.get('annotator_id', 'unknown'))
                    sid = str(o.get('session_id', 'default'))

                    if not tid or secs is None:
                        continue

                    if filter_project and str(pid) != str(filter_project):
                        continue

                    key = (tid, aid, sid)
                    session_maxes[key] = max(session_maxes[key], int(secs))
                except Exception:
                    continue

    # Step 2: (task_id, annotator_id) -> sum across sessions
    ta_sums = defaultdict(int)
    for (tid, aid, sid), max_sec in session_maxes.items():
        ta_sums[(tid, aid)] += max_sec

    # Step 3: task_id -> take first annotator (or max across annotators)
    mapping = defaultdict(int)
    for (tid, aid), total in ta_sums.items():
        mapping[tid] = max(mapping[tid], total)

    return mapping


def stats_from_values(values: List[float]):
    if not values:
        return None
    return {
        'count': len(values),
        'total_seconds': sum(values),
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'stdev': statistics.stdev(values) if len(values) > 1 else 0.0,
        'min': min(values),
        'max': max(values),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute detailed lead_time stats from Label Studio JSON."
    )
    parser.add_argument(
        "paths", nargs="+", type=Path, help="Paths to JSON export(s) or directories"
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show detailed distribution (min/max/median)",
    )
    parser.add_argument(
        "--active-log",
        type=Path,
        help="Path to active_times.jsonl (optional) to compute active-time stats",
    )
    args = parser.parse_args()

    all_files = list(_iter_json_files(args.paths))
    if not all_files:
        print("No JSON files found in provided paths.")
        raise SystemExit(1)

    print(f"{'File':<30} | {'Count':<5} | {'Total (min)':<12} | {'Mean (s)':<10} | {'Median (s)':<10} | {'Max (s)':<10} | {'Active Mean(s)':<14} | {'Active Median(s)':<16} | {'Active Total(min)':<16}")
    print("-" * 95)

    # optionally parse active logs
    active_map = {}
    if args.active_log:
        if args.active_log.exists():
            active_map = parse_active_log(args.active_log)
        else:
            print(f"Active log file not found: {args.active_log}")

    for path in all_files:
        try:
            stats = avg_lead_time(path)
            total_min = stats['total_seconds'] / 60.0
            # compute active stats for tasks that have active logs
            active_values = []
            for tid in stats.get('task_ids', []):
                val = active_map.get(str(tid))
                if val:
                    active_values.append(int(val))

            active_stats = stats_from_values(active_values) if active_values else None

            active_mean = active_stats['mean'] if active_stats else 0.0
            active_median = active_stats['median'] if active_stats else 0.0
            active_total_min = (active_stats['total_seconds'] / 60.0) if active_stats else 0.0

            print(f"{path.name:<30} | {stats['count']:<5} | {total_min:<12.2f} | {stats['mean']:<10.2f} | {stats['median']:<10.2f} | {stats['max']:<10.2f} | {active_mean:<14.2f} | {active_median:<16.2f} | {active_total_min:<16.2f}")
            
            if args.detail:
                print(f"  -> Distribution (lead_time s): {sorted([round(t,1) for t in stats['raw_times']])}")
                if active_stats:
                    print(f"  -> Distribution (active s): {sorted([round(t,1) for t in active_values])}")
                
        except Exception as e:
            print(f"{path.name:<30} | ERROR: {e}")
