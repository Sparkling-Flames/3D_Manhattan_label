"""Build the offline, source-bound manual-order review addition.

This exports saved numeric results and original release images. It performs no
fusion, scoring, classification, geometry editing or network operation.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil

from .apply_manual_ring_orders_20261104 import ROOT, BASE_COMMIT

IMPACT = ROOT / 'research/fusion/manual_order_impact_20261104'
SITE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
ASSETS = SITE / 'v21-manual-order'


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def csv_rows(path):
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', type=Path, default=ROOT.parent / 'original_images')
    parser.add_argument('--font-source', type=Path, help='Optional original Noto Sans CJK SC OTF for reproducible offline font subsetting')
    args = parser.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    images_out = ASSETS / 'original_images'
    images_out.mkdir(exist_ok=True)
    with gzip.open(IMPACT / 'endpoints/ENDPOINTS.jsonl.gz', 'rt') as f:
        endpoints = [json.loads(line) for line in f]
    with gzip.open(IMPACT / 'coordinate_candidate/CANDIDATE_FULL_STATE.json.gz', 'rt') as f:
        candidate = json.load(f)[1]
    refs = csv_rows(IMPACT / 'dependencies/CURRENT_EXACT_REFERENCES.csv.gz')
    scope = csv_rows(IMPACT / 'dependencies/MODULE_REFERENCE_SCOPE.csv')
    metric_keys = ['B8L2', 'D10', 'IoU3D100', 'WQ', 'score_status', 'geometry_status',
                   'connection_available', 'complete_evaluable', 'floor_evaluable',
                   'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'omission', 'extension',
                   'boundary_loss', 'direction_loss', 'global_height_loss', 'local_height_loss',
                   'height_loss', 'floor_area_camera_h2', 'height_mean_h', 'floor_turn5_n',
                   'floor_short_edge_03_n', 'diag_corner_recall_05', 'diag_wall_coverage_03',
                   'ref_node_recall_5', 'ref_edge_recall_5', 'nodes', 'geometry_reason']
    image_manifest = []
    data = []
    for e in endpoints:
        rs = [r for r in refs if r['team_key'] == e['team_key']]
        image_name = e['image_id'] + '.png'
        src = args.images / image_name
        dst = images_out / image_name
        if not src.exists():
            raise FileNotFoundError(src)
        if not dst.exists() or hashlib.sha256(src.read_bytes()).digest() != hashlib.sha256(dst.read_bytes()).digest():
            shutil.copyfile(src, dst)
        if not any(x['filename'] == image_name for x in image_manifest):
            image_manifest.append({'filename': image_name, 'image': e['image'],
                                   'bytes': dst.stat().st_size,
                                   'sha256': hashlib.sha256(dst.read_bytes()).hexdigest()})
        item = {k: e[k] for k in ['team_key', 'review_id', 'group_id', 'image', 'image_id',
                                    'building', 'k', 'pool_id', 'reference_id', 'reference_version',
                                    'member_workers', 'manual_feature_order', 'source_records']}
        item.update(nodes=e['fixed_nodes'],
                    automatic={k: e['automatic'].get(k) for k in metric_keys},
                    assisted={k: e['assisted'].get(k) for k in metric_keys},
                    audit=e['geometry_check'],
                    reference={k: e['reference_snapshot'].get(k) for k in ['points_1024x512', 'floor_xz_h', 'status', 'method']},
                    modules=sorted(set(r['module'] for r in rs)), references=rs)
        if e['review_id'] == 'fdca268760f9dcc2c83ace58':
            item['candidate'] = dict(score={k: candidate['score'].get(k) for k in metric_keys},
                                     nodes=candidate['nodes'], audit=candidate['geometry_audit'])
        data.append(item)
    assert len(data) == 57 and len(image_manifest) == 22 and len(refs) == 536
    report_rows = csv_rows(IMPACT / 'CONCLUSION_MATRIX.csv')
    payload = clean(dict(version='v21_targeted_manual_order_assisted_20261104_v1',
                        source_commit=BASE_COMMIT, endpoints=data, modules=scope,
                        conclusions=report_rows, images=image_manifest))
    (ASSETS / 'data.js').write_text('window.MANUAL_ORDER_DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + ';\n', encoding='utf-8')
    for name in ['IMAGE_INDEX.csv', 'SELECTED_IMAGE_PROVENANCE.json', 'ORIGINAL_IMAGE_CHECKS.json']:
        source = args.images / name
        if not source.exists():
            source = args.images.parent / name
        if source.resolve() != (ASSETS / name).resolve():
            shutil.copyfile(source, ASSETS / name)
    (ASSETS / 'IMAGE_MANIFEST.json').write_text(json.dumps(image_manifest, indent=2, ensure_ascii=False) + '\n')
    if args.font_source:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        font = TTFont(args.font_source)
        text = (SITE/'v21-manual-order.html').read_text(encoding='utf-8') + ''.join(p.read_text(encoding='utf-8') for p in ASSETS.glob('*.js'))
        characters = set(map(ord,text)) | set(range(32,127))
        options = subset.Options(); options.name_IDs=['*']; options.name_legacy=True; options.name_languages=['*']
        sub = subset.Subsetter(options=options); sub.populate(unicodes=characters); sub.subset(font)
        names = {1:'HOHONET Sans',4:'HOHONET Sans Regular',6:'HOHONETSans-Regular',16:'HOHONET Sans',17:'Regular'}
        for name in font['name'].names:
            if name.nameID in names: name.string=names[name.nameID].encode(name.getEncoding())
        target=ASSETS/'fonts/HOHONETSans-Regular.otf'; target.parent.mkdir(exist_ok=True); font.save(target)
        provenance=dict(source='https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
                        license='SIL Open Font License 1.1',transformation='subset to page/data Unicode; renamed family HOHONET Sans',
                        source_sha256=hashlib.sha256(args.font_source.read_bytes()).hexdigest(),
                        output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),unicode_requested=len(characters),bytes=target.stat().st_size)
        (target.parent/'PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'endpoints': len(data), 'images': len(image_manifest), 'references': len(refs),
                      'conclusions': len(report_rows), 'image_bytes': sum(x['bytes'] for x in image_manifest),
                      'data_bytes': (ASSETS / 'data.js').stat().st_size}))


if __name__ == '__main__':
    main()
