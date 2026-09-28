"""Measurement audit. All proposed correspondences are diagnostics, not semantic repairs."""
import common as c
import sys, json, gzip, hashlib,itertools,collections,math
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.stats import spearmanr

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    from tools.thesis_main.analysis.paired_split_research.study import bottleneck,cyclic
    rows,rec,views,registry,eligible=c.load()
    c.save('eligibility_reconstructed.csv.gz',eligible)
    orig=c.SOURCE/'analysis_results/new_manual_reviewed_20260921'
    re=c.SOURCE/'analysis_results/pro_research_handoff_20260921/recomputed'
    checks={};diff=[]
    def compare(a,b,path):
        if isinstance(a,dict):
            assert a.keys()==b.keys(),path
            for k in a:compare(a[k],b[k],path+'/'+str(k))
        elif isinstance(a,list):
            assert len(a)==len(b),path
            for j,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(j))
        elif a!=b:
            assert isinstance(a,(int,float)) and isinstance(b,(int,float)),(path,a,b)
            diff.append(dict(path=path,original=a,recomputed=b,absolute_error=abs(a-b)))
    for p in sorted(orig.glob('*.json')):
        q=re/p.name
        if q.exists():
            a,b=json.loads(p.read_text()),json.loads(q.read_text());checks[p.name]={'exact_equal':a==b}
            if a!=b:compare(a,b,p.name)
    for name in ['responses.jsonl.gz']:
        a=[json.loads(z) for z in gzip.open(orig/name,'rt')];b=[json.loads(z) for z in gzip.open(re/name,'rt')]
        checks[name]={'parsed_exact_equal':a==b}
    c.save('validation.json',dict(pinned_commit='ce43b2883f63ec1538cffdfe5feca8e2b24518dc',
        archive_sha256=next((hashlib.sha256(z.read_bytes()).hexdigest() for z in [c.ROOT/'source_snapshot.zip',c.SOURCE.parent/'source_export/pro_research_20260921.zip'] if z.exists()),None),
        checks=checks,n_scalar_roundoff=len(diff),max_absolute_error=max((z['absolute_error'] for z in diff),default=0.),
        recommended_tolerance={'rtol':1e-12,'atol':1e-10},all_differences_within_tolerance=all(np.isclose(z['original'],z['recomputed'],atol=1e-10,rtol=1e-12) for z in diff),
        shipped_strict_verify=('failed exact floating JSON equality; do not report verbatim pass' if diff else 'exact JSON comparison passed'),tests='see logs/tests_source.log for the separately executed source test suite',
        main_view={'images':len(views),'responses':sum(v['N'] for v in views.values()),'workers':len(set(w for v in views.values() for w in v['workers'])),'buildings':len(set(v['building'] for v in views.values()))}))
    c.save('floating_roundoff.csv.gz',pd.DataFrame(diff))
    # Verify reconstructed independent distances against source submatrices.
    source_ds=c.read('analysis_results/new_manual_reviewed_20260921/distances.json')
    maxdiff=0.;verified_pairs=0
    for g in source_ds:
        if g['condition'] not in ['manual','oos']:continue
        v=views[g['image_id']];lookup={cid:j for j,cid in enumerate(v['ids'])};s=np.array(g['image'])
        inds=[j for j,cid in enumerate(g['ids']) if cid in lookup]
        dest=[lookup[g['ids'][j]] for j in inds]
        if inds:maxdiff=max(maxdiff,float(abs(v['d'][np.ix_(dest,dest)]-s[np.ix_(inds,inds)]).max()));verified_pairs+=len(inds)*(len(inds)-1)//2
    assert maxdiff<1e-10
    pairs=[];images=[];localp=[];members=[];workers=[]
    for iid,v in sorted(views.items()):
        n=v['N'];d=v['d'];tri=np.triu_indices(n,1)
        counts=np.array([r['effective_point_count'] for r in v['rows']]);ct=collections.Counter(counts)
        base={k:v[k] for k in ['image_id','code','building','N']}
        info=dict(base,point_counts=';'.join(f'{k}:{z}' for k,z in sorted(ct.items())),unique_counts=len(ct),
            count_mode_share=max(ct.values())/n,count_disagreement=np.mean(counts[tri[0]]!=counts[tri[1]]) if n>1 else np.nan,
            pair_disagreement=np.mean(d[tri]>c.CUT) if n>1 else np.nan,
            newer_responses=sum(r['stage']=='scene_stability_stage1' for r in v['rows']))
        for k in [2,3,5,8,10,12,15,18,20,23]:info[f'U{k}']=c.next_uncovered(d,k)
        for kind in ['complete','representative']:
            for cut in [12.8,25.6,51.2]:
                lab,cent=c.part(d,v['ids'],kind,cut);ns=collections.Counter(lab);key=f'{kind}_{cut:g}'
                eq=lab[:,None]==lab[None,:]
                info[key+'_K']=len(ns);info[key+'_single_mass']=sum(z for z in ns.values() if z==1)/n
                info[key+'_repeated_modes']=sum(z>=2 for z in ns.values())
                info[key+'_largest_share']=max(ns.values())/n
                if cut==c.CUT:
                    info[key+'_near_split_count']=int(((d<=cut)&(~eq))[tri].sum())
                    info[key+'_far_join_count']=int(((d>cut)&eq)[tri].sum())
                    for j,cid in enumerate(v['ids']):members.append(dict(base,method=kind,id=cid,worker=v['workers'][j],label=int(lab[j]),cluster_size=ns[lab[j]]))
        images.append(info)
        for j,r in enumerate(v['rows']):
            rest=np.arange(n)!=j
            workers.append(dict(base,id=r['canonical_annotation_id'],worker=r['worker_id'],point_count=int(counts[j]),
                pair_disagreement=float(np.mean(d[j,rest]>c.CUT)) if n>1 else np.nan,
                count_disagreement=float(np.mean(counts[rest]!=counts[j])) if n>1 else np.nan,
                stage=r['stage'],new=r['stage']=='scene_stability_stage1'))
        for ia,ib in itertools.combinations(range(n),2):
            ra,rb=[rec[v['ids'][j]] for j in [ia,ib]];a,b=ra['p'][ra['links']],rb['p'][rb['links']]
            dx=abs((a[:,None,:,0]-b[None,:,:,0]+512)%1024-512);dy=abs(a[:,None,:,1]-b[None,:,:,1])
            per=np.hypot(dx,dy);C=per.max(2);good=C<=c.CUT
            aa,bb=linear_sum_assignment(np.where(good,C/1e5,1.))
            matched=int(good[aa,bb].sum())
            z=dict(base,a_id=v['ids'][ia],b_id=v['ids'][ib],a_worker=v['workers'][ia],b_worker=v['workers'][ib],
                   a_pairs=len(a),b_pairs=len(b),same_count=len(a)==len(b),partial_matching_fraction=matched/max(len(a),len(b)),partial_matched=matched)
            if len(a)==len(b):
                q=np.arange(len(a));ends=per[q,q];dx0=dx[q,q];dy0=dy[q,q];corner=ends.max(1)
                bc,perm=bottleneck(C);cy,shift,margin=cyclic(C)
                cyc = list(np.roll(np.arange(len(a)),shift)) # saved shift only; matching actual cost is authoritative
                maxidx=np.unravel_index(ends.argmax(),ends.shape)
                z.update(fixed_max=ends.max(),endpoint_median=np.median(ends),endpoint_q90=np.quantile(ends,.9),endpoint_rms=np.sqrt((ends**2).mean()),
                    n_endpoint_fail=int((ends>c.CUT).sum()),n_corner_fail=int((corner>c.CUT).sum()),corner_near_share=np.mean(corner<=c.CUT),
                    top_max=ends[:,0].max(),bottom_max=ends[:,1].max(),max_dx=dx0.max(),max_dy=dy0.max(),
                    bottleneck_role='top' if maxidx[1]==0 else 'bottom',bottleneck_a_raw_point=int(ra['links'][maxidx])+1,
                    bottleneck_b_raw_point=int(rb['links'][maxidx])+1,cyclic_max=cy,cyclic_shift=int(shift),free_max=bc,
                    free_mapping_1based=';'.join(str(int(x)+1) for x in perm))
                z['diagnostic_case']='fixed_near' if ends.max()<=c.CUT else 'cyclic_rescue' if cy<=c.CUT else 'free_only_rescue' if bc<=c.CUT else 'still_far'
            else:z['diagnostic_case']='count_gate'
            pairs.append(z)
        # Local versus joint measurements conditional on SAME effective count, not on all responses.
        for count,nn in sorted(ct.items()):
            ix=np.flatnonzero(counts==count)
            if nn<4:continue
            prs=np.array([rec[v['ids'][j]]['p'][rec[v['ids'][j]]['links']] for j in ix]);m=count//2
            dx=abs((prs[:,None,:,:,0]-prs[None,:,:,:,0]+512)%1024-512)
            dy=abs(prs[:,None,:,:,1]-prs[None,:,:,:,1]);locald=np.hypot(dx,dy).max(3)
            joint=locald.max(2);assert np.allclose(joint,d[np.ix_(ix,ix)])
            for k in [3,5,8,12,15,18,20]:
                if k>=nn:continue
                us=[c.next_uncovered(locald[:,:,j],k) for j in range(m)]
                localp.append(dict(base,count=int(count),count_pool_N=int(nn),count_pool_share=nn/n,k=k,
                    joint_U=c.next_uncovered(joint,k),local_mean_U=np.mean(us),local_max_U=max(us),local_U=';'.join(map(str,us))))
    pf=pd.DataFrame(pairs);im=pd.DataFrame(images);lp=pd.DataFrame(localp);wr=pd.DataFrame(workers)
    c.save('pair_diagnostics.csv.gz',pf);c.save('image_metrics.csv',im);c.save('local_vs_joint.csv',lp)
    c.save('current_memberships.csv',pd.DataFrame(members));c.save('response_metrics.csv',wr)
    same=pf[pf.same_count];far=same[same.fixed_max>c.CUT];counts=pf.diagnostic_case.value_counts().to_dict()
    sub=im[im.N>=8]
    summary=dict(distance_reconstruction_max_error=maxdiff,verified_source_pairs=verified_pairs,
        response_N_distribution=im.N.value_counts().sort_index().to_dict(),n_images_at_least={str(k):int((im.N>=k).sum()) for k in [2,4,5,8,10,12,15,18,20,24]},
        n_pairs=len(pf),diagnostic_case_counts=counts,same_count_pairs=len(same),
        far_same_count_single_endpoint=int((far.n_endpoint_fail==1).sum()),far_same_count_single_corner=int((far.n_corner_fail==1).sum()),
        far_same_count_most_80pct_corners_near=int((far.corner_near_share>=.8).sum()),
        different_count_partial80=int(((~pf.same_count)&(pf.partial_matching_fraction>=.8)).sum()),
        bottleneck_role=far.bottleneck_role.value_counts().to_dict(),
        n_ge8_images=len(sub),methods={},
        local_at8={'pools':int((lp.k==8).sum()),'locally_mean_le02_joint_ge05':int(((lp.k==8)&(lp.local_mean_U<=.2)&(lp.joint_U>=.5)).sum()),
                   'all_corners_le02_joint_ge05':int(((lp.k==8)&(lp.local_max_U<=.2)&(lp.joint_U>=.5)).sum())},
        qualifications='Count mismatches and optimal matching rescues are measurable sensitivities, not adjudicated error fractions. Local pools exclude other point counts.')
    for kind in ['complete','representative']:
        summary['methods'][kind]={}
        for cut in [12.8,25.6,51.2]:
            k=f'{kind}_{cut:g}'
            summary['methods'][kind][cut]=dict(median_K_ge8=sub[k+'_K'].median(),mean_single_mass_ge8=sub[k+'_single_mass'].mean(),
                unified_ge8=int((sub[k+'_K']==1).sum()))
        summary['methods'][kind]['near_split_count']=int(im[f'{kind}_25.6_near_split_count'].sum())
        summary['methods'][kind]['far_join_count']=int(im[f'{kind}_25.6_far_join_count'].sum())
    # One accepted cross-response map, never promoted to a default automated distance.
    aa,bb=rec['8178591994d42ce3'],rec['a4e0cac5adec2e1e']
    from tools.thesis_main.analysis.clustering_release.local_points import endpoint_rows
    old=endpoint_rows(aa,bb);new=endpoint_rows(aa,bb,[1,2,4,3,5,6])
    summary['uNb21_approved_mapping']={'a':'8178591994d42ce3','b':'a4e0cac5adec2e1e','fixed_max':max(x['image_px'] for x in old),'reviewed_max':max(x['image_px'] for x in new),'mapping':[1,2,4,3,5,6]}
    c.save('uNb21_endpoint_before_after.json',dict(fixed=old,reviewed=new))
    c.save('measurement_summary.json',summary)
    print(json.dumps(c.clean(summary),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
