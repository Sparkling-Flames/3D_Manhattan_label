#!/usr/bin/env python3
"""
Split active log jsonl files into a new folder by selection criteria.
Usage examples:
  # split by script_version
  python tools/split_active_logs.py --src active_logs/active_logs --dst active_logs/new_server --version 0.22

  # split by date (ISO date or YYYY-MM-DD): select records on/after cutoff
  python tools/split_active_logs.py --src active_logs/active_logs --dst active_logs/new_server --since 2026-02-28

This script will:
- read all active_times_*.jsonl under --src
- write matching records (one-per-line JSON) into per-day files under --dst (same filename)
- leave originals untouched (it makes a small manifest report)
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--src', required=True)
    p.add_argument('--dst', required=True)
    p.add_argument('--version', help='script_version to select, e.g. 0.22')
    p.add_argument('--since', help='ISO date cutoff (inclusive), e.g. 2026-02-28')
    p.add_argument('--dry-run', action='store_true')
    return p.parse_args()


def record_matches(r, version, since_ts):
    if version is not None:
        if str(r.get('script_version','')) != str(version):
            return False
    if since_ts is not None:
        ts = r.get('timestamp')
        if ts is None:
            return False
        try:
            if int(ts) < since_ts:
                return False
        except Exception:
            return False
    return True


def main():
    args = parse_args()
    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    since_ts = None
    if args.since:
        # treat as start of day UTC
        dt = datetime.fromisoformat(args.since)
        since_ts = int(dt.timestamp()) * 1000

    files = sorted(src.glob('active_times_*.jsonl'))
    total_in = 0
    total_out = 0
    per_file_out = {}

    for f in files:
        out_lines = []
        txt = f.read_text(encoding='utf-8')
        for line in txt.splitlines():
            line=line.strip()
            if not line:
                continue
            total_in += 1
            try:
                r = json.loads(line)
            except Exception:
                continue
            if record_matches(r, args.version, since_ts):
                out_lines.append(json.dumps(r, ensure_ascii=False))
        if out_lines:
            out_path = dst / f.name
            if args.dry_run:
                per_file_out[str(out_path)] = len(out_lines)
            else:
                with out_path.open('a', encoding='utf-8') as wf:
                    wf.write('\n'.join(out_lines) + '\n')
                per_file_out[str(out_path)] = len(out_lines)
                total_out += len(out_lines)

    print(f"Processed {len(files)} files, scanned {total_in} records")
    print(f"Wrote {total_out} records into {dst} (dry-run={args.dry_run})")
    if per_file_out:
        print('Per-file counts:')
        for k,v in per_file_out.items():
            print(f'  {k}: {v}')

if __name__=='__main__':
    main()
