#!/usr/bin/env python3
"""Cross-building personnel partitions from frozen within-image answer relations.

Two actual discovery routes are compared separately for Manual and Semi:
  A1: the mean of the frozen 9/12 degree coassignment indicators;
  A2: continuous bound-cyclic similarity, conditioned on equal corner counts,
      with each training image's origin-pair mean removed.
Neither Q nor reference nor fusion enters either relation matrix. Building
splits and the small K grid are fixed below before evaluating held-out answers.
Final descriptive labels and target-building-excluded labels are separate.
All canonical point/ring inputs and existing 9/12 partitions are unchanged.
"""
from __future__ import annotations
import argparse, gzip, hashlib, itertools, json, os, sys
from pathlib import Path
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
sys.path.append('/tmp/hohonet_deps')
from shapely.geometry import Polygon

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
SEED=2026102101
KS=(2,3,4)
MIN_IMAGES=6
MIN_BUILDINGS=3
METHODS=('A1_coassignment','A2_samecount_source_residual')
METRICS=['same9','same12','same_count','bound_deg','bottom_deg','top_deg','floor_iou','height_abslog','q_absdiff']

def read_json(p):
    with gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else open(p,encoding='utf-8') as f:return json.load(f)

def write_json(p,obj):
    def conv(v):
        if isinstance(v,(np.integer,np.floating,np.bool_)):return v.item()
        if isinstance(v,np.ndarray):return v.tolist()
        if isinstance(v,Path):return str(v)
        raise TypeError(type(v).__name__)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=conv)+'\n')

