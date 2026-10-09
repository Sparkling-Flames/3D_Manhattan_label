import csv,json,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
OUT=ROOT/'analysis_results/image_difficulty_full_review_20261010/agent_visual'
def read(p):
 return list(csv.DictReader(open(p,encoding='utf-8-sig')))
b=ROOT/'analysis_results/objective_difficulty_20261009'
w={r['image']:r for r in read(b/'review_examples/working_classification_20261010.csv')}
s={r['image_id']:r for r in read(b/'model_comparison/image_source_audit.csv')}
o={r['object_id']:r for r in load_current_bundle()['data']['objects']}
p=json.load(open(ROOT/'analysis_results/adaptive_point_20261007/expanded/inputs.json',encoding='utf-8'))['images']
old_ids={r['image_id'] for r in p}
full=json.load(open(ROOT/'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json',encoding='utf-8'))['images']
p += [r for r in full if r['image_id'] not in old_ids]
current_ids={r['image_id'] for r in p}
p += [r for r in w.values() if r['image_id'] not in current_ids]
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
records=[]
for z in range(0,len(p),4):
 canvas=Image.new('RGB',(2048,1120),'white');d=ImageDraw.Draw(canvas)
 for k,v in enumerate(p[z:z+4]):
  r=w[v['image']];iid=r['image_id'];path=s[iid]['hohonet_path'];assert v['image_id']==iid
  im=Image.open(path).convert('RGB').resize((1024,512));di=ImageDraw.Draw(im)
  pts=o[r['gt_object_id']]['points_1024x512']; assert len(pts)==int(r['N'])*2
  for i,(x,y) in enumerate(pts):
   di.ellipse((x-4,y-4,x+4,y+4),fill='yellow',outline='black');di.text((x+5,y-16),str(i//2+1),font=font,fill='yellow',stroke_width=1,stroke_fill='black')
  x=k%2*1024;y=k//2*560;canvas.paste(im,(x,y+48));d.text((x+8,y+10),f'{z+k+1:03d} {r["image"]} N={r["N"]} H={r["H"]} {r["assessment_track"]}',font=font,fill='black')
  records.append(dict(serial=z+k+1,in_old_137=iid in old_ids,in_current_178=iid in current_ids,**r,image_path=path,review_page=f'page_{z//4+1:02d}.jpg'))
 canvas.save(OUT/f'page_{z//4+1:02d}.jpg',quality=94)
assert len(records)==259 and len({r['image_id'] for r in records})==259
(OUT/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(len(records))
