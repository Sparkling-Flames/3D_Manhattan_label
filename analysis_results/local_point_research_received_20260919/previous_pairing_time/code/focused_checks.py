"""Focused pairing ablation, true pair/partition counterexample and older stress tests.
No ambiguous matching is selected in the flag-only variant. No coordinate is changed.
"""
import audit_geometry as a
import numpy as np,pandas as pd,json,itertools,math,collections
from scipy.ndimage import uniform_filter1d
O=a.OUT

def run():
    au=pd.read_csv(O/'pairing_audit_all2501.csv').set_index('id');groups=collections.defaultdict(list);rinfo={}
    for r in a.ROWS:
        cid=r['canonical_annotation_id'];z=au.loc[cid]
        if z.excluded_worker or not z.old_valid or not r['calculation_included']:continue
        no=a.NS['normalize_geometry'](r['effective_points_1024x512']);new=no;status='old_unchanged'
        if z.same_hemisphere_pairs>0:
            nn,reason,meta=a.sensible(r['effective_points_1024x512'])
            if nn is None:status='unknown_'+reason;new=None
            elif meta['tied']:status='unknown_matching_tie';new=None
            else:status='unique_flagged_alternative';new=nn
        rinfo[cid]=(no,new,status)
        groups[r['image_id'],r['raw_condition']].append(cid)
    rows=[];pairs=[]
    for key,allids in groups.items():
        ids=[cid for cid in allids if rinfo[cid][1]is not None];n=len(ids)
        if not n:continue
        mats={name:np.zeros((n,n))for name in ['old_mask','alt_mask','old_cyclic','alt_cyclic']};bd={ver:[a.old.dense(a.NS,rinfo[cid][v])for cid in ids]for ver,v in [('old',0),('alt',1)]}
        for i,j in itertools.combinations(range(n),2):
            for ver,v in [('old',0),('alt',1)]:
                mats[ver+'_mask'][i,j]=a.old.dmask(bd[ver][i],bd[ver][j]);ea=a.old.pairs3(rinfo[ids[i]][v]);eb=a.old.pairs3(rinfo[ids[j]][v]);d=abs(ea[:,None,:]-eb[None,:,:]);d[:,:,0]=np.minimum(d[:,:,0],1024-d[:,:,0]);mats[ver+'_cyclic'][i,j]=math.sqrt(a.st.cyclic_cost((d*d).sum(2),200.)/max(len(ea),len(eb)))
            if 'unique_flagged_alternative'in [rinfo[ids[i]][2],rinfo[ids[j]][2]]:
                pairs.append(dict(code=a.AUD.loc[ids[i],'code'],condition=key[1],id_a=ids[i],id_b=ids[j],**{k:v[i,j]for k,v in mats.items()}))
        for v in mats.values():v+=v.T
        cnt=np.array([a.RECS[cid]['effective_point_count']for cid in ids])
        for met,cut,gate in [('mask',.1,False),('mask',.1,True),('cyclic',8.,False),('cyclic',12.,False)]:
            l0=a.complete(mats['old_'+met],cut,cnt if gate else None);l1=a.complete(mats['alt_'+met],cut,cnt if gate else None);eq0=l0[:,None]==l0[None,:];eq1=l1[:,None]==l1[None,:];changes=int((eq0!=eq1).sum()//2)
            rows.append(dict(image_id=key[0],code=a.AUD.loc[ids[0],'code'],condition=key[1],metric=met,cut=cut,count_gate=gate,N_old=len(allids),N_common=n,old_clusters=len(set(l0)),alternative_clusters=len(set(l1)),changed_relations=changes,partition_changed=changes>0))
    pd.DataFrame(rows).to_csv(O/'flag_only_unique_partition_impact.csv',index=False);pd.DataFrame(pairs).to_csv(O/'flag_only_unique_changed_pairs.csv',index=False)
    summary=dict(record_statuses=dict(collections.Counter(x[2]for x in rinfo.values())),partitions=pd.DataFrame(rows).groupby(['metric','cut','count_gate']).agg(units=('N_common','size'),changed=('partition_changed','sum'),changed_relations=('changed_relations','sum')).reset_index().to_dict('records'))
    # Compare original raw-order variants and local distance for the proven b8 example.
    ids=[];boundary=[]
    for w in ['W010','W014']:
        cid=next(cid for cid in rinfo if a.RECS[cid]['worker_id']==w and a.AUD.loc[cid,'code']=='b8cTxDM8gDG-07');ids.append(cid);boundary.append(a.old.dense(a.NS,rinfo[cid][1]))
    delta=np.abs(boundary[0]-boundary[1]);summary['b8_alternative_local_boundary_px']=float(uniform_filter1d(delta.max(0).astype(float),64,mode='wrap').max())
    # Actual triangle proving pairwise compatibility is nontransitive on reviewed data.
    df=pd.read_csv(O/'simple_pointset_pairwise.csv');ms=pd.read_csv(O/'simple_pointset_memberships.csv');lookup={tuple(sorted([r.id_a,r.id_b])):r for r in df.itertuples()}
    reviews=pd.read_csv(O/'user24_relation_comparison.csv');triangle=None
    for r in reviews[reviews.category=='similar_with_tolerance'].itertuples():
        iid,cond,ia,ib=r.key.split('|');q=lookup[tuple(sorted([ia,ib]))]
        for cut in [3.,4.]:
            if q.rms_deg>cut:continue
            lab=ms[(ms.image_id==iid)&(ms.condition==cond)&(ms.method==f'rms_deg_cut{cut:g}')].set_index('id').cluster
            if lab[ia]==lab[ib]:continue
            for ic in lab.index:
                if ic in [ia,ib]:continue
                ac=lookup[tuple(sorted([ia,ic]))];bc=lookup[tuple(sorted([ib,ic]))]
                if (ac.rms_deg<=cut<bc.rms_deg)or(bc.rms_deg<=cut<ac.rms_deg):
                    triangle=dict(code=r.code,condition=cond,cut_deg=cut,worker_A=a.RECS[ia]['worker_id'],worker_B=a.RECS[ib]['worker_id'],worker_C=a.RECS[ic]['worker_id'],AB=q.rms_deg,AC=ac.rms_deg,BC=bc.rms_deg,cluster_A=int(lab[ia]),cluster_B=int(lab[ib]),cluster_C=int(lab[ic]));break
            if triangle:break
        if triangle:break
    summary['nontransitive_actual_triangle']=triangle
    stress=[]
    for code,cond,wa,wb in [('rPc6DW4iMge-20','manual','W034','W037'),('X7HyMhZNoso-19','manual','W011','W015'),('rPc6DW4iMge-15','manual','W002','W011'),('e9zR4mvMWw7-10','semi','W035','W006')]:
        ia=next(cid for cid,r in a.RECS.items()if a.AUD.loc[cid,'code']==code and r['raw_condition']==cond and r['worker_id']==wa);ib=next(cid for cid,r in a.RECS.items()if a.AUD.loc[cid,'code']==code and r['raw_condition']==cond and r['worker_id']==wb);q=lookup[tuple(sorted([ia,ib]))]
        row=dict(code=code,condition=cond,worker_a=wa,worker_b=wb,rms_deg=q.rms_deg,bottleneck_deg=q.bottleneck_deg)
        for met in ['rms_deg_cut3','rms_deg_cut4','bottleneck_deg_cut6']:
            labels=ms[(ms.method==met)&ms.id.isin([ia,ib])].cluster;row[met+'_samecluster']=bool(labels.nunique()==1)
        stress.append(row)
    pd.DataFrame(stress).to_csv(O/'older_cases_pointset_stress.csv',index=False)
    a.save('focused_checks.json',summary);print(json.dumps(a.old.safe_json(summary),indent=2))
if __name__=='__main__':run()
