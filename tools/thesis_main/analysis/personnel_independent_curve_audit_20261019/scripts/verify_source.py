from pathlib import Path
import json,hashlib,gzip,collections
r=Path(__file__).resolve().parents[1];w=r/'extracted/work_v2_20261019';repo=r/'extracted/repo_main_20261019';out=r/'independent'
commit=json.loads((out/'official_commit.json').read_text());tree=json.loads((w/'input/github_tree.json').read_text())
def gitblob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
groups=collections.defaultdict(list)
for x in tree['tree']:
 parent,_,base=x['path'].rpartition('/');groups[parent].append((base,x))
tree_checks=[]
for path,entries in groups.items():
 entries.sort(key=lambda a:(a[0]+('/' if a[1]['type']=='tree' else '')).encode())
 b=b''.join((x['mode'].lstrip('0')+' '+name).encode()+b'\0'+bytes.fromhex(x['sha']) for name,x in entries)
 h=hashlib.sha1(b'tree '+str(len(b)).encode()+b'\0'+b).hexdigest()
 expected=tree['sha'] if not path else next(x['sha'] for x in tree['tree'] if x['path']==path)
 tree_checks.append({'path':path,'match':h==expected})
assert not tree['truncated'] and all(x['match'] for x in tree_checks)
assert tree['sha']==commit['tree']['sha']
lookup={x['path']:x for x in tree['tree']}
files=[]
for f in json.loads((w/'input/DOWNLOAD_MANIFEST.json').read_text())['files']:
 p=repo/f['path'];x=lookup[f['path']];b=p.read_bytes();files.append({'path':f['path'],'bytes':len(b),'git_blob_sha1':gitblob(b),'sha256':hashlib.sha256(b).hexdigest(),'official_tree_match':gitblob(b)==x['sha'] and len(b)==x['size'],'lfs_pointer':b.startswith(b'version https://git-lfs.github.com/spec/v1')})
prefixes={'evidence':'research/statistics/v2_evidence_audit_20261019','integrated':'research/statistics/v2_integrated_analysis_20261019','workers':'research/workers/pro_personnel_v2_20261019','engine':'research/statistics/b8l2_shared_v6_20261016/inputs'}
official_checks=[]
for name,prefix in prefixes.items():
 t=json.loads((out/('official_tree_'+name+'.json')).read_text());assert not t['truncated'];assert t['sha']==lookup[prefix]['sha']
 for x in t['tree']:
  p=prefix+'/'+x['path'];assert x['sha']==lookup[p]['sha']
 official_checks.append({'prefix':prefix,'sha':t['sha'],'entries':len(t['tree']),'matches_authenticated_root':True})
rows=json.load(gzip.open(repo/'research/statistics/v2_evidence_audit_20261019/records.json.gz'))['records'];q=[x for x in rows if x['quality_usable']]
def count(rows,key):return dict(collections.Counter(str(x.get(key)) for x in rows))
counts={'inventory':len(rows),'people':len(set(x['worker_id'] for x in rows)),'images':len(set(x['image_id'] for x in rows)),'origins':count(rows,'origin'),'quality_rows':len(q),'quality_workers':len(set(x['worker_id'] for x in q)),'quality_images':len(set(x['image_id'] for x in q)),'source_time_available':sum(x.get('source_active_time_seconds') is not None for x in rows),'target_matched_time_available':sum(x.get('target_matched_time_seconds') is not None for x in rows),'quality_use':count(rows,'quality_use'),'quality_reference_versions':count(q,'reference_version'),'all_reference_versions':count(rows,'reference_version'),'quality_cleaning_disposition':count(q,'cleaning_disposition'),'binding_status':count(rows,'binding_status'),'quality_condition':count(q,'condition')}
expected=json.loads((repo/'research/workers/pro_personnel_v2_20261019/INPUT_MANIFEST.json').read_text())['counts'];comparisons={k:counts[k]==expected[k] for k in counts if k in expected}
ref_bad=[x['object_id'] for x in q if x['reference_id']!=x['reference_evidence']['target_id'] or x['reference_version']!=x['reference_evidence']['reference_version']]
res={'method':'Independent Git object hashing; archived recursive tree reconstructed and rooted in fresh official GitHub commit metadata, plus four fresh official subtree comparisons. No package code executed.','official_commit':commit['sha'],'official_root_tree':commit['tree']['sha'],'tree_nodes_reconstructed':len(tree_checks),'tree_reconstruction_all_pass':all(x['match'] for x in tree_checks),'official_subtrees':official_checks,'verified_source_files':len(files),'source_blob_all_match':all(x['official_tree_match'] for x in files),'lfs_pointer_files':[x['path'] for x in files if x['lfs_pointer']],'counts':counts,'count_comparisons_to_published_input':comparisons,'quality_reference_identity_version_mismatches':ref_bad,'files':files}
(out/'source_verification.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in res.items() if k!='files'},ensure_ascii=False,indent=2))
