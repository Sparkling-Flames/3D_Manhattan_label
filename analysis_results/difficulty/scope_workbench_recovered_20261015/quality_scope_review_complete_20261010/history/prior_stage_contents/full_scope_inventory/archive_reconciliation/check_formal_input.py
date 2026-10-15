import argparse,csv,hashlib,io,json,sys,zipfile,subprocess
from collections import Counter
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--archive',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
REPO=args.repo.resolve()
ARCHIVE=args.archive.resolve()
sys.path.insert(0,str(REPO))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input
b=load_current_bundle(); assert b['data']==load_current_input()
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
with zipfile.ZipFile(ARCHIVE) as z:
 assert z.testzip() is None
 members=z.namelist()
with zipfile.ZipFile(ARCHIVE) as z:
 index=list(csv.DictReader(io.StringIO(z.read('原清单123项_索引.csv').decode('utf-8-sig'))))
 assert len(index)==123
 for r in index:
  body=z.read(r['包内路径']);assert len(body)==int(r['字节数']) and len(body)>0
patched=[o for o in b['data']['objects'] if o.get('quality_review_provenance')]
assert len(patched)==14
lfs={}
for name in ['preprocessed_source.json','comments.json']:
 rel='analysis_results/research_input_20260929/'+name
 pointer=subprocess.check_output(['git','show',sha+':'+rel],cwd=REPO,text=True)
 data=(REPO/rel).read_bytes(); digest=hashlib.sha256(data).hexdigest()
 assert 'oid sha256:'+digest in pointer and 'size '+str(len(data)) in pointer
 lfs[name]={'sha256':digest,'bytes':len(data),'matches_committed_lfs_pointer':True}
r={'source_commit':sha,'archive_sha256':hashlib.sha256((ARCHIVE).read_bytes()).hexdigest(),'archive_bytes':(ARCHIVE).stat().st_size,'archive_members':len(members),'zip_crc':'passed','indexed_originals_nonempty_and_size_matched':len(index),'lfs_payloads':lfs,'formal_loader_validation':b['validation'],'both_loaders_identical':True,'quality_update_revision':b['data']['quality_update_revision'],'patched_records':len(patched),'patch_effects':dict(Counter(o['quality_review_provenance']['order_effect'] for o in patched)),'quality_scores_recomputed':False,'limitations':['Current loader validates input consistency; not a new quality-score evaluation.','Package source snapshots and early group candidates do not replace current formal input or constitute new user adjudications.','The promised additional image batch is still pending.']}
args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
