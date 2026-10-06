"""Read-only source/intent-contract audit; does not run numerical path pipeline."""
from pathlib import Path
import argparse, json, math, hashlib

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('package',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); p=a.package
    all_workers=set(); rosters=[]; states=[]; failures=[]
    for f in sorted((p/'inputs').glob('*.json')):
        if f.name=='human_review.json': continue
        src=json.loads(f.read_text()); records=src['records']; n=len(records)
        all_workers.update(r['worker'] for r in records)
        src_nodes={(r['id'],i):(r,i) for r in records for i in range(len(r['points'])//2)}
        folder=p/'results'/src['image']; nodes=json.loads((folder/'nodes.json').read_text())
        checked=set()
        for node in nodes:
            key=(node['id'],node['pair_index']); r,i=src_nodes[key]; checked.add(key)
            assert node['worker']==r['worker']
            assert node['points']==r['points'][2*i:2*i+2]
            assert node['source_pair_index']==r['source_pair_indices'][i]
            assert node['source_point_indices']==r['source_point_indices'][2*i:2*i+2]
            assert node['source_ring_confirmed']==r['ring_confirmed']
        assert checked==set(src_nodes) and len(nodes)==len(src_nodes)
        rosters.append({'image':src['image'],'records':n,'workers':len({r['worker'] for r in records}),'pairs':len(nodes),'all_node_bindings_exact':True})
        for metric in ('pair','bottom','top'):
            for tau in (5,9,12):
                s=json.loads((folder/f'{metric}_{tau}.json').read_text())
                assert s['vote_denominator']==n and s['records']==[r['id'] for r in records]
                for method in ('raw_MV','path_witness_MV'):
                    state=s[method]; groups=state['groups']; cover=[]
                    for g in groups:
                        inds=g['node_indices']; cover.extend(inds)
                        workers=[nodes[i]['worker'] for i in inds]
                        assert len(set(workers))==len(workers)==g['support']
                        assert workers==g['support_workers']
                        assert g['selected']==(len(workers)>=math.ceil(n/2))
                    assert sorted(cover)==list(range(len(nodes)))
                    selected=sum(g['selected'] for g in groups)
                    ring=state['ring']; assert ring['selected_pair_count']==selected
                    assert ring['minimum_four_pairs_enforced'] is False
                    for assignment,r in zip(ring['assignments'],records):
                        assert assignment['id']==r['id'] and assignment['worker']==r['worker']
                        assert len(assignment['source_identity_cycle'])==len(r['points'])//2
                    states.append({'image':src['image'],'metric':metric,'threshold':tau,'method':method,'selected_pairs':selected,'all_observations_retained':True,'exact_worker_support':True,'minimum_four_pairs_enforced':False})
    refs=json.loads((p/'evaluation/references.json').read_text())
    result={'rosters':rosters,'records':sum(x['records'] for x in rosters),'unique_workers':len(all_workers),'source_pairs':sum(x['pairs'] for x in rosters),'states':states,'raw_settings_checked':sum(x['method']=='raw_MV' for x in states),'structure_settings_checked':sum(x['method']=='path_witness_MV' for x in states),'sub_four_pair_settings_retained':[x for x in states if x['selected_pairs']<4],'reference_versions':{x['image']:[r['version'] for r in x['references']] for x in refs['images']},'original_reference_copy_equal':(p/'evaluation/references.json').read_bytes()==(p/'upstream/prior_reliability/evaluation/references.json').read_bytes(),'baseline_copy_equal':(p/'src/baseline.py').read_bytes()==(p/'upstream/prior_point_correspondence/src/core.py').read_bytes(),'scope':'available_old_four_image_artifact_only_not_new_worktree_acceptance','errors':failures}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('states','sub_four_pair_settings_retained')},ensure_ascii=False,indent=2))
    print('sub_four_pair_settings_retained',len(result['sub_four_pair_settings_retained']))

if __name__=='__main__':main()
