#!/usr/bin/env python3
"""Research-only visual evidence for unchanged complete fusion endpoints."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d.art3d import Line3DCollection

def erp(v):
    p=np.asarray(v,float);rho=np.linalg.norm(p[:,[0,2]],axis=1)
    return np.c_[(np.arctan2(-p[:,0],p[:,2])%(2*np.pi))*1024/(2*np.pi),256-np.arctan2(p[:,1],rho)*512/np.pi]
def segments(g):
    t=np.asarray(g['top3d']);b=np.asarray(g['bottom3d'])
    return [(q[i],q[(i+1)%len(q)]) for q in [t,b] for i in range(len(q))]+list(zip(t,b))
def outline(ax,g,color):
    for a,b in segments(g):
        q=erp(np.linspace(a,b,100));q[np.r_[False,np.abs(np.diff(q[:,0]))>512]]=np.nan
        ax.plot(q[:,0],q[:,1],color=color,lw=1.2)

def main():
    a=argparse.ArgumentParser();a.add_argument('--workspace',type=Path,default=Path.cwd());a.add_argument('--out',type=Path);x=a.parse_args();W=x.workspace
    E=W/'top_structure_20261012/evidence';out=x.out or E/'figures';out.mkdir(parents=True,exist_ok=True)
    inputs=json.loads((E/'results/fixed_fusion_endpoint_inputs.json').read_text());scores={r['identity']:r for r in json.loads((E/'results/fixed_demo_candidate_scores.json').read_text())};manifest=[]
    for r in inputs:
        if not r.get('independent_output'):continue
        p=W/'top_structure_20261012/review/inputs/originals'/f'{r["image_code"]}.png';raw=p.read_bytes();im=np.array(Image.open(p).convert('RGB').resize((1024,512),Image.Resampling.LANCZOS))
        ann=r['geometry'];ref=r['reference_geometry'];s=scores[r['endpoint_id']]
        fig=plt.figure(figsize=(14,9.8));gs=fig.add_gridspec(2,2,height_ratios=[1.05,1.05],wspace=.18,hspace=.30)
        ax=fig.add_subplot(gs[0,:]);ax.imshow(im,extent=(0,1024,512,0));outline(ax,ref,'#00bd8e');outline(ax,ann,'#ef43b7')
        ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xlabel('ERP x (1024 domain)');ax.set_ylabel('ERP y')
        ax.set_title(f'{r["image_code"]}: fixed full-pool output, n={r["n"]}\nGreen: existing reference; magenta: unchanged fused candidate',fontsize=12)
        ax=fig.add_subplot(gs[1,0]);cloud=[]
        for g,c,label in [(ref,'#00bd8e','existing reference'),(ann,'#ef43b7','fixed fused candidate')]:
            q=np.asarray(g['bottom3d'])[:,[0,2]];q=np.r_[q,q[:1]];ax.plot(q[:,0],q[:,1],'-o',color=c,label=label,ms=3);cloud.append(q)
        ax.scatter(0,0,color='black',marker='+',s=50);ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(fontsize=9)
        ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.set_title('Same-scale floor, no alignment or rescaling',fontsize=11)
        ax=fig.add_subplot(gs[1,1],projection='3d');cloud=[]
        for g,c in [(ref,'#00bd8e'),(ann,'#ef43b7')]:
            ss=[np.array([a,b])[:,[0,2,1]] for a,b in segments(g)];ax.add_collection3d(Line3DCollection(ss,colors=c,lw=1.3));cloud.extend(ss)
        q=np.vstack(cloud);lo=q.min(0);hi=q.max(0);span=np.maximum(.1,hi-lo)
        ax.set_xlim(lo[0]-.07*span[0],hi[0]+.07*span[0]);ax.set_ylim(lo[1]-.07*span[1],hi[1]+.07*span[1]);ax.set_zlim(lo[2]-.07*span[2],hi[2]+.07*span[2]);ax.set_box_aspect(span);ax.view_init(24,-50)
        ax.set_xlabel('x/h');ax.set_ylabel('z/h');ax.set_zlabel('vertical/h');ax.set_title('Physical axis proportions; fixed camera frame',fontsize=11)
        for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.set_major_locator(MaxNLocator(3))
        ax.tick_params(labelsize=8,pad=1)
        fig.subplots_adjust(left=.07,right=.96,top=.90,bottom=.13)
        fig.text(.06,.055,f'v1.1 {s["Q_v11"]:.2f} | no top S {s["Q_no_topS"]:.2f} | quarter top S {s["Q_quarter_topS"]:.2f} | floor IoU {s["iou_2d"]:.3f}\nH* {s["Hstar"]:.3f}; Hcenter {s["Hcenter"]:.3f}; D {s["dir"]:.2f} deg; ceiling F {s["flat"]:.2f} deg',fontsize=10)
        fig.text(.06,.012,'Existing geometry_review candidate, not a newly approved layout. Conditional reference comparison; not a participant-count trajectory.',fontsize=9)
        dest=out/f'fixed_endpoint_{r["image_code"]}.jpg';fig.savefig(dest,dpi=160,pil_kwargs={'quality':94});plt.close(fig)
        manifest.append(dict(image_code=r['image_code'],source_image=str(p.relative_to(W)),source_image_sha256=hashlib.sha256(raw).hexdigest(),source_endpoint_id=r['endpoint_id'],
            existing_point_hash=r['point_hash'],newly_projected_geometry_hash=r['geometry_hash'],figure=str(dest.relative_to(W)),
            source_points_unchanged=True,no_new_human_grade=True,no_reference_selection=True,shown_mode='research_only'))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(f'Created {len(manifest)} endpoint figures.')

if __name__=='__main__':main()
