import json,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
R=Path('D:/Work/HOHONET');O=Path(__file__).parent
d=json.loads((R/'analysis_results/worker_count_composition_20261006/input.json').read_text(encoding='utf-8'))
source=json.loads((R/'analysis_results/research_input_20260929/preprocessed_source.json').read_text(encoding='utf-8'))
mapping={f'R{i:05d}':o for i,o in enumerate(sorted(source['objects'],key=lambda o:o['object_id']),1)}
comments=json.loads((R/'analysis_results/research_input_20260929/comments.json').read_text(encoding='utf-8'))
selected={i:mapping[i] for i in ('R01301','R02122','R00087')}
evidence={}
for alias,obj in selected.items():
    g=next(g for g in d['groups'] if any(r['id']==alias for r in g['records']))
    rec=next(r for r in g['records'] if r['id']==alias)
    assert rec['points']==obj['points_1024x512']
    matches=[{k:x.get(k) for k in ('text','updated_at','source_file','json_pointer','binding_status','text_role','occurrence_id')} for x in comments['occurrences'] if x.get('object_id')==obj['object_id'] and x['source_kind']=='frozen_feedback']
    evidence[alias]=dict(object_id=obj['object_id'],image=g['image'],comments=matches)

g=next(g for g in d['groups'] if g['image']=='e9zR4mvMWw7-19')
per=list(csv.DictReader((R/'analysis_results/worker_count_composition_20261006/per_image.csv').open(encoding='utf-8-sig')))
key=next(r['basis_key'] for r in per if r['image']==g['image']);b=np.load(R/'analysis_results/worker_count_composition_20261006/integration_bases.npz')
p=b[key+'_patterns'];a=b[key+'_area'];j=next(j for j,r in enumerate(g['records']) if r['id']=='R01301')
support=np.array([int(x).bit_count() for x in p]);target=np.array([bool(int(x)&(1<<j)) for x in p]);outside=target & (support<12)
evidence['R01301']['outside_mv50_area']=float(sum(a[outside]));evidence['R01301']['outside_singleton_fraction']=float(sum(a[outside & (support==1)])/sum(a[outside]))

for code,ids in [('e9zR4mvMWw7-19',['R01301','R02122']),('e9zR4mvMWw7-16',['R00087'])]:
    g=next(g for g in d['groups'] if g['image']==code)
    im=Image.open(R/f'research/fast_research_handoff_20261006/quality_images/{code}.png')
    fig,axs=plt.subplots(len(ids),1,figsize=(16,5*len(ids)),squeeze=False)
    for ax,alias in zip(axs[:,0],ids):
        ax.imshow(im,extent=(0,1024,512,0))
        rec=next(r for r in g['records'] if r['id']==alias);pts=np.array(rec['points'])
        for j in range(len(pts)//2):
            ax.plot(pts[j*2:j*2+2,0],pts[j*2:j*2+2,1],color='#ff4040',linewidth=1)
            ax.scatter(pts[j*2:j*2+2,0],pts[j*2:j*2+2,1],s=26,facecolors='none',edgecolors='#ffff00',linewidths=1.5)
            ax.text(pts[2*j,0]+3,pts[2*j,1]-4,str(j),color='yellow',fontsize=9,bbox=dict(facecolor='black',alpha=.6,pad=1))
        if alias=='R00087':
            ref=next(r for r in g['references'] if r['version']=='manual_revision');q=np.array(ref['points'])
            ax.scatter(q[:,0],q[:,1],s=25,c='#00ffff',marker='+',label='Existing revised GT endpoints')
            ax.legend(loc='upper left')
        ax.set(title=f'{code} / {alias} - saved paired endpoints, zero-based pair indices; no inferred edges',xlim=(0,1024),ylim=(512,0))
    fig.tight_layout();fig.savefig(O/f'{code}_endpoints.png',dpi=130);plt.close(fig)
(O/'visual_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(evidence))
