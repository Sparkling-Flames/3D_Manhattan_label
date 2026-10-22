"""New exact-background matches from frozen exhaustive 12-choose-6 panels.

All 66 shared-variable backgrounds, outcome-free hash-selected source anchors,
all same-count alternatives, and every member tie in a frozen predicted target
composition. The 924 endpoints are reused, never recomputed.
"""
from __future__ import annotations
from joint_design import *

def predictor(condition,building,labs):
    f=pd.read_csv(V3/'utility/cross_panel_LOBO'/condition/'new_joint/FITS.csv.gz')
    f=f[(f.heldout_building==building)&f.model.eq('class_coarse_interaction')]
    fs={r.outcome:r for r in f.itertuples()};origin=labs.set_index('worker_id').origin.to_dict();label=labs.set_index('worker_id').coarse_label.to_dict()
    cache={}
    def predict(ws):
        co=counts(ws,label);n=len(ws);new=sum(origin[w]=='new' for w in ws)
        key=(n,new,tuple(sorted(co.items())))
        if key in cache:return cache[key]
        base={'source_new':new/n};base.update({'coarse_'+c:k/n for c,k in co.items()})
        def v(name):
            if name.startswith('invn_'):return 20/n*v(name[5:])
            if name.startswith('product__'):
                _,a,b=name.split('__');return base.get(a,0.)*base.get(b,0.)
            return base.get(name,0.)
        vals={y:float(sum(v(name)*coef for name,coef in zip(row.predictors.split('|'),json.loads(row.coefficient_json)))) for y,row in fs.items()}
        cache[key]=vals;return vals
    return predict

def structural_options(V,lm):
    """Every feasible source anchor per shared background; no endpoint data."""
    outputs=[]
    for S in itertools.combinations(V,2):
        rest=sorted(set(V)-set(S));eligible=[];totalabc=0;allabc=0;sourceanchors=0
        for X in itertools.combinations(rest,4):
            outside=sorted(set(rest)-set(X));xco=counts(X,lm);yy=[];zz=[];allz=0
            for alt in itertools.combinations(outside,4):
                aco=counts(alt,lm);turn=sum(abs(aco[c]-xco[c]) for c in set(aco)|set(xco))//2
                if turn==0:yy.append(alt)
                else:
                    allz+=1
                    if turn==2:zz.append(alt)
            if yy:
                sourceanchors+=1;allabc+=len(yy)*allz
                if zz:
                    totalabc+=len(yy)*len(zz);eligible.append((X,yy,zz))
        outputs.append((S,eligible,sourceanchors,totalabc,allabc))
    return outputs

