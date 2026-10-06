from __future__ import annotations
import json,gzip,csv,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from run import ROOT,dump
from baseline import key
from frechet import rays,spherical_distance_interval

def summarize(out):
    out=Path(out);folder=out/'summary';folder.mkdir(exist_ok=False)
    raw=json.loads((out/'summary.json').read_text())
    tri=json.loads((out/'analysis/three_state_summary.json').read_text())
    tmap={(r['image'],r['metric'],r['threshold_deg']):r for r in tri}
    data=[]
    for r in raw:
        d=tmap[(r['image'],r['metric'],r['threshold_deg'])]
        data.append(dict(r,three_state_selected=d['three_state_selected'],three_state_lost=d['lost_relations'],three_state_new=d['new_relations']))
    dump(folder/'all_MV_comparisons.json',data)
    with (folder/'all_MV_comparisons.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,list(data[0]));w.writeheader();w.writerows(data)
    known=json.loads((out/'analysis/known_development_relations.json').read_text());agg={}
    for r in known:
        for p in ['raw_MV','strict_path_MV','three_state_MV']:
            k=(r['image'],r['metric'],r['threshold_deg'],p)
            x=agg.setdefault(k,{'image':k[0],'metric':k[1],'threshold_deg':k[2],'policy':p,
                'known_positive_pairs':0,'known_negative_pairs':0,'false_splits':0,'false_merges':0})
            x['known_positive_pairs']+=int(r['expected_same']);x['known_negative_pairs']+=int(not r['expected_same'])
            x['false_splits']+=int(r[p]['known_false_split']);x['false_merges']+=int(r[p]['known_false_merge'])
    dump(folder/'known_development_pair_counts.json',list(agg.values()))
    expected=json.loads((ROOT/'upstream/expected_prior_baseline_5deg.json').read_text());checks=[]
    for e in expected:
        s=json.loads((out/e['image']/f"{e['metric']}_5.json").read_text())['raw_MV']['groups']
        same=sorted(map(sorted,e['groups']))==sorted(sorted(g['node_indices']) for g in s)
        center_same=all(x['points']==g['center']['points'] for x,g in zip(e['centers'],s))
        assert same and center_same
        checks.append({'image':e['image'],'metric':e['metric'],'same_partition':same,'same_centers':center_same})
    dump(folder/'previous_baseline_reproduction.json',{'source':'previous shipped snapshot, NOT missing latest local baseline','checks':checks})
    # All structures and candidates, never pick a winning reference score.
    cs=[];post=[];detail=[];examples=[]
    for p in sorted((out/'patches').glob('*_candidate_rings.jsonl.gz')):
        rr=[json.loads(x) for x in gzip.open(p,'rt')]
        if not rr:continue
        for quantity in ['added_relative_to_base_h2','lost_relative_to_base_h2','added_relative_to_anchor_only_h2','lost_relative_to_anchor_only_h2']:
            v=[r[quantity] for r in rr if r.get(quantity) is not None]
            if v:cs.append({'file':p.name,'quantity':quantity,'min':min(v),'median':float(np.median(v)),'max':max(v)})
        count=Counter()
        for r in rr:
            for origin,checks in r.get('post_center_path_comparison',{}).items():
                for side,z in checks.items():count[origin+'_'+side+'_'+z['status']]+=1
            detail.append({'candidate':r['id'],'image':r['image'],'threshold_deg':r['threshold_deg'],
                'removed_base_internal_count':len(r['base_internal_vertices_removed_in_candidate_only']),
                'retained_donor_internal_count':len(r['donor_internal_vertices_retained']),
                'truth_detail_false_deletion':'not_evaluable_no_local_semantic_truth',
                'truth_false_addition':'not_evaluable_no_local_semantic_truth',
                'new_edge_count':sum(e['new_edge_not_exact_original'] for e in r['new_edges']),
                'whole_candidate_support':'not_established'})
        post.append({'file':p.name,'candidates':len(rr),'post_center_checks':dict(count)})
    dump(folder/'patch_area_decomposition.json',cs);dump(folder/'post_center_path_budget.json',post)
    dump(folder/'detail_and_edge_accounting.json',detail)
    encodings=[]; witnesses=[]
    def canonical(points):
        q=np.asarray(points).reshape(-1,4)
        words=[tuple(np.round(row,9)) for row in q]
        return min(tuple(z[i:]+z[:i]) for z in [words,list(reversed(words))] for i in range(len(z)))
    for p in sorted((out/'patches').glob('*_candidate_rings.jsonl.gz')):
        rr=[json.loads(x) for x in gzip.open(p,'rt')]
        if not rr:continue
        keys={canonical(c['points']) for c in rr if c.get('points')}
        bad={canonical(c['points']) for c in rr if c.get('post_center_compatibility_status')=='outside_previous_local_gate'}
        encodings.append({'file':p.name,'records':len(rr),'unique_cyclic_direction_invariant_encodings':len(keys),
            'encodings_outside_post_center_gate':len(bad),'note':'round9 pixel numeric encoding; not semantic equivalence; input voters never deduplicated'})
        if rr[0]['threshold_deg']!=5:continue
        source={r['id']:r for r in json.loads((ROOT/'inputs'/f"{rr[0]['image']}.json").read_text())['records']}
        for c in rr:
            if c.get('post_center_compatibility_status')!='outside_previous_local_gate':continue
            base=np.asarray(source[c['base_record']]['points']).reshape(-1,2,2)[c['base_processed_path']]
            donor=np.asarray(source[c['donor_record']]['points']).reshape(-1,2,2)[c['donor_path_used_order']]
            generated=np.asarray(c['points']).reshape(-1,2,2)[:len(donor)]
            anchor=np.asarray(c['anchor_only_control_points']).reshape(-1,2,2)[c['base_processed_path']]
            metrics={side:{name:spherical_distance_interval(rays(a[:,j]),rays(b[:,j]),.25)
                for name,a,b in [('raw_two_paths',base,donor),('generated_vs_raw_base',generated,base),('generated_vs_anchor_only',generated,anchor)]}
                for side,j in [('top',0),('bottom',1)]}
            witnesses.append({'candidate':c['id'],'base_record':c['base_record'],'base_path':c['base_processed_path'],
                'donor_record':c['donor_record'],'donor_path':c['donor_path_used_order'],'metrics':metrics,
                'source_local_points':{'base':base.tolist(),'donor':donor.tolist()},'candidate_points':c['points']})
    dump(folder/'unique_candidate_encodings.json',encodings)
    dump(folder/'post_center_5deg_witnesses.json',witnesses)
    # Lower identity + raw pair incidence + semantic targets, no top vote copying.
    im='uNb9QFRL6hY-67';ns=json.loads((out/im/'nodes.json').read_text());ix={key(n):i for i,n in enumerate(ns)}
    reviewed={('R00144',0):'low_glass_top',('R00526',0):'glass_to_ceiling',('R02210',0):'glass_to_ceiling'}
    layers=[]
    for tau in [5,9,12]:
        s=json.loads((out/im/f'bottom_{tau}.json').read_text())
        for name,obj in [('raw_MV',s['raw_MV']),('strict_path_MV',s['path_witness_MV']),
                ('three_state_MV',json.loads((out/'analysis'/f'{im}_bottom_{tau}_three_state.json').read_text()))]:
            targets=[ix[k] for k in reviewed]
            for g in obj['groups']:
                if not set(g['node_indices'])&set(targets):continue
                portions=defaultdict(list)
                for i in g['node_indices']:portions[reviewed.get(key(ns[i]),'unknown_upper_target')].append(ns[i])
                layers.append({'threshold_deg':tau,'policy':name,'lower_geometric_group':g['feature_id'],
                    'lower_geometric_support':g['support'],'full_pool_denominator':15,
                    'user_same_lower_status':'tentative_only_for_three_listed_observations',
                    'upper_partitions':[{ 'semantic_status':k,'known_upper_support':len(v) if k!='unknown_upper_target' else None,
                        'original_pair_incidence':len(v),'sources':v,
                        'upper_center_y':float(np.median([x['points'][0][1] for x in v])) if k!='unknown_upper_target' else None}
                         for k,v in portions.items()],
                    'mixed_top_center_for_diagnostic_only':g['center']['points'][0] if g['center']['points'] is not None else None,
                    'no_single_upper_target_selected':True})
    dump(folder/'unb_lower_identity_upper_targets.json',layers)
    print('SUMMARY',len(data),'states',len(detail),'path candidate rings',flush=True)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);summarize(p.parse_args().out)
