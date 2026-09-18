"""Full canonical corpus; W019/W026 excluded before geometry or grouping.
Exploratory configurations, not semantic labels. Unapproved edits stay unapplied.
"""
from __future__ import annotations
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(k,'1')
import json,gzip,collections,itertools,hashlib,argparse,math
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import adjusted_rand_score
import clustering_study as st
import spherical_followup as sp
import legacy_reproduction as old
EXCLUDED={'W019','W026'}
def stable_labels(labels):
    blocks=sorted([np.flatnonzero(labels==v)for v in set(labels)],key=lambda x:(-len(x),int(x.min())))
    out=np.zeros(len(labels),int)
    for j,ix in enumerate(blocks):out[ix]=j+1
    return out

def method_grid(ds,counts):
    for name in st.METHODS:
        lab,noise,D,extra=st.apply(name,ds,counts)
        yield name,lab,noise,D
    for c in [6.,8.,10.,14.,16.]:
        D=ds['gospa20'];yield f'A3_cyclic_cut{int(c):02}',stable_labels(old.clust(D,None,c)),np.zeros(len(counts),bool),D
    for c in [.05,.075,.125,.15,.20]:
        D=ds['mask'];yield f'A1_mask_cut{c:.3f}',stable_labels(old.clust(D,None,c)),np.zeros(len(counts),bool),D

