#!/usr/bin/env python3
"""Returned-package audit. Read-only source; a separate copied working tree only.
Usage: python audit/reproduce_audit.py [--source PATH] [--work PATH] [--rerun]
Dependencies: source requirements plus Python 3.10+.
This audits reproducibility and coverage, not original snapshot equivalence.
"""
from __future__ import annotations
import argparse, ast, collections, csv, hashlib, itertools, json, math, os, pathlib, platform, shutil, subprocess, sys, time
P=pathlib.Path
parser=argparse.ArgumentParser(); parser.add_argument('--source',type=P,required=True);parser.add_argument('--work',type=P,default=P(__file__).resolve().parents[1]);parser.add_argument('--rerun',action='store_true');args=parser.parse_args()
source=args.source.resolve();root=args.work.resolve();out=root/'audit';work=root/'returned_copy';out.mkdir(parents=True,exist_ok=True)
assert source!=work and source not in work.parents and work not in source.parents
(out/'fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><include ignore_missing="yes">/etc/fonts/fonts.conf</include><cachedir>'+str(out/'fontconfig-cache')+'</cachedir></fontconfig>')
(out/'fontconfig-cache').mkdir(exist_ok=True)
import numpy as np, scipy, shapely, matplotlib, mistune
from shapely.geometry import Polygon,Point

def write(name,obj): (out/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def csvrows(path): return list(csv.DictReader(path.open()))
def data(path):
 if path.suffix=='.json': return json.loads(path.read_text())
 return csvrows(path)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dumpcsv(name,rows):
 if not rows:(out/name).write_text('file,path,saved,recomputed,absolute_difference\n');return
 with (out/name).open('w',newline='') as f:
  w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)

manifest=json.loads((source/'FILES.json').read_text());manifest_rows=[]
for rec in manifest:
 f=source/rec['path']; manifest_rows.append(dict(path=rec['path'],exists=f.is_file(),bytes_match=f.is_file() and f.stat().st_size==rec['bytes'],sha256_match=f.is_file() and digest(f)==rec['sha256']))
extra=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and str(p.relative_to(source)) not in {x['path'] for x in manifest} and p.name!='FILES.json')
manifest_check=dict(listed_files=len(manifest_rows),files_including_manifest=len(manifest_rows)+1,all_pass=all(all(v for k,v in r.items() if k!='path') for r in manifest_rows),extra_files=extra,rows=manifest_rows)
write('manifest_verification.json',manifest_check)
versions={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'numpy':np.__version__,'scipy':scipy.__version__,'shapely':shapely.__version__,'geos':shapely.geos_version_string,'matplotlib':matplotlib.__version__,'mistune':mistune.__version__,'source_environment':json.loads((source/'logs/environment.json').read_text()),'numeric_tolerance':{'absolute':1e-12,'relative':1e-12}}
write('audit_environment.json',versions)
commands=[]
if args.rerun:
 if work.exists():shutil.rmtree(work)
 shutil.copytree(source,work)
 # Remove all generated numeric inputs/results so no stale supplied result can pass.
 for folder in ['results','inputs','figures']:
  for p in (work/folder).glob('*'):
   if p.is_file(): p.unlink()
 env=dict(os.environ,MPLCONFIGDIR=str(root/'mplcache'),MPLBACKEND='Agg',FONTCONFIG_FILE=str(out/'fonts.conf'))
 for script in ['run_replication','run_local_research','run_insertion_noise','run_order_and_hybrid','research_checks','make_figures']:
  cmd=[sys.executable,'src/'+script+'.py'];t=time.monotonic()
  res=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True)
  (out/(script+'.stdout.txt')).write_text(res.stdout);(out/(script+'.stderr.txt')).write_text(res.stderr)
  commands.append(dict(command=cmd,cwd=str(work),returncode=res.returncode,seconds=time.monotonic()-t))
  if res.returncode:write('execution_commands.json',commands);raise RuntimeError(script+' failed')
 write('execution_commands.json',commands)

