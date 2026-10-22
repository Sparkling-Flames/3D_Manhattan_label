#!/usr/bin/env python3
"""Targeted independent audit of registered finite-team replay and raw scope evidence.

No geometries are re-fused; saved states, source annotations, frozen task contracts,
fold profiles, denominators and reported aggregation are checked independently.
"""
import argparse
from collections import Counter
from functools import lru_cache
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path
import numpy as np
import pandas as pd


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a,b,tol=1e-9):
    assert (pd.isna(a) and pd.isna(b)) or abs(a-b)<tol,(a,b)


def main(args):
    study=Path(args.study).resolve();repo=Path(args.repo).resolve();out=Path(args.out).resolve()
    fp=study/'fusion';sp=fp/'stage2';rp=study/'reliability'
    names=[fp/'STAGE2_REGISTRATION.json',sp/'PERMUTATIONS.csv',sp/'path_states.csv',sp/'same_k_pairs.csv',
        sp/'prefix_transitions.csv',sp/'strategy_by_image_k.csv',sp/'paired_strategy_differences_by_building.csv',
        sp/'paired_strategy_summary.csv',rp/'scope_object_ledger.csv',rp/'worker_scope_summary.csv',
        fp/'out_of_building_member_profiles.csv',study/'q/fold_profiles_recomputed.csv']
    hashes={str(p.relative_to(study)):sha(p) for p in names}
    reg=json.loads((fp/'STAGE2_REGISTRATION.json').read_text())
    perm=pd.read_csv(sp/'PERMUTATIONS.csv');states=pd.read_csv(sp/'path_states.csv')
    members=pd.read_csv(fp/'out_of_building_member_profiles.csv')
    folds=pd.read_csv(study/'q/fold_profiles_recomputed.csv')
    mm=members.set_index(['image','worker_id']);sm=states.set_index(['image','strategy','path','k'])
    assert len(perm)==336 and len(states)==2688
    assert not perm.duplicated(['image','strategy','path']).any()
    assert not states.duplicated(['image','strategy','path','k']).any()
    assert states.groupby(['image','strategy','path']).k.agg(set).map(lambda x:x==set(range(1,9))).all()
    assert set(perm.image)==set(reg['images']) and perm.building_id.nunique()==6
    for r in members.itertuples():
        qf=folds[folds.panel.eq('current') & folds.axis.eq('B8L2') & folds.fold.eq(r.building_id) & folds.worker_id.eq(r.worker_id)]
        assert len(qf)==1 and qf.supported.iloc[0]
        close(qf.effect.iloc[0],r.B8L2_effect)
        assert r.building_id not in json.loads(r.B8L2_training_buildings)
        assert r.B8L2_Q2==('high' if qf.effect.iloc[0]>0 else 'low')
    rng=np.random.default_rng(reg['seed'])
    seed_checks=membership_checks=geometry_checks=0
    for image in reg['images']:
        ims=members[members.image.eq(image)]
        alias=dict(zip(ims.source_worker,ims.worker_id));pool=sorted(alias)
        highflag={p:mm.loc[(image,alias[p]),'B8L2_Q2']=='high' for p in pool}
        assert min(sum(highflag.values()),24-sum(highflag.values()))>=8
        for repeat in range(reg['paths_per_image_strategy']):
            order=rng.permutation(pool).tolist();hi=[p for p in order if highflag[p]];lo=[p for p in order if not highflag[p]]
            mixed=rng.permutation(hi[:4]+lo[:4]).tolist()
            expected={'8_high':hi[:8],'4_high_4_low':mixed,'8_low':lo[:8],'random_8_from_24':order[:8]}
            for strategy,ps in expected.items():
                p=perm[perm.image.eq(image)&perm.strategy.eq(strategy)&perm.path.eq(repeat)].iloc[0]
                assert p.public_worker_order.split('|')==ps
                ws=[alias[a] for a in ps]; assert p.worker_order.split('|')==ws
                assert len(set(ws))==8 and p.terminal_high_n==sum(highflag[a] for a in ps)
                assert p.object_order.split('|')==[mm.loc[(image,w),'object_id'] for w in ws]
                seed_checks+=1
                for k in range(1,9):
                    s=sm.loc[(image,strategy,repeat,k)]
                    assert set(s.subset.split('|'))==set(ps[:k])
                    assert set(s.worker_ids.split('|'))==set(ws[:k])
                    assert set(s.member_object_ids.split('|'))=={mm.loc[(image,w),'object_id'] for w in ws[:k]}
                    assert s.B8L2_high_n==sum(highflag[a] for a in ps[:k])
                    membership_checks+=1
        saved=json.load(gzip.open(sp/'states'/(image+'.json.gz'),'rt'))
        savedkeys=[]
        for r in saved['states']:
            ps=set(r['workers']);a=r['automatic'];savedkeys.append('|'.join(sorted(ps)))
            assert a['n']==len(ps)
            assert {m['worker'] for g in a['identity_groups'] for m in g['members']}==ps
            geometry_checks+=1
        assert set(savedkeys)==set(states[states.image.eq(image)].subset)
    complete=int(states.complete_evaluable.sum());deferred=int(states.k.eq(2).sum())
    missing=int((~states.complete_evaluable & states.k.ne(2)).sum())
    assert complete+deferred+missing==len(states)
    assert states.B8L2.notna().eq(states.D10.notna()).all()
    assert states.B8L2.notna().eq(states.complete_evaluable).all()
    assert not states.class_pool_exhausted.any()
    st=pd.read_csv(sp/'prefix_transitions.csv');assert len(st)==2352
    for r in st.itertuples():
        a=sm.loc[(r.image,r.strategy,r.path,r.k_from)];b=sm.loc[(r.image,r.strategy,r.path,r.k_to)]
        assert r.k_to==r.k_from+1
        assert set(b.worker_ids.split('|'))-set(a.worker_ids.split('|'))=={r.added_worker_id}
        assert r.previous_subset==a.subset and r.current_subset==b.subset
        close(r.B8L2_change,b.B8L2-a.B8L2)
    pairs=pd.read_csv(sp/'same_k_pairs.csv');assert len(pairs)==14784
    for r in pairs.itertuples():
        a=sm.loc[(r.image,r.strategy,r.path_a,r.k)];b=sm.loc[(r.image,r.strategy,r.path_b,r.k)]
        shared=len(set(a.worker_ids.split('|'))&set(b.worker_ids.split('|')))
        assert r.shared_members==shared
        assert r.same_subset==(a.subset==b.subset)
        assert r.both_complete_floor==(a.complete_floor_evaluable and b.complete_floor_evaluable)
        assert pd.notna(r.floor_difference)==r.both_complete_floor
        if r.same_subset and r.both_complete_floor:close(r.floor_difference,0)
    sums=pd.read_csv(sp/'strategy_by_image_k.csv')
    meanmetrics=['B8L2','D10','IoU3D100','raw_R','complete_evaluable','source_time_total_seconds','target_matched_time_total_seconds','B8L2_high_n','B8L2_mean_effect']
    by={}
    for r in sums.itertuples():
        g=states[states.image.eq(r.image)&states.strategy.eq(r.strategy)&states.k.eq(r.k)]
        assert r.attempts==len(g)==12 and r.complete_n==g.complete_evaluable.sum()
        for col in meanmetrics:close(getattr(r,col+'_mean'),g[col].mean())
        p=pairs[pairs.image.eq(r.image)&pairs.strategy.eq(r.strategy)&pairs.k.eq(r.k)]
        assert r.V_pairs==66 and r.V_valid_pairs==p.both_complete_floor.sum()
        close(r.V_floor,p.floor_difference.mean());close(r.shared_members_mean,p.shared_members.mean())
        by[(r.image,r.strategy,r.k)]=r
    bld=pd.read_csv(sp/'paired_strategy_differences_by_building.csv')
    summary=pd.read_csv(sp/'paired_strategy_summary.csv')
    contrasts=[('8_high','random_8_from_24'),('4_high_4_low','random_8_from_24'),('8_low','random_8_from_24'),('8_high','8_low'),('8_high','4_high_4_low')]
    # Validate score/completeness/V/overlap means through both aggregation levels.
    checkouts=['B8L2_mean','D10_mean','complete_evaluable_mean','V_floor','shared_members_mean']
    aggregation_checks=0
    for k in range(1,9):
        for a,b in contrasts:
            contrast=a+'_minus_'+b
            for outcol in checkouts:
                diffs=[]
                for image in reg['images']:
                    ra=by[(image,a,k)];rb=by[(image,b,k)]
                    diffs.append({'building':ra.building_id,'value':getattr(ra,outcol)-getattr(rb,outcol)})
                expected=pd.DataFrame(diffs).groupby('building').value.mean()
                for building,value in expected.items():
                    row=bld[bld.k.eq(k)&bld.contrast.eq(contrast)&bld.building_id.eq(building)].iloc[0]
                    close(row[outcol+'_difference'],value)
                row=summary[summary.k.eq(k)&summary.contrast.eq(contrast)&summary.outcome.eq(outcol+'_difference')].iloc[0]
                close(row['mean'],expected.mean());assert row.buildings==expected.notna().sum()
                aggregation_checks+=1
    scope=pd.read_csv(rp/'scope_object_ledger.csv');led=pd.read_csv(rp/'reliability_object_ledger.csv')
    current=scope[scope.current_clear_in_scope_adjudicated]
    assert not current.current_gt_error_excluded.any()
    assert current.scene.eq('clear').all() and current.doorway_status.eq('none').all()
    assert current.current_scope_semantics.eq('whole_space_vertical_boundary').all()
    assert current.historical_task_gold.eq('in_scope').all() and current.historical_later_hold.isna().all()
    w=scope[scope.worker_id.eq('W030')&scope.condition.eq('manual')&scope.current_clear_in_scope_adjudicated]
    assert len(w)==11 and w.image_id.nunique()==11 and w.building_id.nunique()==7
    @lru_cache(None)
    def raw(path):return {int(t['id']):t for t in json.loads((repo/path).read_text(encoding='utf-8-sig'))}
    @lru_cache(None)
    def gold(path):return {g['base_task_id']:g for g in map(json.loads,(repo/path).read_text(encoding='utf-8-sig').splitlines())}
    checked_scope=[];additional_hashes={}
    for r in w.itertuples():
        t=raw(r.raw_source_path)[r.raw_task];a=[a for a in t['annotations'] if int(a['id'])==r.raw_annotation]
        assert len(a)==1 and int(a[0]['completed_by'])==30
        assert t['data']['base_task_id']==r.image_id
        g=gold(r.historical_gold_source)[r.image_id]
        assert str(t['data']['task_id'])==str(g['task_id'])
        assert g['scope_gold_ready'] is True and g['final_scope_binary']=='in_scope'
        assert g['adjudication_status']=='final_adjudicated_gold'
        choices=[v for x in a[0]['result'] if x.get('type')=='choices' and x.get('from_name')=='scope' for v in x['value']['choices']]
        assert len(choices)==1
        ans='in_scope' if choices[0]=='normal' else 'oos' if choices[0].startswith('oos') else 'unknown'
        assert ans==r.worker_scope
        assert r.current_compatible_outcome==('correct_acceptance' if ans=='in_scope' else 'false_rejection')
        checked_scope.append(dict(object_id=r.object_id,worker_id=r.worker_id,image_code=r.image_code,building_id=r.building_id,
            raw_task=r.raw_task,raw_annotation=r.raw_annotation,raw_choice=choices[0],bound_gold_task_id=g['task_id'],
            gold='in_scope',outcome=r.current_compatible_outcome,raw_source=r.raw_source_path,gold_source=r.historical_gold_source))
        for p in [repo/r.raw_source_path,repo/r.historical_gold_source]:additional_hashes[str(p.relative_to(repo))]=sha(p)
    ce=set(current.loc[current.current_compatible_outcome.eq('false_rejection'),'object_id'])
    severe=set(led.loc[led.strict_specific_personal_severe,'object_id'])
    broad=set(led.loc[led.reviewer_personal_nonacceptance,'object_id'])
    overlap=scope[scope.object_id.isin(ce&severe)][['object_id','worker_id','image_code','current_compatible_outcome']].copy()
    overlap.to_csv(out/'scope_severe_event_overlap.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(checked_scope).to_csv(out/'W030_scope_raw_audit.csv',index=False,encoding='utf-8-sig')
    assert {str(p.relative_to(study)):sha(p) for p in names}==hashes
    receipt=dict(data_release='v1',read_only=True,source_sha256=hashes,original_scope_source_sha256=additional_hashes,
      stage2=dict(schedules_verified=seed_checks,prefix_memberships_verified=membership_checks,saved_unique_state_member_checks=geometry_checks,
        path_attempts=len(states),complete_states=complete,k2_policy_deferred=deferred,other_incomplete=missing,
        prefix_transitions_verified=len(st),same_k_pairs_with_verified_member_overlap=len(pairs),independent_image_building_aggregation_checks=aggregation_checks,
        target_building_labels_verified=True,target_geometry_used_for_selection=False,all_terminal_Q_compositions_correct=True,
        source_class_pool_exhausted=False,geometry_re_fused_by_auditor=False,limited_to_seven_images_six_buildings=True),
      scope=dict(current_clear_opportunities=len(current),current_clear_false_rejections=len(ce),
        W030_manual_opportunities=len(w),W030_false_rejections=int(w.current_compatible_outcome.eq('false_rejection').sum()),
        W030_correct_acceptance=int(w.current_compatible_outcome.eq('correct_acceptance').sum()),W030_buildings=7,
        W030_raw_choices=Counter(r['raw_choice'] for r in checked_scope),W030_scope_severe_overlap=len(set(w.object_id)&severe),
        all_current_scope_false_rejection_overlap_strict_severe=len(ce&severe),all_current_scope_false_rejection_overlap_broad=len(ce&broad),
        original_gold_verified=True,new_scope_gold_created=False,
        caution='Current-compatible in-scope opportunities do not establish a general current-policy false-acceptance denominator; same objects across scope and rejection evidence must not be penalized twice.'))
    (out/'STAGE2_SCOPE_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',default=str(Path(__file__).resolve().parents[1]))
    p.add_argument('--repo',default=str(Path(__file__).resolve().parents[2]/'repo'))
    p.add_argument('--out',default=str(Path(__file__).resolve().parent));main(p.parse_args())
