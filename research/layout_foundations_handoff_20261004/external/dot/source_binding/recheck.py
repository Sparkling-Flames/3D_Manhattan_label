"""Compare provided source excerpts. --repo additionally rechecks full Git blobs."""
import argparse,json,pathlib,hashlib
HERE=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path);p.add_argument('--author',type=pathlib.Path,default=HERE.parent/'source/layout_foundations_20261004_v2');a=p.parse_args()
raw=json.loads((HERE/'verified_source_subset.json').read_text()); P=a.author/'inputs'
paths={'worker':'analysis_results/worker_profiles_20261003/input.json','lee':'analysis_results/lee_expanded_20261003/input.json'}
if a.repo:
 for key,path in paths.items():
  b=(a.repo/path).read_bytes();h=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert h==raw[key]['source_hashes']['git_blob'];raw[key]['images']=json.loads(b)['images']
indices={k:{r['id']:r for im in d['images']for r in im['annotations']+im['references']}for k,d in raw.items()}
j=lambda n:json.loads((P/n).read_text())
plans=[('worker',j('real24_points.json')['records']),('lee',j('current_excerpt.json')['images'][0]['annotations']),('worker',j('confirmed_ring_domain_case.json')),('worker',[j('real24_reference.json')]),('lee',j('reference_excerpt.json')['references'])]
def match(a,b):return all(k in b and match(v,b[k])for k,v in a.items())if isinstance(a,dict)and isinstance(b,dict)else a==b
n=0;nr=0;subsets=0
for key,records in plans:
 for rec in records:
  nr+=1;s=indices[key][rec['id']]
  for f in set(rec)&set(s):
   n+=1;assert match(rec[f],s[f]),(rec['id'],f)
   subsets+=rec[f]!=s[f]
print(json.dumps(dict(status='passed',records=nr,shared_top_level_fields=n,partial_metadata_objects=subsets,full_source_blobs_rechecked=bool(a.repo)),indent=2))
