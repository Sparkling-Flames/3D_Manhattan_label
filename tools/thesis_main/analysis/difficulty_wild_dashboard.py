"""Build a portable offline HTML explorer of the completed Manual 35 batch."""
from __future__ import annotations
import argparse
import base64
import collections
import io
import json
from pathlib import Path
from PIL import Image

from . import simulate_annotators as base
from .difficulty_wild_inputs import load_inputs, read


def rounded(points):
    return [[round(float(x), 3), round(float(y), 3)] for x, y in points]


def build(run):
    run = Path(run).resolve()
    sources = load_inputs()
    rows = base.read_jsonl(run / 'simulations.jsonl')
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row['image_id']].append(row)
    images = []
    for iid, group in sorted(grouped.items()):
        d = sources['difficulty'][iid]
        photo = next((base.ROOT / 'data/mp3d_layout').glob('*/img/' + iid + '.png'))
        with Image.open(photo) as raw:
            thumb = raw.convert('RGB').resize((768, 384), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            thumb.save(output, 'JPEG', quality=76, optimize=True)
        humans = []
        for r in sources['shared']:
            if r['image_id'] != iid or r['condition'] != 'manual':
                continue
            obj = sources['objects'][r['object_id']]
            pts = obj.get('points_1024x512')
            if not pts or len(pts) % 2 or not obj.get('links_zero_based'):
                continue
            humans.append(dict(id=r['object_id'], worker=r['worker_id'], points=rounded(pts),
                               disposition=r['cleaning_disposition'], independent=r['independent_vote_eligible']))
        samples = []
        for row in sorted(group, key=lambda r: r['export_worker_id']):
            e = row['evaluation']
            samples.append(dict(id=row['export_worker_id'], points=rounded(row['points']),
                wild=row['wild'], types=row['wild_error_types'], family=row['model_family'],
                worker='W' + row['source_worker_profile_id'].zfill(3),
                donor=row['residual_donor_annotation_id'], donorWorker=row['residual_donor_worker_id'],
                donorBuilding=row['residual_donor_building_id'], heldout=row['held_out_building'],
                active=round(row['active_time_seconds'], 2), lead=round(row['lead_time_seconds'], 2),
                response=row['worker_scope_response'], seed=str(row['seed']),
                B8L2=e['B8L2'], D10=e['D10'], floor=e['floor_iou'], status=e['status'],
                geometry=row['geometry_status'], retries=row['duplicate_geometry_retries']))
        reference = sources['v6_references'].get(d['difficulty_target_id'], {})
        images.append(dict(id=iid, code=d['image'], difficulty=d['difficulty_class'],
            photo='data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii'),
            real=group[0]['real_manual_n'], need=group[0]['need'], wild=sum(r['wild'] for r in group),
            bad=d['gt_error_excluded'], pending=group[0]['pending_review'],
            issue=group[0]['scope_issue_flag'], scope=group[0]['scope_reference_status'],
            floor=rounded(reference['floor_xz_h']) if reference.get('floor_xz_h') and not d['gt_error_excluded'] else None,
            humans=humans, samples=samples,
            models={family:rounded(m['points']) for family,m in sources['models'][iid].items()}))
    payload = dict(images=images, summary=read(run/'summary.json'), validation=read(run/'VALIDATION.json'),
                   replay=read(run/'REPRODUCIBILITY.json'), tests=read(run/'TEST_RESULTS.json'))
    template = Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('</', '<\\/')
    destination = run/'dashboard.html'
    destination.write_text(template.replace('/*__DATA__*/', data), encoding='utf-8')
    print(json.dumps(dict(path=str(destination), images=len(images), synthetic=len(rows),
                          human_overlays=sum(len(i['humans']) for i in images), bytes=destination.stat().st_size)))
    return destination


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, default=base.ROOT.parent/'output/difficulty_wild_35_20261017/full')
    build(p.parse_args().run)
