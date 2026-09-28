"""Recreate eight purposively stratified review pairs; not a prevalence sample."""
import sys, json, base64, io, re
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'analysis_results/panorama_research_received_20260921/original_package/code'))
import common as c
c.configure(ROOT/'analysis_results/panorama_research_received_20260921/local_recompute/source_work')
_, recs, views, _, _ = c.load()
membership = pd.read_csv(ROOT/'analysis_results/panorama_research_received_20260921/original_package/results/current_memberships.csv')
foundation = ROOT/'analysis_results/panorama_studio_20260907_v3'
lookup = {s['image_id']:s for s in json.JSONDecoder().raw_decode((foundation/'history_data.js').read_text(encoding='utf8').split('push(...',1)[1])[0]}
selected = [('W037','B6ByNegPMKs-33'),('W037','uNb9QFRL6hY-26'),('W037','q9vSo1VnCiC-09'),('W037','UwV83HsGsw3-06'),('W037','rPc6DW4iMge-01'),('W037','X7HyMhZNoso-13'),('W012','UwV83HsGsw3-23'),('W034','q9vSo1VnCiC-13')]
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
(OUT/'tmp_panels').mkdir(exist_ok=True)
manifest=[]
for rank,(worker,code) in enumerate(selected,1):
    v=next(v for v in views.values() if v['code']==code)
    i=v['workers'].index(worker); ds=v['d'][i].copy();ds[i]=2e6;j=int(ds.argmin())
    same_count=ds[j]<1e6
    if not same_count:
        mm=membership[(membership.image_id==v['image_id'])&(membership.method=='complete')&(membership.worker!=worker)]
        largest=mm.sort_values(['cluster_size','id'],ascending=[False,True]).iloc[0]
        j=v['ids'].index(largest['id'])
    assert membership[(membership.id==v['ids'][i])&(membership.method=='complete')].iloc[0].cluster_size==1
    ids=[v['ids'][i],v['ids'][j]]
    raw=(foundation/lookup[v['image_id']]['history_script']).read_text(encoding='utf8')
    encoded=re.search(r'\{const image="data:image/[^;]+;base64,([^"]+)"',raw).group(1)
    bg=Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB').resize((1024,512))
    canvas=Image.new('RGB',(1024,1120),'white')
    for side,cid in enumerate(ids):
        a=recs[cid];im=bg.copy();d=ImageDraw.Draw(im);color='#ff5030' if side==0 else '#00c7ff'
        for idx,(x,y) in enumerate(a['p']):
            d.ellipse((x-4,y-4,x+4,y+4),fill=color,outline='black')
            d.text((min(x+5,970),max(0,y-17)),f'p{idx+1}',fill=color,font=font,stroke_width=1,stroke_fill='black')
        canvas.paste(im,(0,side*560+48));d=ImageDraw.Draw(canvas)
        d.text((8,side*560+5),f'{rank} {code} {v["workers"][[i,j][side]]} {cid} | {len(a["p"])} points',fill='black',font=font)
        d.text((8,side*560+26),'Effective source point index; no inferred wall edges.',fill='black',font=font)
    canvas.save(OUT/'tmp_panels'/f'{rank:02}.jpg',quality=94)
    item=dict(case=rank,code=code,image_id=v['image_id'],workers=[v['workers'][i],v['workers'][j]],ids=ids,N=v['N'],point_counts=[len(recs[z]['p']) for z in ids],distance_px=float(v['d'][i,j]) if same_count else None,comparison='nearest same-count response' if same_count else 'canonical-first member of largest complete cluster; no same-count peer',pairs_1based=[(recs[z]['links']+1).tolist() for z in ids])
    if same_count:
        a,b=[recs[z] for z in ids];p,q=a['p'][a['links']],b['p'][b['links']];dist=np.hypot(abs((p[:,:,0]-q[:,:,0]+512)%1024-512),p[:,:,1]-q[:,:,1]);k=np.unravel_index(dist.argmax(),dist.shape)
        item['max_distance_point_pair_1based']=[int(a['links'][k])+1,int(b['links'][k])+1]
    manifest.append(item)
assert len(manifest)==8 and len({x['ids'][0] for x in manifest})==8
(OUT/'selection.json').write_text(json.dumps(c.clean(manifest),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(c.clean(manifest),ensure_ascii=False))