def build_pairs(api_path,record_path,out,repo):
    """Calls repository's frozen angular/cyclic implementation directly."""
    sys.path.insert(0,str(repo))
    from tools.thesis_main.analysis.paired_split_research.study import angular,cyclic
    api=read_json(api_path)
    rec=pd.read_csv(record_path).set_index('object_id')
    rows=[]
    for pi,pool in enumerate(api['pools']):
        meta=pool['meta']; gg=pool['geometries']
        labels={}
        for part in pool['partitions']:
            labels[int(part['threshold_deg'])]={obj:c for c,members in enumerate(part['affinity']) for obj in members}
        polys=[]
        for g in gg:
            poly=Polygon(g['floor']) if g['floor'] is not None else None
            polys.append(poly if poly is not None and poly.is_valid and poly.area>0 else None)
        for ia,ib in itertools.combinations(range(len(gg)),2):
            ga,gb=gg[ia],gg[ib]
            ra,rb=rec.loc[ga['object_id']],rec.loc[gb['object_id']]
            if ra.worker_id>rb.worker_id:
                ga,gb=gb,ga;ra,rb=rb,ra;pa,pb=polys[ib],polys[ia]
            else:pa,pb=polys[ia],polys[ib]
            aa,bb=np.asarray(ga['points']),np.asarray(gb['points'])
            equal=len(aa)==len(bb)
            row=dict(pool_id=meta['pool_id'],image_id=meta['image_id'],image_code=meta['image_code'],
                     building_id=meta['building_id'],condition=meta['condition'],layer=meta['layer'],
                     difficulty=meta['difficulty'],worker_a=ra.worker_id,worker_b=rb.worker_id,
                     object_a=ga['object_id'],object_b=gb['object_id'],origin_a=ra.origin,origin_b=rb.origin,
                     origin_pair='|'.join(sorted([ra.origin,rb.origin])),same_origin=ra.origin==rb.origin,
                     count_a=len(aa)//2,count_b=len(bb)//2,same_count=int(equal),
                     same9=int(labels[9][ga['object_id']]==labels[9][gb['object_id']]),
                     same12=int(labels[12][ga['object_id']]==labels[12][gb['object_id']]),
                     bound_deg=np.nan,bottom_deg=np.nan,top_deg=np.nan,floor_iou=np.nan,
                     height_abslog=np.nan,q_absdiff=abs(ra.B8L2-rb.B8L2),q_mean=(ra.B8L2+rb.B8L2)/2)
            if equal:
                top,bottom=angular(aa[::2],bb[::2]),angular(aa[1::2],bb[1::2])
                dd,shift,_=cyclic(np.maximum(top,bottom))
                x=np.arange(len(aa)//2);y=(x+shift)%len(x)
                row.update(bound_deg=dd,top_deg=top[x,y].max(),bottom_deg=bottom[x,y].max())
            if pa is not None and pb is not None:
                area=pa.intersection(pb).area
                row['floor_iou']=area/(pa.area+pb.area-area)
            ha,hb=ga['heights'],gb['heights']
            if ha is not None and hb is not None and min(np.mean(ha),np.mean(hb))>0:
                row['height_abslog']=abs(np.log(np.mean(ha)/np.mean(hb)))
            rows.append(row)
        if (pi+1)%40==0:print('pair geometry',pi+1,'/',len(api['pools']),flush=True)
    d=pd.DataFrame(rows)
    d['coassign']=(d.same9+d.same12)/2
    d['geosim']=np.exp(-d.bound_deg/12.)
    # This centering is within one image and is subsequently used only on
    # training-image rows; no held-out values enter a training relation.
    d['geo_residual']=d.geosim-d.groupby(['pool_id','origin_pair']).geosim.transform('mean')
    d.to_csv(out/'pair_observations.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    return d

def supported(rec):
    s=rec.groupby('worker_id').agg(n_images=('image_id','nunique'),n_buildings=('building_id','nunique'))
    return s[(s.n_images>=MIN_IMAGES)&(s.n_buildings>=MIN_BUILDINGS)]

def fit_labels(rec,pairs,method,k):
    sup=supported(rec)
    workers=sorted(sup.index)
    p=pairs[pairs.worker_a.isin(workers)&pairs.worker_b.isin(workers)].copy()
    metric='coassign' if method=='A1_coassignment' else 'geo_residual'
    # Preserve missing geometric comparisons; a different node count is not
    # given an invented zero angular distance.
    if method!='A1_coassignment':p=p[p.same_count.eq(1)]
    image=p.groupby(['worker_a','worker_b','building_id','image_id'])[metric].mean().reset_index()
    building=image.groupby(['worker_a','worker_b','building_id'])[metric].mean().reset_index()
    stats=building.groupby(['worker_a','worker_b'])[metric].agg(['mean','size'])
    prior=p.groupby(['building_id','image_id'])[metric].mean().groupby('building_id').mean().mean()
    if method!='A1_coassignment':prior=0.
    matrix=np.full((len(workers),len(workers)),float(prior))
    nobs=np.zeros_like(matrix)
    for i,a in enumerate(workers):
        for j in range(i+1,len(workers)):
            key=(a,workers[j])
            if key in stats.index:
                z=stats.loc[key];m=(z['size']*z['mean']+2*prior)/(z['size']+2)
                matrix[i,j]=matrix[j,i]=m
                nobs[i,j]=nobs[j,i]=z['size']
    np.fill_diagonal(matrix,0.)
    degree=np.abs(matrix).sum(1)
    norm=matrix/np.sqrt(np.maximum(degree[:,None]*degree[None,:],1e-20))
    vals,vecs=eigh(norm,subset_by_index=[len(workers)-k,len(workers)-1])
    emb=vecs[:,::-1]
    emb/=np.maximum(np.linalg.norm(emb,axis=1,keepdims=True),1e-12)
    lab=KMeans(n_clusters=k,n_init=40,random_state=SEED+k).fit_predict(emb)
    groups=sorted([sorted(np.array(workers)[lab==c]) for c in np.unique(lab)],key=lambda w:w[0])
    labels={w:f'A{c+1:02d}' for c,ww in enumerate(groups) for w in ww}
    return labels,{'sizes':[len(g) for g in groups], 'members':groups,'eigenvalues':vals[::-1],
                   'observed_pair_fraction':float((nobs[np.triu_indices(len(workers),1)]>0).mean()),
                   'equal_count_pair_support_buildings_median':float(np.median(nobs[np.triu_indices(len(workers),1)])),
                   'training_workers':len(workers),'training_images':rec.image_id.nunique(),
                   'training_buildings':sorted(rec.building_id.unique())}

def align_to(reference,labels):
    aa=sorted(set(reference.values()));bb=sorted(set(labels.values()))
    mat=np.zeros((len(aa),len(bb)),int)
    for w in set(reference)&set(labels):mat[aa.index(reference[w]),bb.index(labels[w])]+=1
    ii,jj=linear_sum_assignment(-mat)
    rename={bb[j]:aa[i] for i,j in zip(ii,jj)}
    return {w:rename.get(v,v) for w,v in labels.items()}

def eval_labels(pairs,labels,stage,method,k,condition):
    p=pairs[pairs.worker_a.isin(labels)&pairs.worker_b.isin(labels)].copy()
    p['within']=p.worker_a.map(labels).eq(p.worker_b.map(labels))
    result=[]
    # Source-stratified and Q-near comparisons address straightforward
    # explanations without putting these external variables into classes.
    for panel,q in [('all_pairs',p),('equal_count',p[p.same_count.eq(1)]),
                    ('equal_count_same_source',p[p.same_count.eq(1)&p.same_origin]),
                    ('equal_count_Qdiff_le5',p[p.same_count.eq(1)&p.q_absdiff.le(5)])]:
        if not len(q):continue
        for metric in METRICS:
            # Both pair types must be observed on this image; report image
            # contrasts, then average images within building and buildings.
            agg=q.groupby(['building_id','image_id','within'])[metric].mean().unstack('within')
            if True not in agg or False not in agg:continue
            agg=agg.reindex(columns=[True,False]).dropna()
            if not len(agg):continue
            agg['gap']=agg[True]-agg[False]
            b=agg.groupby('building_id').mean()
            vals=b['gap'].to_numpy()
            rng=np.random.default_rng(SEED)
            boot=np.mean(rng.choice(vals,size=(2000,len(vals)),replace=True),axis=1)
            result.append(dict(condition=condition,stage=stage,method=method,k=k,panel=panel,metric=metric,
                n_pairs=len(q),n_images=len(agg),n_buildings=len(b),within=b[True].mean(),between=b[False].mean(),
                within_minus_between=vals.mean(),ci_lo=np.quantile(boot,.025),ci_hi=np.quantile(boot,.975),
                buildings_positive=int((vals>0).sum()),buildings_negative=int((vals<0).sum())))
    return result

def label_rows(rec,labels,method,k,stage,condition,target='',aligned=None):
    sup=rec.groupby('worker_id').agg(n_images=('image_id','nunique'),n_buildings=('building_id','nunique'),origin=('origin','first'))
    all_workers=sorted(rec.worker_id.unique())
    return [dict(condition=condition,method=method,k=k,stage=stage,target_building=target,worker_id=w,
                 class_id=labels.get(w,'unknown'),aligned_class_id=(aligned or labels).get(w,'unknown'),
                 n_train_images=int(sup.loc[w,'n_images']),n_train_buildings=int(sup.loc[w,'n_buildings']),
                 origin=sup.loc[w,'origin'],unknown_reason='' if w in labels else 'fewer_than_6_images_or_3_buildings')
            for w in all_workers]

def characterize(rec,pairs,labels,method,k,condition):
    r=rec[rec.worker_id.isin(labels)].copy()
    r['class_id']=r.worker_id.map(labels)
    r['count_gap']=r.pair_count-r.groupby('pool_id').pair_count.transform('median')
    r['log_height']=np.log(r.mean_height.where(r.mean_height>0))
    r['height_gap']=r.log_height-r.groupby('pool_id').log_height.transform('median')
    r['depression_gap']=r.minimum_bottom_depression_deg-r.groupby('pool_id').minimum_bottom_depression_deg.transform('median')
    r['count_more']=(r.count_gap>0).astype(float)
    r['count_less']=(r.count_gap<0).astype(float)
    fields=['pair_count','count_gap','count_more','count_less','height_gap','depression_gap','B8L2','D10','source_time_seconds']
    w=r.groupby(['class_id','worker_id','building_id'])[fields].mean().groupby(['class_id','worker_id']).mean()
    out=[]
    for c,g in w.groupby('class_id'):
        members=g.index.get_level_values('worker_id').tolist()
        z=dict(condition=condition,method=method,k=k,class_id=c,n_workers=len(members),members='|'.join(members))
        z.update({f:float(g[f].mean()) for f in fields})
        z['new_workers']=int(r[r.worker_id.isin(members)].groupby('worker_id').origin.first().eq('new').sum())
        out.append(z)
    return out

def main():
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument('--repo',type=Path,default=REPO)
    ap.add_argument('--input-root',type=Path)
    ap.add_argument('--out',type=Path,default=HERE)
    ap.add_argument('--reuse-pairs',action='store_true')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    inputs=args.input_root or args.repo
    source=inputs/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/clusters'
    rec=pd.read_csv(source/'records_geometry.csv.gz')
    pairs=pd.read_csv(args.out/'pair_observations.csv.gz') if args.reuse_pairs else build_pairs(source/'CLUSTER_API.json.gz',source/'records_geometry.csv.gz',args.out,args.repo)
    registry={'schema':'personnel_relation_classification_A_v1','seed':SEED,'k_candidates':list(KS),
       'methods':METHODS,'support':{'min_images':MIN_IMAGES,'min_buildings':MIN_BUILDINGS},
       'selection_rule':'Development-only drop-one-building ARI; require minimum class size>=3; select maximal median ARI, tie smaller K. Held-out geometric or fusion effects are not used to choose.',
       'similarity':'A1 mean frozen 9/12 degree coassignment; A2 exp(-bound_cyclic_deg/12) among equal pair counts minus within-training-image origin-pair mean.',
       'centering':'Each geometry residual is centered only within its own image and origin-pair stratum. Matrix construction sees training images only.',
       'shrinkage':'Each worker-pair building mean gets two-building prior: training-global coassignment for A1; zero residual for A2.',
       'partitions':'Normalized adjacency spectral embedding, abs-degree normalization for signed A2; KMeans n_init=40.',
       'splits':{},'pair_coverage':pairs.groupby('layer').agg(n_pairs=('image_id','size'),n_images=('image_id','nunique'),n_buildings=('building_id','nunique')).reset_index().to_dict('records')}
    candidates=[];labs=[];evals=[];roles=[];stabilities=[];selected={};lobo_rows=[];lobo_eval=[]
    for condition in ['manual','semi']:
        layer='ordinary_'+condition
        rr=rec[rec.layer.eq(layer)].copy();pp=pairs[pairs.layer.eq(layer)].copy()
        buildings=sorted(rr.building_id.unique(),key=lambda b:hashlib.sha256(('A-development-'+b).encode()).hexdigest())
        # The sparse Semi panel cannot support a deletion check after a 6/6
        # split (one development deletion leaves only one eligible worker).
        # This support-only change was made before any Semi candidate result.
        ndev=len(buildings)//2 if condition=='manual' else int(np.ceil(len(buildings)*2/3))
        dev=sorted(buildings[:ndev]);test=sorted(set(buildings)-set(dev))
        registry['splits'][condition]={'development_buildings':dev,'check_buildings':test}
        rd=rr[rr.building_id.isin(dev)];pd_=pp[pp.building_id.isin(dev)]
        pt=pp[pp.building_id.isin(test)]
        for method in METHODS:
            for k in KS:
                labels,diag=fit_labels(rd,pd_,method,k)
                aris=[]
                for b in dev:
                    loo,_=fit_labels(rd[rd.building_id.ne(b)],pd_[pd_.building_id.ne(b)],method,k)
                    common=sorted(set(labels)&set(loo))
                    ari=adjusted_rand_score([labels[w] for w in common],[loo[w] for w in common])
                    aris.append(ari)
                    stabilities.append(dict(condition=condition,method=method,k=k,removed_building=b,n_common=len(common),ARI=ari))
                sizes=diag['sizes'];nmi=normalized_mutual_info_score(rd.groupby('worker_id').origin.first().loc[list(labels)],list(labels.values()))
                row=dict(condition=condition,method=method,k=k,n_workers=len(labels),class_sizes='|'.join(map(str,sizes)),
                         minimum_class=min(sizes),development_dropbuilding_ARI_median=float(np.median(aris)),
                         development_dropbuilding_ARI_min=float(np.min(aris)),source_NMI=float(nmi))
                candidates.append(row)
                labs+=label_rows(rd,labels,method,k,'development_frozen',condition)
                evals+=eval_labels(pt,labels,'independent_building_check',method,k,condition)
                print('candidate',row,flush=True)
            cc=[c for c in candidates if c['condition']==condition and c['method']==method and c['minimum_class']>=3]
            if not cc:cc=[c for c in candidates if c['condition']==condition and c['method']==method]
            pick=sorted(cc,key=lambda c:(-c['development_dropbuilding_ARI_median'],c['k']))[0]
            k=pick['k'];selected[condition+'|'+method]=dict(pick)
            full,diag=fit_labels(rr,pp,method,k)
            labs+=label_rows(rr,full,method,k,'all_data_descriptive',condition)
            roles+=characterize(rr,pp,full,method,k,condition)
            all_target=[]
            for b in sorted(buildings):
                rtrain=rr[rr.building_id.ne(b)];ptrain=pp[pp.building_id.ne(b)]
                loo,ld=fit_labels(rtrain,ptrain,method,k)
                aligned=align_to(full,loo)
                lobo_rows+=label_rows(rtrain,loo,method,k,'leave_building_out',condition,b,aligned)
                target=pp[pp.building_id.eq(b)&pp.worker_a.isin(loo)&pp.worker_b.isin(loo)].copy()
                target['within']=target.worker_a.map(loo).eq(target.worker_b.map(loo))
                all_target.append(target)
            pe=pd.concat(all_target,ignore_index=True)
            pe['class_a']=np.where(pe.within,'shared','a');pe['class_b']=np.where(pe.within,'shared','b')
            # Use the per-target within flag directly for cross-fitted evaluation.
            lobo_eval+=eval_crossfit(pe,method,k,condition)
            pe[['pool_id','image_id','building_id','worker_a','worker_b','within']].to_csv(args.out/f'crossfit_pairs_{condition}_{method}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        for name,rows in [('candidate_selection',candidates),('worker_labels',labs),('building_deletion_stability',stabilities),
                      ('independent_check',evals),('class_characteristics',roles),('worker_labels_lobo',lobo_rows),('crossfit_check',lobo_eval)]:
            pd.DataFrame(rows).to_csv(args.out/(name+'.csv'),index=False)
        print('completed condition',condition,flush=True)
    for name,rows in [('candidate_selection',candidates),('worker_labels',labs),('building_deletion_stability',stabilities),
                      ('independent_check',evals),('class_characteristics',roles),('worker_labels_lobo',lobo_rows),('crossfit_check',lobo_eval)]:
        pd.DataFrame(rows).to_csv(args.out/(name+'.csv'),index=False)
    registry['selected']=selected
    write_json(args.out/'DESIGN_AND_RECEIPT.json',registry)
    print(json.dumps(selected,indent=2),flush=True)

def eval_crossfit(p,method,k,condition):
    result=[]
    for panel,q in [('all_pairs',p),('equal_count',p[p.same_count.eq(1)]),
                    ('equal_count_same_source',p[p.same_count.eq(1)&p.same_origin]),
                    ('equal_count_Qdiff_le5',p[p.same_count.eq(1)&p.q_absdiff.le(5)])]:
        for metric in METRICS:
            agg=q.groupby(['building_id','image_id','within'])[metric].mean().unstack('within')
            if True not in agg or False not in agg:continue
            agg=agg.reindex(columns=[True,False]).dropna()
            if not len(agg):continue
            agg['gap']=agg[True]-agg[False];b=agg.groupby('building_id').mean();vals=b['gap'].to_numpy()
            rng=np.random.default_rng(SEED);boot=np.mean(rng.choice(vals,size=(2000,len(vals)),replace=True),1)
            result.append(dict(condition=condition,stage='leave_building_out',method=method,k=k,panel=panel,metric=metric,n_pairs=len(q),
                n_images=len(agg),n_buildings=len(b),within=b[True].mean(),between=b[False].mean(),within_minus_between=vals.mean(),
                ci_lo=np.quantile(boot,.025),ci_hi=np.quantile(boot,.975),buildings_positive=int((vals>0).sum()),buildings_negative=int((vals<0).sum())))
    return result

if __name__=='__main__':main()
