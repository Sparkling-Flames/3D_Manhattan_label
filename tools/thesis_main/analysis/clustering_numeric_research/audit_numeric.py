"""Independent endpoint, binding, coverage, partition, and finite-pool audit.
No coordinates, human judgments, or production contracts are modified.
"""
from __future__ import annotations
import sys,json,gzip,itertools,collections,math,functools
import numpy as np,pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
from common import *

def independent_assignment(p,up,dn):
    """Exact subset DP over the inherited allowed horizontal edges; not Hungarian.
    Count equal-cost optimal assignments (capped at 2); 1e-8 matches source gate.
    """
    if len(up)!=len(dn):return None,0,np.nan
    n=len(up)
    dx=np.abs(np.asarray(p)[up,None,0]-np.asarray(p)[dn,0][None,:])%1024
    cost=np.minimum(dx,1024-dx)
    @functools.lru_cache(None)
    def solve(i,mask):
        if i==n:return 0.,1,()
        best=math.inf;count=0;mapping=()
        for j in range(n):
            if mask>>j&1 or cost[i,j]>=51.2:continue
            tail,ways,mp=solve(i+1,mask|1<<j)
            if not ways:continue
            val=float(cost[i,j])+tail
            if val<best-1e-8:best=val;count=ways;mapping=(j,)+mp
            elif abs(val-best)<1e-8:count=min(2,count+ways)
        return best,count,mapping
    best,count,mp=solve(0,0)
    return (np.column_stack([up,np.asarray(dn)[list(mp)]]) if count else None),count,best

def bottleneck_independent(c):
    vals=np.unique(c);lo=0;hi=len(vals)-1
    while lo<hi:
        mid=(lo+hi)//2
        mp=maximum_bipartite_matching(csr_matrix(c<=vals[mid]),perm_type='column')
        if np.all(mp>=0):hi=mid
        else:lo=mid+1
    mp=maximum_bipartite_matching(csr_matrix(c<=vals[lo]),perm_type='column')
    return float(vals[lo]),mp

def cyclic_independent(c):
    n=len(c);values=np.array([np.max(c[np.arange(n),(np.arange(n)+s)%n]) for s in range(n)])
    s=int(np.argmin(values));return float(values[s]),(np.arange(n)+s)%n

