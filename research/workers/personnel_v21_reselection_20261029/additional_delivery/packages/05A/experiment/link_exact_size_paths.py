"""Recover genuine nested size paths already present in registered ABC teams.

Only exact X/Y/Z blocks and nested D are linked. No score is read; arbitrary
equal-m events with different members are not called an n/threshold path.
"""
import argparse,itertools,json,collections
from pathlib import Path
import pandas as pd
from capacity_space import write_csv,read_labels
from register_adaptive import members,write_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--events',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    data=read_labels(a.events);rows=[];non_nested=0
    group=['pool_id','method','source_class','target_class','m','X','Y','Z']
    groups=collections.defaultdict(list)
    for event in data:groups[tuple(event[k] for k in group)].append(event)
    for keys,g in groups.items():
        for lo,hi in itertools.combinations(sorted(g,key=lambda r:int(r['n'])),2):
            if int(lo['n'])>=int(hi['n']):continue
            d0,d1=set(members(lo['D'])),set(members(hi['D']))
            if not d0<=d1:non_nested+=1;continue
            for arm in ['A','B','C']:assert set(members(lo[arm+'_members']))<=set(members(hi[arm+'_members']))
            r={k:v for k,v in zip(group,keys) if k not in ('X','Y','Z')}
            r.update(image=lo['image'],building=lo['building'],condition=lo['condition'],difficulty=lo['difficulty'],
                lower_event_id=lo['event_id'],higher_event_id=hi['event_id'],n_lower=lo['n'],n_higher=hi['n'],
                background_added='|'.join(sorted(d1-d0)),added_n=len(d1-d0),
                D_lower=lo['D'],D_higher=hi['D'],X=lo['X'],Y=lo['Y'],Z=lo['Z'],
                background_source_added=int(hi['background_source_n'])-int(lo['background_source_n']),
                background_target_added=int(hi['background_target_n'])-int(lo['background_target_n']))
            for arm in ['A','B','C']:r[arm+'_lower_team_key']=lo[arm+'_team_key'];r[arm+'_higher_team_key']=hi[arm+'_team_key']
            rows.append(r)
    write_csv(out/'EXACT_NESTED_SIZE_LINKS.csv.gz',rows)
    write_json(out/'SIZE_LINK_RECEIPT.json',dict(links=len(rows),methods=len({r['method'] for r in rows}),pools=len({r['pool_id'] for r in rows}),
        unmatched_non_nested_same_block_pairs=non_nested,link_rule='exact same X/Y/Z, increasing n, D_lower subset D_higher; all ABC lower teams subset their higher teams',
        new_fusion_evaluations=0,not_pure_threshold_causal_effect='Added background observations and increased voting threshold both change; use full traces to distinguish mechanisms.'))
    print(json.dumps(dict(links=len(rows),non_nested_not_linked=non_nested)),flush=True)

if __name__=='__main__':main()
