"""Recheck the portable numerical package without images or visual dependencies."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from tools.thesis_main.analysis.image_portrait.common import BUNDLE, read_images, save_json


def check_npz(path):
    count = 0
    with np.load(path, allow_pickle=False) as data:
        for key in data.files:
            value = data[key]
            if value.dtype.kind in 'fc' and not np.isfinite(value).all():
                raise ValueError(f'nonfinite {path.name}:{key}')
            if value.dtype.kind == 'O':
                raise ValueError(f'object payload {path.name}:{key}')
            count += 1
    if not count:
        raise ValueError(f'empty numerical payload {path.name}')
    return count


def audit(root=BUNDLE):
    ids = {r['image_id'] for r in read_images()}
    report = dict(schema='image_portrait_output_audit_v1', expected_images=len(ids), models={})
    for name in ('hohonet','bilayout','ulayout','dinov3','da3'):
        directory = root/'models'/name
        files = list(directory.glob('*.npz'))
        errors, covered, statuses = [], set(), Counter()
        for path in files:
            image_id = path.name.split('.')[0]
            if image_id not in ids:
                errors.append(dict(file=path.name, error='unknown image identity'))
                continue
            try:
                check_npz(path)
                covered.add(image_id)
            except (ValueError, OSError) as exc:
                errors.append(dict(file=path.name, error=str(exc)))
        if name in ('hohonet','bilayout'):
            for image_id in ids:
                p = directory/f'{image_id}.json'
                if p.exists():
                    item = json.loads(p.read_text(encoding='utf8'))
                    if item['image_id'] != image_id:
                        raise ValueError('status identity mismatch')
                    phases = item['phases']
                    if sorted(v['yaw'] for v in phases) != [0,90,180,270]:
                        errors.append(dict(file=p.name,error='incomplete or duplicate yaw phases'))
                    statuses[item['status']] += 1
        elif (directory/'status.json').exists():
            entries = json.loads((directory/'status.json').read_text(encoding='utf8'))
            if isinstance(entries, list):
                statuses.update(v['status'] for v in entries)
        report['models'][name] = dict(numerical_image_count=len(covered),
            missing_image_ids=sorted(ids-covered), file_count=len(files),
            bytes=sum(p.stat().st_size for p in files), status_counts=dict(statuses), errors=errors)
    save_json(root/'output_coverage.json',report)
    print(json.dumps({k:{'images':v['numerical_image_count'],'errors':len(v['errors']),
        'statuses':v['status_counts']} for k,v in report['models'].items()},ensure_ascii=False))
    return report


if __name__ == '__main__':
    audit()
