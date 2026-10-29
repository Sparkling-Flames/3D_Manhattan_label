"""Complete mixture deliveries, with lossless shared vector associations.

Existing per-method full vectors stay in the working archive. Delivery keeps
their exact contents through integer codes + codebook + a checked restorer.
"""
from pathlib import Path
import hashlib,json,os,zipfile

W=Path(__file__).resolve().parents[2];D=W/'deliverables';D.mkdir(exist_ok=True)
C=W/'composition'

def usable(p):
 return p.is_file() and not p.name.startswith('.') and not p.name.endswith(('.writing','.tmp','.log','.pyc')) and '__pycache__' not in p.parts
def files(root):return [p for p in root.rglob('*') if usable(p)]
def single(*names):
 ps=[W/n for n in names]
 assert all(p.is_file() for p in ps),[str(p) for p in ps if not p.is_file()]
 return ps
def package(name,ps,topic,extra=None):
 ps=sorted(set(ps));assert ps and all(usable(p) for p in ps)
 dst=D/name;tmp=dst.with_name(dst.name+'.writing')
 manifest=dict(topic=topic,source_commit='a476461d7ede8db95da43de4139e612c05e618bc',
  data_release='v2.1',files=[dict(path=str(p.relative_to(W)),bytes=p.stat().st_size,
  sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in ps],**(extra or {}))
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  for p in ps:z.write(p,str(p.relative_to(W)),compress_type=zipfile.ZIP_STORED if p.suffix=='.gz' else zipfile.ZIP_DEFLATED)
  z.writestr('PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
 with tmp.open('rb') as f:os.fsync(f.fileno())
 tmp.replace(dst)
 with zipfile.ZipFile(dst) as z:assert z.testzip() is None
 record=dict(file=str(dst),filename=name,topic=topic,bytes=dst.stat().st_size,
  sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),files=len(ps)+1,readback_crc_ok=True)
 (D/(name+'.receipt.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
 print(json.dumps(record,ensure_ascii=False),flush=True)
 return record

receipt=json.loads((C/'primary_manual45/COMPLETE.json').read_text());methods=receipt['methods'];assert len(methods)==45
compact=json.loads((C/'primary_compact_links/COMPACT_RECEIPT.json').read_text());assert compact['lossless_roundtrip_checked']
assert set(compact['methods'])==set(methods)
assert (C/'primary_mixture_results/COMPLETE.json').is_file()
assert (C/'primary_semi4/COMPLETE.json').is_file()
out=[]
code_names=['prepare_current_panel_endpoints.py','aggregate_frozen_panels.py',
 'compact_vector_links.py','restore_team_vectors.py','build_primary_mixture_note.py',
 'build_semi_mixture_note.py','plot_primary_composition_comparison.py','package_primary_and_semi_panels.py']
core=files(C/'primary_panel_inputs')+files(C/'primary_compact_links')+files(C/'primary_mixture_results')
core += [C/'code'/x for x in code_names]
core += [p for p in (C/'primary_manual45').iterdir() if usable(p)]
core += single('classification/MAIN45_LABELS_ALL_LOBO.csv.gz',
 'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz','targets/POOL_TARGET_CONDITIONS.csv',
 'analysis/global_parent_links/METHOD_HIERARCHY_ALL_LOBO.csv')
out.append(package('HOHONET_v21_阶段03B_Manual完整配比_核心与端点_20261029.zip',core,
 'Manual45 complete finite mixture core, exact teams/endpoints and lossless vector associations',
 dict(methods=methods,panels=231,unique_endpoints=213442,new_fusions=0,
  restore='python composition/code/restore_team_vectors.py --compact composition/primary_compact_links --out composition/primary_manual45')))

groups={
 '01_结构':lambda m:m.startswith(('DSTRUCT','OPPSTRUCT')),
 '02_边界几何':lambda m:m.startswith(('DBOUNDARY','OPPGEOM')),
 '03_联合与跨条件':lambda m:m.startswith(('DJOINT','OPPJOINT','MSDGEOM')),
 '04_融合反推与目标扩展':lambda m:m.startswith(('RFUSE','TARGET_')),
 '05_旧分类与Q基线':lambda m:m.startswith(('V3_','Q_')),
}
assigned=[]
for tag,test in groups.items():
 ms=[m for m in methods if test(m)];assigned+=ms
 ps=[p for m in ms for p in files(C/'primary_manual45/by_method'/m) if p.name!='TEAM_CLASS_VECTORS.csv.gz']
 out.append(package(f'HOHONET_v21_阶段03B_Manual完整配比_{tag}_20261029.zip',ps,
  'Complete per-configuration distributions, coverage, counts and variances',
  dict(methods=ms,team_vectors='losslessly represented in the core package; no duplicated vector tables')))
assert sorted(assigned)==sorted(methods) and len(set(assigned))==45

semi=files(C/'primary_semi_inputs')+files(C/'primary_semi_compact_links')+files(C/'semi_mixture_results')
semi += [p for p in files(C/'primary_semi4') if p.name!='TEAM_CLASS_VECTORS.csv.gz']
semi += [C/'code'/n for n in code_names if n not in ['build_primary_mixture_note.py','plot_primary_composition_comparison.py']]
semi += single('classification/SEMI_BASE_LABELS_ALL_LOBO.csv.gz','targets/POOL_TARGET_CONDITIONS.csv')
out.append(package('HOHONET_v21_阶段03C_Semi自身完整配比与端点_20261029.zip',semi,
 'Semi own four methods, complete panels and exact endpoints',
 dict(methods=['V3_BEHAVIOR_COARSE','V3_BEHAVIOR_FINE','V3_JOINT_QT_COARSE','V3_JOINT_QT_FINE'],
  panels=105,unique_endpoints=97016,new_fusions=0,
  restore='python composition/code/restore_team_vectors.py --compact composition/primary_semi_compact_links --out composition/primary_semi4')))

policy=files(C/'exact_small_pool_policies_manual')+files(C/'exact_small_pool_policies_semi')+files(C/'small_pool_policy_results')
policy += [C/'code'/n for n in ['exact_small_pool_entry_policies.py','build_small_pool_policy_note.py','aggregate_frozen_panels.py']]
policy += single('classification/MAIN45_LABELS_ALL_LOBO.csv.gz',
 'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz','classification/SEMI_BASE_LABELS_ALL_LOBO.csv.gz',
 'composition/semi_mixture_results/OWN_SEMI_CLASS_CENTERS_ALL_LOBO.csv.gz',
 'targets/POOL_TARGET_CONDITIONS.csv')
out.append(package('HOHONET_v21_阶段03D_合法小池新角色进入策略_20261029.zip',policy,
 'Exact same-final-pool prefix marginals, separate Manual/Semi',
 dict(manual_methods=7,semi_methods=4,unique_endpoints=1086,new_fusions=0,
  endpoint_dependency='Stage03A other_targets_design and other_targets_endpoints, not duplicated here')))
(D/'STAGES03BCD_RECEIPTS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(dict(packages=len(out),bytes=sum(r['bytes'] for r in out),all_complete=True)),flush=True)
