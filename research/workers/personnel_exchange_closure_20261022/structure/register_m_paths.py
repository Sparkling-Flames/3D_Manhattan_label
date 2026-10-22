#!/usr/bin/env python3
"""Small registered supplement: fixed original A, nested replacement scale m.

Anchors use the largest already registered n20 block and the first two deep
backgrounds, first source pair and target block. Target results are not read or
used to choose anchors. For k<=m, D_k adds the unremoved X members to D_m, so A is IDENTICAL for the
whole path while Y_k/Z_k are fixed nested prefixes. Every k remains an exact
same-D,n,k ABC contrast. New endpoints only are requested centrally.
"""
import json
import pandas as pd
from register_structure import HERE, h, gs, event, write, save, sha

def main():
    source=HERE/'EVENTS_REGISTERED.csv.gz'
    E=pd.read_csv(source,keep_default_na=False)
    M=E[E.study_group.eq('main_n20')&E.deep_member_panel.eq(True)&E.source_pair_index.eq(0)&E.target_block_index.eq(0)]
    labs=pd.read_csv(HERE/'CLASS_LABELS_REUSED.csv.gz',keep_default_na=False)
    labs=labs[labs.known.astype(str).str.lower().isin(['true','1'])]
    labels={b:dict(zip(g.worker_id,g.coarse_label)) for b,g in labs.groupby('heldout_building')}
    existing=pd.read_csv(HERE/'ENDPOINT_REQUESTS.csv.gz',keep_default_na=False);known=set(existing.team_key)
    pools=gs.pool_lookup();rows=[];paths=[];teams={}
    for key,g in M.groupby(['pool_id','source_role','target_role'],sort=True):
        maxm=int(g.m.max())
        if maxm<=4:continue
        anchors=g[g.m.eq(maxm)].sort_values('background_index').drop_duplicates('panel_id').head(2)
        for a in anchors.to_dict('records'):
            pid=a['pool_id'];meta=pools[pid]['meta'];lab=labels[a['building']]
            path=h('fixed-A-m-path',a['event_id'])[:22]
            X=sorted(a['outgoing_block_X'].split('|'),key=lambda w:h('m-prefix-X',path,w))
            Y=sorted(a['same_count_block_Y'].split('|'),key=lambda w:h('m-prefix-Y',path,w))
            Z=sorted(a['changed_count_block_Z'].split('|'),key=lambda w:h('m-prefix-Z',path,w))
            D=a['common_background'].split('|');A=tuple(sorted(D+X))
            assert gs.team_key(pid,A)==a['team_A']
            paths.append(dict(linked_m_path_id=path,pool_id=pid,image=a['image'],building=a['building'],difficulty=a['difficulty'],
                source_role=a['source_role'],target_role=a['target_role'],n=20,m_values='|'.join(map(str,range(4,maxm+1))),
                maximum_m=maxm,source_anchor_event=a['event_id'],fixed_A=a['A_member_workers'],fixed_A_team_key=a['team_A'],
                D_max='|'.join(D),X_order='|'.join(X),Y_order='|'.join(Y),Z_order='|'.join(Z)))
            for k in range(4,maxm+1):
                DD=tuple(sorted(D+X[k:]));XX,YY,ZZ=map(tuple,(X[:k],Y[:k],Z[:k]))
                panel=h('m-path-panel',path,k)[:22]
                ev=event(meta,'V3_BEHAVIOR','coarse',lab,lab,DD+XX,DD+YY,DD+ZZ,panel_id=panel,source_domain='all_formal',
                    anchor_id=path,design_scope='fixed_A_nested_D_and_XYZ_replacement_scale',event_mode='linked_m_pure_class_block_ABC')
                assert ev['team_A']==a['team_A'];assert ev['m_AB']==ev['m_AC']==ev['m_BC']==ev['composition_turnover_AC']==k
                ev.update(cell_id=h('m-path-cell',path,k)[:22],source_class=a['source_class'],target_class=a['target_class'],
                    source_role=a['source_role'],target_role=a['target_role'],source_semantics=a['source_semantics'],target_semantics=a['target_semantics'],
                    source_pair_index=0,target_block_index=0,background_index=a['background_index'],
                    background_stratum='|'.join(str(sum(lab[w]==c for w in DD)) for c in [a['source_class'],a['target_class']])+'|'+str(sum(lab[w] not in [a['source_class'],a['target_class']] for w in DD)),
                    deep_member_panel=False,study_group='linked_m',selection_partition='fixed_A_replacement_scale_check',linked_n_path_id='',m=k,
                    linked_m_path_id=path,linked_m_reference_event=a['event_id'],linked_m_max=maxm)
                rows.append(ev)
                for arm in 'ABC':
                    tk=ev['team_'+arm]
                    if tk not in teams:
                        teams[tk]=dict(team_key=tk,**{f:meta[f] for f in ['pool_id','image','building','condition','difficulty','layer']},
                            n=20,member_workers=ev[arm+'_member_workers'],pool_input_sha256=gs.digest(pools[pid]),
                            first_study_group='linked_m',first_cell_id=ev['cell_id'],registered_main_endpoint=tk in known)
    outputs=[]
    outputs.append(write(HERE/'M_PATH_EVENTS_REGISTERED.csv.gz',rows))
    outputs.append(write(HERE/'M_PATHS.csv.gz',paths))
    outputs.append(write(HERE/'M_PATH_ALL_ENDPOINTS.csv.gz',list(teams.values())))
    new=[r for r in teams.values() if not r['registered_main_endpoint']]
    outputs.append(write(HERE/'M_PATH_NEW_ENDPOINT_REQUESTS.csv.gz',new))
    combined=pd.concat([E,pd.DataFrame(rows)],ignore_index=True);assert not combined.event_id.duplicated().any()
    outputs.append(write(HERE/'ALL_EVENTS_REGISTERED.csv.gz',combined))
    allt=pd.concat([existing,pd.DataFrame(new)],ignore_index=True);assert not allt.team_key.duplicated().any()
    outputs.append(write(HERE/'ALL_ENDPOINT_REQUESTS.csv.gz',allt))
    R=pd.DataFrame(rows)
    save(HERE/'M_PATH_FREEZE.json',dict(status='frozen_before_supplement_endpoint_evaluation',
        design='A fixed exactly; X/Y/Z frozen nested prefixes; D_k=D_max+remaining_X. Every k has disjoint exact ABC blocks.',
        anchor_rule='Every main n20 image/direction with max m>4; first two pre-registered deep D, source pair 0, target block 0; no target-outcome lookup.',
        internal_validation='Supplement planned during the present research; underlying v2 and some anchor outcomes have previously been explored. Not a new external blind test.',
        paths=len(paths),events=len(rows),unique_supplement_endpoints=len(teams),already_registered_main=sum(r['registered_main_endpoint'] for r in teams.values()),
        additional_unique_endpoint_requests=len(new),combined_unique_endpoints=len(allt),combined_events=len(combined),
        images=R.image.nunique(),buildings=R.building.nunique(),n=20,m_values=sorted(map(int,R.m.unique())),
        anchor_registration_sha256=sha(source),label_sha256=sha(HERE/'CLASS_LABELS_REUSED.csv.gz'),script_sha256=sha(__file__),outputs=outputs))
    print(json.dumps(dict(paths=len(paths),events=len(rows),additional_unique_endpoints=len(new),images=R.image.nunique(),buildings=R.building.nunique()),ensure_ascii=False))

if __name__=='__main__':main()
