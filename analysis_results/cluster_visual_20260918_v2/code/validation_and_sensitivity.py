"""Read-only validation and all-record sensitivity. No outcome or identity-based exclusions."""
from pathlib import Path
import json,hashlib,itertools,math,platform
import numpy as np,pandas as pd
from scipy.spatial.distance import squareform
from sklearn.metrics import adjusted_rand_score
import sklearn,scipy,numba
import clustering_study as st
import spherical_followup as sp
import legacy_reproduction as old
R=Path(__file__).resolve().parents[1]

def run():
    b=(R/'inputs/key39/data.json').read_bytes(); data=json.loads(b)
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==old.DATA_BLOB
    manifest=json.loads((R/'inputs/pixels/MANIFEST.json').read_text())
    for m in manifest:
        assert m['status']=='downloaded'
        assert hashlib.sha256((R/'inputs/pixels'/m['local']).read_bytes()).hexdigest()==m['sha256']
    ns,rec,cov=st.prep(data)
    rows=[];members=[]
    for case in data['cases']:
        for cond in sorted(set(r['raw_condition'] for r in case['responses'])):
            rr=[rec[r['canonical_annotation_id']] for r in case['responses'] if r['raw_condition']==cond and rec[r['canonical_annotation_id']]['norm']['valid']]
            if not rr:continue
            ids=[r['canonical_annotation_id'] for r in rr];assert len(ids)==len(set(ids))
            D=st.pair_matrices(rr); counts=np.array([len(r['events'])*2 for r in rr])
            for method in st.METHODS:
                lab,no,dd,ex=st.apply(method,D,counts)
                rows.append(dict(code=case['code'],condition=cond,N=len(rr),method=method,**old.cluster_stats(lab),density_unassigned=int(no.sum())))
                for i,r in enumerate(rr):members.append(dict(code=case['code'],condition=cond,N=len(rr),method=method,id=r['canonical_annotation_id'],worker=r['worker_id'],cluster=int(lab[i]),density_unassigned=bool(no[i])))
    pd.DataFrame(rows).to_csv(R/'results/all_normalizable_summary.csv',index=False)
    pd.DataFrame(members).to_csv(R/'results/all_normalizable_memberships.csv',index=False)
    rng=np.random.default_rng(20260918);tests={}
    for repeat in range(40):
        m,n=rng.integers(1,5,size=2)
        a=np.column_stack([np.sort(rng.uniform(0,1024,m)),rng.uniform(100,200,m),rng.uniform(300,400,m)])
        b2=np.column_stack([np.sort(rng.uniform(0,1024,n)),rng.uniform(100,200,n),rng.uniform(300,400,n)])
        d=abs(a[:,None,:]-b2[None,:,:]);d[:,:,0]=np.minimum(d[:,:,0],1024-d[:,:,0]);C=np.sum(d*d,axis=2)
        actual=st.cyclic_cost(C,200.)
        assert np.isclose(actual,old.brute(a,b2,20))
        assert np.isclose(actual,old.cyclic_partial(a,b2,20)['total_squared'])
        assert np.isclose(actual,st.cyclic_cost(C.T,200.))
        assert np.isclose(actual,st.cyclic_cost(np.roll(C,1,0),200.))
        assert np.isclose(actual,st.cyclic_cost(np.roll(C,1,1),200.))
    tests['cyclic_DP_brute_reference_symmetry_cyclic_order_instances']=40
    a=np.array([[100,160,350],[350,160,350],[600,160,350],[850,160,350]],float)
    synthetic=[]
    for dx in [19,21]:
        bb=a.copy();bb[:,0]+=dx
        z=old.cyclic_partial(a,bb,20);synthetic.append(dict(x_shift=dx,**z))
    assert synthetic[0]['matched_pairs']==4 and synthetic[0]['localization_squared']==1444
    assert synthetic[1]['matched_pairs']==0 and synthetic[1]['unmatched_squared']==1600
    tests['pure_localization_cutoff_counterexample']=synthetic
    # This three-point example changes hierarchical order without changing any threshold edge.
    d1=np.array([[0,.04,.11],[.04,0,.045],[.11,.045,0]])
    d2=np.array([[0,.05,.11],[.05,0,.045],[.11,.045,0]])
    l1=old.clust(d1,None,.1);l2=old.clust(d2,None,.1)
    assert np.array_equal(d1<=.1,d2<=.1) and adjusted_rand_score(l1,l2)<1
    tests['zero_threshold_flips_but_changed_hierarchy']={'before':l1.tolist(),'after':l2.tolist(),'ARI':adjusted_rand_score(l1,l2)}
    ds=np.array([[0,.1,.3,.4],[.1,0,.2,.3],[.3,.2,0,.1],[.4,.3,.1,0]])
    original=ds.copy();st.density_labels(ds);assert np.array_equal(ds,original)
    tests['HDBSCAN_does_not_mutate_precomputed_input']=True
    # Compare spherical formula to repository pano_connect_points using direct 3D line/ray solve.
    maxerr=0.
    for r in list(rec.values()):
        if not r['norm']['valid']:continue
        e=r['events'];curve,reason=sp.spherical_boundary(e)
        if curve is None:continue
        assert -1e-12<=sp.solid_iou(curve,curve)<=1e-12
        er=e.copy();er[:,0]=(er[:,0]+137)%1024
        shifted,_=sp.spherical_boundary(er)
        assert np.allclose(shifted,np.roll(curve,137,axis=1),atol=1e-9)
        for k in range(len(e)):
            for endpoint,z in [(1,-50),(2,50)]:
                p1=e[k,[0,endpoint]];p2=e[(k+1)%len(e),[0,endpoint]]
                u1=((p1[0]+.5)/1024-.5)*2*np.pi;u2=((p2[0]+.5)/1024-.5)*2*np.pi
                v1=((p1[1]+.5)/512-.5)*np.pi;v2=((p2[1]+.5)/512-.5)*np.pi
                q1=z/np.tan(v1)*np.array([np.cos(u1),np.sin(u1)]);q2=z/np.tan(v2)*np.array([np.cos(u2),np.sin(u2)])
                lo=p1[0];hi=p2[0] if p2[0]>lo else p2[0]+1024
                xx=np.arange(np.ceil(lo),np.floor(hi)+1)%1024
                u=((xx+.5)/1024-.5)*2*np.pi;v=q2-q1
                t=(np.tan(u)*q1[0]-q1[1])/(v[1]-np.tan(u)*v[0])
                radius=np.linalg.norm(q1[None,:]+t[:,None]*v[None,:],axis=1)
                yy=(np.arctan2(z,radius)/np.pi+.5)*512-.5
                if len(xx):maxerr=max(maxerr,float(np.max(abs(curve[endpoint-1,xx.astype(int)]-yy))))
    assert maxerr<1e-7
    tests['spherical_vs_repository_3D_line_projection_max_abs_px']=maxerr
    tests['spherical_periodic_shift_and_identity_for_every_available_record']=True
    tests['all_39_image_SHA256_match']=True
    tests['key39_source_blob_unchanged']=True
    tests['versions']={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'numba':numba.__version__}
    old.save_json(R/'results/validation_tests.json',tests)
    print(pd.DataFrame(rows).groupby('method')[['N','clusters','singletons','density_unassigned']].sum().to_string())
    print(json.dumps(old.safe_json(tests),ensure_ascii=False,indent=2))
if __name__=='__main__':run()
