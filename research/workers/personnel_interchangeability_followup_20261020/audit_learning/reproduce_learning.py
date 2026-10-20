"""Portable explicit-root reconstruction. Stages immutable code then runs chosen stages."""
import argparse,shutil,subprocess,sys,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--work-root',type=Path,required=True);p.add_argument('--bundle-root',type=Path,required=True,help='Extracted Pro package root containing analysis/ and interchangeability_20261020/');p.add_argument('--restored-root',type=Path,required=True);p.add_argument('--native-root',type=Path,help='Optional existing audit_replay-layout directory');p.add_argument('--stage',choices=['setup','audit-definitions','forward','legacy','mixed','history-block-native','history-block-pairs','block-fit'],required=True);p.add_argument('--jobs',default='3');a=p.parse_args();src=Path(__file__).resolve().parent;work=a.work_root.resolve();work.mkdir(parents=True,exist_ok=True)
def link(dest,target):
 target=target.resolve()
 if dest.exists() or dest.is_symlink():
  if dest.resolve()!=target:raise ValueError(f'Existing path does not match requested input: {dest}')
 else:dest.parent.mkdir(parents=True,exist_ok=True);dest.symlink_to(target,target_is_directory=target.is_dir())
link(work/'unpacked',a.bundle_root);link(work/'restored',a.restored_root)
if a.native_root:link(work/'audit_replay',a.native_root)
else:(work/'audit_replay').mkdir(exist_ok=True)
for directory in ['audit_learning','audit_corner']:
 source=src if directory=='audit_learning' else src.parent/'audit_corner';dest=work/directory;dest.mkdir(exist_ok=True)
 for f in list(source.glob('*.py'))+list(source.glob('*REGISTRATION.json')):
  d=dest/f.name
  if f.resolve()==d.resolve():continue
  if d.exists() and d.read_bytes()!=f.read_bytes():raise ValueError(f'Refuse silently replace changed code: {d}')
  if not d.exists():shutil.copy2(f,d)
base=work/'audit_learning';rev=base/'reverse_input_root';link(rev/'restored',work/'restored');link(rev/'analysis/composition/SPLIT.json',work/'unpacked/analysis/composition/SPLIT.json')
env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
def run(script,*args):subprocess.run([sys.executable,str(script),*map(str,args)],cwd=work,env=env,check=True)
if a.stage=='audit-definitions':run(base/'audit_learning.py')
elif a.stage=='forward':
 run(work/'unpacked/interchangeability_20261020/reproduction/rebuild_forward.py','--package-root',work/'unpacked','--restored',work/'restored','--out',base/'full_forward_rebuild');run(base/'rebuild_fold_qt.py')
elif a.stage=='legacy':
 run(base/'extract_corner_history.py','--jobs',a.jobs);run(base/'learn_corner_types.py','--tier','legacy');run(base/'summarize_corner_labels.py','--tier','legacy')
elif a.stage=='mixed':
 run(work/'unpacked/analysis/composition/fusion_runner.py','--restored',work/'restored','--requests',work/'unpacked/interchangeability_20261020/history_panel/history_requests.json.gz','--out',work/'audit_replay/history_native','--jobs',a.jobs)
 run(base/'extract_corner_h20.py','--jobs',a.jobs);run(base/'refit_original_new2.py');run(base/'learn_corner_types.py','--tier','mixed');run(base/'summarize_corner_labels.py','--tier','mixed')
 for tier in ['legacy','mixed']:
  if (base/('corner_fit_'+tier)/'fold_labels.csv').exists():run(base/'compare_original_new2.py','--tier',tier)
elif a.stage=='history-block-native':
 run(base/'design_history_blocks.py');run(work/'unpacked/analysis/composition/fusion_runner.py','--restored',work/'restored','--requests',base/'history_blocks/history_block_requests.json.gz','--out',work/'audit_replay/history_corner_blocks','--jobs',a.jobs)
elif a.stage=='history-block-pairs':run(work/'audit_corner/evaluate_common_library.py','--requests',base/'history_blocks/history_block_requests.json.gz','--native',work/'audit_replay/history_corner_blocks','--out',work/'audit_corner/history_block_metrics','--pairs-only','--jobs',a.jobs)
elif a.stage=='block-fit':run(base/'test_block_objective.py');run(base/'learn_block_types.py');run(base/'summarize_block_fit.py')
print(json.dumps({'stage':a.stage,'work_root':str(work),'bundle_root':str(a.bundle_root.resolve()),'restored_root':str(a.restored_root.resolve()),'completed':True}))
