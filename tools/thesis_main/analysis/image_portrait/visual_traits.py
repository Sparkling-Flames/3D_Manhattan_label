"""Generate blinded, indexed original-image sheets; no outcome metadata is read."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json'
QA = ROOT / 'output/image_portrait_20260914_v1/visual_qa'
def images():
    rows = json.loads(SOURCE.read_text(encoding='utf-8'))['images']
    assert len(rows) == 648 and len({r['image_id'] for r in rows}) == 648
    return [dict(index=i, image_id=r['image_id'], path=r['path']) for i, r in enumerate(rows)]
def sheet(start, count):
    assert 0 <= start < 648 and count > 0
    rows = images()[start:start+count]
    QA.mkdir(parents=True, exist_ok=True)
    canvas = Image.new('RGB', (2048, ((len(rows)+3)//4)*280), 'white')
    draw = ImageDraw.Draw(canvas)
    for j, row in enumerate(rows):
        with Image.open(ROOT / row['path']) as image:
            thumb = image.convert('RGB')
            thumb.thumbnail((508,254))
        x,y=j%4*512,j//4*280
        canvas.paste(thumb,(x,y))
        draw.text((x+4,y+258),str(row['index']),fill='black')
    target=QA/f'{start:03d}.jpg'
    canvas.save(target,quality=95)
    print(target)
if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--start',type=int,default=0)
    parser.add_argument('--count',type=int,default=12)
    args=parser.parse_args()
    sheet(args.start,args.count)

def record(start, codes, notes):
    """Persist only explicitly reviewed rows. Codes: p/a/u; boundary p/m/u."""
    dest = ROOT / 'analysis_results/image_portrait_20260914_v1/visual/visual_traits.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    fields = ('floor_boundary','ceiling_boundary','corner_occlusion','connected_space','reflection_glass','low_contrast')
    result=json.loads(dest.read_text(encoding='utf-8')) if dest.exists() else [dict(index=r['index'],image_id=r['image_id'],reviewed=False,**dict.fromkeys(fields,'unknown'),evidence='') for r in images()]
    codes, notes=codes.split(), notes.split('|')
    assert len(codes)==len(notes) and 0 <= start < 648 and start + len(codes) <= 648
    assert [r['image_id'] for r in result] == [r['image_id'] for r in images()]
    assert all(n.strip() for n in notes)
    for i,(code,note) in enumerate(zip(codes,notes),start):
        assert len(code)==6 and set(code)<=set('pamu') and 'm' not in code[2:]
        result[i].update(dict(zip(fields,[dict(p='present',a='absent',m='partial',u='unknown')[c] for c in code])),reviewed=True,evidence=note,reviewer='AI_image_only',review_basis='508x254 original-image thumbnail; no outcome records')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('reviewed',sum(r['reviewed'] for r in result))
