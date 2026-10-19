"""Independent checks of the provided frozen population; never reprocess geometry."""
from pathlib import Path
import argparse, collections, gzip, hashlib, json, math

def read(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f: return json.load(f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    index=read(a.repo/'research/workers/personnel_composition_handoff_20261019/INPUTS.json')['sources']
    records=read(a.repo/index['record_evidence'])['records']; evidence={r['object_id']:r for r in records}
    assert len(records)==len(evidence)==10439
    snap=read(a.repo/index['frozen_pools']); pools=snap['images']; context=read(a.repo/index['image_reference_context'])
    refs={r['target_id']:r for r in context['reference_catalog']}; members=[]
    for p in pools:
        seen=set();m=p['meta'];ref=refs[m['reference_id']]
        for f in ['points_1024x512','floor_xz_h']: assert p['reference'][f]==ref[f],(p['pool_id'],f)
        assert p['reference']['reference_version']==m['reference_version']
        for r in p['records']:
            x=evidence[r['object_id']]; assert r['worker_id'] not in seen;seen.add(r['worker_id']);members.append(r['object_id'])
            assert x['quality_usable'] and x['independent_vote_eligible']
            assert r['points']==x['points_1024x512']
            assert r['worker_id']==x['worker_id'] and r['origin']==x['origin']
            assert x['reference_id']==m['reference_id'] and x['reference_version']==m['reference_version']
            for f in ['B8L2','D10']: assert r[f]==x[f],(r['object_id'],f)
        assert len(seen)==m['pool_n']
    assert len(members)==len(set(members))==7302
    assert set(members)=={x['object_id'] for x in records if x['quality_usable']}
    assert snap['fusion_gap']==7.5 and snap['N1_applied'] is False
    hashes={k:{'path':p,'bytes':(a.repo/p).stat().st_size,'sha256':hashlib.sha256((a.repo/p).read_bytes()).hexdigest()} for k,p in index.items()}
    result=dict(main_commit='e572eb73bedc4fe9056df838e458bab83c3fa423',scientific_source_commit=snap['git_commit'],inventory=len(records),quality_records=len(members),images=len({p['meta']['image_id'] for p in pools}),workers=len({r['worker_id'] for p in pools for r in p['records']}),pools=len(pools),layers=dict(collections.Counter(p['meta']['layer'] for p in pools)),all_frozen_coordinates_equal=True,all_quality_values_equal=True,all_reference_geometry_equal=True,all_real_members_unique=True,N1_applied=False,sources=hashes)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='sources'},ensure_ascii=False))

if __name__=='__main__':main()
