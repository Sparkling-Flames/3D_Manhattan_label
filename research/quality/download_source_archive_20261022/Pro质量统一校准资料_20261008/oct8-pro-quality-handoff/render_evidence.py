#!/usr/bin/env python3
"""Plot frozen paths and vertices without geometry repair or metric recalculation."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
GEOM=json.loads((ROOT/'inputs/frozen_geometry.json').read_text())
HUMAN=json.loads((ROOT/'inputs/review36_user_20261008.json').read_text())
RATING={r['recordId']:r for r in HUMAN['ratings']}
LOOKUP={a['reviewId']:(im,a) for im in GEOM['images'] for a in im['annotations']}
CYAN='#03cced'; ORANGE='#ffad32'

def loop(p):return np.vstack([p,p[0]])
def vertices(records):return np.concatenate([np.asarray(r[k]) for r in records for k in ['top3d','bottom3d']]+[np.zeros((1,3))])
def refs(im,a):return next(r for r in im['groundtruths'] if r['version']==RATING[a['id']]['referenceVersion'])

def row(fig,gs,i,im,a,bounds):
    g=refs(im,a)
    ax=fig.add_subplot(gs[i,0])
    photo=Image.open(ROOT/'inputs/original_photos'/f"{im['code']}.png")
    ax.imshow(photo,extent=(0,1024,512,0))
    for record,color,ls in [(g,ORANGE,'--'),(a,CYAN,'-')]:
        for path in record['erpPaths']:
            for segment in path['segments']:
                p=np.asarray(segment);ax.plot(p[:,0],p[:,1],color=color,lw=1.3,ls=ls,alpha=.94)
    ax.set(xlim=(0,1024),ylim=(512,0));ax.axis('off')
    ax.set_title(f"{a['reviewId']} / {a['id']} | {im['code']} | GT {g['id']} ({g['version']})",fontsize=8,loc='left',pad=5)
    ax2=fig.add_subplot(gs[i,1]); ax3=fig.add_subplot(gs[i,2],projection='3d')
    for record,color,ls in [(g,ORANGE,'--'),(a,CYAN,'-')]:
        t,b=np.asarray(record['top3d']),np.asarray(record['bottom3d'])
        f=loop(b[:,[0,2]])
        ax2.plot(f[:,0],f[:,1],color=color,lw=1.8,ls=ls)
        for p in [loop(t),loop(b)]:ax3.plot(p[:,0],p[:,2],p[:,1],color=color,lw=1.4,ls=ls)
        for pt,pb in zip(t,b):ax3.plot([pt[0],pb[0]],[pt[2],pb[2]],[pt[1],pb[1]],color=color,lw=1.,ls=ls,alpha=.85)
    xyz=bounds;lo=xyz.min(0);hi=xyz.max(0);c=(lo+hi)/2;span=max(hi-lo)*1.12
    ax2.set(xlim=(c[0]-span/2,c[0]+span/2),ylim=(c[2]-span/2,c[2]+span/2),aspect='equal',xlabel='X / h',ylabel='Z / h')
    ax2.scatter([0],[0],s=12,c='black');ax2.tick_params(labelsize=6);ax2.grid(alpha=.18)
    ax2.set_title('BEV | equal X-Z scale',fontsize=8)
    ax3.set(xlim=(c[0]-span/2,c[0]+span/2),ylim=(c[2]-span/2,c[2]+span/2),zlim=(c[1]-span/2,c[1]+span/2),xlabel='X/h',ylabel='Z/h',zlabel='Y/h')
    ax3.set_box_aspect((1,1,1));ax3.view_init(elev=22,azim=-54);ax3.tick_params(labelsize=5,pad=0)
    ax3.set_title('Frozen conditional 3D proxy',fontsize=8)

def save(records,out,title,common_bounds):
    n=len(records);fig=plt.figure(figsize=(15,3.35*n+.7))
    gs=fig.add_gridspec(n,3,width_ratios=[2.4,1,1.16],left=.025,right=.97,top=(.89 if n<=2 else .95),bottom=.025,wspace=.18,hspace=.29)
    for i,(im,a) in enumerate(records):row(fig,gs,i,im,a,common_bounds)
    fig.suptitle(title+'\nCyan = annotation | Orange dashed = recorded GT | h = camera-to-floor unit, not metres | Scores and metrics intentionally omitted',fontsize=10,y=.993)
    fig.savefig(out,dpi=130,pil_kwargs={'quality':85,'optimize':True},facecolor='white');plt.close(fig)

def main():
    (ROOT/'visuals').mkdir(exist_ok=True);meta=[]
    for im in GEOM['images']:
        photo=ROOT/'inputs/original_photos'/f"{im['code']}.png"
        assert hashlib.sha256(photo.read_bytes()).hexdigest()==im['imageSha256']
        records=[(im,a) for a in im['annotations']]
        bounds=vertices(im['annotations']+[refs(im,im['annotations'][0])])
        out=ROOT/'visuals'/f"review_{im['code']}.jpg"
        save(records,out,im['code']+' | six unchanged annotation records',bounds)
        meta.append(dict(file=str(out.relative_to(ROOT)),records=[a['reviewId'] for a in im['annotations']],photograph_sha256_verified=True,geometry='exact stored erpPaths/top3d/bottom3d',axis_bounds='same all-six-records bounds within image',human_scores_shown=False))
    for cid,qs in [('X01',['Q11','Q20']),('X04',['Q10','Q19']),('W02',['Q25','Q30'])]:
        recs=[LOOKUP[q] for q in qs];bounds=vertices([x for im,a in recs for x in [a,refs(im,a)]])
        out=ROOT/'visuals'/f'contrast_{cid}.jpg';save(recs,out,f'{cid} | '+ ' versus '.join(qs),bounds)
        meta.append(dict(file=str(out.relative_to(ROOT)),records=qs,geometry='exact stored coordinates',axis_bounds='common pair bounds in h units',human_scores_shown=False))
    (ROOT/'provenance/visuals.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':len(meta),'bytes':sum((ROOT/m['file']).stat().st_size for m in meta)}))
if __name__=='__main__':main()