# Exact bytes first; then recursively compare all parsed leaves, including labels/errors.
comparisons=[];mismatches=[]
def compare(a,b,path,stats,file):
 if isinstance(a,dict) and isinstance(b,dict):
  if set(a)!=set(b):mismatches.append(dict(file=file,path=path,saved=str(sorted(a)),recomputed=str(sorted(b)),absolute_difference='keys'))
  for k in a.keys()&b.keys(): compare(a[k],b[k],path+'/'+str(k),stats,file)
 elif isinstance(a,list) and isinstance(b,list):
  if len(a)!=len(b):mismatches.append(dict(file=file,path=path,saved=len(a),recomputed=len(b),absolute_difference='length'))
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i),stats,file)
 else:
  stats['leaves']+=1
  try:
   x,y=float(a),float(b)
   if isinstance(a,bool) or isinstance(b,bool):raise ValueError
   if not math.isfinite(x) or not math.isfinite(y):raise ValueError
   stats['numeric_leaves']+=1;d=abs(x-y);stats['max_absolute_difference']=max(stats['max_absolute_difference'],d)
   ok=math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12)
  except (ValueError,TypeError):ok=a==b;d='non-numeric'
  if not ok:mismatches.append(dict(file=file,path=path,saved=a,recomputed=b,absolute_difference=d))
for folder in ('results','inputs'):
 for f in sorted((source/folder).glob('*')):
  g=work/folder/f.name;stats=dict(file=folder+'/'+f.name,bytes_identical=f.read_bytes()==g.read_bytes(),leaves=0,numeric_leaves=0,max_absolute_difference=0.0)
  compare(data(f),data(g),'',stats,stats['file']);comparisons.append(stats)
write('file_comparison.json',comparisons);dumpcsv('file_comparison.csv',comparisons);dumpcsv('mismatches.csv',mismatches)

checks=[]
def check(name,condition,details):
 checks.append(dict(check=name,passed=bool(condition),details=details))
R=work/'results';load=lambda name:json.loads((R/name).read_text())
input_records=[r for pair in json.loads((work/'inputs/real_excerpts.json').read_text()) for r in pair]+[r[k] for r in json.loads((work/'inputs/synthetic_74.json').read_text()) for k in ['a','b']]
check('all_delivered_coordinates_finite',all(np.isfinite(np.asarray(r['points'],float)).all() for r in input_records),dict(record_occurrences=len(input_records)))
synth=csvrows(R/'snapshot_74_independent.csv'); skeys={(r['family'],r['case'],float(r['amplitude'])) for r in synth};family=collections.Counter(r['family'] for r in synth)
check('synthetic_74_unique_cases',len(synth)==len(skeys)==74 and dict(family)==dict(equivalence=5,extent=19,detail=14,localization=36),dict(rows=len(synth),unique=len(skeys),families=dict(family)))
bev_valid=sum(bool(r['bev_iou']) for r in synth);wall_valid=sum(bool(r['column_iou_1024']) for r in synth)
error_rows=[{k:v for k,v in r.items() if k in ['case','amplitude','bev_iou','bev_reason','column_reason_512','column_reason_1024']} for r in synth if r['bev_reason'] or r['column_reason_1024']]
check('synthetic_status_coverage',bev_valid==73 and wall_valid==72,dict(bev_numeric=bev_valid,column_numeric_each_resolution=wall_valid,error_rows=error_rows,note='74 parameter cases, not 74 usable BEV+column numerical measurements'))
real=csvrows(R/'real_recomputed.csv');check('real_3_image_3_comparison',len(real)==3 and len({r['image'] for r in real})==3,dict(rows=len(real),max_embedded_bev_delta=max(abs(float(r['diff_bev'])) for r in real),max_embedded_column_delta=max(abs(float(r['diff_column'])) for r in real)))
al=load('cyclic_alignment_sensitivity.json');images={r['image'] for r in al};actual={(r['image'],r['sigma_px'],r['gap']) for r in al};expected=set(itertools.product(images,[1,2,4,8,16],[.5,2,8]));conflicts=[]
for r in al:
 mt,mb=dict(r['top']['matched']),dict(r['bottom']['matched']);it,ib={j:i for i,j in mt.items()},{j:i for i,j in mb.items()}
 ca=sorted(i for i in mt.keys()&mb.keys() if mt[i]!=mb[i]);cb=sorted(j for j in it.keys()&ib.keys() if it[j]!=ib[j])
 assert ca==sorted(r['conflict_a_indices']) and cb==sorted(r['conflict_b_indices']) and len(ca)+len(cb)==r['conflict_count']
 if ca or cb:conflicts.append({k:r[k] for k in ['image','sigma_px','gap','conflict_count','conflict_a_indices','conflict_b_indices']})
