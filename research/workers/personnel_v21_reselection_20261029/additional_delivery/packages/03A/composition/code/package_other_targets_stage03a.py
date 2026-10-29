from pathlib import Path
import zipfile,json,hashlib,os
w=Path(__file__).resolve().parents[2]
roots=['composition/other_targets_design','composition/other_targets_endpoints','composition/other_targets_manual45','composition/other_targets_semi4','composition/small_pool_direct_ac','composition/small_pool_semi_direct_ac','composition/stage03A_other_targets']
files=[p for r in roots for p in (w/r).rglob('*') if p.is_file() and not p.name.endswith(('.writing','.tmp','.log','.pyc')) and '__pycache__' not in p.parts]
files += [w/'composition/code'/n for n in ['aggregate_frozen_panels.py','build_other_target_stage03a.py','plot_composition_cases.py','package_other_targets_stage03a.py']]
output=w/'deliverables/HOHONET_v21_阶段03A_31合法新增空间完整配比与端点_20261029.zip';temp=output.with_name(output.name+'.writing')
with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
 for f in sorted(files):z.write(f,str(f.relative_to(w)))
with temp.open('rb') as f:os.fsync(f.fileno())
temp.replace(output)
with zipfile.ZipFile(output) as z:
 assert z.testzip() is None
 for n in ['README.md','ALL45_COMMON_SUPPORT_METRIC_MATRIX.csv']:
  p=w/'composition/stage03A_other_targets'/n;assert z.read(str(p.relative_to(w)))==p.read_bytes()
receipt={'file':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'complete':True,'unique_teams':8940,'native_new_fusions':6481,'reused_endpoints':2459,'manual_candidates':45,'semi_candidates':4,'packaging_revision':2,'revision_note':'Convenience time columns split by original time source; underlying results unchanged; all-configuration figure included.'}
(w/'deliverables/STAGE03A_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False));print(json.dumps(receipt,ensure_ascii=False))
