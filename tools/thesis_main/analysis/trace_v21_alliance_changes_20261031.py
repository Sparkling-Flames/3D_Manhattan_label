"""Trace label-only and membership changes without generating any new fusion."""
import gzip
import itertools
import json
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis.audit_v21_closeout_identity_20261030 import members, ROOT, SRC

OUT=ROOT/'research/data/releases/v2.1/closeout_20261030'
UP=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030'
BASE=ROOT/'research/workers/personnel_v21_reselection_20261029/classification'

def main():
    old=pd.read_csv(SRC/'stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz',low_memory=False)
    new=pd.read_csv(UP/'classification/LABELS_ALL_LOBO.csv.gz')
    baseline=pd.read_csv(BASE/'MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    old=old[old.method.eq('TARGET_DSTRUCT_K3')];new=new[new.method.eq('TARGET_DSTRUCT_K3')]
    check=old.merge(baseline[baseline.method.eq('TARGET_DSTRUCT_K3')],on=['worker_id','heldout_building'],suffixes=('_ac','_base'))
    assert len(check)==len(old)==1426
    assert check.class_id_ac.fillna('').eq(check.class_id_base.fillna('')).all() and check.known_ac.eq(check.known_base).all()
    raw=pd.read_csv(BASE/'RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False);updated=pd.read_csv(UP/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    pd.testing.assert_frame_equal(raw.drop(columns='official_difficulty'),updated.drop(columns='official_difficulty'))
    changed=raw.official_difficulty.fillna('').ne(updated.official_difficulty.fillna(''))
    assert raw.loc[changed,'scope'].eq('other_admitted').all()
    roster={};before={};mapping={};folds=[];workers=[]
    for fold,g in new.groupby('heldout_building'):
        a=old[old.heldout_building.eq(fold)].set_index('worker_id');b=g.set_index('worker_id')
        assert set(a.index)==set(b.index)
        ar={w:str(r.class_id) for w,r in a.iterrows() if r.known};br={w:str(r.class_id) for w,r in b.iterrows() if r.known}
        roster[fold]=br;before[fold]=ar
        common=set(ar)&set(br);classes=['C1','C2','C3']
        perm=max(itertools.permutations(classes),key=lambda p:sum(ar[w]==dict(zip(classes,p))[br[w]] for w in common))
        mp=dict(zip(classes,perm));mapping[fold]=mp
        n=sum(ar[w]!=mp[br[w]] for w in common)
        folds.append(dict(fold=fold,known_old=len(ar),known_new=len(br),literal_changes=sum(ar.get(w)!=br.get(w) for w in a.index),partition_changes_aligned=n,new_to_old=json.dumps(mp)))
        for w in a.index:
            if ar.get(w)!=br.get(w):workers.append(dict(fold=fold,worker=w,old_class=ar.get(w),new_class=br.get(w),aligned_new=mp.get(br.get(w))))
    pd.DataFrame(folds).to_csv(OUT/'ALLIANCE_LABEL_CAUSE.csv',index=False)
    pd.DataFrame(workers).to_csv(OUT/'ALLIANCE_CHANGED_WORKERS.csv',index=False)
    teams=pd.read_csv(SRC/'stage01_capacity/ALL_CLASS_ALLIANCE_TEAMS.csv.gz');teams=teams[teams.method.eq('TARGET_DSTRUCT_K3')]
    inventory={p:set().union(*(members(x) for x in g.members)) for p,g in teams.groupby('pool_id')}
    requests=pd.read_csv(SRC/'stage01_registered/TEAM_REQUESTS.csv.gz')
    lookup={(r.pool_id,r.reference_id,r.reference_version,frozenset(members(r.member_workers))):r.team_key for r in requests.itertuples()}
    details=[];needed={}
    for r in teams.itertuples():
        pool=inventory[r.pool_id];assert len(pool)==r.pool_n
        br=roster[r.heldout_building];ar=before[r.heldout_building];oldteam=members(r.members);cls=members(r.alliance_classes)
        expected={w for w in pool if br.get(w) in cls or (r.unknown_background_included and w not in br)}
        if expected==oldteam:continue
        possible=[]
        for k in range(1,4):
            for comb in itertools.combinations(['C1','C2','C3'],k):
                candidate={w for w in pool if br.get(w) in comb or (r.unknown_background_included and w not in br)}
                if candidate==oldteam:possible.append('|'.join(comb))
        aligned={w for w in pool if mapping[r.heldout_building].get(br.get(w)) in cls or (r.unknown_background_included and w not in br)}
        key=lookup.get((r.pool_id,r.reference_id,r.reference_version,frozenset(expected)))
        oldkey=lookup.get((r.pool_id,r.reference_id,r.reference_version,frozenset(oldteam)))
        row=dict(pool_id=r.pool_id,image=r.image,building=r.building,scope=r.scope,condition=r.condition,reference_id=r.reference_id,reference_version=r.reference_version,classes=r.alliance_classes,old_n=len(oldteam),new_n=len(expected),old_members='|'.join(sorted(oldteam)),new_members='|'.join(sorted(expected)),old_team_key=oldkey,new_team_key=key,old_team_is_other_new_alliance=bool(possible),new_identity_for_old_team=';'.join(possible),only_label_permutation=aligned==oldteam,changed_people='|'.join(sorted(w for w in pool if ar.get(w)!=br.get(w))),new_n_at_least3=len(expected)>=3,endpoint_found=False)
        details.append(row)
        if key:needed.setdefault(r.pool_id,set()).add(key)
        if oldkey:needed.setdefault(r.pool_id,set()).add(oldkey)
    assert len(details)==414
    scores={}
    for pool,keys in needed.items():
        for path in sorted((SRC/'stage03_endpoints/pools'/pool).glob('part_*.jsonl.gz')):
            with gzip.open(path,'rt',encoding='utf8') as f:
                for line in f:
                    v=json.loads(line)
                    if v['team_key'] in keys:
                        scores[v['team_key']]={k:v.get(k) for k in ['pool_id','reference_id','reference_version','member_workers','member_object_ids','B8L2','complete_evaluable','engine_digest','input_pool_sha256','reference_sha256','fusion_quality_contract_unchanged']}
            if keys<=scores.keys():break
        print('endpoint lookup',pool,len(keys&scores.keys()),'/',len(keys),flush=True)
    historical=ROOT/'research/data/releases/v2.1/current_exchange_endpoints/REUSED_ENDPOINTS.jsonl.gz'
    wanted={(r['pool_id'],frozenset(members(r['new_members']))):r for r in details if not r['new_team_key'] and r['new_n_at_least3']}
    historical_hits=0
    with gzip.open(historical,'rt',encoding='utf8') as f:
        for line in f:
            v=json.loads(line);key=(v.get('pool_id'),frozenset(v.get('member_workers',[])))
            row=wanted.get(key)
            if row is None or (v.get('reference_id'),v.get('reference_version'))!=(row['reference_id'],row['reference_version']):continue
            assert 'geometry' in v
            row['new_team_key']=v['team_key'];row['additional_cache']=str(historical.relative_to(ROOT))
            scores[v['team_key']]={k:v.get(k) for k in ['pool_id','reference_id','reference_version','member_workers','member_object_ids','B8L2','complete_evaluable','engine_digest','input_pool_sha256','reference_sha256','fusion_quality_contract_unchanged']}
            historical_hits+=1
    for row in details:
        v=scores.get(row['new_team_key']);oldv=scores.get(row['old_team_key'])
        if v:
            assert set(v['member_workers'])==members(row['new_members'])
            assert (v['reference_id'],v['reference_version'])==(row['reference_id'],row['reference_version'])
            row['endpoint_found']=True;row['new_Q']=v['B8L2'];row['new_complete_evaluable']=v['complete_evaluable']
        if oldv:row['old_Q']=oldv['B8L2']
        if oldv and v:
            row['same_engine_and_pool']=all(oldv[k]==v[k] for k in ['engine_digest','input_pool_sha256','reference_sha256'])
        row['action']='capacity_only_n_lt3' if not row['new_n_at_least3'] else ('reuse_saved_endpoint' if v else 'not_in_AC_endpoint_archive')
        if v and row.get('additional_cache'):
            row['action']='historical_endpoint_contract_check'
    d=pd.DataFrame(details);d.to_csv(OUT/'ALLIANCE_414_TRACE.csv',index=False)
    d[d.action.eq('not_in_AC_endpoint_archive')].to_csv(OUT/'ALLIANCE_TEAM_SEARCH_QUEUE.csv',index=False)
    summary=dict(changed_grade_records=int(changed.sum()),ac_labels_equal_original_main45=True,changed_alliances=len(d),images=d.image.nunique(),pools=d.pool_id.nunique(),buildings=d.building.nunique(),pure_permutation=int(d.only_label_permutation.sum()),old_team_other_complete_union=int(d.old_team_is_other_new_alliance.sum()),actions=d.action.value_counts().to_dict(),scope=d.scope.value_counts().to_dict(),historical_cache_hits=historical_hits,new_fusion=0)
    (OUT/'ALLIANCE_414_CHECKS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(summary)

if __name__=='__main__':main()
