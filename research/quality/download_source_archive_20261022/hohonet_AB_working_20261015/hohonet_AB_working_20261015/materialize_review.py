"""Reuse the already hydrated local Codex 20-card page without executing its scripts,
or hydrate through the actual repository loader. Read-only; no best-reference search.
The --existing-page route checks the 20 display/image identities, not fresh geometry.
The --repo route remeasures frozen components and requires readable original photos.
Neither external-data route was executable with missing photos/LFS in this container.
"""
from pathlib import Path
import argparse,json,re,sys
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from native_geometry import project,erp_triples,iou,direction,bottom_distance,height_components,prism_iou
from working_models import score,WQ
from build_review import write_viewer

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--existing-page',type=Path);g.add_argument('--repo',type=Path)
 p.add_argument('--images',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 if args.output.exists():raise FileExistsError('Use a new directory to preserve old receipts')
 b=pd.read_csv(ROOT/'inputs/next_review_bindings.csv');audit=[];cards=[]
 if args.existing_page:
  txt=args.existing_page.read_text(encoding='utf-8');match=re.search(r'<script\s+id="payload"\s+type="application/json">(.*?)</script>',txt,re.S)
  if not match:raise ValueError('Expected trusted generated viewer JSON payload; scripts are never executed')
  payload=json.loads(match.group(1));source={c['display_id']:c for c in payload['cards']}
  if set(source)!=set(b.blind_id):raise ValueError('The page does not contain the same 20 frozen display IDs')
  for r in b.itertuples():
   c=source[r.blind_id]
   if c['image_id']!=r.image_id or c.get('floor') is None or c.get('original_floor') is None:raise ValueError('Missing geometry / changed image')
   # Whitelist only geometry/display fields; no source model scores or worker names copied.
   cards.append({k:c[k] for k in ['display_id','image_id','floor','height','original_floor','original_height','photo_path'] if k in c})
   audit.append(dict(blind_id=r.blind_id,record_id=r.record_id,reference_id=r.reference_id,check='same frozen display and image; pre-existing geometry provenance retained, not newly remeasured'))
 else:
  if args.images is None:raise ValueError('--images is required with --repo')
  from PIL import Image
  sys.path.insert(0,str(args.repo.resolve()))
  from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
  bundle=load_current_bundle();objs={o['object_id']:o for o in bundle['data']['objects']}
  d=pd.read_csv(ROOT/'inputs/JOINT_COMPARISON_1145.csv').set_index('record_id');photos={f.stem:f for f in args.images.rglob('*') if f.suffix.lower() in ['.png','.jpg','.jpeg']}
  for r in b.itertuples():
   a,g=objs[r.object_id],objs[r.reference_id]
   if a['image_id']!=r.image_id or g['image_id']!=r.image_id or a['condition']!='manual' or a['cleaning_disposition']!='retained':raise ValueError('Changed identity/qualification')
   x,h=project(erp_triples(a['points_1024x512']));y,k=project(erp_triples(g['points_1024x512']))
   I,S,D=iou(x,y),bottom_distance(x,y),direction(x);M,L=height_components(x,h,y,k)
   v=np.array([I,S,D,M,L,score(I,S,D,M,L),100*prism_iou(x,h,y,k)],float);z=d.loc[r.record_id]
   frozen=z[['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','WQ','IoU3D100']].to_numpy(float)
   err=float(np.max(abs(v-frozen)))
   if err>1e-6:raise ValueError(f'Changed inputs/implementation: {r.record_id}, max error {err}. Reconcile, do not silently replace.')
   ph=photos.get(r.image_id)
   if ph is None:raise FileNotFoundError('Original photo '+r.image_id)
   with Image.open(ph) as im:im.verify()
   cards.append(dict(display_id=r.blind_id,image_id=r.image_id,floor=x.tolist(),height=h.tolist(),original_floor=y.tolist(),original_height=k.tolist(),photo_path=ph.resolve().as_uri()))
   audit.append(dict(blind_id=r.blind_id,record_id=r.record_id,object_id=r.object_id,reference_id=r.reference_id,max_component_error=err,photo_path=str(ph),check='live loader+frozen metrics+photo readability'))
 args.output.mkdir(parents=True);write_viewer(cards,args.output/'NEXT_ORDINARY_REVIEW.html',mode='ordinary')
 (args.output/'PRIVATE_BINDING_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print('Generated',len(cards),'score-hidden cards')
if __name__=='__main__':main()
