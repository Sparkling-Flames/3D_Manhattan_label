#!/usr/bin/env python3
"""Audit exact object/label bindings, assets, seam paths and local HTML references.

This does not run a browser. Visual review and that limitation are recorded in
DISPLAY_VALIDATION.json. Source audits require the cited repository files.
"""
from pathlib import Path
from html.parser import HTMLParser
import gzip, hashlib, json, re, subprocess, tempfile
import numpy as np
import pandas as pd
from PIL import Image
import render_examples

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src') and v:self.links.append(v)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    data=json.loads((HERE/'EXAMPLE_DATA.json').read_text())
    assert len(data['slots'])==93 and len(data['objects'])==39
    typical=[s for s in data['slots'] if s['image_group']!='near_collinear_feature_supplement']
    assert len(typical)==92
    frame=pd.DataFrame(typical)
    sizes=frame.groupby(['image','method','class_id']).size()
    expected=frame.groupby(['image','method','class_id']).class_available.first().clip(upper=2)
    assert sizes.equals(expected.rename(None))
    assert frame[frame.method.eq('OPPJOINT_K4')].groupby('image').size().eq(7).all()
    assert not frame.duplicated(['image','method','class_id','object_id']).any()
    assert frame.groupby('image').time_source.nunique().eq(1).all()
    assert frame.source_active_time_seconds.gt(0).all()
    assert set(frame.scope)=={'primary'} and set(frame.layer)=={'ordinary_manual'}
    originals=json.loads(gzip.decompress((HERE/'SOURCE_OBJECTS.json.gz').read_bytes()))
    original_by_id={x['object_id']:x for x in originals}
    for k,o in data['objects'].items():
        assert o['points_1024x512']==original_by_id[k]['points_1024x512']
        assert o['ordered_source_pair_indices']==original_by_id[k]['ordered_source_pair_indices']
    source_checks=[]
    audit=json.loads((HERE/'BINDING_AND_VERIFICATION.json').read_text())
    for f in audit['source_files']:
        p=ROOT/f['path']
        if p.is_file():assert sha(p)==f['sha256']
        source_checks.append(dict(path=f['path'],local_present=p.is_file(),sha256_match=p.is_file() and sha(p)==f['sha256']))
    label_sources={
      'TARGET_DSTRUCT_K3':'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz',
      'RFUSE_GEOM_K2':'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/rfuse/RFUSE_LABELS_ALL_LOBO.csv.gz',
      'OPPJOINT_K3':'research/workers/personnel_v21_reselection_20261029/classification/MAIN45_LABELS_ALL_LOBO.csv.gz',
      'OPPJOINT_K4':'research/workers/personnel_v21_reselection_20261029/classification/MAIN45_LABELS_ALL_LOBO.csv.gz'}
    independent_label_checks=[]
    for method,path in label_sources.items():
        p=ROOT/path
        if p.is_file():
            lab=pd.read_csv(p,keep_default_na=False,low_memory=False)
            lab=lab[lab.method.eq(method)].set_index(['heldout_building','worker_id'])
            for s in data['slots']:
                if s['method']!=method:continue
                row=lab.loc[(s['fold'],s['worker_id'])]
                assert str(row.known).lower()=='true' and row.class_id==s['class_id']
            independent_label_checks.append(dict(method=method,path=path,sha256=sha(p),match=True))
        else:independent_label_checks.append(dict(method=method,path=path,match=None))
    source_images=[]
    for r in json.loads((HERE/'ORIGINAL_IMAGE_RECEIPT.json').read_text()):
        p=HERE/r['path'];assert sha(p)==r['sha256']
        with Image.open(p) as im:
            im.load();assert im.size==(r['width'],r['height'])==(2048,1024)
        source_images.append(dict(path=r['path'],sha256=r['sha256'],complete_png=True))
    pngs=[]
    for p in sorted((HERE/'figures').glob('*.png')):
        with Image.open(p) as im:im.load();size=im.size
        pngs.append(dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p),size=list(size),complete_png=True))
    assert len(pngs)==17
    enriched=render_examples.enrich(data);segment_count=0;max_seam_step=0.;max_endpoint_error=0.
    for o in list(enriched['objects'].values())+list(enriched['references'].values()):
        points=np.array(o['points_1024x512'])
        for sg in o['panorama_segments']:
            a=np.array(sg['xy']);assert np.isfinite(a).all()
            assert ((a[:,0]>=-1e-7)&(a[:,0]<=1024+1e-7)).all()
            step=float(abs(np.diff(a[:,0])).max());max_seam_step=max(max_seam_step,step)
            assert step<=512+1e-7;segment_count+=1
        for level in (0,1):
            for k,p in enumerate(points[level::2],1):
                starts=[s['xy'][0] for s in o['panorama_segments'] if s['level']==level and s['edge']==k]
                errors=[abs((s[0]-p[0]+512)%1024-512)+abs(s[1]-p[1]) for s in starts]
                error=float(min(errors));max_endpoint_error=max(max_endpoint_error,error);assert error<1e-7
    text=(HERE/'index.html').read_text();parser=Links();parser.feed(text)
    local_links=[]
    for link in parser.links:
        if link.startswith(('https:','http:','data:','#')):continue
        assert (HERE/link.split('#')[0]).is_file(),link
        local_links.append(link)
    embedded=json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>',text,re.S).group(1))
    assert embedded['source_commit']==data['source_commit'] and len(embedded['slots'])==93
    for r in embedded['images']:assert (HERE/r['path']).is_file()
    for r in embedded['products']:assert (HERE/r['path']).is_file()
    scripts=re.findall(r'<script>(.*?)</script>',text,re.S);assert len(scripts)==1
    with tempfile.TemporaryDirectory() as temp:
        file=Path(temp)/'viewer.js';file.write_text(scripts[0]);result=subprocess.run(['node','--check',str(file)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    out=dict(status='passed',objects=39,typical_slots=92,feature_supplement_slots=1,originals=source_images,
       generated_pngs=pngs,all_source_coordinate_arrays_and_saved_orders_identical=True,
       model_label_checks_against_original_tables=independent_label_checks,source_hash_checks=source_checks,
       full_spherical_boundary_segments=segment_count,max_segment_x_step=max_seam_step,
       max_original_vertex_projection_error_px=max_endpoint_error,local_html_links_checked=len(local_links),
       local_html_images_and_figure_paths_checked=True,javascript_syntax='node --check passed',
       visual_review='Original 12 main plates and near-collinear plate retained; four added JOINT K4 plates visually reviewed, including singleton-class labels and complete annotation/metric panels',
       browser_interaction_test='not_performed_no_installed_browser; no claim of browser runtime validation',
       html_sha256=sha(HERE/'index.html'))
    (HERE/'DISPLAY_VALIDATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['status','objects','typical_slots','feature_supplement_slots','full_spherical_boundary_segments','max_original_vertex_projection_error_px','local_html_links_checked']},ensure_ascii=False))

if __name__=='__main__':main()
