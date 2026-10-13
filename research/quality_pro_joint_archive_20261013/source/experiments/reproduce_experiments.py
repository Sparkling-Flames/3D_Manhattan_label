#!/usr/bin/env python3
"""Rebuild all experiment results in a new output directory with explicit inputs."""
import argparse,os,subprocess,sys
from pathlib import Path


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--config',required=True,type=Path);ap.add_argument('--local-results',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    here=Path(__file__).resolve().parent;source=args.source.resolve();out=args.out.resolve()
    if out==here or out==source or source in out.parents:
        raise ValueError('choose a fresh output directory outside code and source')
    results=out/'results';figures=out/'figures';results.mkdir(parents=True,exist_ok=True)
    common=['--source',str(source),'--out',str(results)]
    steps=[('export_real_descriptors.py',common),
           ('axis_switch_and_joint_hinge.py',['--descriptors',str(results/'real_direction_descriptors.json'),'--out',str(results)]),
           ('run_targeted_experiments.py',common),('verify_sampling.py',common),
           ('projection_extreme_extension.py',common),
           ('verify_input_alignment.py',common+['--local-results',str(args.local_results.resolve())]),
           ('validate_candidates.py',common+['--config',str(args.config.resolve())]),
           ('summarize_analytic_diagnostics.py',common),
           ('render_experiments.py',['--results',str(results),'--out',str(figures)])]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(out/'matplotlib_cache'))
    for i,(script,arguments) in enumerate(steps):
        print(f'[{i+1}/{len(steps)}] {script}',flush=True)
        subprocess.run([sys.executable,str(here/script),*arguments],check=True,env=env)
    print('All independent experiment stages completed.',flush=True)


if __name__=='__main__':main()
