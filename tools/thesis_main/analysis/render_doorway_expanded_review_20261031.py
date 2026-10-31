"""Original-panorama evidence sheets for the remaining unadjudicated answers."""
import gzip,json,math,zipfile
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
from tools.thesis_main.analysis.supplement_doorway_preparation_20261031 import floor
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030'
OUT=BASE/'expanded_visual_review_20261031'

def load():
    rows=json.loads((OUT/'REVIEW_INPUT.json').read_text(encoding='utf8'))
    cases={x['image']:x for x in json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']}
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        records=json.loads(gzip.decompress(z.read('HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz')))
    return rows,cases,records

def pane(row,record,photo,index,width=512):
    scale=width/1024;image=Image.new('RGB',(width,int(512*scale)+24),'white')
    image.paste(photo.resize((width,int(512*scale))),(0,24));draw=ImageDraw.Draw(image)
    draw.text((5,5),f'{index} {row["image"]} {row["worker"]}',fill='black')
    pts=record['points'];xz=floor(pts);bottom=[[x,-1,z] for x,z in xz];top=[]
    for i,(u,v) in enumerate(pts[::2]):
        a=(u/1024-.5)*math.tau;d=math.hypot(*xz[i]);top.append([d*math.sin(a),d*math.tan((.5-v/512)*math.pi),-d*math.cos(a)])
    for ring in [bottom,top]:
        for a,b in zip(ring,ring[1:]+ring[:1]):
            last=None
            for t in np.linspace(0,1,70):
                x,y,z=np.array(a)*(1-t)+np.array(b)*t
                point=((math.atan2(x,-z)/math.tau+.5)*width,(.5-math.atan2(y,math.hypot(x,z))/math.pi)*width/2+24)
                if last and abs(point[0]-last[0])<width/2:draw.line([last,point],fill='#ff24db',width=max(1,int(scale*2)))
                last=point
    for j in range(0,len(pts),2):
        a,b=pts[j:j+2];draw.line([(a[0]*scale,a[1]*scale+24),(b[0]*scale,b[1]*scale+24)],fill='#ff24db')
        for x,y in [a,b]:
            x,y=x*scale,y*scale+24;draw.ellipse([x-2,y-2,x+2,y+2],fill='yellow')
            if width>=1024:draw.text((x+4,y-5),str(j//2+1),fill='yellow')
    return image

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--detail',nargs='*',type=int);args=parser.parse_args()
    rows,cases,records=load();photos={im:Image.open(BASE/c['photo']).convert('RGB') for im,c in cases.items()}
    if args.detail:
        for i in args.detail:
            r=rows[i];pane(r,records[r['object_id']],photos[r['image']],i,1024).save(OUT/f'detail_{i:03}.jpg')
        return
    assert len(rows)==524 and len({r['object_id'] for r in rows})==524
    manifest=[]
    for start in range(0,len(rows),12):
        selected=list(enumerate(rows[start:start+12],start));sheet=Image.new('RGB',(1536,280*math.ceil(len(selected)/3)),'white')
        for j,(i,r) in enumerate(selected):
            sheet.paste(pane(r,records[r['object_id']],photos[r['image']],i),(512*(j%3),280*(j//3)))
        name=f'sheet_{start//12:02}.jpg';sheet.save(OUT/name,quality=95)
        manifest.append(dict(file=name,indices=[i for i,_ in selected]))
    (OUT/'SHEETS.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('524 records, 44 original-panorama annotation sheets; no quality scores or statistical plots')

if __name__=='__main__':main()
