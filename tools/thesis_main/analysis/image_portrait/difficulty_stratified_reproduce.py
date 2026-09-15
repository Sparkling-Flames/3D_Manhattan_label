"""Reproduce the delivered numerical analysis without images or model weights.

Run in a copy of the extracted delivery. Existing archived v1/v2 outputs are
read-only. --refit preserves the present fit cache under a timestamped directory
before making new fits. No network request or visual inference is performed.
"""
from __future__ import annotations
import argparse, datetime, importlib, json, os, shutil, subprocess, sys
from pathlib import Path

PREFIX = 'tools.thesis_main.analysis.image_portrait.'
ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT / 'analysis_results/image_portrait_20260914_v1'
OUTPUT = BUNDLE / 'cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7'


def run(module: str, *args: str) -> None:
    command = [sys.executable, '-m', PREFIX + module, *args]
    print('+', ' '.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refit', action='store_true', help='Refit every outer/inner model; preserve current cv cache first.')
    parser.add_argument('--refresh-pooling', action='store_true', help='Read original repository numeric NPZ (not included twice in ZIP); never images/weights.')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    subprocess.run([sys.executable, '-m', PREFIX+'build_bundle', '--check'], cwd=ROOT, check=True)
    if args.tests_only:
        subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_difficulty_stratified_followup.py', '-q'], cwd=ROOT, check=True)
        return
    if args.refresh_pooling:
        run('difficulty_stratified_prepare', 'metadata')
        run('difficulty_stratified_prepare', 'features')
        run('difficulty_stratified_feedback')
        run('difficulty_stratified_full_local')
    needed = ['dinov3__block12__panorama_mean.npy', 'hohonet__legacy_current.npy',
              'feedback__point_counts.npy']
    # Inventory is the authoritative cache set: all five-model features required.
    import csv
    with (OUTPUT/'models/feature_inventory.csv').open(encoding='utf-8-sig') as stream:
        needed = [row['feature']+'.npy' for row in csv.DictReader(stream)]
    missing = [name for name in needed if not (OUTPUT/'cache'/name).is_file()]
    if missing:
        raise SystemExit('Missing numerical inputs: '+', '.join(missing[:8])+f' ({len(missing)} total). Use the FULL delivery; the reader ZIP deliberately omits high-dimensional caches.')
    if args.refit and (OUTPUT/'cv').is_dir():
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = OUTPUT/'reproduction_backups'/('cv_'+stamp)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(OUTPUT/'cv'), str(backup))
        print('Previous fits preserved:', backup, flush=True)
    if args.refit:
        for extra in [[], ['--within'], ['--within', '--stratum', 'main']]:
            run('difficulty_stratified_cv', '--workers', str(args.workers), *extra)
    elif not (OUTPUT/'cv/pooled').is_dir():
        raise SystemExit('Missing fit caches; use --refit with the FULL package.')
    for module in ['difficulty_stratified_results', 'difficulty_stratified_contrasts',
                   'difficulty_stratified_legacy', 'difficulty_stratified_rooms',
                   'difficulty_history_bridge', 'difficulty_history_confirmation',
                   'difficulty_stratified_controls', 'difficulty_stratified_audit']:
        run(module)
    from tools.thesis_main.analysis.image_portrait.difficulty_stratified_figures import make_figures
    make_figures(show=False)
    run('difficulty_stratified_report')
    subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_difficulty_stratified_followup.py', '-q'], cwd=ROOT, check=True)
    print('Numerical reanalysis complete. No remote files were changed.', flush=True)

if __name__ == '__main__':
    main()
