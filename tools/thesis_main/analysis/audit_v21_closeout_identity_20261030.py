"""Check frozen teams against current candidate labels; never design or fuse teams."""
import json
from collections import Counter
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis.recompute_v21_image_difficulty_20261030 import labels

ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/'research/workers/personnel_ac_v21_20261030'
OUT=ROOT/'research/data/releases/v2.1/closeout_20261030'

def members(value):
    return set() if pd.isna(value) or value=='' else set(str(value).split('|'))

def complete_class(team,pool,roster,class_id):
    expected={w for w in pool if roster.get(w)==class_id}
    return bool(expected) and team==expected

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    lab=labels();rosters={(m,b):dict(zip(g.loc[g.known,'worker_id'],g.loc[g.known,'class_id'])) for (m,b),g in lab.groupby(['method','heldout_building'])}
    alliance=pd.read_csv(SRC/'stage01_capacity/ALL_CLASS_ALLIANCE_TEAMS.csv.gz')
    classes=pd.read_csv(SRC/'stage01_capacity/POOL_CLASS_MEMBERS.csv.gz')
    pools={}
    pool_sizes=classes.groupby(['method','pool_id']).pool_n.first().to_dict()
    for key,g in classes.groupby(['method','pool_id']):
        pools[key]=set().union(*(members(v) for v in g.class_workers))
    for key,g in alliance.groupby(['method','pool_id']):
        pools[key]|=set().union(*(members(v) for v in g.members))
        assert len(pools[key])<=int(g.pool_n.iloc[0])
    rows=[]
    for r in alliance.itertuples():
        key=(r.method,r.heldout_building)
        if key not in rosters:continue
        roster=rosters[key];pool=pools[r.method,r.pool_id];team=members(r.members)
        class_set=members(r.alliance_classes);assert class_set
        expected={w for w in pool if roster.get(w) in class_set or (r.unknown_background_included and w not in roster)}
        complete=len(pool)==r.pool_n
        rows.append(dict(method=r.method,pool_id=r.pool_id,image=r.image,building=r.building,reference_id=r.reference_id,reference_version=r.reference_version,alliance_classes=r.alliance_classes,n=r.n,members=r.members,execution_status=r.execution_status,pool_roster_complete=complete,still_declared_alliance=(team==expected) if complete else None,expected_n=len(expected) if complete else None,added_members='|'.join(sorted(expected-team)) if complete else '',removed_members='|'.join(sorted(team-expected)) if complete else ''))
    a=pd.DataFrame(rows);a.to_csv(OUT/'ALLIANCE_IDENTITY.csv.gz',index=False)
    # Inspect all affected archived AC events, without reading or recomputing geometry.
    rows=[]
    for chunk in pd.read_csv(SRC/'stage01_registered/AC_EVENTS.csv.gz',chunksize=30000,low_memory=False):
        for r in chunk.itertuples():
            key=(r.method,r.heldout_building)
            if key not in rosters:continue
            roster=rosters[key];pool=pools[r.method,r.pool_id];x=members(r.X_workers);z=members(r.Z_workers);d=members(r.D_workers)
            source={roster.get(w) for w in x};target={roster.get(w) for w in z}
            cross=bool(x and z and len(source)==len(target)==1 and None not in source|target and source!=target)
            direction=cross and source=={r.source_class} and target=={r.target_class}
            full_pool=len(pool)==pool_sizes[r.method,r.pool_id]
            counts=dict(Counter(roster.get(w,'unknown') for w in d))
            rows.append(dict(event_id=r.event_id,method=r.method,pool_id=r.pool_id,image=r.image,design_family=r.design_family,n_A=r.n_A,n_C=r.n_C,m_X=r.m_X,m_Z=r.m_Z,frozen_pure_cross_class=r.pure_cross_class_blocks,still_cross_class=cross,still_declared_direction=direction,whole_target_declared=r.whole_target,pool_roster_complete=full_pool,whole_target_preserved=complete_class(z,pool,roster,r.target_class) if r.whole_target and full_pool else None,background_counts_unchanged=counts==json.loads(r.D_class_counts)))
    e=pd.DataFrame(rows);e.to_csv(OUT/'AC_IDENTITY.csv.gz',index=False)
    summary=[]
    for method,g in e.groupby('method'):
        w=g[g.whole_target_declared]
        summary.append(dict(method=method,events=len(g),still_cross_class=int(g.still_cross_class.sum()),still_declared_direction=int(g.still_declared_direction.sum()),background_counts_unchanged=int(g.background_counts_unchanged.sum()),whole_target_declared=len(w),whole_target_evaluable=int(w.whole_target_preserved.notna().sum()),whole_target_preserved=int(w.whole_target_preserved.sum())))
    pd.DataFrame(summary).to_csv(OUT/'AC_IDENTITY_SUMMARY.csv',index=False)
    a.groupby('method').agg(teams=('n','size'),pool_roster_complete=('pool_roster_complete','sum'),still_declared_alliance=('still_declared_alliance','sum')).to_csv(OUT/'ALLIANCE_IDENTITY_SUMMARY.csv')
    checks=dict(classification_finalized=False,label_source='admitted_space_extension/image_difficulty_20261030',alliance_rows=len(a),ac_rows=len(e),new_fusion=0,new_teams=0,semantics='literal declared class IDs; no automatic relabeling; incomplete pool inventories are not full-class proofs')
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(checks)

if __name__=='__main__':run()
