#!/usr/bin/env python3
"""One final population aggregation after all 194 frozen pools have finished.

This never starts fusion or adds samples. Partial completion order cannot
trigger population summaries. Each completed step is saved atomically.
"""
from pathlib import Path
import argparse, json, subprocess, sys, time
from precision_core import save_json


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--wait', action='store_true')
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args(); root = args.root.resolve()
    owner = root / 'analysis_precision26'; out = owner / 'results_stage2'
    complete = out / 'WATCH_COMPLETE.json'
    while not complete.exists():
        if not args.wait:
            raise RuntimeError('All frozen stage2 pools are not complete; no partial population aggregation')
        time.sleep(30)
    receipt = json.loads(complete.read_text())
    assert receipt['complete'] and receipt['pools'] == 194
    steps = [
        ('components', 'refresh_components.py', ['--stage', '2']),
        ('compile', 'analyze_natural.py', ['--stage', '2', '--resume', '--compile-only']),
        ('summaries', 'summarize_natural.py', ['--stage', '2']),
        ('exact', 'exact_anchor_and_display.py', ['--stage', '2']),
        ('figures', 'plot_natural_precision.py', ['--stage', '2'])]
    for name, script, arguments in steps:
        marker = out / ('FINAL_STEP_' + name.upper() + '.json')
        if args.resume and marker.exists() and json.loads(marker.read_text()).get('returncode') == 0:
            continue
        command = [sys.executable, str(owner / script), '--root', str(root)] + arguments
        started = time.time()
        result = subprocess.run(command, text=True, capture_output=True)
        save_json(dict(step=name, command=command, returncode=result.returncode,
                       wall_seconds=time.time() - started, stdout_tail=result.stdout[-12000:],
                       stderr_tail=result.stderr[-12000:], completed_unix=time.time()), marker)
        if result.returncode:
            raise RuntimeError(name + ' failed; read ' + str(marker))
    save_json(dict(complete=True, pools=194, new_fusion=False, steps=[x[0] for x in steps],
                   completed_unix=time.time(), figures='analysis_precision26/figures_stage2'),
              out / 'NATURAL_FINALIZATION_COMPLETE.json')


if __name__ == '__main__':
    main()
