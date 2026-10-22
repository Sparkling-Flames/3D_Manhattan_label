"""Reproduce the reliability analysis from the pinned repository and Q artifacts."""
import argparse,datetime,json,os,subprocess,sys,time
from pathlib import Path
from paths import REPO,STUDY,OUT

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=REPO);ap.add_argument('--study',type=Path,default=STUDY);ap.add_argument('--out',type=Path,default=OUT);a=ap.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);code=Path(__file__).resolve().parent
 env=dict(os.environ,PANORAMA_REPO=str(a.repo.resolve()),PANORAMA_STUDY=str(a.study.resolve()),PANORAMA_RELIABILITY_OUT=str(out))
 for name in ['analyze_q.py','worker_profiles_enriched.csv','fold_profiles_recomputed.csv']:
  if not (a.study/'q'/name).exists():raise FileNotFoundError('Run the supplied Q analysis first: '+str(a.study/'q'/name))
 jobs=[('prepare_inputs.py',[]),('build_reason_candidates.py',[]),('build_reliability_ledger.py',[]),('recover_initializations.py',[]),('canonicalize_initial_rings.py',[]),('score_semi.py',['--ring-view','payload']),('score_semi.py',['--ring-view','compatible']),('build_correction_ledger.py',[]),('recover_scope.py',[]),('analyze_semi.py',[]),('validate_scope.py',[])]
 records=[]
 for i,(script,args) in enumerate(jobs,1):
  tag=f'{i:02d}_'+Path(script).stem+('_'+args[-1] if args else '')
  started=datetime.datetime.now(datetime.timezone.utc).isoformat();tick=time.monotonic();print(f'[{i}/{len(jobs)}] {script} {" ".join(args)}',flush=True)
  with (out/(tag+'.stdout.txt')).open('w') as stdout,(out/(tag+'.stderr.txt')).open('w') as stderr:
   r=subprocess.run([sys.executable,str(code/script),*args],env=env,stdout=stdout,stderr=stderr)
  records.append(dict(stage=tag,script=script,arguments=args,started_utc=started,elapsed_seconds=time.monotonic()-tick,exit_code=r.returncode,stdout=tag+'.stdout.txt',stderr=tag+'.stderr.txt'))
  (out/'run_evidence.json').write_text(json.dumps(dict(data_release='v1',stages=records,all_completed=len(records)==len(jobs) and all(x['exit_code']==0 for x in records)),ensure_ascii=False,indent=2),encoding='utf8')
  if r.returncode:raise RuntimeError(f'{script} failed; inspect {tag}.stderr.txt')
 print('Completed all reliability stages; every source gate remains unchanged.',flush=True)

if __name__=='__main__':main()