check('matching_complete_45_grid',len(images)==3 and len(al)==45 and actual==expected and len(conflicts)==6,dict(settings=len(al),per_setting_endpoint_modes=['bound','top','bottom'],total_alignments=3*len(al),conflicting_settings=conflicts))
noise=csvrows(R/'insertion_noise.csv');groups=collections.defaultdict(list)
for r in noise:groups[(r['record'],float(r['noise_px']),int(r['rep']))].append(r)
methods={'unordered_bound','cyclic_bound','split_top','split_bottom'};expected_groups=set(itertools.product(['R00236','R00705'],[.25,.5,1,2,4],range(30)))
assert set(groups)==expected_groups
bound_equal=True;noise_constraints=True
for key,rr in groups.items():
 assert len(rr)==4 and {r['method'] for r in rr}==methods
 dd={r['method']:r for r in rr};a,b=dd['unordered_bound'],dd['cyclic_bound'];bound_equal &= all(a[k]==b[k] for k in ['correct','wrong','missed','matched','inserted_node_wrongly_matched'])
 assert len({r['split_pair_conflict'] for r in rr})==1
 for r in rr:
  c,w,m,e,z=map(lambda k:int(r[k]),['correct','wrong','matched','expected','missed'])
  noise_constraints &= 0<=c<=e and 0<=w<=e and m==c+w and z==e-c and int(r['inserted_node_wrongly_matched'])<=w and e==(7 if r['record']=='R00236' else 8)
summary=load('insertion_noise_summary.json');summary_ok=True
for r in summary:
 rr=[v for v in noise if v['record']==r['record'] and float(v['noise_px'])==r['noise_px'] and v['method']==r['method']];n=sum(int(v['expected']) for v in rr);m=sum(int(v['matched']) for v in rr);c=sum(int(v['correct']) for v in rr)
 expected_values=dict(runs=len(rr),correct_coverage=c/n,matched_coverage=m/n,wrong_per_expected=(m-c)/n,precision_on_matched=c/m,split_conflict_rate=sum(int(v['split_pair_conflict']) for v in rr)/len(rr))
 summary_ok &= all(math.isclose(r[k],v,rel_tol=1e-12,abs_tol=1e-12) for k,v in expected_values.items())
selected=[r for r in summary if r['record']=='R00705' and r['noise_px']==4]
check('noise_300_examples_1200_outputs',len(noise)==1200 and len(groups)==300 and noise_constraints and bound_equal and len(summary)==40 and summary_ok,dict(rows=len(noise),unique_perturbations=len(groups),summary_rows=len(summary),bound_matching_identical_counts_all_examples=bound_equal,selected_summary=selected,shared_x_noise=True,independent_y_noise=True))
tree=ast.parse((work/'src/run_insertion_noise.py').read_text());seeds=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='default_rng' and len(n.args)==1 and isinstance(n.args[0],ast.Constant)]
check('noise_explicit_seed',seeds==[61001],dict(seeds=seeds,algorithm='numpy.random.default_rng; current default PCG64',noise_stream_order='R00236 then R00705; sigma ascending; repetitions 0..29; x draw then y draw',numpy_version=np.__version__))
# Second full seed replay, comparing exact CSV/JSON to the freshly rerun result.
noise_before={n:(R/n).read_bytes() for n in ['insertion_noise.csv','insertion_noise_summary.json']}
seed_run=subprocess.run([sys.executable,'src/run_insertion_noise.py'],cwd=work,capture_output=True,text=True)
check('noise_seed_second_replay_byte_exact',seed_run.returncode==0 and all((R/n).read_bytes()==v for n,v in noise_before.items()),dict(returncode=seed_run.returncode))

