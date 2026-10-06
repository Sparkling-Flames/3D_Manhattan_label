from pathlib import Path
from collections import Counter
import json,gzip
from run_study import dump,POLICIES

def summarize(out):
    out=Path(out);rows=json.loads((out/'summary.json').read_text());known=json.loads((out/'known_human_relations.json').read_text())
    changes=json.loads((out/'known_unknown_changes.json').read_text());totals=[]
    for p in POLICIES:
        rr=[r for r in rows if r['policy']==p];cc=[r for r in changes if r['policy']==p]
        totals.append({'policy':p,'selected_pairs':sum(r['selected_pairs'] for r in rr),
            'covered_observations':sum(r['covered_observations'] for r in rr),
            'below_four_images_by_gate':{str(t):sum(r['below_four'] for r in rr if r['threshold_deg']==t) for t in [5,9,12]},
            'known_false_splits':sum(r['policies'][p]['false_split'] for r in known),
            'known_false_merges':sum(r['policies'][p]['false_merge'] for r in known),
            'lost_unknown':sum(r['lost_comemberships']['unknown'] for r in cc),
            'new_unknown':sum(r['new_comemberships']['unknown'] for r in cc)})
    evid={k:{'statuses':Counter(),'contexts':Counter()} for k in ['fixed','event']}
    for f in out.glob('*/pair_*.json'):
        z=json.loads(f.read_text())
        for k in evid:
            for field in evid[k]:evid[k][field].update(z['evidence'][k][field])
    dump(out/'aggregate_summary.json',{'policy_totals':totals,'evidence':evid,
        'denominators':{'same_relation_gate_checks':sum(r['expected_same'] for r in known),
                        'different_relation_gate_checks':sum(not r['expected_same'] for r in known)},
        'caution':'gate-state counts reuse observations and relations; not independent trials'})
    dossiers=[]
    for code,t,keys,question in [
        ('rPc6DW4iMge-06',9,[['R02452',2],['R01986',2],['R01557',4]],
         'The focal trio is already reviewed. Which of the seven other members of the recovered 10-person group share that corner, and which removed members belong there? No new judgment is assumed.'),
        ('wc2JMjhGNzB-53',5,[['R00011',4],['R00966',1]],
         'Are these focal corners and their outer anchors genuinely corresponding? The event witness uses a three-edge versus one-edge source path, retaining both interior observations; this identity is unreviewed.')]:
        folder=out/code;nodes=json.loads((folder/'nodes.json').read_text());ix={(n['id'],n['pair_index']):i for i,n in enumerate(nodes)}
        ns=[ix[tuple(k)] for k in keys];state=json.loads((folder/f'pair_{t}.json').read_text());groups={}
        for p,v in state['policies'].items():
            groups[p]=[{**g,'source_members':[nodes[i] for i in g['node_indices']]} for g in v['groups'] if any(i in g['node_indices'] for i in ns)]
        bank_rows={};paths={}
        for bank in ['fixed','event']:
            bank_rows[bank]=[r for r in map(json.loads,gzip.open(folder/f'{bank}_{t}_evidence.jsonl.gz','rt'))
                             if set(r['nodes'])<=set(ns)]
            ids={pid for r in bank_rows[bank] for w in r['witnesses'] for li in w['leg_indices'] for pid in r['legs'][li]['paths']}
            paths[bank]=[p for p in map(json.loads,gzip.open(folder/f'{bank}_source_paths.jsonl.gz','rt')) if p['path_id'] in ids]
        dossiers.append({'image':code,'threshold_deg':t,'focals':[nodes[i] for i in ns],'question':question,
                         'policy_groups':groups,'focal_evidence':bank_rows,'witness_source_paths':paths,
                         'source_image_filename':code+'.png','no_semantic_label_inferred':True})
    dump(out/'review_dossiers.json',dossiers)
    print('Saved aggregate summary and two compact review dossiers',flush=True)
