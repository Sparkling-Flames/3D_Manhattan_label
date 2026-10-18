"""打包已完成的多人单人替换实验供离线查看；不重新分析或融合。"""
import json

from .build_worker_composition_view_20261018 import ROOT, PAGE, read, table, pack_pools

WORKERS = ROOT / 'research/workers/worker_exchangeability_20261018'
FUSION = ROOT / 'research/fusion/worker_exchangeability_fusion_20261018'


def bind_pairs(planned, rows, teams):
    lookup = {r['comparison_id']: r for r in rows}
    if len(lookup) != len(rows) or set(lookup) != {r['comparison_id'] for r in planned}:
        raise ValueError('exchange display comparison coverage mismatch')
    requests = {r['request_id']: r for r in teams}
    for design in planned:
        row = lookup[design['comparison_id']]
        if (row['request_a'], row['request_b']) != (design['request_a'], design['request_b']):
            raise ValueError('exchange display pair binding mismatch')
        a, b = (requests[row[k]] for k in ('request_a', 'request_b'))
        wa, wb = set(a['worker_ids']), set(b['worker_ids'])
        if a['image_id'] != b['image_id'] or len(wa) != len(wb) or len(wa ^ wb) != 2:
            raise ValueError('exchange display requires one replacement in the same image')
        row.update({k: v for k, v in design.items() if k not in row})
    return rows


def build():
    requests = read(WORKERS / 'TEAM_REQUESTS.json')
    teams = table(FUSION / 'team_results.csv')
    pools = pack_pools(requests['requests'], teams, FUSION)
    pairs = bind_pairs(requests['comparisons'], table(WORKERS / 'exchange_analysis.csv'), teams)
    transfer_keys = ['image_code', 'scene_bucket', 'scheme', 'k', 'anchor_class', 'entrant_a', 'entrant_b',
                     'discover_exact_full', 'discover_small_floor_001', 'full_geometry_equal_check',
                     'floor_jaccard_difference_discovery', 'floor_jaccard_difference_check', 'shared_background_members']
    payload = dict(schema='worker_exchangeability_display_20261018_v1', data_release='v1',
                   summary=read(WORKERS / 'summary.json'), teams=teams, pairs=pairs, pools=pools,
                   profiles=table(WORKERS / 'fold_profiles.csv'), support=table(WORKERS / 'class_support.csv'),
                   by_k=table(WORKERS / 'summary_by_k.csv'), fixed_curves=table(WORKERS / 'fixed_chain_curve_summary.csv'),
                   transfers=[{key: row[key] for key in transfer_keys} for row in table(WORKERS / 'background_transfer.csv')],
                   feedback=read(WORKERS / 'human_feedback.json'))
    (PAGE / 'exchangeability-data.js').write_text('window.EXCHANGEABILITY=' +
        json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + ';\n', encoding='utf-8')
    print(json.dumps(dict(teams=len(teams), pairs=len(pairs), pools=len(pools))))


if __name__ == '__main__':
    build()
