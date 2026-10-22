"""Three-method actual outcomes on identical A/background/n/m anchors."""
from __future__ import annotations
from summarize_joint import *
METHODS=['V3_JOINT_QT','XCOND_GEOM_QT','XCOND_PAIRED']

def run(condition):
    src=HERE/f'CROSS_{condition.upper()}_EVENTS_COMPLETE.csv.gz';d=pd.read_csv(src,low_memory=False)
    for pre,a,b in [('same','A','B'),('cross','A','C'),('net','B','C')]:
        d[pre+'_B8L2_completion_lower']=d[b+'_B8L2'].fillna(0)-d[a+'_B8L2'].fillna(100)
        d[pre+'_B8L2_completion_upper']=d[b+'_B8L2'].fillna(100)-d[a+'_B8L2'].fillna(0)
    primary=[c for c in PRIMARY if c in d];numeric=[c for c in d if c in primary or (c.startswith(('same_','cross_','net_','common_geometry_','common_expression_')) and pd.api.types.is_numeric_dtype(d[c]))]
    keys=['condition','source_domain','building','image','pool_id','panel_id','n','common_anchor_id','method_id'];a=d.groupby(keys,dropna=False)[numeric].mean().reset_index()
    support=d.groupby(keys).agg(events=('event_id','size'),all_scored=('all_scored','all'),all_time=('recorded_time_single_source','all'),all_complete=('all_complete','all')).reset_index();a=a.merge(support,on=keys)
    common=a.groupby('common_anchor_id').agg(methods=('method_id','nunique'),all_scored=('all_scored','all'),all_time=('all_time','all'),all_complete=('all_complete','all'));assert common.methods.eq(3).all()
    a['shared_scored_time_anchor']=a.common_anchor_id.isin(common.index[common.all_scored&common.all_time]);a['shared_all_scored_anchor']=a.common_anchor_id.isin(common.index[common.all_scored]);a['common_background']=a.common_anchor_id
    write(HERE/f'CROSS_{condition.upper()}_ANCHOR_RESPONSES.csv.gz',a)
    summaries=[];pairrows=[];imageout=[];buildout=[]
    for domain,g in a.groupby('source_domain'):
        for scope,x in [('all_registered_anchors',g),('all_methods_scored_time_same_anchors',g[g.shared_scored_time_anchor])]:
            if x.empty:continue
            for method,z in x.groupby('method_id'):
                _,_,im,bu=means(z,primary);row=dict(condition=condition,source_domain=domain,scope=scope,method_id=method,anchors=z.common_anchor_id.nunique(),panels=z.panel_id.nunique(),images=z.image.nunique(),buildings=z.building.nunique(),events=int(z.events.sum()))
                for metric in primary:row[metric]=float(bu[metric].mean())
                for pre in ['same','cross','net']:row[pre+'_recorded_time_geomean_pct']=100*np.expm1(row[pre+'_recorded_time_logratio'])
                for unit,frame in [('image',im),('building',bu)]:
                    q=frame.net_B8L2;t=frame.net_recorded_time_logratio;known=q.notna()&t.notna();row[unit+'_QT_known']=int(known.sum());row[unit+'_QT_both']=int((q.gt(0)&t.lt(0)&known).sum())
                summaries.append(row)
                for k,v in {'condition':condition,'source_domain':domain,'scope':scope,'method_id':method}.items():im[k]=v;bu[k]=v
                imageout.append(im);buildout.append(bu)
            base=x[x.method_id.eq(METHODS[0])].set_index('common_anchor_id')
            for method in METHODS[1:]:
                alt=x[x.method_id.eq(method)].set_index('common_anchor_id');assert set(alt.index)==set(base.index)
                z=alt.reset_index()[['building','image','pool_id','panel_id','n','common_anchor_id','common_background']].copy()
                for metric in primary:z[metric]=(alt[metric]-base[metric]).reindex(z.common_anchor_id).values
                _,_,im,bu=means(z,primary)
                for metric in primary:
                    vals=bu[metric].dropna().to_numpy();lo=hi=np.nan
                    if len(vals)>1:
                        rng=np.random.default_rng(int(h('cross-paired-bootstrap',condition,domain,scope,method,metric)[:16],16));res=vals[rng.integers(len(vals),size=(2000,len(vals)))].mean(axis=1);lo,hi=np.quantile(res,[.025,.975])
                    pairrows.append(dict(condition=condition,source_domain=domain,scope=scope,method_id=method,baseline=METHODS[0],metric=metric,anchors=len(z),images=len(im),buildings=len(vals),mean_difference=float(vals.mean()) if len(vals) else np.nan,bootstrap_lo=lo,bootstrap_hi=hi))
    write(HERE/f'CROSS_{condition.upper()}_SAME_SUPPORT_SUMMARY.csv',pd.DataFrame(summaries));write(HERE/f'CROSS_{condition.upper()}_PAIRED_METHOD_DIFFERENCES.csv.gz',pd.DataFrame(pairrows));write(HERE/f'CROSS_{condition.upper()}_SAME_SUPPORT_IMAGE_EFFECTS.csv.gz',pd.concat(imageout,ignore_index=True));write(HERE/f'CROSS_{condition.upper()}_SAME_SUPPORT_BUILDING_EFFECTS.csv.gz',pd.concat(buildout,ignore_index=True))
    save(HERE/f'CROSS_{condition.upper()}_COMPARISON_RECEIPT.json',dict(condition=condition,registered_events=len(d),registered_common_anchors=len(common),shared_fully_scored_time_anchors=int((common.all_scored&common.all_time).sum()),methods=METHODS,all_failure_anchors_retained_in_full_table=True,source_sha256=sha(src),causal_identity='same A,D,n,m and complete 924-candidate inventory; method-specific B and C members; common center rule',new_fusion_calls=0))
    cols=['condition','source_domain','scope','method_id','anchors','images','buildings','same_B8L2','cross_B8L2','net_B8L2','net_recorded_time_geomean_pct','abs_Q_change_advantage','net_failure_difference','image_QT_both','image_QT_known']
    print(pd.DataFrame(summaries)[cols].to_string(index=False),flush=True)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('condition',choices=['manual','semi']);run(ap.parse_args().condition)
