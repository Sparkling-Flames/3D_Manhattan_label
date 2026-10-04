"""Run the delivered package into a new isolated output tree.

Use an existing environment with requirements.txt installed. No network access,
upstream writes, source-input acceptance override, or full-panel run is performed.
"""
import argparse,json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=pathlib.Path)
 p.add_argument('--repo',type=pathlib.Path);a=p.parse_args()
 if a.out.exists():p.error('--out must not exist')
 a.out.mkdir(parents=True);out=a.out.resolve();src=ROOT/'source/extracted/full_layout_consensus_20261004'
 dest=out/'package';shutil.copytree(src,dest,ignore=shutil.ignore_patterns('results','__pycache__'))
 (out/'logs').mkdir();steps=[]
 def run(label,args):
  with (out/'logs'/f'{label}.stdout').open('w') as stdout,(out/'logs'/f'{label}.stderr').open('w') as stderr:
   ret=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],stdout=stdout,stderr=stderr)
  steps.append({'step':label,'exit_code':ret.returncode});return ret.returncode
 if run('experiments',[dest/'run_experiments.py'])==0:
  run('tests',['-m','unittest','discover','-s',dest/'tests','-v'])
  run('adapter_fixture',[dest/'smoke_test_adapters.py'])
 if a.repo:
  repo=a.repo.resolve()
  run('source_fields',[dest/'verify_local_excerpt.py','--repo',repo])
  run('pinned_pilot',[dest/'run_local_panel.py','--repo',repo,'--codes','2t7WUuJeko7-06','--out',out/'pinned_pilot'])
  run('pinned_schedule',[dest/'run_subset_schedule.py','--repo',repo,'--schedule',dest/'inputs/example_real_schedule.json','--out',out/'pinned_schedule'])
 (out/'run_status.json').write_text(json.dumps(steps,indent=2));print(json.dumps(steps,indent=2))
 raise SystemExit(any(x['exit_code'] for x in steps))
if __name__=='__main__':main()
