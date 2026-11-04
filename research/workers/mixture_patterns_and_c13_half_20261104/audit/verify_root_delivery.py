"""Final integration checks: independent headline aggregation and deliverable references."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import ast,gzip,json,math,re,hashlib
import numpy as np,pandas as pd
from PIL import Image
BASE=Path(__file__).resolve().parents[1]
checks={};errors=[]
def check(name,condition,detail=None):
 checks[name]={'pass':bool(condition),'detail':detail}
 if not condition:errors.append(name)
# Independently average the saved image rows, not the headline summary cells.
a=pd.read_csv(BASE/'mixtures/DSTRUCT_ALLIANCE_IMAGE_CONTRASTS.csv.gz')
sa=pd.read_csv(BASE/'mixtures/DSTRUCT_ALLIANCE_STRATA.csv')
audit=[]
for before,after in [('C1','C1|C3'),('C2','C2|C3'),('C1|C2','C1|C2|C3'),('C3','C1|C3'),('C3','C2|C3')]:
 d=a[(a.from_classes==before)&(a.to_classes==after)].dropna(subset=['B8L2'])
 s=sa[(sa.from_classes==before)&(sa.to_classes==after)&(sa.axis=='ALL')&(sa.metric=='B8L2')].iloc[0]
 avg=float(d.groupby('image').B8L2.mean().mean());p=int((d.groupby('image').B8L2.mean()>1e-9).sum());neg=int((d.groupby('image').B8L2.mean()<-1e-9).sum())
 good=abs(avg-s.image_mean)<1e-10 and d.image.nunique()==s.valid_images and p==s.positive_images and neg==s.negative_images
 check('alliance_'+before+'__'+after,good);audit.append({'from':before,'to':after,'mean_Q':avg,'images':int(d.image.nunique()),'positive':p,'negative':neg})
n=pd.read_csv(BASE/'curves/NAMED_MIXTURE_PAIRED_IMAGE_EFFECTS.csv.gz');n=n[(n.method=='TARGET_DSTRUCT_K3')&(n.with_set=='C2+C3')&(n.without_set=='C1+C2')&(n.min_arm_paths==16)&(n.metric=='Q_mean_complete_paths')].dropna(subset=['with_value','without_value','effect'])
s=pd.read_csv(BASE/'curves/NAMED_MIXTURE_SUMMARY.csv');s=s[(s.method=='TARGET_DSTRUCT_K3')&(s.with_set=='C2+C3')&(s.without_set=='C1+C2')&(s.min_arm_paths==16)&(s.metric=='Q_mean_complete_paths')].iloc[0]
check('named_mixture_image_average',len(n)==190 and abs(n.effect.mean()-s.mean_image)<1e-10 and (n.effect>1e-9).sum()==165,{'images':len(n),'mean':float(n.effect.mean())})
p=pd.read_csv(BASE/'c13_half/analysis/PAIRED_FOUR_IMAGE.csv');sp=pd.read_csv(BASE/'c13_half/analysis/PAIRED_FOUR_SUMMARY.csv').set_index('metric')
for field in ['GS_C1_to_C3','GS_C3_to_C1','C3_minus_C1_mean_Q']:
 check('C13_'+field,len(p)==36 and abs(p[field].mean()-sp.loc[field,'image_equal_mean'])<1e-10,{'mean':float(p[field].mean()),'images':len(p)})
check('C13_GS_identity',np.max(np.abs(p.GS_C1_to_C3-(p.cross-p.C1_within)))<1e-10 and np.max(np.abs(p.GS_C3_to_C1-(p.cross-p.C3_within)))<1e-10)
req=pd.read_csv(BASE/'c13_half/design/REQUESTS.csv.gz')
identity_errors=[]
for r in req.itertuples():
 workers=r.member_workers.split('|');expected=r.pool_id+'__'+hashlib.sha256(json.dumps(sorted(workers),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
 if len(workers)!=r.n or len(set(workers))!=r.n or expected!=r.team_key:identity_errors.append(r.team_key)
check('C13_unique_canonical_requests',len(req)==4992 and req.team_key.is_unique and not identity_errors)
# Verify supported script syntax and saved figure/data containers once.
formats={'python':0,'png':0,'svg':0,'gzip':0,'json':0};format_errors=[]
import xml.etree.ElementTree as ET
for path in sorted(BASE.rglob('*')):
 if not path.is_file() or '__pycache__' in path.parts:continue
 try:
  if path.suffix=='.py':ast.parse(path.read_text(encoding='utf-8-sig'));formats['python']+=1
  elif path.suffix=='.png':
   with Image.open(path) as im:im.load()
   formats['png']+=1
  elif path.suffix=='.svg':ET.parse(path);formats['svg']+=1
  elif path.suffix=='.gz':
   with gzip.open(path,'rb') as f:
    while f.read(2**20):pass
   formats['gzip']+=1
  elif path.suffix=='.json':json.loads(path.read_text(encoding='utf-8-sig'));formats['json']+=1
 except Exception as e:format_errors.append({'path':str(path.relative_to(BASE)),'error':str(e)})
check('saved_files_decode_and_syntax',not format_errors,{'counts':formats,'errors':format_errors})
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['href','src'] and v:self.links.append(v)
missing=[];count=0
for path in sorted(BASE.rglob('*')):
 if path.suffix not in ['.md','.html']:continue
 text=path.read_text(encoding='utf-8')
 if path.suffix=='.html':parser=Links();parser.feed(text);urls=parser.links
 else:urls=re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)',text)
 for url in urls:
  u=urlsplit(url)
  if u.scheme or u.netloc or not u.path:continue
  target=(path.parent/unquote(u.path)).resolve();count+=1
  if not target.exists():missing.append({'source':str(path.relative_to(BASE)),'url':url})
check('local_report_and_workbench_links',not missing,{'checked':count,'missing':missing})
runtime=json.loads((BASE/'audit/WORKBENCH_RUNTIME_CHECK.json').read_text());check('workbench_controls',runtime.get('offline_javascript_execution')=='pass',runtime)
check('ten_scientific_figures_present',formats['png']==10,{'PNG':formats['png'],'visually_reviewed':10})
result={'status':'passed' if not errors else 'failed','scope':'new mixture/curve/C13 deliverables and their current-entry references','source_commit':'48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b','headline_aggregates':audit,'checks':checks,'failed_checks':errors,'scientific_subreviews':['mixtures/FINAL_VERIFICATION.json','curves/FINAL_NUMERICAL_VERIFICATION.json','c13_half/audit/FINAL_VALIDATION.json'],'native_input_and_formula_checks':'See C13 final validation; existing endpoint parity performed before new run.','actual_browser_rendered':False}
(BASE/'DELIVERY_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'failed':errors,'formats':formats,'links':count,'missing':missing},ensure_ascii=False))
if errors:raise SystemExit(1)
