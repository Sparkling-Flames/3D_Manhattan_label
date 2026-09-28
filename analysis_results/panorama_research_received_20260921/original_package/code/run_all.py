"""Reproduce the delivered analyses locally. No network, synthetic annotators, or Git writes.

Use a fresh copy of the research folder: outputs are written beside this script.
The packaged original source archive is verified before safe extraction. Dependencies
must already be installed; see requirements.txt and the Chinese README.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '61995e05bfb57994491edc62e9fe74c525d61cd558d0121f77b24d498c1ddcf0'

def run(command: list[str], log_name: str, *, cwd: Path, allow_failure: bool = False,
        env: dict[str,str] | None = None) -> int:
    log = ROOT / 'logs' / log_name
    log.parent.mkdir(exist_ok=True)
    print('RUN:', ' '.join(command), flush=True)
    with log.open('w', encoding='utf8') as handle:
        result = subprocess.run(command, cwd=cwd, stdout=handle,
                                stderr=subprocess.STDOUT, env=env, check=False)
    print(f'  exit={result.returncode}; log={log}', flush=True)
    if result.returncode and not allow_failure:
        raise RuntimeError(f'Step failed: {command}. Read {log}; do not use partial results.')
    return result.returncode

def unpack(archive: Path, source: Path) -> None:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise ValueError(f'Wrong source archive SHA256: {digest}')
    source.mkdir(parents=True, exist_ok=True)
    root = source.resolve()
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target = (root/member.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f'Unsafe archive member: {member.filename}')
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symlinks are not accepted in source archives.')
        z.extractall(root)

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, help='Existing unpacked pinned handoff; no Git clone required.')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--fresh', action='store_true', help='Remove only this bundle’s per-image replay cache and recompute all 200 orders.')
    p.add_argument('--skip-source-verify', action='store_true', help='Only when source recomputed/ outputs already exist and were separately checked.')
    p.add_argument('--plots-only', action='store_true')
    args = p.parse_args()
    if args.jobs < 1:
        p.error('--jobs must be positive')
    if args.plots_only:
        from figures import make_figures
        make_figures(ROOT)
        return
    source = args.source_root.resolve() if args.source_root else ROOT/'source_work'
    if args.source_root is None:
        unpack(ROOT/'source_snapshot.zip', source)
    if not (source/'analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz').is_file():
        raise FileNotFoundError('Not an unpacked 2026-09-21 handoff: '+str(source))
    if shutil.which('node') is None:
        raise RuntimeError('Node.js is required for the actual JavaScript projector check (step 08).')
    env = dict(os.environ, PANORAMA_SOURCE=str(source), PYTHONDONTWRITEBYTECODE='1')
    verify_exit = None
    if not args.skip_source_verify:
        verify_exit = run([sys.executable,'-B','-m','tools.thesis_main.analysis.pro_research_handoff_20260921','--verify'],
                         'source_strict_verify.log', cwd=source, allow_failure=True, env=env)
    run([sys.executable,'-B','-m','pytest','tests/test_reviewed_manual_20260921.py','tests/test_new_manual_20260921.py','-q'],
        'tests_source.log',cwd=source,env=env)
    def step(name: str, extra: list[str] | None = None, log: str | None = None) -> None:
        run([sys.executable,'-B',str(ROOT/'code'/name),'--source-root',str(source)]+(extra or []),
            log or name.replace('.py','.log'),cwd=ROOT,env=env)
    step('01_measurements.py')
    audit = json.loads((ROOT/'results/validation.json').read_text())
    exceptions = [k for k,v in audit['checks'].items()
                  if not v.get('exact_equal',v.get('parsed_exact_equal',False)) and k != 'distances.json']
    if exceptions or not audit['all_differences_within_tolerance']:
        raise RuntimeError(f'Substantive source reproduction mismatch: {exceptions}. See validation.json.')
    if verify_exit:
        print('Strict source verify returned nonzero; independent checks confirm only tolerated floating differences. This is NOT a verbatim strict-verify pass.',flush=True)
    if args.fresh:
        cache = ROOT/'results/replay_image_cache'
        if cache.exists():
            shutil.rmtree(cache)
        (ROOT/'results/replay_cache_manifest.json').unlink(missing_ok=True)
    step('02_replay.py',['--jobs',str(args.jobs),'--start','0','--end','240'],log='02_replay_fresh_or_resume.log')
    step('02_replay.py',['--aggregate'],log='02_replay_aggregate.log')
    for name in ['03_workers.py','04_transfer.py','05_geometry_time.py','06_synthesis_checks.py','07_controls.py','08_panels_and_renderer.py']:
        step(name)
    run([sys.executable,'-B','-m','pytest',str(ROOT/'code/test_research.py'),'-q'],
        'tests_research.log',cwd=ROOT,env=env)
    from figures import make_figures
    make_figures(ROOT)
    print('Completed. Recomputed tables in results/; logs and figures saved. Report prose is the delivered interpretation and is not regenerated automatically.',flush=True)

if __name__ == '__main__':
    main()
