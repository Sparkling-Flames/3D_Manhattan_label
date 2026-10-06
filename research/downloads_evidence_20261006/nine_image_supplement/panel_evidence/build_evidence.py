"""Read-only scientific figures for five explicitly selected shortfall cases."""
import json, hashlib, argparse
from pathlib import Path
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--handoff',type=Path,required=True,help='Extracted handoff directory containing inputs.json, baselines.json, evidence/ and images/')
parser.add_argument('--out',type=Path,required=True,help='Output directory for evidence figures and source data')
args=parser.parse_args()
SRC=args.handoff.resolve()
OUT=args.out.resolve()
OUT.mkdir(parents=True,exist_ok=True)
inputs=json.loads((SRC/'inputs.json').read_text())
baselines=json.loads((SRC/'baselines.json').read_text())
audit=json.loads((SRC/'evidence/all_image_pair_count_audit.json').read_text())
rows=[r for r in audit['rows'] if r['threshold_deg']==12 and r['route']=='paired' and r['below_four_selected_pairs']]
assert len(rows)==5
expected={r['image'] for r in rows}
images={im['image']:im for im in inputs['images']}
states={(s['image'],s['threshold_deg'],s['route']):s['result'] for s in baselines['states']}
summary=[]
for ar in rows:
    name=ar['image']; inp=images[name]; r=states[(name,12,'paired')]
    path=SRC/'images'/f'{name}.png'; pic=Image.open(path)
    assert pic.size==(2048,1024)
    groups=r['identity_groups']
    fig, axs=plt.subplots(2,1,figsize=(20.48,22.0),dpi=100)
    for ax in axs:
        ax.imshow(pic);ax.set_xlim(0,2048);ax.set_ylim(1024,0)
        ax.set_xticks(range(0,2049,256));ax.set_yticks(range(0,1025,256))
        ax.tick_params(labelsize=9);ax.set_xlabel('Original PNG pixels; annotation coordinates multiplied by 2',fontsize=10)
    label_pos={}; lanes=[]
    for g in sorted(groups, key=lambda x:x['center'][0][0]):
        left=max(4,min(1940,g['center'][0][0]*2-35))
        lane=next((i for i,used in enumerate(lanes) if all(abs(left-q)>130 for q in used)),len(lanes))
        if lane==len(lanes):lanes.append([])
        lanes[lane].append(left);label_pos[g['feature_id']]=(left,32+40*lane)
    for g in groups:
        col='#00f5e9' if g['selected'] else '#ffb629'
        for m in g['members']:
            for p in m['points']:
                axs[0].scatter(p[0]*2,p[1]*2,s=19,facecolors='none',edgecolors=col,linewidths=.65,alpha=.75)
        if g['center']:
            x=g['center'][0][0]*2;t=g['center'][0][1]*2;b=g['center'][1][1]*2
            axs[1].plot([x,x],[t,b],color=col,lw=1.2,alpha=.8)
            axs[1].scatter([x,x],[t,b],s=40,facecolors='none',edgecolors=col,linewidths=1.4)
            idx=int(g['feature_id'].split('_')[-1]);pos=label_pos[g['feature_id']]
            axs[1].annotate(f'{idx}: {g["support"]}/{len(inp["records"])}',(x,t),pos,fontsize=10,color=col,bbox=dict(boxstyle='round,pad=.12',facecolor='black',alpha=.68,edgecolor='none'),arrowprops=dict(arrowstyle='-',color=col,lw=.5))
    axs[0].set_title(f'{name} | Every supplied pair observation, grouped by raw paired MV at 12 deg',fontsize=15)
    axs[1].set_title('Group centers only | cyan = reached >=50%; amber = below threshold | label leaders and pair markers only; no layout edges',fontsize=13)
    fig.tight_layout(pad=1.0)
    fig.savefig(OUT/f'{name}_12deg_evidence.png',dpi=100)
    plt.close(fig)
    item={'image':name,'n_records':len(inp['records']),'threshold_deg':12,'minimum_support':r['minimum_support'],'raw_png_size':list(pic.size),'annotation_canvas':[1024,512],'overlay_scale':[2,2],'source_pair_counts':dict(Counter(len(x['points'])//2 for x in inp['records'])),'order_statuses':dict(Counter(x['order_status'] for x in inp['records'])),'groups':groups,'routes':{f'{t}_{route}': {'status':states[(name,t,route)]['status'],'selected_count':sum(g.get('selected',False) for g in states[(name,t,route)].get('identity_groups',[])) if route!='split_unique' else None,'generated_pair_count':len(states[(name,t,route)]['candidate'].get('points') or [])//2 if states[(name,t,route)]['candidate'].get('points') is not None else None} for t in [5,9,12] for route in ['paired','bottom_anchor','top_anchor','split_unique']}}
    summary.append(item)
(OUT/'five_case_evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
(OUT/'source_hashes.json').write_text(json.dumps({str(p.relative_to(SRC)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC/'inputs.json',SRC/'baselines.json',SRC/'human_review.json',SRC/'manifest.json',SRC/'evidence/all_image_pair_count_audit.json']+[SRC/'images'/f'{s["image"]}.png' for s in summary]},indent=2))
for s in summary:
 print(s['image'],s['n_records'],'pair counts',s['source_pair_counts'],'order',s['order_statuses'])
 print('routes',s['routes'])
