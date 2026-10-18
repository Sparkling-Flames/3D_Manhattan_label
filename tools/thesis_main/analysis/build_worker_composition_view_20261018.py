"""把已保存的人员细分类实验接入离线展示；不拟合、评分或重新融合。"""
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKERS = ROOT / 'research/workers/worker_fine_composition_20261018'
FUSION = ROOT / 'research/fusion/worker_composition_fusion_20261018'
PAGE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def pack_geometry(request, pool, state):
    records = {r['worker_id']: r for r in pool['records']}
    subset = '|'.join(sorted(records[w]['id'] for w in request['worker_ids']))
    if subset != state['subset']:
        raise ValueError('display member binding mismatch: ' + subset)
    automatic = state['automatic']
    return dict(candidate=automatic.get('candidate'),
                ring_diagnostics=automatic.get('ring_diagnostics'),
                origin=state.get('origin'), subset=subset)


def pack_pools(planned, rows, fusion):
    by_request = {row['request_id']: row for row in rows}
    if len(by_request) != len(rows):
        raise ValueError('duplicate display request ID')
    if set(by_request) != {r['request_id'] for r in planned}:
        raise ValueError('display request coverage mismatch')
    snapshots = read(fusion / 'input_snapshot.json')
    pools = {p['image_id']: p for p in snapshots['images']}
    gallery = read(ROOT / 'research/statistics/annotation_gallery_20261017/gallery.json')
    images = {i['image_id']: i for i in gallery['images']}
    packed_pools = {}
    for image_id in sorted({r['image_id'] for r in planned}):
        pool = pools[image_id]
        source = fusion / 'pools' / pool['pool_id'] / 'states.json.gz'
        states = json.loads(gzip.decompress(source.read_bytes()))['states']
        by_subset = {s['subset']: s for s in states}
        records = {r['worker_id']: r for r in pool['records']}
        packed_states = {}
        for request in (r for r in planned if r['image_id'] == image_id):
            subset = '|'.join(sorted(records[w]['id'] for w in request['worker_ids']))
            row = by_request[request['request_id']]
            row.update({k: v for k, v in request.items() if k not in row})
            row['worker_ids'] = request['worker_ids']
            row['state_key'] = subset
            if subset in by_subset:
                packed_states[subset] = pack_geometry(request, pool, by_subset[subset])
            # 失败请求保留行，未保存几何不由其他团队代替。
        image = images[image_id]
        photo = next((p for p in (image.get('original_path'), image.get('thumbnail_path'))
                      if p and (ROOT / p).is_file()), None)
        packed_pools[image_id] = dict(image_code=pool['image'], photo='../../../' + photo if photo else None,
                                     reference=pool['reference'], states=packed_states,
                                     records=[{k: r.get(k) for k in ('id', 'worker_id', 'points')}
                                              for r in pool['records']])
    return packed_pools


def build():
    requests = read(WORKERS / 'TEAM_REQUESTS.json')
    rows = table(WORKERS / 'team_analysis.csv')
    packed_pools = pack_pools(requests['requests'], rows, FUSION)
    payload = dict(schema='worker_composition_display_20261018_v1', data_release='v1',
                   request_metadata={k: v for k, v in requests.items() if k != 'requests'},
                   summary=read(WORKERS / 'summary.json'), teams=rows,
                   cells=table(WORKERS / 'composition_cells.csv'),
                   profiles=table(WORKERS / 'fold_classes.csv'),
                   thresholds=table(WORKERS / 'class_thresholds.csv'),
                   review_cases=read(WORKERS / 'review_cases.json')['cases'],
                   point_edits=[r for r in table(ROOT / 'research/data/processed_input_review_20261018/effective_point_edits_current.csv')
                                if r['status'] == 'current_effective_edit_preserved'],
                   support=table(WORKERS / 'pool_support.csv'), pools=packed_pools)
    feedback = ROOT / 'research/workers/worker_exchangeability_20261018/human_feedback.json'
    payload['human_feedback'] = read(feedback)['records'] if feedback.exists() else []
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    (PAGE / 'personnel-composition-data.js').write_text('window.PERSONNEL_COMPOSITION=' + encoded + ';\n', encoding='utf-8')
    print(json.dumps(dict(requests=len(rows), images=len(packed_pools),
                          saved_member_sets=sum(len(p['states']) for p in packed_pools.values()))))


if __name__ == '__main__':
    build()
