from __future__ import annotations
import json,gzip,math,copy,hashlib,itertools
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from baseline import nodes_from_records,distances,partition,key,center
from structure import report_groups,ring_diagnostics,partition_changes
from run import dump,ROOT

def context_state(row,nodes,records):
    if row['status']=='witnessed':return 'positive_path_witness'
    i,j=row['nodes'];ni=len(records[nodes[i]['id']]['points'])//2;nj=len(records[nodes[j]['id']]['points'])//2
    possible=[]
    for a in row['legs']:
        for b in row['legs']:
            if a['orientation']!=b['orientation'] or a['side_of_focal']!=-1 or b['side_of_focal']!=1:continue
            if a['steps'][0]+b['steps'][0]>=ni or a['steps'][1]+b['steps'][1]>=nj:continue
            if a['status'] not in ['accept','reject','undetermined'] or b['status'] not in ['accept','reject','undetermined']:continue
            possible.append((a['status'],b['status']))
    if not possible:return 'no_comparable_two_sided_anchor_path'
    if any('undetermined' in x and 'reject' not in x for x in possible):return 'numeric_undetermined'
    return 'all_proposed_two_sided_paths_disagree'

def assisted_partition(nodes,D,tau,metric,must,cannot):
    parent=list(range(len(nodes)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for rel in must:
        a=find(rel[0])
        for b in rel[1:]:parent[find(b)]=a
    components=defaultdict(list)
    for i in range(len(nodes)):components[find(i)].append(i)
    components=list(components.values());bad={tuple(sorted(x)) for x in cannot}
    for comp in components:
        if len({nodes[i]['worker'] for i in comp})<len(comp):return {'status':'human_same_person_conflict','groups':None}
        if D[metric][np.ix_(comp,comp)].max()>tau+1e-10:return {'status':'human_constraint_outside_numeric_gate','groups':None}
        if any(tuple(sorted((i,j))) in bad for i in comp for j in comp if i!=j):return {'status':'contradictory_human_constraints','groups':None}
    A=np.zeros((len(components),len(components)))
    for a,c in enumerate(components):
        for b in range(a+1,len(components)):
            h=components[b]
            conflict=bool({nodes[i]['worker'] for i in c}&{nodes[i]['worker'] for i in h}) or any(tuple(sorted((i,j))) in bad for i in c for j in h)
            A[a,b]=A[b,a]=181. if conflict else D[metric][np.ix_(c,h)].max()
    lab=fcluster(linkage(squareform(A,checks=False),method='complete'),tau,criterion='distance')
    gs=[[i for ci,c in enumerate(components) if lab[ci]==v for i in c] for v in set(lab)]
    return {'status':'given_human_focal_constraints_only_not_automatic_anchors','groups':gs,'must':must,'cannot':cannot}

def known_relations(human,image,metric,nodes):
    ix={key(n):i for i,n in enumerate(nodes)};out=[]
    for review in human['reviews']:
        if review['image']!=image:continue
        ks=[(rid,i) for rid,i in zip(review['record_ids'],review['processed_pair_indices'])]
        if review['relation']=='same_corner_pair':
            for a,b in itertools.combinations(ks,2):out.append((ix[a],ix[b],True,review['case_id']))
            if 'rejected_previous_purple_processed_pair_index' in review:
                wrong=(ks[2][0],review['rejected_previous_purple_processed_pair_index'])
                for a in ks[:2]:out.append((ix[a],ix[wrong],False,review['case_id']+'_rejected'))
        elif review['relation']=='different_upper_targets':
            if metric=='bottom':
                for a,b in itertools.combinations(ks,2):out.append((ix[a],ix[b],True,'unb_bottom_user_tentative'))
            else:
                out.extend([(ix[ks[0]],ix[ks[1]],False,'unb_distinct_upper_target'),(ix[ks[0]],ix[ks[2]],False,'unb_distinct_upper_target')])
    return out

def group_relation(groups,i,j):return any(i in g and j in g for g in groups)

def analyze(out):
    out=Path(out);target=out/'analysis';target.mkdir(exist_ok=False)
    # This stage runs only after all automatic candidates have been serialized.
    human=json.loads((ROOT/'inputs/human_review.json').read_text())
    before={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*/*.json')}
    relation_rows=[];tri_summary=[];context_rows=[];assist_summary=[]
    for f in sorted((ROOT/'inputs').glob('*.json')):
        if f.name=='human_review.json':continue
        im=json.loads(f.read_text());rs={r['id']:r for r in im['records']};folder=out/im['image']
        ns=json.loads((folder/'nodes.json').read_text());D=distances(ns);index={key(n):i for i,n in enumerate(ns)}
        for metric in ['pair','bottom','top']:
            for tau in [5,9,12]:
                state=json.loads((folder/f'{metric}_{tau}.json').read_text())
                rows=[json.loads(l) for l in gzip.open(folder/f'{metric}_{tau}_path_evidence.jsonl.gz','rt')]
                classes={tuple(x['nodes']):context_state(x,ns,rs) for x in rows}
                M=D[metric].copy()
                for (i,j),label in classes.items():
                    if label=='all_proposed_two_sided_paths_disagree':M[i,j]=M[j,i]=181.
                groups,_=partition(ns,M,tau)
                gg,lut=report_groups(ns,groups,D,len(rs));tr={'groups':gg,'ring':ring_diagnostics(im['records'],ns,gg,lut)}
                base=[x['node_indices'] for x in state['raw_MV']['groups']]
                tr['changes']=partition_changes(ns,base,groups)
                dump(target/f"{im['image']}_{metric}_{tau}_three_state.json",tr)
                counts=Counter(classes.values());context_rows.append({'image':im['image'],'metric':metric,'threshold_deg':tau,**dict(counts)})
                tri_summary.append({'image':im['image'],'metric':metric,'threshold_deg':tau,
                    'raw_selected':state['raw_MV']['ring']['selected_pair_count'],'three_state_selected':tr['ring']['selected_pair_count'],
                    'lost_relations':len(tr['changes']['lost_comemberships']),'new_relations':len(tr['changes']['new_comemberships']),
                    'affected_observations':len(tr['changes']['affected_nodes'])})
                rels=known_relations(human,im['image'],metric,ns)
                for i,j,same,case in rels:
                    row={'image':im['image'],'metric':metric,'threshold_deg':tau,'case':case,'nodes':[i,j],
                        'sources':[key(ns[i]),key(ns[j])],'expected_same':same,'distance_deg':float(D[metric][i,j]),
                        'path_context':classes.get(tuple(sorted((i,j))),'focal_outside_gate')}
                    for name,z in [('raw_MV',state['raw_MV']),('strict_path_MV',state['path_witness_MV']),('three_state_MV',tr)]:
                        bs=[x['node_indices'] for x in z['groups']];v=group_relation(bs,i,j)
                        row[name]={'same_group':v,'known_false_split':same and not v,'known_false_merge':not same and v}
                    relation_rows.append(row)
                # Explicit assistance: human same-corner constraints or semantic cannot-links.
                must=[];cannot=[]
                for rev in human['reviews']:
                    if rev['image']!=im['image']:continue
                    ks=[index[(rid,i)] for rid,i in zip(rev['record_ids'],rev['processed_pair_indices'])]
                    if rev['relation']=='same_corner_pair':
                        must.append(ks)
                        if 'rejected_previous_purple_processed_pair_index' in rev:
                            wrong=index[(rev['record_ids'][2],rev['rejected_previous_purple_processed_pair_index'])]
                            cannot.extend((k,wrong) for k in ks[:2])
                    elif metric=='bottom':must.append(ks)
                    else:cannot.extend([(ks[0],ks[1]),(ks[0],ks[2])])
                if must or cannot:
                    ass=assisted_partition(ns,D,tau,metric,must,cannot)
                    if ass['groups'] is not None:
                        ag,lu=report_groups(ns,ass['groups'],D,len(rs));ass.update(reports=ag,ring=ring_diagnostics(im['records'],ns,ag,lu),
                            changes=partition_changes(ns,base,ass['groups']))
                    dump(target/f"{im['image']}_{metric}_{tau}_human_assisted.json",ass)
                    assist_summary.append({'image':im['image'],'metric':metric,'threshold_deg':tau,'status':ass['status'],
                       'selected_count':ass.get('ring',{}).get('selected_pair_count'),
                       'lost_relations':len(ass.get('changes',{}).get('lost_comemberships',[])),
                       'new_relations':len(ass.get('changes',{}).get('new_comemberships',[]))})
    dump(target/'known_development_relations.json',relation_rows)
    dump(target/'context_classes.json',context_rows);dump(target/'three_state_summary.json',tri_summary)
    dump(target/'human_assisted_summary.json',assist_summary)
    dump(target/'automatic_candidates_frozen_before_human_read.json',before)
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);analyze(a.parse_args().out)
