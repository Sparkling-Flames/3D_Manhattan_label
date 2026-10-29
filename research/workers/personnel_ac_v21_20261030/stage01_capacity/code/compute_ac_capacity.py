"""Score-blind capacity census for direct AC and per-pool whole-class studies.

Only frozen labels, qualified worker identities and pool metadata are read into
the design calculations. No target-image quality, time or geometry determines a
condition. Every number describes capacity, never execution or an effect.
"""
from pathlib import Path
from itertools import permutations, combinations
from collections import Counter
import csv, gzip, hashlib, json, math
import pandas as pd

OUT=Path(__file__).resolve().parents[1]
WORK=OUT.parents[1]
REPO=WORK/'repo'
CUR=OUT.parent/'stage00_intake/current_source'
COMMIT='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff'
METHODS=['TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K2','V21_DSTRUCT_RAW3_K3',
         'OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2','OPPSTRUCT_K3']
KEY_M=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]
KEY_N=[3,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,35]

def dump(obj,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def save(rows,name):
    frame=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    destination=OUT/name
    temporary=destination.with_name(destination.name+'.partial')
    frame.to_csv(temporary,index=False,encoding='utf-8-sig',compression='gzip' if name.endswith('.gz') else None)
    temporary.replace(destination)
    return frame

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encode(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def block_key(pool,workers):return hashlib.sha256((pool+'\n'+'|'.join(sorted(workers))).encode()).hexdigest()[:24]
def choose(n,k):return math.comb(n,k) if 0<=k<=n else 0
def known(row):return str(row['known']).lower() in ['true','1','1.0'] and pd.notna(row['class_id']) and str(row['class_id']) not in ['', 'unknown','nan','None']

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    paths=[REPO/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
           REPO/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
    pools=[];input_receipts=[]
    for path in paths:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        for p in data['images']:
            # Explicit projection prevents accidental score-driven selection.
            meta=p['meta'];ws=sorted(r['worker_id'] for r in p['records'])
            assert len(ws)==len(set(ws))
            pools.append({'pool_id':p['pool_id'],'meta':meta,
                          'members':[{'worker_id':r['worker_id'],'object_id':r.get('object_id',r['id'])} for r in p['records']],
                          'workers':ws,'scope':'other_admitted' if meta.get('analysis_scope')=='other_admitted_target' else 'primary'})
        input_receipts.append({'path':str(path.relative_to(WORK)),'sha256':sha(path),'pools':len(data['images'])})
    assert len({p['pool_id'] for p in pools})==len(pools)==294
    frozen=CUR/'research/data/releases/v2.1/final_classification_downstream/sources/stage03_completed_ABC/FROZEN_LABELS_ALL_LOBO.csv.gz'
    used=CUR/'research/data/releases/v2.1/final_classification_downstream/USED_FINAL_LOBO_LABELS.csv.gz'
    f=pd.read_csv(frozen,low_memory=False);u=pd.read_csv(used,low_memory=False)
    ff=f[f.heldout_building.ne('ALL')];uu=u[u.heldout_building.ne('ALL')]
    overlap=ff.merge(uu,on=['method','heldout_building','worker_id'],suffixes=('_f','_u'))
    assert len(overlap)==1364
    assert overlap.class_id_f.fillna('unknown').eq(overlap.class_id_u.fillna('unknown')).all()
    assert overlap.known_f.eq(overlap.known_u).all()
    labels=pd.concat([ff,uu[~uu.method.isin(ff.method.unique())]],ignore_index=True)
    labels=labels[labels.method.isin(METHODS)]
    assert not labels.duplicated(['method','heldout_building','worker_id']).any()
    save(labels,'FROZEN_LABELS_USED_ALL_LOBO.csv.gz')
    lookups={};universes={}
    for (method,building),g in labels.groupby(['method','heldout_building']):
        lookup={r['worker_id']:str(r['class_id']) for r in g.to_dict('records') if known(r)}
        lookups[(method,building)]=lookup;universes[(method,building)]=sorted(set(lookup.values()))
    input_receipts.extend({'path':str(p.relative_to(WORK)),'sha256':sha(p)} for p in [frozen,used])
    dump({'commit':COMMIT,'pools':pools,'input_fields_used':['pool_id','scope','meta','worker_id','object_id'],
          'quality_time_and_geometry_not_used_for_capacity':True},OUT/'SCORE_BLIND_POOL_INPUTS.json')
    inventory=[];pool_methods=[];class_rows=[];directions=[];whole_equal=[];whole_unequal=[];alliances=[];alliance_edges=[];feasible=[]
    for p in pools:
        meta=p['meta'];ws=p['workers'];N=len(ws)
        base={k:meta.get(k) for k in ['image','image_id','building','condition','layer','difficulty','difficulty_aligned','reference_id','reference_version']}
        base.update(pool_id=p['pool_id'],scope=p['scope'],pool_n=N)
        ordinary=meta['condition']=='manual' and meta['layer']=='ordinary_manual'
        inventory.append(dict(base,workers='|'.join(ws),record_ids='|'.join(str(x['object_id']) for x in sorted(p['members'],key=lambda x:x['worker_id'])),capacity_domain='ordinary_manual' if ordinary else 'inventory_only_not_manual_classification'))
        if not ordinary:continue
        for method in METHODS:
            lookup=lookups.get((method,meta['building']),{});classes=universes.get((method,meta['building']),[])
            members={c:sorted(w for w in ws if lookup.get(w)==c) for c in classes}
            unknown=sorted(w for w in ws if w not in lookup)
            counts={c:len(v) for c,v in members.items()};known_n=N-len(unknown)
            common=dict(base,method=method,heldout_building=meta['building'],known_n=known_n,unknown_n=len(unknown))
            class_max=max([min(counts[s],counts[t]) for s,t in permutations(classes,2)] or [0])
            pool_methods.append(dict(common,class_members_json=encode(members),unknown_workers='|'.join(unknown),
                                     class_counts_json=encode(counts),n_classes_present=sum(n>0 for n in counts.values()),
                                     max_m_AC=min(class_max,N//2),max_n_at_m7=N-7 if class_max>=7 and N>=14 else None,
                                     max_n_at_m8=N-8 if class_max>=8 and N>=16 else None,
                                     max_n_at_m9=N-9 if class_max>=9 and N>=18 else None,
                                     max_n_at_m10=N-10 if class_max>=10 and N>=20 else None,
                                     max_n_at_m12=N-12 if class_max>=12 and N>=24 else None))
            for cl in classes:
                class_rows.append(dict(common,class_id=cl,class_n=counts[cl],class_workers='|'.join(members[cl]),
                                       class_member_object_ids='|'.join(str(x['object_id']) for x in p['members'] if x['worker_id'] in members[cl])))
            for source,target in permutations(classes,2):
                s=counts[source];t=counts[target];maxm=min(s,t,N//2)
                drow=dict(common,source_class=source,target_class=target,source_n=s,target_n=t,
                          source_workers='|'.join(members[source]),target_workers='|'.join(members[target]),
                          unknown_workers='|'.join(unknown),max_m=maxm,undirected_class_pair='|'.join(sorted([source,target])),
                          source_whole_equal_possible=s>0 and t>=s,target_whole_equal_possible=t>0 and s>=t)
                directions.append(drow)
                if not maxm:continue
                for m in range(1,maxm+1):
                    xz=choose(s,m)*choose(t,m)
                    for n in range(max(3,m),N-m+1):
                        d=n-m;dc=choose(N-2*m,d)
                        feasible.append(dict(pool_id=p['pool_id'],image=meta['image'],building=meta['building'],scope=p['scope'],method=method,
                                             source_class=source,target_class=target,source_n=s,target_n=t,pool_n=N,known_n=known_n,unknown_n=len(unknown),
                                             n=n,m=m,d=d,replacement_fraction=m/n,mv50_threshold=math.ceil(n/2),block_can_reach_MV50=m>=math.ceil(n/2),
                                             at_pool_frontier=n==N-m,whole_source=m==s,whole_target=m==t,
                                             possible_XZ_blocks=str(xz),possible_D_per_XZ=str(dc),possible_directed_AC_events=str(xz*dc),
                                             execution_status='capacity_only_not_yet_designed'))
                m=min(s,t)
                for n in range(max(3,m),N-m+1):
                    d=n-m
                    whole_equal.append(dict(drow,n=n,m=m,d=d,whole_source=m==s,whole_target=m==t,
                                             whole_mode='both_whole_equal' if s==t else ('whole_source_out' if s<t else 'whole_target_in'),
                                             possible_XZ_blocks=str(choose(s,m)*choose(t,m)),possible_D_per_XZ=str(choose(N-2*m,d)),
                                             possible_directed_AC_events=str(choose(s,m)*choose(t,m)*choose(N-2*m,d)),
                                             at_pool_frontier=n==N-m,execution_status='capacity_only_not_yet_designed'))
                if s!=t:
                    other=N-s-t
                    for d in range(max(0,3-s,3-t),other+1):
                        whole_unequal.append(dict(drow,D_n=d,n_A=d+s,n_C=d+t,X_n=s,Z_n=t,delta_n=t-s,
                                                 D_candidate_n=other,D_candidates='|'.join(w for w in ws if lookup.get(w) not in [source,target]),
                                                 possible_D_blocks=str(choose(other,d)),equal_match_m=min(s,t),equal_match_n=d+min(s,t),
                                                 all_other_members_in_D=d==other,execution_status='capacity_only_not_yet_designed'))
            present=[c for c in classes if counts[c]>0]
            for with_unknown in ([False,True] if unknown else [False]):
                team_rows=[]
                for size in range(1,len(present)+1):
                    for subset in combinations(present,size):
                        team=sorted(w for cl in subset for w in members[cl])+ (unknown if with_unknown else [])
                        team=sorted(team);clset='|'.join(subset);teamkey=block_key(p['pool_id'],team)
                        row=dict(common,alliance_classes=clset,alliance_class_count=size,unknown_background_included=with_unknown,
                                 n=len(team),members='|'.join(team),member_identity_key=teamkey,
                                 n_at_least3=len(team)>=3,all_available_labelled_classes=size==len(present),
                                 execution_status='capacity_only_not_yet_designed')
                        alliances.append(row);team_rows.append(row)
                for a,c in combinations(team_rows,2):
                    ca=set(a['alliance_classes'].split('|'));cc=set(c['alliance_classes'].split('|'))
                    sa=ca-cc;sc=cc-ca;dc=ca&cc
                    typ='class_addition' if not sa else 'class_removal' if not sc else ('whole_class_equal_swap' if a['n']==c['n'] else 'whole_class_unequal_swap')
                    alliance_edges.append(dict(common,A_alliance=a['alliance_classes'],C_alliance=c['alliance_classes'],
                                              unknown_background_included=with_unknown,A_identity_key=a['member_identity_key'],C_identity_key=c['member_identity_key'],
                                              n_A=a['n'],n_C=c['n'],D_n=sum(counts[k] for k in dc)+(len(unknown) if with_unknown else 0),
                                              X_n=sum(counts[k] for k in sa),Z_n=sum(counts[k] for k in sc),
                                              D_classes='|'.join(sorted(dc)),X_classes='|'.join(sorted(sa)),Z_classes='|'.join(sorted(sc)),
                                              comparison_type=typ,both_n_at_least3=a['n']>=3 and c['n']>=3,
                                              canonical_once_no_reverse_duplicate=True))
    inv=save(inventory,'POOL_INVENTORY_ALL_DOMAINS.csv')
    pm=save(pool_methods,'POOL_METHOD_CAPACITY.csv.gz')
    cr=save(class_rows,'POOL_CLASS_MEMBERS.csv.gz')
    di=save(directions,'DIRECTED_CLASS_CAPACITY.csv.gz')
    ff=save(feasible,'ALL_LEGAL_AC_N_M_DIRECTION_CAPACITY.csv.gz')
    we=save(whole_equal,'WHOLE_CLASS_EQUAL_CAPACITY.csv.gz')
    wu=save(whole_unequal,'WHOLE_CLASS_UNEQUAL_CAPACITY.csv.gz')
    al=save(alliances,'ALL_CLASS_ALLIANCE_TEAMS.csv.gz')
    ae=save(alliance_edges,'ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz')
    assert pm.groupby('method').size().eq(236).all()
    assert pm[pm.scope.eq('primary')].groupby('method').size().eq(206).all()
    assert pm[pm.scope.eq('other_admitted')].groupby('method').size().eq(30).all()
    summary=[];frontiers=[];funnel=[]
    for (method,scope),g in pm.groupby(['method','scope']):
        for m in KEY_M:
            fits=g.max_m_AC.ge(m)&g.pool_n.ge(max(3,m)+m)
            vals=g.loc[fits,'pool_n']-m
            frontiers.append(dict(method=method,scope=scope,m=m,legal_pools=len(g),class_feasible_pools=int(fits.sum()),
                                  images=g.loc[fits,'image'].nunique(),buildings=g.loc[fits,'building'].nunique(),
                                  frontier_n_min=int(vals.min()) if len(vals) else None,frontier_n_max=int(vals.max()) if len(vals) else None))
            for n in KEY_N:
                total=(n>=m)&g.pool_n.ge(n+m);hist=total&g.known_n.ge(2*m);fits=hist&g.max_m_AC.ge(m)
                row=dict(method=method,scope=scope,n=n,m=m,legal_pools=len(g),legal_images=g.image.nunique(),legal_buildings=g.building.nunique(),
                         total_n_sufficient_pools=int(total.sum()),historical_2m_sufficient_pools=int(hist.sum()),class_feasible_pools=int(fits.sum()),
                         class_feasible_images=g.loc[fits,'image'].nunique(),class_feasible_buildings=g.loc[fits,'building'].nunique(),
                         n_less_than_m=n<m,total_n_insufficient_pools=int((~total).sum()),history_insufficient_after_total_pools=int((total&~hist).sum()),
                         class_distribution_insufficient_after_history_pools=int((hist&~fits).sum()),
                         designed_pools=0,executed_pools=0,not_yet_designed_feasible_pools=int(fits.sum()))
                summary.append(row)
                if m in [7,8,9,10,12] and n in [12,14,16,18,20,22,24,26,28,30]:
                    for _,pr in g.iterrows():
                        reason='n_less_than_m' if n<m else 'total_pool_people_insufficient' if pr.pool_n<n+m else 'known_class_history_total_insufficient' if pr.known_n<2*m else 'class_distribution_insufficient' if pr.max_m_AC<m else 'feasible_not_yet_designed'
                        funnel.append(dict(pool_id=pr.pool_id,image=pr.image,building=pr.building,scope=scope,method=method,n=n,m=m,pool_n=pr.pool_n,
                                           known_n=pr.known_n,unknown_n=pr.unknown_n,class_counts_json=pr.class_counts_json,capacity_status=reason))
    ks=save(summary,'KEY_N_M_AC_CAPACITY_FUNNEL.csv')
    save(frontiers,'POOL_FRONTIER_CAPACITY_SUMMARY.csv')
    save(funnel,'KEY_N_M_POOL_FUNNEL.csv.gz')
    # Directly compare the currently published handoff capacity, not effects.
    m10path=CUR/'research/workers/personnel_v21_reselection_20261029/independent_review/reaudit_20261029/M10_CAPACITY_FROM_FROZEN_LABELS.csv'
    m10=pd.read_csv(m10path);old=m10[m10.design.eq('AC')&m10.n.eq(20)&m10.m.eq(10)]
    new=ff[ff.scope.eq('primary')&ff.n.eq(20)&ff.m.eq(10)&ff.method.isin(old.method.unique())]
    oldset=set(old[['method','image','source','target','source_n','target_n','pool_n']].itertuples(index=False,name=None))
    newset=set(new[['method','image','source_class','target_class','source_n','target_n','pool_n']].itertuples(index=False,name=None))
    assert oldset==newset,(len(oldset-newset),len(newset-oldset))
    expected={'TARGET_DSTRUCT_K3':3,'V21_DSTRUCT_RAW3_K3':19,'OPPJOINT_K3':82,'OPPJOINT_K4':107}
    actual=new.groupby('method').image.nunique().to_dict();assert actual==expected
    save(new,'M10_N20_PUBLISHED_CAPACITY_REPRODUCED.csv')
    brief=[]
    for method in METHODS:
        g=ff[ff.method.eq(method)&ff.scope.eq('primary')]
        for m in [7,8,9,10,12]:
            mm=g[g.m.eq(m)]
            brief.append({'method':method,'m':m,'any_n_pools':mm.pool_id.nunique(),'any_n_buildings':mm.building.nunique(),
                          'n20_pools':mm[mm.n.eq(20)].pool_id.nunique(),'n22_pools':mm[mm.n.eq(22)].pool_id.nunique(),
                          'n24_pools':mm[mm.n.eq(24)].pool_id.nunique(),'max_n':int(mm.n.max()) if len(mm) else None})
    save(brief,'MAIN_SCALE_BRIEF.csv')
    design_summary=[]
    for method in METHODS:
        for scope in ['primary','other_admitted']:
            w=we[we.method.eq(method)&we.scope.eq(scope)];v=wu[wu.method.eq(method)&wu.scope.eq(scope)];a=al[al.method.eq(method)&al.scope.eq(scope)]
            design_summary.append(dict(method=method,scope=scope,whole_equal_pools=w.pool_id.nunique(),whole_equal_direction_n_cells=len(w),
                                       whole_equal_m_ge7_pools=w[w.m.ge(7)].pool_id.nunique(),whole_equal_m_ge10_pools=w[w.m.ge(10)].pool_id.nunique(),
                                       whole_unequal_pools=v.pool_id.nunique(),whole_unequal_direction_background_n_cells=len(v),
                                       alliance_teams=len(a),alliance_teams_n_ge3=int(a.n_at_least3.sum()),
                                       distinct_physical_alliance_teams=a.member_identity_key.nunique()))
    save(design_summary,'WHOLE_CLASS_AND_ALLIANCE_SUMMARY.csv')
    receipt={'source_commit':COMMIT,'input_receipts':input_receipts,'label_overlap_records_checked':len(overlap),'label_overlap_matches':True,
             'all_pool_inventory':len(inv),'ordinary_manual_pools':236,'ordinary_primary_pools':206,'ordinary_other_target_pools':30,
             'methods':METHODS,'label_rows':len(labels),'pool_method_rows':len(pm),'class_rows':len(cr),'directed_class_rows':len(di),
             'all_legal_AC_direction_n_m_cells':len(ff),'whole_equal_cells':len(we),'whole_unequal_cells':len(wu),'alliance_teams':len(al),'alliance_edges':len(ae),
             'm10_n20_published_matches_all_direction_rows':True,'m10_n20_primary_capacity':actual,
             'fusion_calls':0,'score_calls':0,'target_scores_used_for_design':False,
             'capacity_not_execution':True,'n_min':3,'background_can_be_empty':True,
             'unknown_labels_only_allowed_in_D':True,'scope_and_mode_never_mixed':True,
             'combination_formula':'C(source_n,m)*C(target_n,m)*C(pool_n-2m,n-m); directed AC, reverse is same physical pair with opposite direction',
             'unequal_whole_class_formula':'X=all source, Z=all target, D subset remaining N-source_n-target_n; min(nA,nC)>=3',
             'alliance_definition':'union of all available members of each nonempty class subset; optional fixed unknown-background inclusion; no outcome selection'}
    dump(receipt,OUT/'CAPACITY_RECEIPT.json')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
