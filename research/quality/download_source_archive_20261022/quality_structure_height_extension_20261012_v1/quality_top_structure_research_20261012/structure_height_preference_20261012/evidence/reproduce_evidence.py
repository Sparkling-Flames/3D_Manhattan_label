#!/usr/bin/env python3
"""Reproduce this evidence module from the shared, source-preserving research root."""
from __future__ import annotations
import argparse,importlib.util,subprocess,sys
from pathlib import Path
from apply_exposure_and_audit import read,write,sha


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2]);a=ap.parse_args();W=a.workspace.resolve()
    E=W/'structure_height_preference_20261012/evidence';L=E/'reproduction_logs';L.mkdir(parents=True,exist_ok=True)
    cf_path=W/'structure_height_preference_20261012/height/candidate_functions.py';sp=importlib.util.spec_from_file_location('new_cf',cf_path);cf=importlib.util.module_from_spec(sp);sp.loader.exec_module(cf)
    base=cf.prior.PRIMARY_METHODS+cf.prior.DIAGNOSTIC_METHODS
    initial=[r['name'] for r in read(cf_path.parent/'candidate_config.json')['candidates']]
    assert len(initial)==15
    q=E/'recheck_comparisons.py'
    steps=[
        [E/'apply_exposure_and_audit.py'],[q],
        [q,'--scores',cf_path.parent/'results/initial15_before_log_addendum/candidate_scores_39.json','--methods',*base,*initial,'--out',E/'new_candidate_comparison'],
        [q,'--scores',cf_path.parent/'results/candidate_scores_39.json','--methods',*base,*cf.NEW_METHODS,'--out',E/'new_candidate_comparison_log_addendum'],
        [E/'monotone_ordinal_probe.py'],[E/'extend_ordinal_baselines.py'],
        [E/'check_frozen_model_controls.py'],[E/'critical_case_differences.py'],[E/'rescore_fixed_fusion_demo.py']]
    receipt=[]
    for i,cmd in enumerate(steps,1):
        full=[sys.executable,*map(str,cmd),'--workspace',str(W)]
        cp=subprocess.run(full,cwd=W,text=True,capture_output=True)
        log=L/f'{i:02d}_{Path(cmd[0]).stem}.log';log.write_text(cp.stdout+cp.stderr,encoding='utf8')
        receipt.append(dict(step=i,script=str(Path(cmd[0]).relative_to(W)),args=[str(v.relative_to(W)) if isinstance(v,Path) and v.is_relative_to(W) else str(v) for v in cmd[1:]],
            returncode=cp.returncode,log=str(log.relative_to(W)),log_sha256=sha(log)))
        if cp.returncode:
            write(L/'execution_manifest.json',receipt);raise RuntimeError(f'Failed step {i}; see {log}')
    write(L/'execution_manifest.json',receipt)
    print(f'Completed {len(steps)} evidence reproduction commands. Original data, labels, split and prior scores were not overwritten.')


if __name__=='__main__':main()
