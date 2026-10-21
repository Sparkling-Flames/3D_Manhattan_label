#!/usr/bin/env python3
"""Freeze selections from the complete inner-loss ledger, then export labels.

Capacity failures remain in the loss denominator. This guard was added while
development was running, before any new team outcome was joined to a label.
"""
import json,hashlib
import pandas as pd
import numpy as np
from sklearn.metrics import adjusted_rand_score
import discover_behavior_classes as b
import discover_joint_qt as j

def run(cls,prefix):
    x=b.load();s=cls(x)
    d=pd.read_csv(b.HERE/(prefix+'INNER_BUILDING_CANDIDATE_LOSSES.csv.gz'))
    choices=[];labels=[];cands=[];members=[];stability=[]
    for (cond,held),g in d.groupby(['condition','heldout_building'],sort=True):
        ch,cs=s.choose(cond,held,g.to_dict('records'))
        choices.append(ch);labels.append(s.labels(ch));cands.append(cs)
    labs=pd.concat(labels,ignore_index=True);cs=pd.concat(cands,ignore_index=True)
    b.save(labs[labs.heldout_building.ne('ALL')],prefix+'LABELS_LOBO.csv.gz')
    b.save(labs[labs.heldout_building.eq('ALL')],prefix+'LABELS_ALL_DATA.csv')
    b.save(cs,prefix+'CANDIDATE_SELECTION_ALL.csv')
    b.js(prefix+'SELECTED_MODELS.json',choices)
    for (c,co,fi),g in labs[labs.heldout_building.eq('ALL')].groupby(['condition','coarse_label','fine_label']):
        vals={col:float(g[col].mean()) for col in b.HIST+b.CONTEXT+(['q_history','q_downside','t_history'] if prefix else [])}
        members.append(dict(method=g.method.iloc[0],condition=c,coarse_label=co,fine_label=fi,known=bool(g.known.all()),
            n_members=len(g),members='|'.join(g.worker_id),selected_family=g.selected_family.iloc[0],
            records=int(g.n_records.sum()),member_buildings_min=int(g.n_buildings.min()),member_buildings_max=int(g.n_buildings.max()),
            old_members=int(g.origin.eq('v1').sum()),new_members=int(g.origin.eq('new').sum()),**vals))
    b.save(pd.DataFrame(members),prefix+'CLASS_MEMBERS_AND_FEATURES.csv')
    for c,g in labs.groupby('condition'):
        full=g[g.heldout_building.eq('ALL')]
        for held,z in g[g.heldout_building.ne('ALL')].groupby('heldout_building'):
            a=z.merge(full,on='worker_id',suffixes=('_fold','_full'))
            a=a[a.known_fold & a.known_full]
            stability.append(dict(condition=c,heldout_building=held,workers=len(a),
                coarse_ari=float(adjusted_rand_score(a.coarse_label_fold,a.coarse_label_full)),fine_ari=float(adjusted_rand_score(a.fine_label_fold,a.fine_label_full)),
                fold_family=z.selected_family.iloc[0],fold_coarse_k=int(z.coarse_k.iloc[0]),fold_fine_k=int(z.fine_k.iloc[0]),
                condition_has_target=bool(((x.condition==c)&(x.building_id==held)).any())))
    b.save(pd.DataFrame(stability),prefix+'OUTER_LABEL_STABILITY.csv')
    # Detailed member-level matching uses co-membership instead of comparing
    # arbitrary numeric class IDs when family/K changes between outer folds.
    stability_people=[]
    for c,g in labs.groupby('condition'):
        full=g[(g.heldout_building=='ALL')&g.known].set_index('worker_id')
        for w in full.index:
            for tier in ['coarse_label','fine_label']:
                scores=[]
                for held,z in g[(g.heldout_building!='ALL')&g.known].groupby('heldout_building'):
                    zz=z.set_index('worker_id')
                    if w not in zz.index or held not in s.bb[c]:continue
                    common=full.index.intersection(zz.index).difference([w])
                    aa=full.loc[common,tier].eq(full.loc[w,tier]);bb=zz.loc[common,tier].eq(zz.loc[w,tier])
                    union=(aa|bb).sum();scores.append(float((aa&bb).sum()/union) if union else 1.)
                stability_people.append(dict(condition=c,worker_id=w,tier=tier,folds=len(scores),co_member_jaccard=np.mean(scores) if scores else np.nan))
    b.save(pd.DataFrame(stability_people),prefix+'MEMBER_COASSIGNMENT_STABILITY.csv')
    print(prefix or 'GEOMETRY',pd.DataFrame(members)[['condition','fine_label','n_members','selected_family']].to_string(index=False),flush=True)
    return labs

def main():
    a=run(b.Study,'');z=run(j.Joint,'JOINT_')
    combined=pd.concat([a,z],ignore_index=True)
    b.save(combined[combined.heldout_building.ne('ALL')],'ALL_METHOD_LABELS_LOBO.csv.gz')
    b.save(combined[combined.heldout_building.eq('ALL')],'ALL_METHOD_LABELS_ALL_DATA.csv')
    b.js('LABEL_FREEZE.json',dict(stage='frozen_before_joining_new_fusion_endpoints',
        input_main='324dba44d0a82d9d64a62965f2e549ee05165417',
        selection_loss_denominator='all inner validation buildings, including sub-capacity cuts; capacity is only an admissibility gate',
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [b.HERE/'LABELS_LOBO.csv.gz',b.HERE/'LABELS_ALL_DATA.csv',b.HERE/'JOINT_LABELS_LOBO.csv.gz',b.HERE/'JOINT_LABELS_ALL_DATA.csv']},
        observations='Known labels do not grant formal team eligibility. ALL labels describe the final working taxonomy; each target uses its own inner-selected outside-building map.'))

if __name__=='__main__':main()