def run(root):
    inputs=root/'inputs/frozen';out=root/'results';out.mkdir(parents=True,exist_ok=True)
    data=json.loads((inputs/'key39/data.json').read_text());ns=old.legacy_functions(data)
    allrows=[json.loads(l)for l in gzip.open(inputs/'human/responses.jsonl.gz','rt')]
    meta_path=root/'snapshot/history/analysis_results/image_portrait_20260914_v1/metadata/images.jsonl'
    md=[json.loads(l)for l in meta_path.read_text().splitlines()]
    image_meta={x['image_id']:x for x in md};key39={x['image_id']:x['code'] for x in data['cases']}
    groups=collections.defaultdict(list);audit=[];rstore={}
    for r in allrows:
        iid=r['image_id'];w=r['worker_id'];cid=r['canonical_annotation_id'];norm=ns['normalize_geometry'](r['effective_points_1024x512'])
        code=key39.get(iid,'');m=image_meta.get(iid,{})
        if not code:code=m.get('code',m.get('display_code',''))
        if not code:
            num=m.get('number',m.get('image_number'))
            code=f"{r['building_id']}-{int(num):02}" if num is not None else iid
        blocked=w in EXCLUDED;eligible=(not blocked and r['calculation_included'] and norm['valid'])
        status='worker_excluded'if blocked else('confirmed_excluded'if r['effective_points_1024x512'] is None else('geometry_available'if eligible else'geometry_unavailable'))
        a=dict(id=cid,image_id=iid,code=code,building=r['building_id'],worker=w,condition=r['raw_condition'],stage=r['stage'],exposure=r['assistance_exposure'],analysis_status=status,geometry_eligible=eligible,normalization_reason=norm['reason'],inventory_calculation_included=r['calculation_included'],raw_points=r['raw_point_count'],effective_points=r['effective_point_count'],processing_status=r['processing_status'],confirmation_source=r['confirmation_source'],imputed_point=r['imputed_point'],exclusion_reason=r['exclusion_reason'],raw_export_path=r['raw_export_path'],annotation_identity=r['annotation_identity'])
        audit.append(a)
        if blocked:continue
        groups[(iid,r['raw_condition'])]
        rr={**r,'id':cid,'norm':norm,'code':code}
        if eligible:
            rr['events']=old.pairs3(norm);rr['boundary']=old.dense(ns,norm).astype(float)
            try:
                rr['native'],cross=old.native_dense(ns,r['effective_points_1024x512'],norm)
                if cross:rr['native']=None
            except ValueError:rr['native']=None
            groups[(iid,r['raw_condition'])].append(rr)
        rstore[cid]=rr
    adf=pd.DataFrame(audit);adf.to_csv(out/'all_response_audit.csv',index=False)
    adf[(~adf.worker.isin(EXCLUDED))&((adf.raw_points.fillna(0)%2==1)|(adf.processing_status!='unchanged')|(adf.analysis_status!='geometry_available'))].to_csv(out/'odd_repair_exclusion_audit.csv',index=False)
    summary=[];members=[];pairrows=[];cache={};spherical=[];sphmembers=[];novel=[];loo=[]
    for gi,((iid,cond),rr) in enumerate(sorted(groups.items())):
        rr=sorted(rr,key=lambda r:r['worker_id']);ids=[r['id']for r in rr];assert len({r['worker_id']for r in rr})==len(rr)
        n=len(rr);gobs=adf[(adf.image_id==iid)&(adf.condition==cond)&~adf.worker.isin(EXCLUDED)];code=gobs.iloc[0].code
        common=dict(image_id=iid,code=code,condition=cond,building=iid.split('_')[0],N_observed=len(gobs),N_geometry=n,N_unavailable=len(gobs)-n,development_image=iid in key39)
        if n==0:
            summary.append({**common,'method':'no_geometry','clusters':None});continue
        ds=st.pair_matrices(rr);counts=np.array([r['effective_point_count']for r in rr]);labels={}
        for method,l,noise,D in method_grid(ds,counts):
            labels[method]=l.tolist();stats=old.cluster_stats(l)
            summary.append(dict(**common,method=method,**stats,noise_n=int(noise.sum()),inference_status='single_response_not_consensus'if n==1 else'exploratory_partition'))
            for j,r in enumerate(rr):members.append(dict(**common,method=method,id=r['id'],worker=r['worker_id'],cluster=int(l[j]),density_unassigned=bool(noise[j]),effective_points=int(counts[j]),imputed_point=r['imputed_point']))
            if method in ['A0_legacy','A1_mask','A3_cyclic_cut08','A3_cyclic']and n>=3:
                for omit in range(n):
                    ix=np.delete(np.arange(n),omit);Dm=D[np.ix_(ix,ix)]
                    cut=.1 if method in ['A0_legacy','A1_mask']else(8. if method.endswith('08')else 12.)
                    ll=old.clust(Dm,counts[ix]if method=='A0_legacy'else None,cut)
                    eq=l[ix,None]==l[ix][None,:];eq2=ll[:,None]==ll[None,:]
                    loo.append(dict(**common,method=method,omitted_worker=rr[omit]['worker_id'],ARI=adjusted_rand_score(l[ix],ll),changed_pairs=int((eq!=eq2).sum()//2),total_pairs=len(ix)*(len(ix)-1)//2))
        for i,j in itertools.combinations(range(n),2):pairrows.append(dict(**common,id_a=ids[i],id_b=ids[j],worker_a=rr[i]['worker_id'],worker_b=rr[j]['worker_id'],count_a=int(counts[i]),count_b=int(counts[j]),**{k:float(v[i,j])for k,v in ds.items()}))
        for label,D,cut in [('mask',ds['mask'],.1),('cyclic8',ds['gospa20'],8.),('cyclic12',ds['gospa20'],12.)]:
            neighbor=(D<=cut+1e-12).sum(1)-1
            for k in [2,4,8,12,16]:
                if k>=n:continue
                val=np.mean([math.comb(n-1-int(m),k)/math.comb(n-1,k)if n-1-int(m)>=k else 0. for m in neighbor])
                novel.append(dict(**common,metric=label,k=k,finite_pool_new_incompatible_probability=val))
        sy=[];sidx=[]
        for j,r in enumerate(rr):
            y,reason=sp.spherical_boundary(r['events'])
            if y is not None:sy.append(y);sidx.append(j)
        if sidx:
            m=len(sidx);sds={'linear_common':ds['mask'][np.ix_(sidx,sidx)],'spherical':np.zeros((m,m)),'solid_angle':np.zeros((m,m))}
            for i,j in itertools.combinations(range(m),2):
                sds['spherical'][i,j]=sds['spherical'][j,i]=old.dmask(np.rint(sy[i]).astype(int),np.rint(sy[j]).astype(int))
                sds['solid_angle'][i,j]=sds['solid_angle'][j,i]=sp.solid_iou(sy[i],sy[j])
            for name,D in sds.items():
                for cut in [.075,.10,.125,.15]:
                    l=stable_labels(old.clust(D,None,cut));spherical.append(dict(**common,N_spherical=m,method=name,cut=cut,**old.cluster_stats(l)))
                    if cut==.1:
                        for j,ind in enumerate(sidx):sphmembers.append(dict(**common,method=name,id=ids[ind],worker=rr[ind]['worker_id'],cluster=int(l[j])))
        cache[iid+'|'+cond]=dict(ids=ids,workers=[r['worker_id']for r in rr],counts=counts,Ds=ds,labels=labels,code=code,spherical_ids=[ids[j]for j in sidx])
        if gi%30==0:print('done',gi,code,cond,n,flush=True)
    for name,rows in [('group_summary',summary),('memberships',members),('pairwise_features',pairrows),('spherical_summary',spherical),('spherical_memberships',sphmembers),('finite_pool_novelty',novel),('leave_one_out',loo)]:pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
    old.save_json(out/'group_cache.json',cache)
    old.save_json(out/'computation_counts.json',dict(raw_records=len(allrows),excluded_workers=sorted(EXCLUDED),excluded_records=int(adf.worker.isin(EXCLUDED).sum()),included_records=int((~adf.worker.isin(EXCLUDED)).sum()),geometry_records=int(adf.geometry_eligible.sum()),unavailable_records=int((~adf.worker.isin(EXCLUDED)&~adf.geometry_eligible).sum()),images=adf.loc[~adf.worker.isin(EXCLUDED),'image_id'].nunique(),groups=len(groups),methods=18,member_rows=len(members),pair_rows=len(pairrows),source_main='d3477e700082c0a8482f1ffabd9dcc5649c9754d',source_human='c61930ecac1a20c99cd0b73c10aa7e10bd9e65ac',pending_updates_applied=False))
    print(pd.DataFrame(summary).groupby('method')[['clusters','singletons']].sum().to_string(),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);run(p.parse_args().root)
