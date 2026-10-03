"""Replay the independent numerical work into a NEW output directory."""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--figures',action='store_true')
    args=parser.parse_args();out=args.out.resolve()
    if out.exists():raise SystemExit('Refusing to overwrite an existing output directory.')
    out.mkdir(parents=True)
    for name in ('inputs','src','tests'):
        shutil.copytree(ROOT/name,out/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('results','figures'):(out/name).mkdir()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR=str(out/'mpl_cache'))
    commands=[[sys.executable,'src/analyze_profiles.py'],[sys.executable,'src/composition_kernel.py'],
              [sys.executable,'src/paired_replacement.py'],
              [sys.executable,'-m','pytest','tests','-q','-p','no:cacheprovider']]
    if args.figures:commands.append([sys.executable,'src/make_figures.py'])
    for n,command in enumerate(commands):
        p=subprocess.run(command,cwd=out,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/'results'/f'replay_step_{n+1}.log').write_text(p.stdout,encoding='utf-8')
        if p.returncode:raise SystemExit(f'Failed: {command}; see replay log in {out}')
    checks=[]
    for path in sorted((ROOT/'results').rglob('*.csv')):
        rel=path.relative_to(ROOT);other=out/rel
        if other.exists():checks.append(dict(path=str(rel),byte_equal=path.read_bytes()==other.read_bytes()))
    (out/'results/replay_csv_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),compared_csvs=len(checks),all_csv_equal=all(c['byte_equal'] for c in checks))))

if __name__=='__main__':main()
