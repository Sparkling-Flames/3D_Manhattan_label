#!/usr/bin/env python3
"""Checkpoint completed new-pool shards while independent native fusion runs.

No inference is made from completion order. No output-dependent stopping or
additional seed selection is performed. The watcher stops after all frozen
eligible pools have their stage inputs and complete analysis checkpoints.
"""
from pathlib import Path
import argparse, json, subprocess, sys, time
from precision_core import save_json, METRICS, IMETRICS


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--stage", type=int, choices=[1, 2], required=True)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--interval-seconds", type=int, default=30)
    args = ap.parse_args(); root = args.root.resolve()
    owner = root / "analysis_precision26"
    out = owner / ("results_stage" + str(args.stage)); out.mkdir(parents=True, exist_ok=True)
    pids = json.loads((owner / "prior_pool_cache/READY.json").read_text())["pool_ids"]
    def valid_done(pid):
        p = out / "pool_checkpoints" / (pid + "__DONE.json")
        if not p.exists():
            return False
        d = json.loads(p.read_text())
        return (d.get("metric_names") == METRICS and d.get("interval_metric_names") == IMETRICS
                and d["bootstrap"] == args.bootstrap
                and (out / "pool_checkpoints" / (pid + "__path_strata.csv.gz")).exists())
    while True:
        ready = [pid for pid in pids if all((root / "new_endpoints26" / ("stage" + str(stage)) /
                 "prefix_values" / (pid + ".csv.gz")).exists() for stage in range(1, args.stage + 1))]
        done = [pid for pid in ready if valid_done(pid)]
        if len(done) < len(ready):
            command = [sys.executable, str(owner / "analyze_natural.py"), "--root", str(root),
                       "--stage", str(args.stage), "--bootstrap", str(args.bootstrap),
                       "--ready-only", "--resume", "--no-compile"]
            result = subprocess.run(command, capture_output=True, text=True)
            save_json(dict(stage=args.stage, ready_at_start=len(ready), previously_done=len(done),
                           eligible_pools=len(pids), returncode=result.returncode,
                           stdout_tail=result.stdout[-8000:], stderr_tail=result.stderr[-8000:],
                           unix_timestamp=time.time(), provisional_completion_order_not_population_sample=True),
                      out / "WATCH_STATUS.json")
            if result.returncode:
                raise SystemExit(result.returncode)
            done = [pid for pid in ready if valid_done(pid)]
        if len(ready) == len(pids) and len(done) == len(pids):
            command = [sys.executable, str(owner / "analyze_natural.py"), "--root", str(root),
                       "--stage", str(args.stage), "--bootstrap", str(args.bootstrap), "--resume", "--compile-only"]
            subprocess.run(command, check=True)
            save_json(dict(stage=args.stage, pools=len(pids), complete=True, unix_timestamp=time.time()),
                      out / "WATCH_COMPLETE.json")
            return
        time.sleep(min(60, max(1, args.interval_seconds)))


if __name__ == "__main__":
    main()