def compare_outputs():
    result=[]
    for old in sorted((SOURCE/'results').iterdir()):
        new=OUT/'source_replay'/old.name
        if old.name=='EXPERIMENT_MANIFEST.json':continue
        if not new.exists():result.append(dict(file=old.name,match=False,reason='missing'));continue
        if old.name.endswith('.json'):
            a=json.loads(old.read_text());b=json.loads(new.read_text())
            errors=[]
            def compatible(x,y):
                if isinstance(x,dict):return isinstance(y,dict) and x.keys()==y.keys() and all(compatible(x[k],y[k]) for k in x)
                if isinstance(x,list):return isinstance(y,list) and len(x)==len(y) and all(compatible(i,j) for i,j in zip(x,y))
                if isinstance(x,(int,float)) and not isinstance(x,bool) and isinstance(y,(int,float)):
                    errors.append(abs(x-y));return bool(np.isclose(x,y,rtol=1e-11,atol=1e-11))
                return x==y
            same=compatible(a,b);err=max(errors,default=0.)
        elif old.name.endswith(('.csv','.csv.gz')):
            a=pd.read_csv(old);b=pd.read_csv(new);same=a.shape==b.shape and list(a)==list(b);err=0.
            if same:
                for c in a:
                    if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
                        x=a[c].astype(float).to_numpy();y=b[c].astype(float).to_numpy();mask=np.isfinite(x)&np.isfinite(y)
                        e=float(np.max(np.abs(x[mask]-y[mask]))) if mask.any() else 0.;err=max(err,e)
                        same &= bool(np.allclose(x,y,rtol=1e-11,atol=1e-11,equal_nan=True))
                    else:same &= a[c].fillna('<NULL>').equals(b[c].fillna('<NULL>'))
        else:continue
        result.append(dict(file=old.name,match=bool(same),max_numeric_absolute_error=err))
    d=save('source_replay_comparison.csv',result)
    assert d.match.all(),'Source reproduction failed'
    return d

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    replay=compare_outputs();rows,by,rec,el,approved=records()
    assert len(rows)==len(by)==2501
    retained=[r for r in rows if r['worker_id'] not in {'W019','W026'}]
    assert len({(r['image_id'],r['raw_condition'],r['worker_id']) for r in retained})==len(retained)
    bind=[]
    for cid,r in rec.items():
        links,ways,cost=independent_assignment(r['p'],r['up'],r['dn'])
        exempt=cid in approved
        if not exempt:
            assert bool(ways==1)==bool(r['links'] is not None),(cid,ways,r['audit'])
            if ways==1:assert {tuple(x) for x in links.tolist()}=={tuple(x) for x in r['links'].tolist()},cid
        bind.append(dict(id=cid,worker=r['row']['worker_id'],key=r['row']['image_id']+'|'+r['row']['raw_condition'],
            inherited_human_links=exempt,n_top=len(r['up']),n_bottom=len(r['dn']),dp_optima_capped2=ways,
            dp_min_cost_px=cost,source_bound_available=r['links'] is not None,status=r['audit'].get('pairing_source')))
    save('independent_binding_dp.csv',bind);save('eligibility_all_records.csv',el)
    oldp=SOURCE/'rc2_received/sources/old_release/clustering_release_RC1_20260920/input/source/analysis_results/paired_split_research_received_20260920/inputs/responses.jsonl.gz'
    old={r['canonical_annotation_id']:r for r in readrows(oldp)}
    changes=[]
    for cid,r in by.items():
        o=old[cid];raw_equal=r['raw_points_1024x512']==o['raw_points_1024x512'];eff_equal=r['effective_points_1024x512']==o['effective_points_1024x512']
        assert raw_equal
        if not eff_equal:changes.append(dict(id=cid,worker=r['worker_id'],image_id=r['image_id'],old_count=o['effective_point_count'],new_count=r['effective_point_count'],processing_status=r['processing_status'],raw_points_equal=raw_equal))
    save('effective_version_changes.csv',changes);assert len(changes)==2
    sourcegroups=source_json('results/groups.json');notes=source_json('evidence/latest_decisions.json')
    human={frozenset((h['id_a'],h['id_b'])):h for h in notes['confirmed_correspondences']}
    groups={};eps=[];prs=[];audits=[];summaries=[];members=[];relations=[];extremes=[];correspond=[]
    sphereerr=pixelerr=matrixerr=0.;endpoint_n=0;allpairs=0;count_blocked=0;partition_mismatch=0
    for unit,(key,g) in enumerate(sorted(sourcegroups.items())):
        ids=g['ids'];n=len(ids);rr=[rec[i] for i in ids];allpairs+=n*(n-1)//2
        D={m:np.full((n,n),BLOCK) for m in ('sphere','image')}
        for d in D.values():np.fill_diagonal(d,0)
        hc={};base={x:g[x] for x in ('code','image_id','building','condition','N')};base['unit']=unit
        for i,j in itertools.combinations(range(n),2):
            a,b=rr[i],rr[j]
            if len(a['p'])!=len(b['p']):count_blocked+=1;continue
            L,R=a['links'],b['links'];T=angle_matrix(a['p'][L[:,0]],b['p'][R[:,0]]);B=angle_matrix(a['p'][L[:,1]],b['p'][R[:,1]])
            PT=image_matrix(a['p'][L[:,0]],b['p'][R[:,0]]);PB=image_matrix(a['p'][L[:,1]],b['p'][R[:,1]])
            sp=max(np.diag(T).max(),np.diag(B).max());px=max(np.diag(PT).max(),np.diag(PB).max())
            D['sphere'][i,j]=D['sphere'][j,i]=sp;D['image'][i,j]=D['image'][j,i]=px
            # independent controls retain every endpoint; no automatic correction
            cv,cm=cyclic_independent(np.maximum(T,B));fv,fm=bottleneck_independent(np.maximum(T,B))
            ST=angle_matrix(a['p'][a['up']],b['p'][b['up']]);SB=angle_matrix(a['p'][a['dn']],b['p'][b['dn']])
            sc=max(cyclic_independent(ST)[0],cyclic_independent(SB)[0]);sf=max(np.diag(ST).max(),np.diag(SB).max())
            sfree=max(bottleneck_independent(ST)[0],bottleneck_independent(SB)[0])
            row=dict(**base,key=key,id_a=ids[i],id_b=ids[j],worker_a=g['workers'][i],worker_b=g['workers'][j],count=len(a['p']),sphere_deg=sp,image_px=px,
                     top_max_deg=float(np.diag(T).max()),bottom_max_deg=float(np.diag(B).max()),mean_endpoint_deg=float(np.r_[np.diag(T),np.diag(B)].mean()),
                     split_fixed_deg=sf,split_cyclic_deg=sc,split_free_deg=sfree,bound_cyclic_deg=cv,bound_free_deg=fv,
                     cyclic_mapping_1based='|'.join(map(str,cm+1)),free_mapping_1based='|'.join(map(str,fm+1)))
            prs.append(row)
            if any(sp>t and fv<=t for t in CUTS):correspond.append(row)
            views=[('automatic',a,b,L,R)]
            h=human.get(frozenset((ids[i],ids[j])))
            if h:
                ha,hb=rec[h['id_a']],rec[h['id_b']];HL=ha['links'];HR=hb['links'][np.array(h['pair_order_b_1based'])-1]
                views.append(('human_correspondence',ha,hb,HL,HR));hval={}
                for metric,fun in [('sphere',angle_matrix),('image',image_matrix)]:
                    hval[metric]=max(np.diag(fun(ha['p'][HL[:,r]],hb['p'][HR[:,r]])).max() for r in (0,1))
                hc[i,j]=hval
            for view,aa,bb,LL,RR in views:
                for roleidx,role in enumerate(('top','bottom')):
                    ap,bp=aa['p'][LL[:,roleidx]],bb['p'][RR[:,roleidx]]
                    ang=np.diag(angle_matrix(ap,bp));pix=np.diag(image_matrix(ap,bp))
                    for k,(p,q) in enumerate(zip(ap,bp)):
                        eps.append(dict(unit=unit,key=key,id_a=aa['id'],id_b=bb['id'],view=view,role=role,
                            a_point_1based=int(LL[k,roleidx])+1,b_point_1based=int(RR[k,roleidx])+1,
                            a_x=p[0],a_y=p[1],b_x=q[0],b_y=q[1],dx_px=(q[0]-p[0]+512)%1024-512,dy_px=q[1]-p[1],sphere_deg=ang[k],image_px=pix[k]))
                    endpoint_n+=len(ap)
        views={'automatic':D,'human_correspondence':{m:d.copy() for m,d in D.items()}}
        for (i,j),v in hc.items():
            for m,z in v.items():views['human_correspondence'][m][i,j]=views['human_correspondence'][m][j,i]=z
        ng={**g,'unit':unit,'matrices':{v:{m:d.tolist() for m,d in dd.items()} for v,dd in views.items()},'labels':{},'representatives':{}}
        tri=np.triu_indices(n,1)
        for view,dd in views.items():
            for metric,d in dd.items():
                oldD=np.array(g['matrices'][view][metric]);err=float(np.max(np.abs(d-oldD)))
                matrixerr=max(matrixerr,err)
                assert np.allclose(d,oldD,rtol=0,atol=2e-10),(key,view,metric,err)
                for t0 in CUTS:
                    t=nominal_cut(metric,t0);near=np.round(d,8)<=t
                    for kind in ('complete','representative'):
                        method=f'{view}:{metric}:{kind}:{t0:g}';lab,centers=partition(d,ids,t,kind)
                        same=coassign(lab);bad=int((coassign(g['labels'][method])!=same)[tri].sum());partition_mismatch+=bad
                        assert bad==0,(key,method,bad)
                        assert centers==g['representatives'][method],(key,method,'representative_mismatch')
                        ng['labels'][method]=lab.tolist();ng['representatives'][method]=centers
                        cnt=collections.Counter(lab);base2=dict(**base,view=view,metric=metric,partition=kind,nominal_cut=t0,actual_cut=t,method=method)
                        near_split=int((near&~same)[tri].sum());far_same=int((~near&same)[tri].sum())
                        assert kind!='complete' or far_same==0
                        summaries.append(dict(**base2,clusters=len(cnt),singletons=sum(v==1 for v in cnt.values()),largest_share=max(cnt.values())/n,
                                              near_pairs=int(near[tri].sum()),near_pairs_split=near_split,far_pairs_merged=far_same))
                        for idx,cid in enumerate(ids):
                            k=int(lab[idx]);ix=np.flatnonzero(lab==k);repidx=ids.index(centers[k-1]);alts=[c for c in centers if near[idx,ids.index(c)]]
                            farest=int(ix[np.argmax(d[idx,ix])]);outs=np.flatnonzero(near[idx]&~same[idx])
                            peersamecount=sum(len(rr[j]['p'])==len(rr[idx]['p']) for j in range(n))-1
                            reason=('different_effective_counts_only' if peersamecount==0 else 'no_within_tolerance_peer' if near[idx].sum()==1 else 'partition_isolation') if cnt[k]==1 else 'not_singleton'
                            members.append(dict(**base2,id=cid,worker=g['workers'][idx],cluster=k,cluster_size=cnt[k],effective_count=len(rr[idx]['p']),representative_id=centers[k-1],
                                distance_to_representative=d[idx,repidx],farthest_member_id=ids[farest],farthest_member_distance=d[idx,farest],
                                eligible_representatives='|'.join(alts),outside_close_ids='|'.join(ids[j] for j in outs),singleton_reason=reason))
                        for k,center in enumerate(centers,1):
                            ix=np.flatnonzero(lab==k);sub=d[np.ix_(ix,ix)];aa,bb=np.unravel_index(np.argmax(sub),sub.shape)
                            extremes.append(dict(**base2,cluster=k,size=len(ix),representative_id=center,max_pair_a=ids[ix[aa]],max_pair_b=ids[ix[bb]],diameter=float(sub[aa,bb]),
                                far_pairs=int((sub>t)[np.triu_indices(len(ix),1)].sum())))
                        for i,j in zip(*tri):
                            if near[i,j] and not same[i,j] or not near[i,j] and same[i,j]:
                                relations.append(dict(unit=unit,method=method,id_a=ids[i],id_b=ids[j],distance=d[i,j],kind='near_split' if near[i,j] else 'far_merged',cluster_a=int(lab[i]),cluster_b=int(lab[j])))
        groups[key]=ng
    ep=save('endpoint_differences.csv.gz',eps);pair=save('pairwise_independent.csv.gz',prs)
    oldep=pd.read_csv(SOURCE/'results/endpoint_residuals.csv.gz')
    keys=['key','id_a','id_b','view','role','a_point_1based','b_point_1based']
    joined=oldep.merge(ep,on=keys,suffixes=('_source','_independent'),validate='one_to_one')
    assert len(joined)==len(ep)==len(oldep)
    sphereerr=float((joined.sphere_deg_source-joined.sphere_deg_independent).abs().max())
    pixelerr=float((joined.image_px_source-joined.image_px_independent).abs().max())
    oldpair=pd.read_csv(SOURCE/'results/pairwise.csv.gz');joint=oldpair.merge(pair,on=['key','id_a','id_b'],suffixes=('_source','_independent'),validate='one_to_one')
    for c in ['sphere_deg','image_px','split_fixed_deg','split_cyclic_deg','bound_free_deg','bound_cyclic_deg']:
        err=float((joint[c+'_source']-joint[c+'_independent']).abs().max());audits.append(dict(metric=c,pairs=len(joint),max_absolute_error=err));assert err<2e-8
    save('independent_distance_checks.csv',audits)
    summary=save('partition_totals_by_unit.csv',summaries)
    save('partition_totals.csv',summary.groupby(['view','metric','partition','nominal_cut'],as_index=False)[['clusters','singletons','near_pairs','near_pairs_split','far_pairs_merged']].sum())
    save('memberships_and_representatives.csv.gz',members);save('group_extremes.csv.gz',extremes);save('near_split_far_merged_pairs.csv.gz',relations)
    save('correspondence_probe_queue.csv',correspond);dump('independent_groups.json',groups)
    # Own coverage versus identical common pool: split-fixed uses no pairing.
    units=collections.defaultdict(list)
    for r in retained:units[r['image_id']+'|'+r['raw_condition']].append(r)
    coverage=[];splitpairs=[]
    for key,rs in sorted(units.items()):
        available=[rec[r['canonical_annotation_id']] for r in rs if r['canonical_annotation_id'] in rec]
        bound=[r for r in available if r['links'] is not None]
        coverage.append(dict(key=key,code=available[0]['audit']['code'] if available else '',condition=rs[0]['raw_condition'],building=rs[0]['building_id'],observed=len(rs),role_available=len(available),bound_available=len(bound),
                             role_unavailable_ids='|'.join(r['canonical_annotation_id'] for r in rs if r['canonical_annotation_id'] not in rec),binding_unavailable_ids='|'.join(r['id'] for r in available if r['links'] is None)))
        n=len(available);ds=np.full((n,n),BLOCK);np.fill_diagonal(ds,0)
        for i,j in itertools.combinations(range(n),2):
            a,b=available[i],available[j]
            if len(a['p'])!=len(b['p']) or len(a['up'])!=len(b['up']) or len(a['dn'])!=len(b['dn']):continue
            ds[i,j]=ds[j,i]=max(np.diag(angle_matrix(a['p'][a['up']],b['p'][b['up']])).max(),np.diag(angle_matrix(a['p'][a['dn']],b['p'][b['dn']])).max())
        common=[i for i,a in enumerate(available) if a['links'] is not None]
        db=None if key not in groups else np.array(groups[key]['matrices']['automatic']['sphere'])
        # Reindex bound matrix to the role-order subset, so personnel are identical.
        if db is not None:
            ids0=groups[key]['ids'];ix=[ids0.index(available[i]['id']) for i in common];db=db[np.ix_(ix,ix)]
        for k in [3,5,8,12,16]:
            for t in CUTS:
                splitpairs.append(dict(key=key,condition=rs[0]['raw_condition'],N_role=n,N_common=len(common),k=k,cut=t,
                    split_own_pool=next_uncovered(ds,k,t),split_common_pool=next_uncovered(ds[np.ix_(common,common)],k,t) if common else np.nan,
                    bound_common_pool=next_uncovered(db,k,t) if db is not None else np.nan))
    save('coverage_by_unit.csv',coverage);save('own_vs_common_pool_curves.csv',splitpairs)
    dump('NUMERIC_AUDIT.json',dict(source_commit='457081270c88b719f70d96a721ec0c810a76a2d1',raw_records=len(rows),retained_records=len(retained),
        split_available=len(rec),bound_available=sum(r['links'] is not None for r in rec.values()),historical_units=len(units),bound_units=len(groups),
        all_bound_person_pairs=allpairs,equal_count_bound_pairs=len(pair),count_incompatible_pairs=count_blocked,endpoints=len(ep),
        endpoint_sphere_max_absolute_error=sphereerr,endpoint_pixel_max_absolute_error=pixelerr,full_matrix_max_error=matrixerr,
        changed_coclustering_relations=partition_mismatch,partitions_verified=len(summaries),source_result_files_reproduced=len(replay),
        independent_binding_solver='exact subset dynamic programming; inherited 51.2px admissibility, 1e-8 tie tolerance',
        original_points_changed=0,effective_version_changes=changes,human_pair_overrides=len(human),new_visual_adjudications=0,
        source_scope='frozen packaged records and existing source lineage; original runtime logs not re-parsed'))
    print('INDEPENDENT_NUMERIC_AUDIT',len(pair),'pairs',len(ep),'endpoints',sphereerr,pixelerr,flush=True)
if __name__=='__main__':main()
