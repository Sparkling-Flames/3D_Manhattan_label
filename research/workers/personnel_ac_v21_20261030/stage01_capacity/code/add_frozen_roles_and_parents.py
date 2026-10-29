"""Attach historical roles and exact frozen parent partitions to AC capacity.

No class fitting, score-based choice, scoring, or fusion is performed. Rankings
come from the already frozen leave-building-out class centers.
"""
from pathlib import Path
from collections import Counter
import hashlib,json
import pandas as pd

OUT=Path(__file__).resolve().parents[1];WORK=OUT.parents[1]
BASE=WORK/'repo/research/workers/personnel_v21_reselection_20261029/classification'
PREVIOUS=WORK/'HOHONET_v21_reaudit_20261029/stage01_classification/results'

def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def save(d,n):d.to_csv(OUT/n,index=False,encoding='utf-8-sig')
def members(x):return sorted(str(x).split('|')) if pd.notna(x) and str(x) else []

def main():
    labels=pd.read_csv(OUT/'FROZEN_LABELS_USED_ALL_LOBO.csv.gz',low_memory=False)
    old=pd.read_csv(BASE/'MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    new=pd.read_csv(PREVIOUS/'NEW_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    parent_extras=pd.concat([old[old.method.isin(['OPPSTRUCT_K2','OPPJOINT_K2'])],new[new.method.eq('V21_DSTRUCT_RAW3_K2')]],ignore_index=True)
    lab=pd.concat([labels,parent_extras[parent_extras.heldout_building.ne('ALL')]],ignore_index=True)
    lm={(method,b):{r.worker_id:r.class_id for r in g.itertuples() if r.known and pd.notna(r.class_id)} for (method,b),g in lab.groupby(['method','heldout_building'])}
    roles=pd.read_csv(BASE/'CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',low_memory=False)
    centers=pd.read_csv(PREVIOUS/'CLASS_CENTERS_ALL_LOBO.csv.gz',low_memory=False)
    rc=centers[centers.method.eq('V21_DSTRUCT_RAW3_K3')].copy()
    axes={'turn_rank_asc':'m_all_turn_n','hard_turn_rank_asc':'m_hard_turn_n','challenge_turn_rank_asc':'m_challenge_turn_n',
          'q_rank_asc':'m_all_B8L2','time_rank_asc':'m_all_log_time','area_rank_asc':'m_all_log_area_ratio',
          'height_rank_asc':'m_all_log_height','redundancy_rank_asc':'m_all_near_straight_nodes_5deg'}
    for rank,field in axes.items():rc[rank]=rc.groupby(['method','heldout_building'])[field].rank(method='dense')
    rc['semantic_training_role']='RAW3 frozen class center; use explicit hard/challenge/Q ranks, not class ID ordinal'
    roles=pd.concat([roles[roles.method.isin(labels.method.unique())],rc],ignore_index=True)
    roles=roles[roles.heldout_building.ne('ALL')].copy()
    assert not roles.duplicated(['method','heldout_building','class_id']).any()
    parent_method={'TARGET_DSTRUCT_K3':'TARGET_DSTRUCT_K2','V21_DSTRUCT_RAW3_K3':'V21_DSTRUCT_RAW3_K2',
                   'OPPJOINT_K4':'OPPJOINT_K3','OPPJOINT_K3':'OPPJOINT_K2','OPPSTRUCT_K3':'OPPSTRUCT_K2'}
    axis_for={'TARGET_DSTRUCT_K3':'hard_turn_rank_asc','TARGET_DSTRUCT_K2':'hard_turn_rank_asc','V21_DSTRUCT_RAW3_K3':'hard_turn_rank_asc',
              'OPPJOINT_K3':'q_rank_asc','OPPJOINT_K4':'q_rank_asc','OPPSTRUCT_K3':'challenge_turn_rank_asc','RFUSE_GEOM_K2':'response_hard_turn_rank_asc'}
    rows=[]
    for r in roles.to_dict('records'):
        method=r['method'];building=r['heldout_building'];cl=r['class_id'];ws=members(r['members'])
        known_ws=sorted(w for w,c in lm[(method,building)].items() if c==cl)
        assert ws==known_ws,(method,building,cl)
        parent=parent_method.get(method);pc=Counter(lm[(parent,building)].get(w,'unknown') for w in ws) if parent else Counter()
        if parent:assert len(pc)==1 and 'unknown' not in pc,(method,building,cl,pc)
        tc=Counter(lm[('TARGET_DSTRUCT_K2',building)].get(w,'unknown') for w in ws)
        record={k:r.get(k) for k in ['method','heldout_building','class_id','k','workers','members','semantic_training_role',
                                    *axes.keys(),'response_hard_turn_rank_asc','response_turn_rank_asc','response_q_rank_asc',
                                    'm_all_turn_n','m_hard_turn_n','m_challenge_turn_n','m_all_B8L2','m_all_log_time']}
        record.update(parent_method=parent,parent_class=next(iter(pc)) if pc else None,
                      parent_mapping_exact=bool(pc),TARGET_K2_global_crosswalk=enc(tc),
                      all_members_in_one_TARGET_K2_class=len(tc)==1 and 'unknown' not in tc,
                      TARGET_K2_class=next(iter(tc)) if len(tc)==1 else None,
                      primary_role_axis=axis_for[method],primary_role_rank=r.get(axis_for[method]))
        rows.append(record)
    role=pd.DataFrame(rows);save(role,'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv')
    lookup={(r.method,r.heldout_building,r.class_id):r._asdict() for r in role.itertuples(index=False)}
    caps=pd.read_csv(OUT/'DIRECTED_CLASS_CAPACITY.csv.gz')
    details=[]
    for r in caps.to_dict('records'):
        for m in [7,8,9,10,12]:
            if r['max_m']<m:continue
            record=dict(r,m=m,min_n=max(3,m),max_n=r['pool_n']-m,
                        n20_feasible=r['pool_n']>=20+m,n22_feasible=r['pool_n']>=22+m,n24_feasible=r['pool_n']>=24+m)
            a=lookup[(r['method'],r['building'],r['source_class'])];c=lookup[(r['method'],r['building'],r['target_class'])]
            for prefix,v in [('source',a),('target',c)]:
                for col in ['parent_method','parent_class','TARGET_K2_class','all_members_in_one_TARGET_K2_class','semantic_training_role',
                            'primary_role_axis','primary_role_rank','hard_turn_rank_asc','challenge_turn_rank_asc','q_rank_asc','time_rank_asc']:
                    record[prefix+'_'+col]=v.get(col)
                # `*_workers` is the exact local pool identity list, never the
                # global class size from the historical role table.
                record[prefix+'_global_class_n']=v.get('workers')
                local_ws=members(r[prefix+'_workers'])
                assert len(local_ws)==int(r[prefix+'_n'])
                assert record[prefix+'_workers']==r[prefix+'_workers']
                # The global crosswalk and the actually available local members
                # are distinct when a class overlaps a coarser structure group.
                lc=Counter(lm[('TARGET_DSTRUCT_K2',r['building'])].get(w,'unknown') for w in local_ws)
                record[prefix+'_local_TARGET_K2_counts']=enc(lc)
                record[prefix+'_local_TARGET_K2_single_class']=next(iter(lc)) if len(lc)==1 else None
            record['same_true_family_parent']=bool(a.get('parent_method') and a.get('parent_method')==c.get('parent_method') and a.get('parent_class')==c.get('parent_class'))
            record['same_TARGET_K2_global_parent']=bool(a.get('all_members_in_one_TARGET_K2_class') and c.get('all_members_in_one_TARGET_K2_class') and a.get('TARGET_K2_class')==c.get('TARGET_K2_class'))
            record['role_axis']=a['primary_role_axis']
            record['role_direction']=str(int(a['primary_role_rank']))+'/'+str(int(a['k']))+'->'+str(int(c['primary_role_rank']))+'/'+str(int(c['k']))
            record['source_highest_Q_role']=a['q_rank_asc']==role[(role.method.eq(r['method']))&role.heldout_building.eq(r['building'])].q_rank_asc.max()
            record['target_highest_Q_role']=c['q_rank_asc']==role[(role.method.eq(r['method']))&role.heldout_building.eq(r['building'])].q_rank_asc.max()
            details.append(record)
    d=pd.DataFrame(details);save(d,'M7_M8_M9_M10_M12_DIRECTION_ROLES_AND_PARENTS.csv.gz')
    selected=d[d.m.isin([9,10,12])];save(selected,'M9_M10_M12_DIRECTION_ROLES_AND_PARENTS.csv')
    summary=[]
    for keys,g in d.groupby(['method','scope','m','role_axis','role_direction'],dropna=False):
        summary.append(dict(zip(['method','scope','m','role_axis','role_direction'],keys),pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
                            n20_pools=g[g.n20_feasible].pool_id.nunique(),n22_pools=g[g.n22_feasible].pool_id.nunique(),n24_pools=g[g.n24_feasible].pool_id.nunique(),
                            all_same_true_parent=bool(g.same_true_family_parent.all()),all_same_TARGET_K2_parent=bool(g.same_TARGET_K2_global_parent.all()),
                            any_highest_Q_role=bool((g.source_highest_Q_role|g.target_highest_Q_role).any())))
    save(pd.DataFrame(summary),'DIRECTION_ROLE_CAPACITY_SUMMARY.csv')
    target=selected[selected.method.eq('TARGET_DSTRUCT_K3')]
    assert target.same_true_family_parent.all() and target.same_TARGET_K2_global_parent.all()
    joint=selected[selected.method.isin(['OPPJOINT_K3','OPPJOINT_K4'])&selected.m.isin([10,12])]
    no_high_q=not (joint.source_highest_Q_role|joint.target_highest_Q_role).any()
    receipt={'methods':role.method.unique().tolist(),'frozen_class_role_rows':len(role),'all_parent_mappings_exact':True,
             'TARGET_m9_m10_all_within_TARGET_K2_parent':True,'TARGET_m12_capacity':int(target[target.m.eq(12)].pool_id.nunique()),
             'JOINT_m10_m12_highest_Q_role_never_in_source_or_target':bool(no_high_q),
             'profile_is_historical_LOBO_not_target_image_Q':True,'class_ids_are_not_semantic_ordinals':True,
             'input_sources':{str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',PREVIOUS/'CLASS_CENTERS_ALL_LOBO.csv.gz',BASE/'MAIN45_LABELS_ALL_LOBO.csv.gz',PREVIOUS/'NEW_LABELS_ALL_LOBO.csv.gz']}}
    (OUT/'ROLE_PARENT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
