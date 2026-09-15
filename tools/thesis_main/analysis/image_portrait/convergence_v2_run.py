"""Run or verify the delivered numerical follow-up. Never runs visual models."""
import argparse,subprocess,sys,os,json
from pathlib import Path
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import ROOT,OUT

STAGES=[
('prepare',[]),('process',[]),('subgroups',['--stage','all']),('prediction',[]),
('combinations',[]),('prefix',[]),('context',[]),
('deep_groups',['--stage','behavior']),('deep_groups',['--stage','growth']),
('deep_groups',['--stage','fixed']),('deep_groups',['--stage','support']),
('mode_latency',[]),('partition_audit',[]),('strictcold',[]),('finalize',[]),
('interpret',[]),('figures',[]),('deliver',[])]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');ap.add_argument('--stage',choices=['all']+sorted(set(s for s,_ in STAGES)),default='all');args=ap.parse_args();env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 if args.verify:
  cmd=[sys.executable,'-m','pytest','tests/test_image_portrait_convergence_v2.py','tests/test_image_portrait_bundle.py','tests/test_image_portrait_common.py','-q'];return subprocess.call(cmd,cwd=ROOT,env=env)
 (OUT/'execution_logs').mkdir(parents=True,exist_ok=True)
 for name,options in STAGES:
  if args.stage not in ['all',name]:continue
  cmd=[sys.executable,'-m','tools.thesis_main.analysis.image_portrait.convergence_v2_'+name,*options];log=OUT/'execution_logs'/('_'.join([name,*[s.replace('--','')for s in options]])+'.log');print(' '.join(cmd),flush=True)
  with log.open('w')as handle:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT)
  if r.returncode:print('FAILED',name,'see',log,file=sys.stderr);return r.returncode
 return 0

if __name__=='__main__':sys.exit(main())