sub=load('subtraction_exhaustive.json');p=np.asarray(sub['source']);raw=valid=0;ids=[];orth=[]
for k in range(3,len(p)+1):
 for ix in itertools.combinations(range(len(p)),k):
  raw+=1;q=p[list(ix)];poly=Polygon(q)
  valid+=poly.is_valid and poly.area>=1e-8
  if poly.is_valid and poly.area>=1e-8 and poly.contains(Point(0,0)):
   ids.append(list(ix));e=np.roll(q,-1,axis=0)-q
   if all(abs(v[0])<1e-10 or abs(v[1])<1e-10 for v in e):orth.append(list(ix))
orth_polys=[]
for ix in orth:
 poly=Polygon(p[ix])
 if not any(poly.equals(v) for v in orth_polys):orth_polys.append(poly)
check('subcycle_independent_enumeration',raw==219 and valid==195 and len(ids)==61 and ids==[r['ids'] for r in sub['all_candidates']] and len(orth)==5 and len(orth_polys)==2,dict(raw_subsets=raw,valid_simple_positive=valid,strict_camera_inside=len(ids),orthogonal_rings=len(orth),orthogonal_geometries=len(orth_polys)))
small=sub['residual_then_complexity'];check('subtraction_detail_loss',small['ids']==[0,1,2,7] and small['vertices']==4 and abs(small['bev_iou']-16/16.16)<1e-12 and abs(small['fidelity_lower']-.4)<1e-12,small)
cons=load('consensus_joint_counterexample.json');observed=np.asarray(cons['observed']);mv=(observed.mean(axis=0)>=.5).astype(int);check('joint_support_counterexample',mv.tolist()==[1,1,1] and not (observed==mv).all(axis=1).any(),dict(majority=mv.tolist(),whole_support=int((observed==mv).all(axis=1).sum())))
check('returned_smoke_checks_10',json.loads((work/'logs/research_checks.json').read_text())['passed']==10,dict(note='Package checks counts/selected values; these are not original snapshot validator or all-field tests'))
write('structural_checks.json',checks)

# Source itself must remain unchanged after all work.
check('original_source_unchanged',all(digest(source/r['path'])==r['sha256'] for r in manifest),dict(manifest_files=len(manifest)))
write('structural_checks.json',checks)
summary=dict(scope='returned-package reproducibility and independently recomputed structural counts; original validator and general algorithm correctness are separate audits',manifest_ok=manifest_check['all_pass'],numeric_and_input_files=len(comparisons),all_bytes_identical=all(r['bytes_identical'] for r in comparisons),numeric_leaves=sum(r['numeric_leaves'] for r in comparisons),max_absolute_difference=max(r['max_absolute_difference'] for r in comparisons),mismatch_count=len(mismatches),checks_passed=sum(r['passed'] for r in checks),checks_total=len(checks),figures_generated=sorted(p.name for p in (work/'figures').glob('*')),failure_examples=mismatches[:10],unrun=['original snapshot full validator and full-field comparison (see companion source comparison)','STAPLE/MACCHIatO/Lee original implementations','true multi-person clustering/automatic reliable anchors','original image-based adjudication'],notes=['requirements are minimum bounds rather than lockfile; source environment omits matplotlib/mistune/GEOS versions','74 parameter cases contain 73 numeric BEV and 72 numeric column-IoU cases at each resolution; 2 explicit exclusion conditions were preserved','Second noise replay uses seed 61001 and same NumPy 2.3.5; no extra independent human sample is implied'])
write('summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if mismatches or not all(r['passed'] for r in checks) or not manifest_check['all_pass']:raise SystemExit(1)
