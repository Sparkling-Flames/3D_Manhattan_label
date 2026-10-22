"""Exact shared A/background/n/m comparison of three frozen taxonomy methods."""
from __future__ import annotations
from joint_design import *
from register_cached_matches import structural_options
METHODS=['V3_JOINT_QT','XCOND_GEOM_QT','XCOND_PAIRED']
CROSS=HERE.parent/'cross_condition_taxonomy'

def run(condition):
    panels,old,_=inputs();panels=panels[panels.condition.eq(condition)]
    cross=pd.read_csv(CROSS/'CROSS_LABELS_LOBO.csv.gz');cross=cross[cross.known&cross.method.isin(METHODS)&cross.condition.eq(condition)].copy();prefix='m_' if condition=='manual' else 's_'
    for feature in FEATURES:cross[feature]=cross[prefix+feature]
    old=old[old.condition.eq(condition)].copy();old['selection_status']='selected'
    label=pd.concat([old,cross],ignore_index=True);lookup={(m,b):g for (m,b),g in label.groupby(['method','heldout_building'])}
    structures={};events=[];opps=[];panelcaps=[]
    for pi,pa in enumerate(panels.to_dict('records')):
        F=pa['background_workers'].split('|');V=pa['variable_workers'].split('|');Dws=set(F+V);building=pa['building'];pid=pa['panel_id'];maps={};folds={};centers={};opts={}
        common=True
        for method in METHODS:
            fold=lookup.get((method,building),pd.DataFrame());lm=fold.set_index('worker_id').coarse_label.to_dict() if len(fold) else {};unknown=sorted(Dws-lm.keys())
            panelcaps.append(dict(panel_id=pid,pool_id=pa['pool_id'],condition=condition,building=building,method_id=method,source_domain=pa['source_domain'],n=pa['n'],all_panel_labels_known=not unknown,unknown_workers='|'.join(unknown)))
            common&=not unknown;folds[method]=fold;maps[method]=lm
            if len(fold):centers[method]=fold.groupby('coarse_label')[FEATURES].mean()
        if not common:continue
        for method in METHODS:
            vk=(method,building,tuple(V))
            if vk not in structures:structures[vk]=structural_options(V,maps[method])
            opts[method]={S:(eligible,sourceanchors,totalabc,allabc) for S,eligible,sourceanchors,totalabc,allabc in structures[vk]}
        for S in itertools.combinations(V,2):
            available={m:{r[0]:r for r in opts[m][S][0]} for m in METHODS};Xcommon=set.intersection(*(set(v) for v in available.values()));D=F+list(S)
            for method in METHODS:
                el,sa,ta,aa=opts[method][S];opps.append(dict(panel_id=pid,pool_id=pa['pool_id'],condition=condition,building=building,source_domain=pa['source_domain'],n=pa['n'],method_id=method,shared_variable_background='|'.join(S),source_anchor_population=210,own_feasible_source_anchors=len(el),own_all_feasible_ABC_r2=ta,common_source_anchors=len(Xcommon),registered=bool(Xcommon)))
            if not Xcommon:continue
            X=min(Xcommon,key=lambda x:h('cross-common-source',pid,S,x));A=D+list(X)
            anchor=h('cross-shared-anchor',pid,S,X)[:24]
            for method in METHODS:
                _,yy,zz=available[method][X];lm=maps[method];cm=centers[method];fold=folds[method]
                score={c:float(row.q_history-10*row.t_history) for c,row in cm.iterrows()}
                values=[sum(score[lm[w]] for w in z) for z in zz];best=max(values);winners=[z for z,s in zip(zz,values) if abs(s-best)<=1e-9]
                for Y,Z in itertools.product(yy,winners):
                    ev=make_event(pa,A,D+list(Y),D+list(Z),lm,stage='joint_cross_common',comparison_method=method,panel_id=pid,source_domain=pa['source_domain'],common_anchor_id=anchor,selected_family=str(fold.selected_family.iloc[0]),coarse_k=int(fold.coarse_k.iloc[0]),selection_status=str(fold.selection_status.iloc[0]),design_scope='three_methods_identical_A_D_n_m',event_mode='complete_panel_shared_anchor',source_anchor_rule='hash_intersection_of_three_method_feasible_anchors',target_rule='class_center_q_minus_10logtime',same_member_alternatives=len(yy),cross_r2_member_alternatives=len(zz),selected_cross_member_ties=len(winners),input_conditions='manual' if method=='V3_JOINT_QT' and condition=='manual' else ('semi' if method=='V3_JOINT_QT' else 'manual|semi'))
                    ev['method_id']=method
                    for feature in FEATURES:
                        ev['class_center_delta_'+feature]=float(np.mean([cm.loc[lm[w],feature] for w in Z])-np.mean([cm.loc[lm[w],feature] for w in Y]))
                    ev['training_QT_direction']=('q_up' if ev['class_center_delta_q_history']>0 else 'q_down')+'__'+('faster' if ev['class_center_delta_t_history']<0 else 'slower');events.append(ev)
        if pi%20==0:print(condition,'panels',pi+1,'events',len(events),flush=True)
    E=pd.DataFrame(events);write(HERE/f'CROSS_{condition.upper()}_EVENTS_REGISTERED.csv.gz',E);write(HERE/f'CROSS_{condition.upper()}_OPPORTUNITIES.csv.gz',pd.DataFrame(opps));write(HERE/f'CROSS_{condition.upper()}_PANEL_LABEL_SUPPORT.csv',pd.DataFrame(panelcaps))
    summary=E.groupby(['condition','source_domain','method_id']).agg(events=('event_id','size'),physical_triples=('physical_triple_id','nunique'),common_anchors=('common_anchor_id','nunique'),panels=('panel_id','nunique'),pools=('pool_id','nunique'),buildings=('building','nunique')).reset_index();write(HERE/f'CROSS_{condition.upper()}_REGISTRATION_SUMMARY.csv',summary)
    save(HERE/f'CROSS_{condition.upper()}_DESIGN_FREEZE.json',dict(condition=condition,methods=METHODS,events=len(E),physical_triples=E.physical_triple_id.nunique(),common_anchors=E.common_anchor_id.nunique(),event_sha256=sha(HERE/f'CROSS_{condition.upper()}_EVENTS_REGISTERED.csv.gz'),cross_label_sha256=sha(CROSS/'CROSS_LABELS_LOBO.csv.gz'),original_label_sha256=sha(TAX/'JOINT_LABELS_LOBO.csv.gz'),same_A_background_n_m=True,all_backgrounds_checked=True,one_hash_source_anchor_per_feasible_background=True,all_source_anchors_exhaustive=False,all_same_member_sets_and_selected_target_ties=True,new_fusion_calls=0,target_endpoint_outcomes_used=False))
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('condition',choices=['manual','semi']);run(ap.parse_args().condition)
