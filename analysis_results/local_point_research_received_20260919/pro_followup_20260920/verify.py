"""Read-only portable evidence check. Run from any cwd after extracting the bundle."""
import gzip
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
sys.path.insert(0,str(REPO))
from tools.thesis_main.analysis.local_point_research import local_points as lp
from tools.thesis_main.analysis.local_point_research.precision_audit import stable_angles


def main():
    root=HERE.parent
    rows=[json.loads(l) for l in gzip.open(root/'inputs/responses.jsonl.gz','rt',encoding='utf-8')]
    by={r['canonical_annotation_id']:r for r in rows}
    evidence=json.loads((HERE/'evidence.json').read_text(encoding='utf-8'))
    assert len(rows)==len(by)==2501
    assert sum(lp.point_ok(r) for r in rows)==2381
    assert len(evidence)==6 and sum(len(r['ids']) for r in evidence)==126
    for c in evidence:
        assert c['user_decision'] is None
        assert len(set(c['workers']))==len(c['ids'])
        for id,w,n in zip(c['ids'],c['workers'],c['counts']):
            r=by[id]
            assert (r['image_id'],r['raw_condition'],r['worker_id'],r['effective_point_count'])==(c['image_id'],c['condition'],w,n)
        for p in c['pairs_detail']:
            a,b=[by[id]['effective_points_1024x512'] for id in p['ids']]
            f=lp.features(stable_angles(a,b))
            assert abs(f['ospa1']-p['ospa1'])<1e-8 and abs(f['hausdorff']-p['hausdorff'])<1e-8
    u=json.loads((root/'pair_pilot/用户_六图点对审核_原始.json').read_text(encoding='utf-8-sig'))
    assert len(u['decisions'])==6 and sum(d['Relation']=='可视为相近' for d in u['decisions'].values())==2
    print('PASS: 2501 frozen records / 2381 point-set eligible / 6 new images / 126 response identities / stable pair metrics / earlier six decisions')


if __name__=='__main__':main()
