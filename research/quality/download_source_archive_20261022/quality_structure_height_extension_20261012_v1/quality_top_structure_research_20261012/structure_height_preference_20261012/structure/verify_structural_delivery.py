#!/usr/bin/env python3
"""Verify delivered figures, anonymous page, source coordinates and provenance.

Checks artifact integrity, not the validity of any human quality definition.
Requires the repaired base package and this additive research directory.
"""
from __future__ import annotations
import argparse,base64,csv,hashlib,io,json,re,sys
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Page(HTMLParser):
    def __init__(self):super().__init__();self.images=[];self.text=[];self.inputs=[]
    def handle_data(self,data):self.text.append(data)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='img':self.images.append(a)
        if tag=='input':self.inputs.append(a)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());args=ap.parse_args()
    root=args.root.resolve();out=Path(__file__).resolve().parent;review=out/'review_pairs'
    mani=read(review/'material_manifest.json');assert mani['script_sha256']==sha(out/'prepare_targeted_pairs.py')
    for rel,expected in mani['source_hashes'].items():assert sha(root/rel)==expected,rel
    ri=read(review/'inputs/selected_pairs_full.json');assert len(ri['records'])==8
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    objects={r['object_id']:r for r in read(b/'inputs/current_formal_loader_data.json')['objects']}
    geometries=read(b/'inputs/current_geometry_compact.json')['geometries']
    for r in ri['records']:
        o=r['current_formal_input'];assert o==objects[o['object_id']]
        assert r['frozen_annotation_geometry']==geometries[o['object_id']]
        assert r['fixed_reference_geometry']==geometries[r['reference_object_id']]
        image_path=review/r['photo']['relative_path'];assert sha(image_path)==r['photo']['sha256']
        with Image.open(image_path) as im:assert im.size==(r['photo']['width'],r['photo']['height']);im.verify()
    all_figs=[]
    for base in [out,review]:
        for r in read(base/'figures/manifest.json'):
            p=base/r.get('file');assert sha(p)==r['sha256']
            with Image.open(p) as im:im.verify()
            all_figs.append(p)
    assert len(all_figs)==18
    page_path=review/'review_pairs_blind_user.html';page=Page();page.feed(page_path.read_text(encoding='utf-8'))
    assert sha(page_path)==mani['html_sha256'];assert len(page.images)==16
    visible=' '.join(page.text)
    assert not re.search(r'\bR\d{5}\b|\bW\d{3}\b|Q_dbounded|cap1|cap2|Hcenter|Hmean|v1\.1|预期答案|R02196',visible)
    assert all('checked' not in v for v in page.inputs)
    expected={sha(p) for p in all_figs}
    expected|={sha(review/r['photo']['relative_path']) for r in ri['records']}
    embedded=[]
    for item in page.images:
        header,data=item['src'].split(',',1);assert ';base64' in header
        raw=base64.b64decode(data,validate=True);digest=hashlib.sha256(raw).hexdigest();assert digest in expected
        with Image.open(io.BytesIO(raw)) as im:im.verify()
        embedded.append(digest)
    answers=read(review/'answers_blank.json');assert len(answers['answers'])==4
    assert all(v['processed_result_preference'] is None and v['current_input_preference'] is None and v['confidence'] is None for v in answers['answers'])
    num=read(out/'results/run_manifest.json');assert num['script_sha256']==sha(out/'run_structure_audit.py')
    assert num['synthetic_count']==num['synthetic_available']==43
    assert num['real_summary']['pool_count']==907 and num['real_summary']['real39_count']==39
    for rel,expected_hash in num['source_hashes'].items():assert sha(root/rel)==expected_hash,rel
    # Retain rejected selections and verify their copied source layers exactly.
    rejected=read(review/'nonselected_cases_research.json')
    for group in rejected['rejects']:
        for r in group['source_records']:
            o=r['current_input'];assert o==objects[o['object_id']]
            assert r['frozen_annotation_geometry']==geometries[o['object_id']]
            assert r['new_human_quality'] is None
    result={'actual_utc':datetime.now(timezone.utc).isoformat(),'verification_kind':'file integrity and exact source alignment; not human validation',
            'all_checks_passed':True,'figures_verified':18,'embedded_image_instances_verified':len(embedded),'anonymous_pairs':4,'distinct_pair_images':len({r['image_id'] for r in ri['records']}),
            'source_versions_verified':8,'new_human_labels_created':0,'anonymous_page_no_record_worker_or_method_strings':True,'all_answers_missing':True,
            'synthetic_count':43,'aligned_real_rows':39,'conditional_development_rows':907,'shared_physical_limits_per_pair':ri['shared_limits'],
            'html_sha256':sha(page_path),'script_sha256':sha(Path(__file__)),'run_manifest_sha256':sha(out/'results/run_manifest.json'),
            'source_images_prioritized_from_delivered_hashed_copies':True,
            'actual_visual_inspection':'All 12 new pair plates and all 6 final research plates; source originals inspected. Exact pixel crops verified T21 title/ticks and C02 title after high-level preview appeared clipped.'}
    (out/'results/delivery_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='shared_physical_limits_per_pair'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
