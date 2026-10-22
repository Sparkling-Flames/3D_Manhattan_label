from pathlib import Path
import sys,json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
IMAGE_DIRS=[Path('/mnt/data/quality_recovery_verified/quality_readonly_evidence_20261016/images'),Path('/mnt/data/quality_recovery_verified/latest_acquisition/images')]
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(n):return ImageFont.truetype(FONT,n)
def projection(q,w,h):
 q=np.asarray(q);u=(np.arctan2(-q[:,0],q[:,2])/(2*np.pi))%1;v=.5-np.arctan2(q[:,1],np.linalg.norm(q[:,[0,2]],axis=1))/np.pi
 return np.column_stack((u*w,v*h))
def overlay(photo,a,r):
 im=Image.open(photo).convert('RGB');im.thumbnail((1280,640));w,h=im.size;draw=ImageDraw.Draw(im)
 for g,col,label in [(r,(0,191,255),'R'),(a,(255,141,38),'A')]:
  b=np.asarray(g['bottom3d']);t=np.asarray(g['top3d'])
  for p in [b,t]:
   for i in range(len(p)):
    q=p[i]+np.linspace(0,1,250)[:,None]*(p[(i+1)%len(p)]-p[i]);xy=projection(q,w,h)
    for u,v in zip(xy[:-1],xy[1:]):
     if abs(u[0]-v[0])<w/2:draw.line([tuple(u),tuple(v)],fill=col,width=2)
  xb=projection(b,w,h);xt=projection(t,w,h)
  for j,(u,v) in enumerate(zip(xb,xt)):
   if abs(u[0]-v[0])<w/2:draw.line([tuple(u),tuple(v)],fill=col,width=1)
   draw.ellipse((u[0]-3,u[1]-3,u[0]+3,u[1]+3),fill=col);draw.text((u[0]+4,u[1]),label+str(j),fill=col,font=font(12))
 return im

def bev(a,r):
 fig,ax=plt.subplots(figsize=(6,5));
 for g,label in [(r,'Fixed reference'),(a,'Answer')]:
  p=np.asarray(g['bottom3d'])[:,[0,2]];pp=np.vstack([p,p[0]]);line=ax.plot(pp[:,0],pp[:,1],'-o',label=label,markersize=3)[0]
  for j,v in enumerate(p):ax.annotate(('R' if label.startswith('Fixed') else 'A')+str(j),v,fontsize=8,xytext=(3,3),textcoords='offset points')
 ax.scatter([0],[0],marker='+',label='Camera');ax.set_aspect('equal');ax.legend(loc='best');ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height');fig.tight_layout()
 import io
 mem=io.BytesIO();fig.savefig(mem,format='png',dpi=110);plt.close(fig);mem.seek(0);return Image.open(mem).convert('RGB')

def main():
 (ROOT/'figures/review24').mkdir(parents=True,exist_ok=True)
 s=json.loads((ROOT/'inputs/review24/reviewed_snapshot.json').read_text());manifest=[]
 for c in s['cases']:
  p=c['source_pair'];image=None
  for d in IMAGE_DIRS:
   candidates=list(d.glob(p['image_id']+'.*'))
   if candidates:image=candidates[0];break
  if image is None:manifest.append({'case_id':c['case_id'],'status':'missing_image','image_id':p['image_id']});continue
  top=overlay(image,p['answer'],p['reference']);bt=bev(p['answer'],p['reference']);bt.thumbnail((900,660))
  panel=Image.new('RGB',(1280,top.height+bt.height+60),'white');panel.paste(top,(0,40));panel.paste(bt,((1280-bt.width)//2,top.height+50))
  draw=ImageDraw.Draw(panel);draw.text((15,10),c['case_id']+' | '+c['record_id']+' | '+c['image_code']+' | cyan=reference orange=answer',fill='black',font=font(19))
  path=ROOT/'figures/review24'/f"{c['case_id']}.jpg";panel.save(path,quality=88)
  manifest.append({'case_id':c['case_id'],'object_id':p['object_id'],'image_id':p['image_id'],'original_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'original_path':str(image),'panel':str(path.relative_to(ROOT)),'status':'panel_created_not_automatic_visual_adjudication'})
 (ROOT/'results/photo_review_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 # Contact sheets used to inspect all cases, not a substitute for original resolution.
 for batch in range(4):
  rows=manifest[batch*6:(batch+1)*6];canvas=Image.new('RGB',(1600,3*740),'white')
  for j,row in enumerate(rows):
   im=Image.open(ROOT/row['panel']);im.thumbnail((800,740));canvas.paste(im,((j%2)*800,(j//2)*740))
  canvas.save(ROOT/'figures'/f'contact_{batch+1}.jpg',quality=90)
 print(len(manifest),'cases',sum(x['status'].startswith('panel') for x in manifest),'panels')
if __name__=='__main__':main()
