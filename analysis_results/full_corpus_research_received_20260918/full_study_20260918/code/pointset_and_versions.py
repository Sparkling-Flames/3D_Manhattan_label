"""SOP point-set view and explicit no-imputation/pending-export sensitivities.
OSPA uses raw POINT endpoints without inventing pairing, adjacency, or semantic events.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,gzip,collections,itertools,math,argparse
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score
import clustering_study as st
import legacy_reproduction as old
from full_corpus import method_grid

def xyz(p):
    p=np.asarray(p,float);u=((p[:,0]+.5)/1024-.5)*2*np.pi;v=((p[:,1]+.5)/512-.5)*np.pi
    return np.column_stack([np.cos(v)*np.cos(u),np.cos(v)*np.sin(u),np.sin(v)])
def ospa(a,b,c=30.):
    A=xyz(a);B=xyz(b);d=np.rad2deg(np.arccos(np.clip(A@B.T,-1,1)));ii,jj=linear_sum_assignment(np.minimum(d,c));return float((np.minimum(d[ii,jj],c).sum()+abs(len(A)-len(B))*c)/max(len(A),len(B)))
def run(root):
    inp=root/'inputs/frozen';out=root/'results';k=json.loads((inp/'key39/data.json').read_text());ns=old.legacy_functions(k)
    raw=[json.loads(l)for l in gzip.open(inp/'human/responses.jsonl.gz','rt')];rows=[r for r in raw if r['worker_id']not in ['W019','W026']]
    audit=pd.read_csv(out/'all_response_audit.csv');codes=dict(zip(audit.image_id,audit.code));groups=collections.defaultdict(list);summ=[];mem=[];pairs=[]
    for r in rows:
        if not r['calculation_included']:continue
        p=np.array(r['effective_points_1024x512'],float)
        if p.ndim==2 and p.shape[1]==2 and len(p)>0 and np.isfinite(p).all() and ((p[:,0]>=0)&(p[:,0]<=1024)&(p[:,1]>=0)&(p[:,1]<=512)).all():groups[(r['image_id'],r['raw_condition'])].append(r)
    for (iid,cond),rr in sorted(groups.items()):
        rr=sorted(rr,key=lambda r:r['worker_id']);n=len(rr);D=np.zeros((n,n));counts=np.array([len(r['effective_points_1024x512'])for r in rr])
        for i,j in itertools.combinations(range(n),2):
            d=ospa(rr[i]['effective_points_1024x512'],rr[j]['effective_points_1024x512']);D[i,j]=D[j,i]=d
            pairs.append(dict(image_id=iid,condition=cond,id_a=rr[i]['canonical_annotation_id'],id_b=rr[j]['canonical_annotation_id'],ospa30_deg=d))
        for gate in [False,True]:
            for cut in [3.,6.,9.]:
                l=old.clust(D,counts if gate else None,cut);name=f'OSPA30_c{int(cut)}_gate{int(gate)}'
                summ.append(dict(image_id=iid,code=codes[iid],condition=cond,N=n,method=name,**old.cluster_stats(l)))
                for i,r in enumerate(rr):mem.append(dict(image_id=iid,code=codes[iid],condition=cond,N=n,method=name,id=r['canonical_annotation_id'],worker=r['worker_id'],cluster=int(l[i]),point_count=int(counts[i]),pairing_available=ns['normalize_geometry'](r['effective_points_1024x512'])['valid']))
    for name,x in [('pointset_summary',summ),('pointset_memberships',mem),('pointset_pairwise',pairs)]:pd.DataFrame(x).to_csv(out/(name+'.csv'),index=False)
    cache=json.loads((out/'group_cache.json').read_text());changed=[];vsummary=[];ps_versions=[]
    variants={'no_borrowed_imputation':{},'pending_two_export_updates':{}}
    for r in rows:
        if r['imputed_point']:variants['no_borrowed_imputation'][r['canonical_annotation_id']]=r['raw_points_1024x512']
    for change in k['pending_export_update']['changes']:
        variants['pending_two_export_updates'][change['canonical_annotation_id']]=change['new_raw_points_1024x512']
    for version,updates in variants.items():
        targets={(r['image_id'],r['raw_condition'])for r in rows if r['canonical_annotation_id']in updates}
        for (iid,cond)in targets:
            prs=[]
            for r in sorted([a for a in rows if a['image_id']==iid and a['raw_condition']==cond],key=lambda x:x['worker_id']):
                cid=r['canonical_annotation_id'];p=updates.get(cid,r['effective_points_1024x512'])
                if (not r['calculation_included']) and cid not in updates:continue
                a=np.asarray(p,float)
                if a.ndim!=2 or a.shape[1]!=2 or not len(a) or not np.isfinite(a).all():continue
                if not ((a[:,0]>=0)&(a[:,0]<=1024)&(a[:,1]>=0)&(a[:,1]<=512)).all():continue
                prs.append((r,a))
            pdm=np.zeros((len(prs),len(prs)))
            for i,j in itertools.combinations(range(len(prs)),2):pdm[i,j]=pdm[j,i]=ospa(prs[i][1],prs[j][1])
            for gate in [False,True]:
                for cut in [3.,6.,9.]:
                    pl=old.clust(pdm,np.array([len(a)for r,a in prs])if gate else None,cut)
                    for i,(r,a)in enumerate(prs):ps_versions.append(dict(version=version,image_id=iid,code=codes[iid],condition=cond,method=f'OSPA30_c{int(cut)}_gate{int(gate)}',id=r['canonical_annotation_id'],worker=r['worker_id'],points=len(a),cluster=int(pl[i])))
            rr=[]
            for r in sorted([a for a in rows if a['image_id']==iid and a['raw_condition']==cond],key=lambda x:x['worker_id']):
                cid=r['canonical_annotation_id'];p=updates.get(cid,r['effective_points_1024x512']);norm=ns['normalize_geometry'](p)
                if cid in updates:changed.append(dict(version=version,id=cid,worker=r['worker_id'],image_id=iid,code=codes[iid],old_points=r['effective_point_count'],new_points=len(p),new_valid=norm['valid'],new_reason=norm['reason']))
                if not norm['valid']:continue
                if not r['calculation_included'] and cid not in updates:continue
                a={**r,'id':cid,'norm':norm,'events':old.pairs3(norm),'boundary':old.dense(ns,norm),'native':None};a['effective_point_count']=len(p);rr.append(a)
            ds=st.pair_matrices(rr);counts=np.array([r['effective_point_count']for r in rr]);base=cache[iid+'|'+cond]
            for name,l,no,D in method_grid(ds,counts):
                shared=[(j,base['ids'].index(r['id']))for j,r in enumerate(rr)if r['id']in base['ids']]
                la=[l[j]for j,b in shared];lb=[base['labels'][name][b]for j,b in shared]
                vsummary.append(dict(version=version,image_id=iid,code=codes[iid],condition=cond,method=name,N=len(rr),N_base=len(base['ids']),N_shared=len(shared),shared_ARI=adjusted_rand_score(la,lb),**old.cluster_stats(l)))
    pd.DataFrame(changed).to_csv(out/'input_version_changes.csv',index=False);pd.DataFrame(vsummary).to_csv(out/'input_version_partition_sensitivity.csv',index=False)
    pd.DataFrame(ps_versions).to_csv(out/'pointset_input_version_memberships.csv',index=False)
    tests={'ospa_identity_max':0.}
    for r in rows[:10]:
        p=r['effective_points_1024x512']
        if p:tests['ospa_identity_max']=max(tests['ospa_identity_max'],ospa(p,p))
    assert tests['ospa_identity_max']<1e-5
    tests['pointset_eligible_records']=sum(map(len,groups.values()));tests['no_imputation_record_ids']=list(variants['no_borrowed_imputation']);tests['pending_export_record_ids']=list(variants['pending_two_export_updates'])
    old.save_json(out/'pointset_version_tests.json',tests)
    print(pd.DataFrame(summ).groupby('method')[['clusters','singletons']].sum());print(pd.DataFrame(changed).to_string(index=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);run(p.parse_args().root)
