"""发布摘录保持真实输入的几何／资格指纹，且不泄露原评论与内部来源。"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT/'research/pro_parallel_return_20261006/PUBLIC_INPUT_CONTRACT_20261006.json'


def test_public_cases_preserve_frozen_algorithm_inputs_and_resolve_photos():
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    for row in contract['files']:
        if row['algorithm_projection_sha256'] is None:
            continue
        path = ROOT/row['path']
        data = json.loads(path.read_text(encoding='utf-8'))
        projection = dict(coordinate_frame=data['coordinate_frame'], preprocessing=data['preprocessing'], images=[
            {key: image[key] for key in ('code','building','room','population','scene','annotations','references','review')}
            for image in data['images']])
        encoded = json.dumps(projection, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode('utf-8')
        assert hashlib.sha256(encoded).hexdigest() == row['algorithm_projection_sha256']
        assert all((path.parent/image['image_file']).is_file() for image in data['images'])


def test_published_inputs_omit_original_comments_and_internal_identifiers():
    for row in json.loads(CONTRACT.read_text(encoding='utf-8'))['files']:
        path = ROOT/row['path']
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['published_sha256']
        pending = [json.loads(raw)]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                assert not {'image_comment','object_id','selected_snapshot_path','mirror_path'} & value.keys()
                if 'source' in value:
                    assert set(value['source']) <= {'worker','condition'}
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
