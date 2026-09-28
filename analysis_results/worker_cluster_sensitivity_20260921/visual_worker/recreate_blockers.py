"""Inspect farthest members of the nearest neighbour's complete-link cluster."""
import sys,json,base64,io,re
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'analysis_results/panorama_research_received_20260921/original_package/code'))
import common as c
c.configure(ROOT/'analysis_results/panorama_research_received_20260921/local_recompute/source_work')
_,recs,views,_,_=c.load()
members=pd.read_csv(ROOT/'analysis_results/panorama_research_received_20260921/original_package/results/current_memberships.csv')
foundation=ROOT/'analysis_results/panorama_studio_20260907_v3'
lookup={s['image_id']:s for s in json.JSONDecoder().raw_decode((foundation/'history_data.js').read_text(encoding='utf8').split('push(...',1)[1])[0]}
selection=json.loads((OUT/'selection.json').read_text(encoding='utf8'));result=[]
(OUT/'tmp_panels').mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
for case in [r for r in selection if r['case'] in [5,6]]:
    v=views[case['image_id']];a,b=case['ids'];i,j=[v['ids'].index(x) for x in [a,b]]
    mm=members[(members.image_id==v['image_id'])&(members.method=='complete')]
    label=mm[mm.id==b].iloc[0].label;group=mm[mm.label==label].id.tolist()
    blocker=max(group,key=lambda z:(v['d'][i,v['ids'].index(z)],z));k=v['ids'].index(blocker)
    assert v['d'][i,j]<=25.6 and v['d'][i,k]>25.6 and v['d'][j,k]<=25.6
    ra,rb=recs[a],recs[blocker];p,q=ra['p'][ra['links']],rb['p'][rb['links']]
    distances=np.hypot(abs((p[:,:,0]-q[:,:,0]+512)%1024-512),p[:,:,1]-q[:,:,1]);h=np.unravel_index(distances.argmax(),distances.shape)
    r=dict(code=case['code'],image_id=v['image_id'],ids=[a,b,blocker],workers=[v['workers'][z] for z in [i,j,k]],nearest_cluster_members=group,nearest_distance_px=float(v['d'][i,j]),blocking_distance_px=float(v['d'][i,k]),neighbor_to_blocker_distance_px=float(v['d'][j,k]),blocking_points_1based=[int(ra['links'][h])+1,int(rb['links'][h])+1],blocking_endpoints=[p[h].tolist(),q[h].tolist()])
    raw=(foundation/lookup[v['image_id']]['history_script']).read_text(encoding='utf8');encoded=re.search(r'\{const image="data:image/[^;]+;base64,([^"]+)"',raw).group(1)
    bg=Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB').resize((1024,512))
    canvas=Image.new('RGB',(1024,1120),'white')
    for side in [0,1]:
        im=bg.copy();d=ImageDraw.Draw(im)
        plotted=[(blocker,'#ffea00','C')] if side==0 else [(a,'#ff5030','A'),(b,'#00c7ff','B'),(blocker,'#ffea00','C')]
        for cid,color,prefix in plotted:
            for index,(x,y) in enumerate(recs[cid]['p'],1):
                d.ellipse((x-3,y-3,x+3,y+3),fill=color,outline='black')
                if side==0:d.text((min(x+4,965),max(0,y-16)),f'p{index}',fill=color,font=font,stroke_width=1,stroke_fill='black')
        canvas.paste(im,(0,side*560+48));d=ImageDraw.Draw(canvas)
        d.text((8,side*560+6),f'{case["code"]}: C={r["workers"][2]} {blocker}' if side==0 else f'A=red W037; B=cyan {r["workers"][1]}; C=yellow {r["workers"][2]}; none is GT',fill='black',font=font)
        d.text((8,side*560+27),f'A-B={r["nearest_distance_px"]:.3f}; A-C={r["blocking_distance_px"]:.3f}; B-C={r["neighbor_to_blocker_distance_px"]:.3f}',fill='black',font=font)
    canvas.save(OUT/'tmp_panels'/f'blocker_{case["case"]}.jpg',quality=94);result.append(r)
assert len(result)==2
(OUT/'blocking_pairs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
