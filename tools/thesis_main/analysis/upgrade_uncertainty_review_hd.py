"""Add full-resolution local images, vector overlays and existing Studio to review pages."""
import csv
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from tools.thesis_main.analysis.prepare_uncertainty_visual_review import OUT, ROOT, helpers, write_json, finalize
from tools.label_studio.panorama_studio.build import build


def paired_payload(points, audit):
    ordered, ids = audit.roles(points)
    return dict(width=1024, height=512, coordinate_mode='pixels', ordered_pairs=[
        dict(source_pair_id=f'raw:{ids[i]}/{ids[i+1]}', top=dict(zip(('x','y'),ordered[i].tolist())), bottom=dict(zip(('x','y'),ordered[i+1].tolist())))
        for i in range(0,len(ids),2)])


def overlay_svg(points, audit):
    lines = []
    try:
        floor, top, _ = audit.lift(points)
        for ring in (floor, top):
            for i in range(len(ring)):
                t=np.linspace(0,1,129)[:,None]
                xy=audit.project(ring[i]*(1-t)+ring[(i+1)%len(ring)]*t)
                for a,b in zip(xy[:-1],xy[1:]):
                    if abs(a[0]-b[0])<512:
                        lines.append(f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}"/>')
        for f,t in zip(floor,top):
            xy=audit.project(np.linspace(f,t,80))
            for a,b in zip(xy[:-1],xy[1:]):
                if abs(a[0]-b[0])<512: lines.append(f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}"/>')
    except ValueError:
        pass  # Invalid roles: show exact points only, never invent their pairing.
    labels=[]
    for i,p in enumerate(points):
        x,y=p
        labels.append(f'<circle cx="{x}" cy="{y}" r="2" fill="white"/><text x="{x+3}" y="{y-3}">{i}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="1024" viewBox="0 0 1024 512"><image href="panorama.png" width="1024" height="512"/><g stroke="#ffe600" stroke-width="0.7" fill="none">'+''.join(lines)+'</g><g font-size="8" font-family="sans-serif" fill="white" stroke="black" stroke-width="0.5" paint-order="stroke">'+''.join(labels)+'</g></svg>'


def run():
    audit,_=helpers()
    rows=list(csv.DictReader((OUT/'selection.csv').open(encoding='utf-8')))
    receipt=[]
    for row in rows:
        case=OUT/'cases'/row['case_id']; hd=case/'hd'; hd.mkdir(exist_ok=True)
        split = 'valid' if row['split']=='val' else row['split']
        source=ROOT/'data/mp3d_layout'/split/'img'/(row['image_id']+'.png')
        with Image.open(source) as image:
            size=image.size
            if size!=(2048,1024): raise ValueError(f'Unexpected source size: {source}: {size}')
            high=np.asarray(image.convert('RGB').resize((256,128)),float)
        with Image.open(OUT/'images'/(row['image_id']+'.jpg')) as old:
            low=np.asarray(old.convert('RGB').resize((256,128)),float)
        correlation=float(np.corrcoef(high.ravel(),low.ravel())[0,1])
        if correlation<0.95: raise ValueError(f'Image alignment requires review: {source}: {correlation}')
        shutil.copy2(source,hd/'panorama.png')
        variants=[]; links=[]
        for file in sorted(case.glob('*_source.json')):
            data=json.loads(file.read_text(encoding='utf-8')); stem=file.stem.removesuffix('_source')
            (hd/(stem+'.svg')).write_text(overlay_svg(data['points'],audit),encoding='utf-8')
            reason=''
            try: payload=paired_payload(data['points'],audit)
            except ValueError as error:
                reason=str(error)
                payload=dict(width=1024,height=512,coordinate_mode='pixels',ordered_pairs=[],unparsed_original_points=data['points'],parse_error=reason)
            write_json(hd/(stem+'.json'),payload)
            variants.append(dict(name=data['name']+(' · 原始点组' if not reason else ' · 读取受阻：'+reason),path=str(hd/(stem+'.json')),role='raw_review',source_id=data['source_id'],original_source=str(file),parse_error=reason))
            links.append(dict(name=data['name'],overlay=stem+'.svg',source_id=data['source_id']))
        build(dict(cases=[dict(image_id=row['image_id'],title=row['case_id']+' · 高清辅助检查',image=str(hd/'panorama.png'),variants=variants)],selection='Existing 50 review images; display upgrade only; fitted geometry is a diagnostic, never adjudication'),hd/'studio')
        write_json(hd/'assets.json',dict(source=source.relative_to(ROOT).as_posix(),width=size[0],height=size[1],alignment_correlation=correlation,overlays=links))
        receipt.append(dict(case_id=row['case_id'],source=source.relative_to(ROOT).as_posix(),width=size[0],height=size[1],alignment_correlation=correlation))
    write_json(OUT/'HD_UPGRADE.json',dict(images=receipt,new_visual_reviews=0,annotation_values_changed=False))
    finalize()


if __name__=='__main__': run()
