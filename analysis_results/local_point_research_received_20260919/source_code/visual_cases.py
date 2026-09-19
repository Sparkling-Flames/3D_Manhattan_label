"""Read-only evidence overlays; no inferred walls or modified annotation points."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from PIL import Image,ImageDraw,ImageFont
import local_points as lp
R=lp.ROOT
CASES=[
('e9zR4mvMWw7-16','semi','W006','W032','samecount_mean_near_local_far'),
('uNb9QFRL6hY-60','manual','W011','W032','samecount_mean_near_local_far'),
('rPc6DW4iMge-17','semi','W030','W034','samecount_mean_near_local_far'),
('yqstnuAEVhm-31','manual','W002','W010','samecount_mean_near_local_far'),
('rPc6DW4iMge-06','manual','W032','W035','samecount_mean_near_local_far'),
('7y3sRwLe3Va-12','oos','W028','W032','samecount_mean_near_local_far'),
('rPc6DW4iMge-20','manual','W034','W037','samecount_known_expression_change'),
('q9vSo1VnCiC-15','semi','W002','W006','differentcount_near_coverage'),
('wc2JMjhGNzB-30','manual','W001','W011','differentcount_near_coverage'),
('e9zR4mvMWw7-03','semi','W006','W035','differentcount_near_coverage'),
('e9zR4mvMWw7-32','semi','W006','W012','differentcount_near_coverage'),
('uNb9QFRL6hY-45','manual','W001','W036','differentcount_near_coverage'),
('VFuaQ6m2Qom-07','manual','W001','W017','differentcount_near_coverage'),
('VFuaQ6m2Qom-07','manual','W001','W031','samecount_near_but_matching_collision'),
('X7HyMhZNoso-13','manual','W002','W030','explicit_near_but_complete_link_split'),
('b8cTxDM8gDG-07','semi','W029','W031','explicit_near_but_complete_link_split'),
('wc2JMjhGNzB-15','manual','W008','W036','explicit_tolerance_control'),
('X7HyMhZNoso-19','manual','W011','W015','correspondence_not_identified_by_point_nearness'),
]

def paths():
 mp={}
 key=json.loads((R/'inputs/key39.json').read_text())
 for c in key['cases']:
  mp[c['code']]=(R/'inputs/original_images'/(c['code']+'.png'),c['image_path_reference_only'].replace('\\','/'))
 rv=json.loads((R/'inputs/user12_review_original.json').read_text())
 for c in rv['evidence']:
  p=R/'inputs/original_images'/(c['code']+'.png')
  if p.exists():mp[c['code']]=(p,c['image_path'])
 return mp

def run():
 rows,au=lp.load();records={(au.loc[r['canonical_annotation_id'],'code'],r['raw_condition'],r['worker_id']):r for r in rows};imagepaths=paths();out=[]
 try:
  font=ImageFont.truetype('DejaVuSans.ttf',18);small=ImageFont.truetype('DejaVuSans.ttf',13)
 except OSError:
  font=ImageFont.load_default(size=18);small=ImageFont.load_default(size=13)
 for no,(code,cond,wa,wb,why)in enumerate(CASES,1):
  a,b=records[code,cond,wa],records[code,cond,wb];pa=np.array(a['effective_points_1024x512']);pb=np.array(b['effective_points_1024x512']);C=lp.angular(pa,pb);f=lp.features(C)
  path,rpath=imagepaths[code];base=Image.open(path).convert('RGB').resize((1024,512));panels=[]
  for title,points,colour in [('Original (no inferred connections)',None,(255,255,255)),(wa,pa,(255,70,40)),(wb,pb,(0,235,255))]:
   im=Image.new('RGB',(1024,540),'white');im.paste(base,(0,28));draw=ImageDraw.Draw(im);draw.text((8,3),title,font=font,fill=(0,0,0))
   if points is not None:
    for j,(x,y)in enumerate(points):
     y+=28;draw.ellipse((x-4,y-4,x+4,y+4),outline=(0,0,0),fill=colour,width=1);draw.text((x+5,y-10),str(j+1),font=small,fill=colour,stroke_width=1,stroke_fill=(0,0,0))
   panels.append(im)
  canvas=Image.new('RGB',(1024,1690),'white');d=ImageDraw.Draw(canvas)
  d.text((8,5),f'{no:02} {code} / {cond} / {wa} - {wb}',font=font,fill='black')
  d.text((8,31),f'n={len(pa)}/{len(pb)}, OSPA1={f["ospa1"]:.3f}, H={f["hausdorff"]:.3f}, bottleneck={f["bottleneck"]:.3f} deg',font=font,fill='black')
  for j,im in enumerate(panels):canvas.paste(im,(0,65+j*540))
  name=f'{no:02}_{code}_{cond}_{wa}_{wb}.jpg';canvas.save(R/'visual'/name,quality=94)
  # Native-resolution local crop for largest directed nearest-neighbour residual on each side.
  orig=Image.open(path).convert('RGB');sx=orig.width/1024;sy=orig.height/512
  nc=Image.new('RGB',(1000,400),'white');nd=ImageDraw.Draw(nc)
  for side,(p,q,v,color,w)in enumerate([(pa,pb,C.min(1),(255,70,40),wa),(pb,pa,C.min(0),(0,235,255),wb)]):
   at=int(np.argmax(v));x,y=p[at];cx=x*sx;cy=y*sy;box=(int(cx-220),int(cy-160),int(cx+220),int(cy+160));crop=orig.crop(box)
   cd=ImageDraw.Draw(crop)
   for pp,co in [(p,color),(q,(255,255,0))]:
    for j,(xx,yy)in enumerate(pp):
     xx=xx*sx-box[0];yy=yy*sy-box[1]
     if 0<=xx<440 and 0<=yy<320:
      cd.ellipse((xx-5,yy-5,xx+5,yy+5),fill=co,outline=(0,0,0));cd.text((xx+5,yy-10),str(j+1),font=small,fill=co,stroke_width=1,stroke_fill=(0,0,0))
   nc.paste(crop,(side*500+30,50));nd.text((side*500+12,5),f'{w} point {at+1}, nearest={v[at]:.3f} deg',font=font,fill='black')
  cropname=name.replace('.jpg','_crop.jpg');nc.save(R/'visual'/cropname,quality=94)
  out.append(dict(case_id=no,code=code,condition=cond,worker_a=wa,worker_b=wb,id_a=a['canonical_annotation_id'],id_b=b['canonical_annotation_id'],selection=why,overlay=name,crop=cropname,source_path=rpath,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),n_a=len(pa),n_b=len(pb),ospa1=f['ospa1'],hausdorff=f['hausdorff'],bottleneck=f['bottleneck'],visual_review_status='rendered_not_yet_reviewed',points_a=pa.tolist(),points_b=pb.tolist()))
 (R/'results/visual_cases.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print('rendered',len(out))
if __name__=='__main__':run()
