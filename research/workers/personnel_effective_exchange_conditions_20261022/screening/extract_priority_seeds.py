"""Freeze existing exact seed events for root's background/member extension."""
from __future__ import annotations
from common_screening import *

def run():
    maps,labels=label_maps();pools,origin=pool_workers();found=[];inputs={}
    wanted=set(META+CORE)
    for stage,condition,path in event_sources(['LARGE','PURE','PURE_CROSS'],['manual']):
        inputs[str(path.relative_to(WORKERS))]=sha(path)
        for d in pd.read_csv(path,usecols=lambda c:c in wanted,chunksize=2000,low_memory=False):
            m=d.m_AC
            keep=((d.method_id.eq('A2_relation')&d.n.eq(17)&m.eq(9)) |
                  (d.method_id.eq('M_structure')&d.tier.eq('fine')&d.n.eq(10)&m.isin([5,6])) |
                  (d.method_id.eq('V3_BEHAVIOR')&d.n.eq(10)&m.eq(7)))
            for row in d[keep].to_dict('records'):
                key=(row['method_id'],row['tier'],row['condition'],row['building']);lm=maps[key]
                bg=workers(row['common_background']);x=workers(row['outgoing_block_X']);z=workers(row['changed_count_block_Z'])
                y=workers(row.get('same_count_block_Y',''))
                xc=canonical_counts(lm[w] for w in x);zc=canonical_counts(lm[w] for w in z)
                if row['method_id']=='M_structure' and not (set(lm[w] for w in x)=={'M01'} and set(lm[w] for w in z)=={'M00'}):continue
                domain=pools[row['pool_id']]
                if row['source_domain'].startswith('new_only'):domain=[w for w in domain if origin[w]=='new']
                domain=[w for w in domain if w in lm]
                explicit=workers(row.get('labelled_domain_workers',''))
                if explicit:assert set(explicit)==set(domain),(row['event_id'],len(explicit),len(domain))
                cap=collections.Counter(lm[w] for w in domain)
                left=[w for w in domain if w not in bg];after=collections.Counter(lm[w] for w in left)
                available={cl:'|'.join(w for w in left if lm[w]==cl) for cl in sorted(cap)}
                focus=('A2_manual_n17_m9' if row['method_id']=='A2_relation' else
                       'M_parent_M01_to_M00_n10_m'+str(int(m.loc[d.event_id.eq(row['event_id'])].iloc[0])) if row['method_id']=='M_structure' else
                       'BEHAVIOR_manual_n10_m7')
                row.update(prior_stage=stage,focus_id=focus,base_data_version='v2',
                    matched_ABC=(stage!='PURE_CROSS'),exact_block_direction=xc+' -> '+zc,
                    X_class_counts=xc,Y_class_counts=canonical_counts(lm[w] for w in y),Z_class_counts=zc,
                    labelled_domain_workers='|'.join(domain),known_domain_n=len(domain),
                    domain_class_capacities=canonical_counts(cap),remaining_after_background_class_capacities=canonical_counts(after),
                    remaining_workers_by_class_json=json.dumps(available,sort_keys=True),
                    background_n=len(bg),ordered_ABC_union_n=len(set(bg+x+y+z)),
                    selected_team_keys='|'.join(str(row.get('team_'+a,'')) for a in 'ABC' if str(row.get('team_'+a,'')) not in ['','nan']),
                    native_fusion_needed_for_seed=False)
                found.append(row)
    d=pd.DataFrame(found).sort_values(['focus_id','source_domain','building','image','prior_stage','event_id'])
    receipt=save_csv('PRIORITY_SEED_EVENTS.csv.gz',d)
    small=[]
    for key,g in d.groupby(['focus_id','prior_stage','source_domain','tier','exact_block_direction'],dropna=False):
        q=g.cross_B8L2.dropna();a=g.abs_Q_change_advantage.dropna() if 'abs_Q_change_advantage' in g else pd.Series(dtype=float)
        small.append(dict(zip(['focus_id','prior_stage','source_domain','tier','exact_block_direction'],key))|
          dict(events=len(g),images=g.image.nunique(),buildings=g.building.nunique(),
               distinct_backgrounds=g[['pool_id','common_background']].drop_duplicates().shape[0],
               cross_Q_event_mean=q.mean(),cross_Q_event_median=q.median(),cross_Q_valid_events=len(q),
               stability_difference_event_mean=a.mean(),A_failed=int(g.A_failure.sum()),C_failed=int(g.C_failure.sum()),
               note='Preliminary event-weighted seed description. Complete screening will add building/image balanced summaries.'))
    receipt2=save_csv('PRIORITY_SEED_SUPPORT.csv',pd.DataFrame(small))
    out=dict(status='complete',base_data_version='v2',prior_round_directory_is_not_data_version=True,
             files=[receipt,receipt2],input_sha256=inputs,native_calls=0,
             events=len(d),focus_counts=d.focus_id.value_counts().to_dict(),
             new_teams_registered=False,interpretation='Seeds are inherited discoveries, not a fresh blind test; both direction and source identity preserved.')
    save_json('PRIORITY_SEED_RECEIPT.json',out);print(json.dumps(out,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
