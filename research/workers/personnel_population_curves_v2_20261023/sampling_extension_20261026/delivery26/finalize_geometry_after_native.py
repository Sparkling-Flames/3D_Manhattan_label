"""Finish saved-geometry analyses after native jobs release their CPU budget.

No fusion, new permutations or changed geometry estimand. Reuses atomically
closed pool checkpoints; an interrupted in-progress pool is recomputed from
the same saved endpoints. Only the explicitly named owned process is stopped.
"""
from pathlib import Path
import argparse, json, os, signal, subprocess, sys, time


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.writing')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)


def owned_geometry_process(pid, base):
    try:
        cmd = (Path('/proc') / str(pid) / 'cmdline').read_bytes().replace(b'\0', b' ').decode()
    except FileNotFoundError:
        return False
    return 'analysis_geometry26/geometry_extension.py' in cmd and base.name in cmd


def children(pid):
    result = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            stat = (proc / 'stat').read_text().split()
            if int(stat[3]) == pid:
                result.append(int(stat[0]))
        except (OSError, ValueError, IndexError):
            pass
    return result


def run_job(base, name, command):
    folder = base / 'analysis_geometry26'
    start = time.time()
    with (folder / (name + '.log')).open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    record = dict(job=name, command=command, returncode=result.returncode,
                  elapsed_seconds=time.time()-start, new_fusion_endpoints=0,
                  new_random_orders=0)
    save(folder / (name + ('_COMPLETE.json' if result.returncode == 0 else '_FAILED.json')), record)
    if result.returncode:
        raise RuntimeError(name + ' failed; see its exact log')
    print(json.dumps(record), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--existing-pid', type=int)
    ap.add_argument('--jobs', type=int, default=4)
    args = ap.parse_args(); base = args.base.resolve()
    native = base / 'new_endpoints26/stage2/RUN_RECEIPT.json'
    while not native.exists():
        time.sleep(30)
    assert read(native)['completed_unique'] == 572517
    folder = base / 'analysis_geometry26'
    complete = folder / 'results_stage2/RUN_RECEIPT.json'
    if not complete.exists():
        checkpoint = folder / 'checkpoints/stage2'
        before = sorted(p.name for p in checkpoint.glob('*.receipt.json'))
        stopped = []
        pid = args.existing_pid
        if pid and owned_geometry_process(pid, base):
            owned_children = children(pid)
            for target in owned_children + [pid]:
                try:
                    os.kill(target, signal.SIGTERM); stopped.append(target)
                except ProcessLookupError:
                    pass
            # A shared /proc mount can expose PIDs that cannot be signalled
            # from the current PID namespace. Check every verified old owner,
            # including one for which os.kill returned ProcessLookupError.
            old_owners = owned_children + [pid]
            deadline = time.time() + 15
            while time.time() < deadline and any(owned_geometry_process(x, base) for x in old_owners):
                time.sleep(.25)
            if any(owned_geometry_process(x, base) for x in old_owners):
                raise RuntimeError('Owned geometry process is still visible (possibly a PID namespace mismatch); close that verified owner before starting a second runner')
        save(folder / 'PARALLEL_FINISH_RESUME.json', dict(
            closed_pool_checkpoints_before_resume=len(before), preserved_receipts=before,
            stopped_owned_pids=stopped, jobs=args.jobs,
            reason='Native stage2 completed; release its CPU budget to remaining saved-geometry analysis',
            checkpoint_rule='Only receipt-complete pools reused; any interrupted pool rebuilt from saved endpoints',
            new_fusion_endpoints=0, new_random_orders=0))
        run_job(base, 'final_geometry_compute', [sys.executable, str(folder/'geometry_extension.py'),
            '--study', str(base), '--stage', '2', '--jobs', str(args.jobs)])
    assert read(complete)['pools'] == 194 and read(complete)['uncomputed_links'] == 0
    run_job(base, 'final_geometry_summary', [sys.executable, str(folder/'summarize_geometry_extension.py'),
        '--root', str(folder), '--stage', '2', '--replicates', '2000'])
    run_job(base, 'final_geometry_figures', [sys.executable, str(folder/'render_geometry_results.py'),
        '--root', str(folder)])
    run_job(base, 'final_geometry_lowk_case', [sys.executable, str(folder/'build_lowk_geometry_case.py'),
        '--study', str(base), '--select-largest'])
    save(folder/'GEOMETRY_FINALIZATION_COMPLETE.json', dict(complete=True, pools=194,
        new_fusion_endpoints=0, new_random_orders=0, whole_curve_sampling_design_unchanged=True))


if __name__ == '__main__':
    main()
