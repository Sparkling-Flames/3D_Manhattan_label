#!/usr/bin/env python3
"""Outcome-free 7-choose-6 target-block panels at fixed original A and n=10.

Only registered events, frozen labels/centers and pool inventories are read.
No endpoint or event-effect table is opened. No fusion is run here.
"""
from __future__ import annotations
import collections
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_native import POP,read,save,csv,team_key

SEED=2026102519
METHODS=['DSTRUCT_K3','MSDGEOM_SCOPE_K4']


def digest(value):
    return hashlib.sha256(json.dumps([SEED,value],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def people(value):
    return sorted(set(str(value).split('|'))-{''})


def rank_people(members,key):
    return sorted(members,key=lambda w:digest([key,w]))


def main():
    out=ROOT/'design/target_omissions';out.mkdir(parents=True,exist_ok=True)
    ledgers=[];labels=[];centers=[];phases=[]
    for stage in ['screen','confirm']:
        src=ROOT/'design'/stage
        ev=pd.read_csv(src/'EVENTS_EXACT.csv.gz',low_memory=False)
        ev['paired_m7_ledger']=str((src/'EVENTS_EXACT.csv.gz').relative_to(ROOT))
        ledgers.append(ev)
        labels.append(pd.read_csv(src/'FROZEN_LABELS.csv.gz'))
        centers.append(pd.read_csv(src/'FOLD_ROLE_CENTERS.csv.gz'))
        phases.append(pd.read_csv(src/'IMAGE_PHASE_ASSIGNMENT.csv'))
    original=pd.concat(ledgers,ignore_index=True)
    original=original[original.method.isin(METHODS)&original.n.eq(10)&original.m.eq(7)].copy()
    assert not original.event_id.duplicated().any()
    lab=pd.concat(labels,ignore_index=True).drop_duplicates(['condition','method','heldout_building','worker_id'],keep='last')
    lab=lab[lab.method.isin(METHODS)]
    lab['known']=lab.known.astype(str).str.lower().eq('true')
    lm={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in lab[lab.known].groupby(['method','heldout_building'])}
    cent=pd.concat(centers,ignore_index=True).drop_duplicates(['method','heldout_building','class_id'],keep='last')
    cent=cent[cent.method.isin(METHODS)].copy()
    cent['class_people']=cent.members.fillna('').map(lambda s:len(people(s)))
    cg=cent.groupby(['method','heldout_building'])
    cent['largest_class']=cent.class_people.eq(cg.class_people.transform('max'))
    cent['highest_turn']=cent.m_hard_turn_n.eq(cg.m_hard_turn_n.transform('max'))
    for side in ['source','target']:
        attrs=cent[['method','heldout_building','class_id','largest_class','highest_turn']].rename(
            columns={'heldout_building':'building','class_id':side+'_class',
                     'largest_class':side+'_largest_class','highest_turn':side+'_highest_turn'})
        original=original.merge(attrs,on=['method','building',side+'_class'],how='left',validate='many_to_one')
    original=original[original.source_largest_class.eq(True)&original.target_highest_turn.eq(True)&~original.source_highest_turn.eq(True)].copy()
    pools={p['pool_id']:p for p in read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
    events=[];requests={};anchors=[];capacity=[];links=[]
    for (pid,method),g in original.groupby(['pool_id','method'],sort=True):
        pool=pools[pid];pool_workers=sorted(r['worker_id'] for r in pool['records'])
        mapping=lm[(method,pool['meta']['building'])]
        ranked=sorted(g.to_dict('records'),key=lambda r:digest(['anchor',pid,method,r['event_id']]))
        selected=[ranked[0]]
        remaining=ranked[1:]
        if remaining:
            # Prefer independent XYZ and D. If unavailable, retain another exact
            # anchor and explicitly report whether blocks/backgrounds changed.
            different_both=[r for r in remaining if r['block_id']!=selected[0]['block_id'] and r['background_id']!=selected[0]['background_id']]
            different_xyz=[r for r in remaining if r['block_id']!=selected[0]['block_id']]
            selected.append((different_both or different_xyz or remaining)[0])
        for anchor_index,parent in enumerate(selected):
            D7,X7,Y7,Z7=[people(parent[x]) for x in ['D','X','Y','Z']]
            assert len(D7)==3 and len(X7)==len(Y7)==len(Z7)==7
            assert len(set(D7+X7+Y7+Z7))==24
            source,target=parent['source_class'],parent['target_class']
            assert all(mapping[w]==source for w in X7+Y7)
            assert all(mapping[w]==target for w in Z7)
            x_retained=rank_people(X7,['retain_source',parent['event_id']])[0]
            y_removed=rank_people(Y7,['drop_same_class',parent['event_id']])[0]
            D6=sorted(D7+[x_retained]);X6=sorted(set(X7)-{x_retained});Y6=sorted(set(Y7)-{y_removed})
            total_target=sorted(w for w in pool_workers if mapping.get(w)==target)
            source_n=sum(mapping.get(w)==source for w in pool_workers)
            anchor_id=digest(['panel',parent['event_id'],x_retained,y_removed])[:24]
            anchor_record=dict(anchor_id=anchor_id,pool_id=pid,image=parent['image'],building=parent['building'],
                method=method,phase=parent['phase'],paired_m7_stage=parent['stage'],
                paired_m7_event_id=parent['event_id'],paired_m7_ledger=parent['paired_m7_ledger'],
                anchor_index=anchor_index,available_parent_anchors=len(g),
                paired_m7_block_id=parent['block_id'],paired_m7_background_id=parent['background_id'],
                source_class=source,target_class=target,x_retained_in_D=x_retained,y_removed_from_B=y_removed,
                D6='|'.join(D6),X6='|'.join(X6),Y6='|'.join(Y6),Z7_panel='|'.join(Z7),
                total_target_capacity=len(total_target),target_panel_n=7,feasible_panel_combinations=7,
                target_workers_outside_panel='|'.join(sorted(set(total_target)-set(Z7))),
                A7_team_key=parent['A_team_key'],B7_team_key=parent['B_team_key'],C7_team_key=parent['C_team_key'])
            anchors.append(anchor_record)
            # Parent endpoints are included to keep scale contrasts self-contained.
            for arm in 'ABC':
                members=people(parent[arm+'_members']);key=team_key(pid,members)
                assert key==parent[arm+'_team_key']
                requests[key]=dict(pool_id=pid,worker_ids=members,team_key=key)
            for omitted in Z7:
                Z6=sorted(set(Z7)-{omitted})
                assert len(set(D6+X6+Y6+Z6))==22
                teams={arm:sorted(D6+block) for arm,block in [('A',X6),('B',Y6),('C',Z6)]}
                assert all(len(x)==10 for x in teams.values())
                assert teams['A']==people(parent['A_members'])
                e={k:v for k,v in parent.items() if not k.startswith(('feasible_','planned_','source_largest_','source_highest_','target_largest_','target_highest_'))}
                e.update(event_id=digest(['omit',anchor_id,omitted])[:24],design='strict_disjoint_ABC',
                    design_variant='fixed_A_original_Z7_complete_leave_one_out',stage='target_omissions',
                    n=10,m=6,actual_m_AB=6,actual_m_AC=6,actual_m_BC=6,
                    replacement_fraction=.6,source_block_fraction=6/source_n,seat_net_change_l1=12,
                    source_capacity=source_n,target_capacity=len(total_target),pool_n=len(pool_workers),feasible=True,
                    D='|'.join(D6),X='|'.join(X6),Y='|'.join(Y6),Z='|'.join(Z6),
                    background_id=digest([pid,D6])[:20],block_id=digest([pid,X6,Y6,Z6])[:20],
                    block_replicate=anchor_index,background_replicate=0,
                    background_target_n=sum(mapping.get(w)==target for w in D6),
                    background_source_n=sum(mapping.get(w)==source for w in D6),
                    background_unknown_n=sum(w not in mapping for w in D6),
                    anchor_id=anchor_id,Z_omitted_worker=omitted,
                    x_retained_in_D=x_retained,y_removed_from_B=y_removed,
                    paired_m7_event_id=parent['event_id'],paired_m7_stage=parent['stage'],paired_m7_phase=parent['phase'],
                    paired_m7_block_id=parent['block_id'],paired_m7_background_id=parent['background_id'],
                    A7_team_key=parent['A_team_key'],B7_team_key=parent['B_team_key'],C7_team_key=parent['C_team_key'],
                    total_target_capacity=len(total_target),target_panel_n=7,feasible_panel_combinations=7,
                    panel_enumeration_complete=True,anchor_selection_seed=SEED,
                    parent_m=7,parent_n=10,actual_m_C7_C6=1,actual_m_B7_B6=1)
                # These quotas describe the anchored finite experiment, not the
                # much larger full-pool configuration space from the parent.
                e['background_target_min']=e['background_target_n'];e['background_target_max']=e['background_target_n']
                all_classes=sorted(set(mapping.get(w,'unknown') for w in pool_workers))
                for arm,members in teams.items():
                    key=team_key(pid,members);e[arm+'_team_key']=key;e[arm+'_members']='|'.join(members)
                    e[arm+'_class_vector']='|'.join(f'{c}:{sum(mapping.get(w,"unknown")==c for w in members)}' for c in all_classes)
                    requests[key]=dict(pool_id=pid,worker_ids=members,team_key=key)
                assert e['A_team_key']==parent['A_team_key'] and e['A_class_vector']==e['B_class_vector']
                events.append(e)
                links.append({k:e[k] for k in ['event_id','anchor_id','pool_id','method','phase','paired_m7_event_id',
                    'paired_m7_ledger','Z_omitted_worker','x_retained_in_D','y_removed_from_B','A_team_key','B_team_key',
                    'C_team_key','A7_team_key','B7_team_key','C7_team_key','actual_m_C7_C6','actual_m_B7_B6']})
            capacity.append(dict(anchor_record,n=10,m=6,feasible=True,events_generated=7,
                                 enumeration_scope='all_7_choose_6_from_this_original_Z7_panel_only',
                                 exact_target_panel_combinations=7,other_pool_target_sets_not_enumerated=True))
    ev=pd.DataFrame(events)
    assert not ev.event_id.duplicated().any()
    assert ev.groupby('anchor_id').Z_omitted_worker.nunique().eq(7).all()
    csv(out/'EVENTS_EXACT.csv.gz',ev);save(out/'REQUESTS.json.gz',list(requests.values()))
    csv(out/'ANCHORS.csv.gz',pd.DataFrame(anchors));csv(out/'PAIR_LINKS.csv.gz',pd.DataFrame(links))
    csv(out/'CAPACITY_AND_ATTEMPTS.csv.gz',pd.DataFrame(capacity));csv(out/'FROZEN_LABELS.csv.gz',lab)
    csv(out/'FOLD_ROLE_CENTERS.csv.gz',cent)
    csv(out/'IMAGE_PHASE_ASSIGNMENT.csv',pd.concat(phases,ignore_index=True).drop_duplicates('pool_id',keep='last'))
    receipt=dict(stage='target_omissions',underlying_data='v2',seed=SEED,methods=METHODS,
        role='source largest class by fold members -> target highest historical difficult-image turns; source not itself highest',
        source_registered_m7_events=len(original),anchors=len(anchors),events=len(events),
        unique_required_endpoints=len(requests),images=ev.pool_id.nunique(),buildings=ev.building.nunique(),
        phases=ev.phase.value_counts().to_dict(),
        enumeration='Each original Z7 panel: all 7 leave-one-out Z6 sets. Not all target class members or all pool teams.',
        fixed_A='A6=A7 exactly; X-retained person moves from X7 into common D6; Y7 omission fixed per anchor.',
        target_comparisons='C7-C6 and B7-B6 are one actual member change each; net is their difference. ABC at m6 remains strict matched replacement.',
        selection='Fixed hash of registered event identity only. Prefer distinct XYZ and background for the second anchor. No effects, failures, or endpoints read for selection.',
        fusion_status='Registered only; parent runner computes/reuses endpoints.',
        validation=dict(all_ABC_disjoint=True,all_actual_m6=True,all_A_equals_parent_A=True,all_seven_omissions_present=True))
    save(out/'DESIGN.json',receipt)
    (out/'README.md').write_text(f'''# 固定原队的7人目标块留一研究登记

使用真实v2、既有楼外标签、screen与confirm登记的n10/m7严格ABC。只从最大人数历史类→困难转折最高历史类选锚点，不读取效果选锚点。

实际登记：{len(anchors)}个锚点，{len(events)}个m6事件，{ev.pool_id.nunique()}图、{ev.building.nunique()}楼，去重需要{len(requests)}个端点（包括已登记m7端点以支持配对差）。这里只登记，尚未声称完成融合。

每锚点把X7的一人留到共同D，固定A不变；Y7固定删一人；原Z7完整枚举7个留一Z6。三队n=10、实际m=6，D/X/Y/Z仍两两不交叠。原目标七人面板内7选6已经完整登记；全池若有其它目标类成员，它们明确列在ANCHORS中，此设计不称全类穷举。

核心文件：EVENTS_EXACT.csv.gz、REQUESTS.json.gz、ANCHORS.csv.gz、PAIR_LINKS.csv.gz、CAPACITY_AND_ATTEMPTS.csv.gz、FROZEN_LABELS.csv.gz、FOLD_ROLE_CENTERS.csv.gz。PAIR_LINKS定位原m7事件、原B7/C7和遗漏者。

评价应同时看C7−C6、B7−B6及两者净差，不能把净优势变化直接称C队升质。C7与C6、B7与B6各只换1个实际成员；m6三队之间各换6人。失败、缺分不补零。此有限面板用于找出效果是否依赖某个成员，以及少换1人是否改变结构、质量、几何与风险。

复现：python exchange_research_20261025/design_advice/register_target_omissions.py
''')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