def run():
    panels,labs,_=inputs();lookup={(c,b):g for (c,b),g in labs.groupby(['condition','heldout_building'])};opportunities=[];events=[];structures={};predictors={}
    old_triples=set();old_pairs=set()
    for name in ['PANEL_MATCHED_EVENTS.csv.gz','LARGE_BLOCK_EVENTS.csv.gz','PURE_BLOCK_MATCHED_EVENTS.csv.gz']:
        p=COMP/'matched'/name
        if not p.exists():continue
        d=pd.read_csv(p,usecols=['team_A','team_B','team_C'])
        old_triples.update(tuple(sorted(t)) for t in d.itertuples(index=False,name=None))
        old_pairs.update(tuple(sorted((a,b))) for a,b,c in d.itertuples(index=False,name=None))
        old_pairs.update(tuple(sorted((a,c))) for a,b,c in d.itertuples(index=False,name=None))
    for j,panel in enumerate(panels.to_dict('records')):
        key=(panel['condition'],panel['building']);fold=lookup[key];fi=fold.set_index('worker_id');lm=fi.coarse_label.to_dict();fm={f:fi[f].to_dict() for f in FEATURES};F=panel['background_workers'].split('|');V=panel['variable_workers'].split('|');unknown=sorted(set(F+V)-lm.keys());pid=panel['panel_id']
        if unknown:
            opportunities.append(dict(panel_id=pid,pool_id=panel['pool_id'],condition=key[0],building=key[1],n=panel['n'],source_domain=panel['source_domain'],status='unknown_label_in_panel',unknown_workers='|'.join(unknown),background_population=66,backgrounds_registered=0,registered_ABC=0));continue
        vkey=(key,tuple(V));options=structures.get(vkey)
        if options is None:options=structural_options(V,lm);structures[vkey]=options
        if key not in predictors:predictors[key]=predictor(*key,fold)
        predict=predictors[key]
        for S,eligible,sourceanchors,totalabc,allabc in options:
            D=F+list(S);cap=dict(panel_id=pid,pool_id=panel['pool_id'],condition=key[0],building=key[1],n=panel['n'],source_domain=panel['source_domain'],shared_variable_background='|'.join(S),common_background='|'.join(sorted(D)),background_population=66,source_anchor_population=210,source_anchors_with_same_count=sourceanchors,source_anchors_with_r2_count=len(eligible),all_feasible_ABC_r1_or_r2=allabc,all_feasible_ABC_r2=totalabc,status='no_r2_matched_opportunity',registered_ABC=0)
            if not eligible:opportunities.append(cap);continue
            X,yy,zz=min(eligible,key=lambda t:h('cached-source-anchor',pid,S,t[0]));A=D+list(X)
            values=[predict(D+list(z)) for z in zz];scores=[v['B8L2']-10*v['log_total_time'] for v in values];best=max(scores);winners=[z for z,s in zip(zz,scores) if abs(s-best)<=1e-9]
            cap.update(status='registered',selected_X='|'.join(X),same_member_alternatives=len(yy),cross_r2_member_alternatives=len(zz),selected_cross_member_ties=len(winners),registered_ABC=len(yy)*len(winners));opportunities.append(cap)
            for Y,Z in itertools.product(yy,winners):
                e=make_event(panel,A,D+list(Y),D+list(Z),lm,stage='joint_cached_r2',panel_id=pid,source_domain=panel['source_domain'],selected_family=str(fold.selected_family.iloc[0]),coarse_k=int(fold.coarse_k.iloc[0]),design_scope='all_66_backgrounds_hash_anchor_predicted_balanced_target',event_mode='complete_panel_new_matched_background',source_anchor_rule='hash_among_all_r2_feasible',target_rule='frozen_class_coarse_interaction_Q_minus_10logtime',same_member_alternatives=len(yy),selected_cross_member_ties=len(winners))
                e['old_physical_triple']=tuple(sorted((e['team_A'],e['team_B'],e['team_C']))) in old_triples;e['old_AB_pair']=tuple(sorted((e['team_A'],e['team_B']))) in old_pairs;e['old_AC_pair']=tuple(sorted((e['team_A'],e['team_C']))) in old_pairs
                pa,pb,pc=map(predict,[A,D+list(Y),D+list(Z)])
                for tag,outcome in [('Q','B8L2'),('logtime','log_total_time')]:
                    for ab,first,second in [('AB',pa,pb),('AC',pa,pc),('BC',pb,pc)]:e[f'pred_{tag}_{ab}']=second[outcome]-first[outcome]
                e['pred_QT_both_improve_BC']=e['pred_Q_BC']>0 and e['pred_logtime_BC']<0;e['pred_balanced_BC']=e['pred_Q_BC']-10*e['pred_logtime_BC']
                for feature in FEATURES:
                    mm=fm[feature];e['block_history_delta_'+feature]=float(np.mean([mm[w] for w in Z])-np.mean([mm[w] for w in Y]))
                e['training_QT_direction']=('q_up' if e['block_history_delta_q_history']>0 else 'q_down')+'__'+('faster' if e['block_history_delta_t_history']<0 else 'slower')
                events.append(e)
        if j%30==0:
            print('panels',j+1,'events',len(events),flush=True)
    E=pd.DataFrame(events).drop_duplicates('event_id');O=pd.DataFrame(opportunities);write(HERE/'CACHED_EVENTS_REGISTERED.csv.gz',E);write(HERE/'CACHED_OPPORTUNITIES.csv.gz',O)
    keys=set(E.team_A)|set(E.team_B)|set(E.team_C);teams=pd.read_csv(COMP/'DESIGN_TEAMS.csv.gz');T=teams[teams.team_key.isin(keys)];assert set(T.team_key)==keys
    write(HERE/'CACHED_ENDPOINT_REFERENCES.csv.gz',T)
    s=E.groupby(['condition','source_domain','m_AB','composition_turnover_AC']).agg(events=('event_id','size'),physical_triples=('physical_triple_id','nunique'),panels=('panel_id','nunique'),pools=('pool_id','nunique'),buildings=('building','nunique'),backgrounds=('common_background','nunique'),old_triples=('old_physical_triple','sum')).reset_index();write(HERE/'CACHED_REGISTRATION_SUMMARY.csv',s)
    save(HERE/'CACHED_DESIGN_FREEZE.json',dict(seed=SEED,events=len(E),physical_triples=E.physical_triple_id.nunique(),old_physical_triples=int(E.old_physical_triple.sum()),unique_teams=len(T),cached_teams=len(T),new_endpoint_requests=0,all_shared_variable_backgrounds=True,anchors_per_feasible_background=1,same_member_sets_for_selected_anchor='all',cross_member_sets_for_frozen_best_prediction='all_ties',actual_m=4,class_seat_change=2,all_possible_anchors_exhaustive=False,events_sha256=sha(HERE/'CACHED_EVENTS_REGISTERED.csv.gz'),target_endpoint_outcomes_used=False,native_calls=0))
    print(s.to_string(index=False),flush=True)

if __name__=='__main__':run()
