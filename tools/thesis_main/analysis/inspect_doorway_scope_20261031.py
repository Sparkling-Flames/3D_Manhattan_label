"""Quality-blind BEV contact sheets for pending scope and historical bindings."""
import json,gzip,zipfile
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from tools.thesis_main.analysis.supplement_doorway_preparation_20261031 import floor
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030'
OUT=BASE/'pro_delivery_independent_audit_20261031'
def main():
    pending=json.loads((OUT/'CORRECTION_OVERLAY.json').read_text(encoding='utf8'))
    pending=[r for r in pending if r['correction_reasons']]
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        records=json.loads(gzip.decompress(z.read('HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz')))
    final={r['image']:r for r in json.loads((BASE/'curve_preparation_v21/full_review_20261031/ALIGNMENT_DECISIONS.json').read_text(encoding='utf8'))}
    cases={c['image']:c for c in json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']}
    for im in sorted({r['image'] for r in pending}):
        rows=[r for r in pending if r['image']==im]
        fig,axs=plt.subplots(int(np.ceil(len(rows)/5)),5,figsize=(18,3.5*int(np.ceil(len(rows)/5))),squeeze=False)
        polygons=final[im]['space_polygons'];allpts=np.concatenate(polygons);lo=allpts.min(0);hi=allpts.max(0);pad=(hi-lo)*.12+.05
        for ax,r in zip(axs.flat,rows):
            for poly,color in zip(polygons,['#00acbc','#fa8b30']):
                p=np.array(poly);ax.fill(p[:,0],p[:,1],color=color,alpha=.25);p=np.vstack([p,p[0]]);ax.plot(p[:,0],p[:,1],color=color,lw=1)
            p=np.array(floor(records[r['object_id']]['points']));p=np.vstack([p,p[0]])
            ax.plot(p[:,0],p[:,1],'-o',color='black',lw=1,ms=3);ax.scatter([0],[0],c='red',s=20)
            ax.set_xlim(lo[0]-pad[0],hi[0]+pad[0]);ax.set_ylim(lo[1]-pad[1],hi[1]+pad[1]);ax.set_aspect('equal');ax.set_title(r['worker']+' '+str(r['frozen_scope']).replace('空间','S').replace('全部','ALL'));ax.grid(alpha=.2)
        for ax in list(axs.flat)[len(rows):]:ax.axis('off')
        fig.suptitle(im+' | cyan=S1 orange=S2 black=answer red=camera; outside viewport may be clipped',fontsize=13);fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(OUT/(im+'_scope.png'),dpi=110);plt.close(fig)
        photo=(BASE/cases[im]['photo']).resolve();assert photo.exists()
        print(im,len(rows),photo)
if __name__=='__main__':main()
