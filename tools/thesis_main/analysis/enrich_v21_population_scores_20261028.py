"""补齐参考相关分项；完整端点复用已重测的指标，不再融合或重测球面距离。"""
import gzip
import json
from concurrent.futures import ProcessPoolExecutor
from .rebuild_v21_20261028 import OUT, read
from .rescore_v21_population_20261028 import SOURCE, TARGET
from .scope_quality_scoring_20261016 import scoring_engine
from .wall_consensus_quality_20261015 import measured


def enrich(result, geometry, k, ref, engine):
    if result and result.get('score_status') == 'complete':
        scores = engine.score(result)
        result.update({key: value for key, value in scores.items()
                       if key not in ('status', 'current', 'floor_current')})
        areas = engine.au.area_metrics(
            {'bottom3d': [[x, -1, z] for x, z in geometry['footprint']]},
            {'bottom3d': [[x, -1, z] for x, z in ref['floor_xz_h']]})
        result.update(omission=areas['omission'], extension=areas['extension'],
                      floor_WQ_upper_bound=scores['floor_WQ'])
        return result
    if geometry is None:
        return result
    state = dict(n=k, candidate=geometry,
                 node_consensus=dict(nodes=[None] * len(geometry.get('footprint') or [])))
    return measured(engine, state, dict(floor=ref['floor_xz_h'], points=ref['points_1024x512']))


def process(spec):
    path = OUT / spec['file']
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        rows = [json.loads(line) for line in f]
    if all(r['reference_dependent_diagnostics_status'] == 'complete' for r in rows):
        return len(rows)
    refs = {r['target_id']: r for r in read(OUT / 'reference_catalog.json')}
    source = SOURCE / rows[0]['geometry_source']
    with scoring_engine() as (engine, _), gzip.open(source, 'rt', encoding='utf-8') as f:
        geometries = [json.loads(line) for line in f]
        assert len(rows) == len(geometries)
        for r, g in zip(rows, geometries):
            assert r['team_key'] == g['team_key']
            previous_q = (r['result'] or {}).get('B8L2')
            r['result'] = enrich(r['result'], g.get('geometry'), r['k'], refs[r['reference_id']], engine)
            assert (r['result'] or {}).get('B8L2') == previous_q
            r['reference_dependent_diagnostics_status'] = 'complete'
    temporary = path.with_suffix('.writing')
    with gzip.open(temporary, 'wt', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)
    return len(rows)


def main():
    specs = read(TARGET / 'NEW208_SHARDS.json')
    total = 0
    with ProcessPoolExecutor(max_workers=4) as executor:
        for i, n in enumerate(executor.map(process, specs), 1):
            total += n
            if i % 100 == 0:
                print('diagnostics', i, '/', len(specs), flush=True)
    (TARGET / 'DIAGNOSTICS_CHECKS.json').write_text(json.dumps(dict(
        rows=total, shards=len(specs), complete=True, full_scores_preserved=True,
        partial_floor_diagnostics=True, new_fusion=0), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
