"""Read-only geometric audit. No point sorting, fitting, relabeling, or raw writes.
Projected curves join each original adjacent pair by its great-circle plane.
Uniform ERP-area and spherical-solid-angle band Jaccards are separate outputs.
"""
from pathlib import Path
from collections import Counter,defaultdict
from itertools import combinations
import json, math, hashlib, argparse
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely.geometry import Polygon, Point

ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1'
OUT=ROOT/'analysis_results/visual_takeover_20260906_v1'
SEED=20260906

def truth(x): return str(x).lower() in ('true','1')
def csv(p): return pd.read_csv(p,dtype=str,keep_default_na=False)
def js(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def jl(p): return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def save(name, rows):
    q=OUT/name;q.parent.mkdir(parents=True,exist_ok=True)
    (rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)).to_csv(q,index=False)
def dump(name,obj):
    q=OUT/name;q.parent.mkdir(parents=True,exist_ok=True)
    q.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def rays(points):
    a=np.asarray(points,float);u=2*np.pi*(a[:,0]/1024-.5);v=np.pi*(.5-a[:,1]/512)
    return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
def project(xyz):
    a=np.asarray(xyz,float)
    return np.c_[((np.arctan2(a[:,0],-a[:,2])/2/np.pi+.5)*1024)%1024,
                 (.5-np.arctan2(a[:,1],np.hypot(a[:,0],a[:,2]))/np.pi)*512]

def boundary(points, n=1024, projected=True):
    a=np.asarray(points,float);x=a[:,0]/1024;y=a[:,1]
    delta=(np.roll(x,-1)-x+.5)%1-.5
    if np.any(abs(delta)<1e-8): raise ValueError('duplicate_azimuth_edge')
    if not (np.all(delta>0) or np.all(delta<0)) or abs(abs(delta.sum())-1)>1e-6:
        raise ValueError('non_single_circular_order_or_nonstar_projection')
    gx=(np.arange(n)+.5)/n; result=np.full(n,np.nan)
    v=np.pi*(.5-y/512)
    if np.any(abs(v)>=np.pi/2-1e-8):raise ValueError('pole_endpoint')
    for i,d in enumerate(delta):
        t=((gx-x[i])%1)/d if d>0 else -((x[i]-gx)%1)/d
        use=(t>=0)&(t<1+1e-10)
        z=t[use]
        if projected:
            du=d*2*np.pi
            if abs(np.sin(du))<1e-8:raise ValueError('antipodal_edge')
            q=(np.tan(v[i])*np.sin((1-z)*du)+np.tan(v[(i+1)%len(a)])*np.sin(z*du))/np.sin(du)
            result[use]=(.5-np.arctan(q)/np.pi)*512
        else:result[use]=(1-z)*y[i]+z*y[(i+1)%len(a)]
    if not np.all(np.isfinite(result)):raise ValueError('incomplete_angular_coverage')
    return result

def pair_roles(points):
    a=np.asarray(points,float)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)<6 or len(a)%2:raise ValueError('odd_or_insufficient_points')
    if not np.isfinite(a).all() or np.any(a<0) or np.any(a[:,0]>1024) or np.any(a[:,1]>512):raise ValueError('nonfinite_or_out_of_bounds')
    pairs=a.reshape(-1,2,2)
    if np.any((pairs[:,0,1]-256)*(pairs[:,1,1]-256)>=0):raise ValueError('both_endpoints_same_hemisphere_or_horizon')
    idx=np.arange(len(a)).reshape(-1,2)
    reverse=pairs[:,0,1]>pairs[:,1,1]
    idx[reverse]=idx[reverse,::-1]
    return a[idx.ravel()].copy(),idx.ravel().tolist()

def bands(points,n=1024,projected=True):
    a=np.asarray(points,float)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)<6 or len(a)%2:raise ValueError('odd_or_insufficient_points')
    if not np.isfinite(a).all() or np.any(a<0) or np.any(a[:,0]>1024) or np.any(a[:,1]>512):raise ValueError('nonfinite_or_out_of_bounds')
    a,_=pair_roles(a) # role interpretation only; original adjacent pairs and corner cycle unchanged
    b=np.array([boundary(a[::2],n,projected),boundary(a[1::2],n,projected)])
    if np.any(b[0]>=b[1]):raise ValueError('crossed_boundaries')
    return b

def distance(a,b,solid=False):
    if solid:
        # Equal azimuth columns, integral cos(elevation) d(elevation).
        a=-np.sin(np.pi*(.5-a/512));b=-np.sin(np.pi*(.5-b/512))
    inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])).sum()
    union=(a[1]-a[0]).sum()+(b[1]-b[0]).sum()-inter
    return float(1-inter/union) if union>1e-12 else float('nan')

def assess(points):
    a=np.asarray(points,float);r={'endpoint_count':len(a) if a.ndim else 0}
    try:
        resolved,mapping=pair_roles(a)
        r.update(endpoint_role_map=json.dumps(mapping),endpoint_role_swaps=sum(i!=j for i,j in enumerate(mapping))//2,corner_adjacency_changed=False)
        b=bands(resolved);l=bands(resolved,projected=False)
        dx=abs((a[::2,0]-a[1::2,0]+512)%1024-512)
        r.update(projected_ok=True,pair_dx_max=float(dx.max()),pair_misaligned=bool(dx.max()>1e-6),reason='')
        return r,b,l
    except (ValueError,IndexError,TypeError) as e:r.update(projected_ok=False,pair_dx_max=None,pair_misaligned=None,reason=str(e));return r,None,None

def matrix(ids,cache):
    n=len(ids);out=np.zeros((n,n))
    for i,j in combinations(range(n),2):out[i,j]=out[j,i]=distance(cache[ids[i]],cache[ids[j]])
    return out

def load():
    ann=csv(P/'annotations.csv.gz'); images=csv(P/'images.csv');parts=csv(P/'clusters/partitions.csv.gz');members=csv(P/'clusters/memberships.csv.gz')
    raw=jl(P/'raw_annotation_versions.jsonl'); models=jl(P/'models/layouts.jsonl'); refs=jl(P/'references.jsonl')
    for r in refs:r.setdefault('layout_id',r['reference_id'])
    norm=csv(P/'facts/geometry_variants.csv.gz');norm=norm[norm.variant=='strict_normalized']
    points={r['canonical_annotation_id']:r['points_1024x512'] for r in raw if truth(r['selected_canonical_version'])}
    normalized={r.canonical_annotation_id:json.loads(r.points_json) for r in norm.itertuples()}
    return ann,images,parts,members,raw,models,refs,points,normalized

def rank_corr(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);ok=np.isfinite(a)&np.isfinite(b)
    if ok.sum()<4 or np.ptp(a[ok])==0 or np.ptp(b[ok])==0:return None
    return float(spearmanr(a[ok],b[ok]).statistic)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    ann,images,parts,members,raw,models,refs,points,norm=load()
    models_by=defaultdict(dict)
    for r in models:models_by[r['image_id']][r['model_family']+'|'+r['head']+'|'+r['source_role']]=r
    ref_by=defaultdict(list)
    for r in refs:ref_by[r['image_id']].append(r)
    layouts=dict(points);layouts.update({r['layout_id']:r['points_1024x512'] for r in models+refs})
    layouts.update({'norm|'+k:v for k,v in norm.items()})
    cache={};linear={};audit=[]
    for key,v in layouts.items():
        r,b,l=assess(v);r.update(layout_key=key);audit.append(r)
        if b is not None:cache[key]=b;linear[key]=l
    save('measurement/layout_parse_audit.csv',audit)
    model_pairs=[]
    for r in images.to_dict('records'):
        mid=r['image_id'];mm=models_by[mid];e=mm[midkey] if (midkey:='Bi-Layout|enclosed|offline_dual_prediction') in mm else None
        x=mm.get('Bi-Layout|extended|offline_dual_prediction');h=mm.get('HoHoNet|single|offline_ep300_replay')
        row={'image_id':mid,'building_id':r['building_id'],'population_role':r['population_role'],'model_count':len(mm),'reference_count':len(ref_by[mid])}
        row['bi_raw_equal']=bool(e and x and e['points_1024x512'] and np.array_equal(e['points_1024x512'],x['points_1024x512']))
        for name,aa,bb in [('bi_gap',e,x),('hoho_bi_enclosed',h,e),('hoho_bi_extended',h,x)]:
            ia=aa['layout_id'] if aa else '';ib=bb['layout_id'] if bb else ''
            row[name]=distance(cache[ia],cache[ib]) if ia in cache and ib in cache else np.nan
            if name=='bi_gap':
                row['bi_linear_same_support']=distance(linear[ia],linear[ib]) if ia in cache and ib in cache else np.nan
                row['bi_solid_angle_gap']=distance(cache[ia],cache[ib],True) if ia in cache and ib in cache else np.nan
        row['reference_projected_count']=sum(r['layout_id'] in cache for r in ref_by[mid])
        model_pairs.append(row)
    modeldf=pd.DataFrame(model_pairs);save('measurement/model_comparisons_380.csv',modeldf)
    responses=[];context_rows=[];pairrows=[]
    proposal=csv(P/'facts/proposal_fact.csv.gz');pr={(r.base_task_id,r.stage):r.initialization_source_kind for r in proposal.itertuples()}
    for context,g in ann.groupby('context_key',sort=True):
        first=g.iloc[0];image=first.base_task_id;mm=models_by[image];e=mm.get('Bi-Layout|enclosed|offline_dual_prediction');x=mm.get('Bi-Layout|extended|offline_dual_prediction')
        ids=[i for i in g.canonical_annotation_id if i in cache]
        row=dict(context_key=context,image_id=image,building_id=first.building_id,stage=first.stage,condition=first.raw_condition,raw_count=len(g),projected_count=len(ids),worker_count=g.worker_id.nunique(),current20_count=sum(g.current20_member.map(truth)),initialization_source_kind=pr.get((image,first.stage),'not_recorded') if first.raw_condition=='semi' else 'manual_or_oos_no_semi_initialization')
        pairs=[]
        for a,b in combinations(ids,2):
            d=distance(cache[a],cache[b]);lin=distance(linear[a],linear[b]);solid=distance(cache[a],cache[b],True)
            pp=dict(context_key=context,left=a,right=b,d_projected=d,d_linear=lin,d_solid_angle=solid)
            pairs.append(pp);pairrows.append(pp)
        row.update(pair_count=len(pairs),d_human_mean=np.mean([z['d_projected'] for z in pairs]) if pairs else np.nan,d_human_linear=np.mean([z['d_linear'] for z in pairs]) if pairs else np.nan,d_human_solid=np.mean([z['d_solid_angle'] for z in pairs]) if pairs else np.nan)
        ni=['norm|'+i for i in g.canonical_annotation_id if 'norm|'+i in cache]
        row['normalized_projected_count']=len(ni)
        row['normalized_projected_mean']=np.mean([distance(cache[a],cache[b]) for a,b in combinations(ni,2)]) if len(ni)>1 else np.nan
        row.update(modeldf.set_index('image_id').loc[image][['bi_gap','bi_raw_equal','bi_linear_same_support','bi_solid_angle_gap']].to_dict())
        context_rows.append(row)
        for r in g.to_dict('records'):
            key=r['canonical_annotation_id'];z=dict(canonical_annotation_id=key,context_key=context,image_id=image,worker_id=r['worker_id'],projected_ok=key in cache)
            for name,m in [('d_enclosed',e),('d_extended',x)]:
                mid=m['layout_id'] if m else '';z[name]=distance(cache[key],cache[mid]) if key in cache and mid in cache else np.nan
            responses.append(z)
    contexts=pd.DataFrame(context_rows);save('analysis/context_metrics.csv',contexts);save('analysis/response_to_bi.csv',responses);save('analysis/pair_distances.csv.gz',pairrows)
    cr=[];membership_checks=[]
    for part in parts.to_dict('records'):
        pm=members[members.partition_id==part['partition_id']]
        membership_checks.append(dict(partition_id=part['partition_id'],version=part['version'],reported=int(part['member_count']),found=len(pm),count_match=len(pm)==int(part['member_count']),raw_only=int((pm.mapping_status=='raw_version_only').sum())))
        if part['version']!='extended73':continue
        mm=models_by[part['image_id']];e=mm.get('Bi-Layout|enclosed|offline_dual_prediction');x=mm.get('Bi-Layout|extended|offline_dual_prediction')
        for cid,gg in pm.groupby('cluster_id',sort=True):
            ids=['norm|'+i for i in gg.canonical_annotation_id if 'norm|'+i in cache]
            rr=dict(partition_id=part['partition_id'],cluster_id=cid,image_id=part['image_id'],context_key=part['context_key'],rank=int(gg.iloc[0]['rank']),original_support=len(gg),projected_support=len(ids),partition_status=part['partition_status'],structure_status=part['structure_status'],display_representative_status='new_metric_medoid_not_archived_representative',semantic_label='not_assigned')
            if ids:
                D=matrix(ids,cache);ix=sorted(range(len(ids)),key=lambda i:(round(D[i].sum(),12),ids[i]))[0];rep=ids[ix];rr['display_representative_id']=rep.removeprefix('norm|')
                rr['within_mean']=float(D.sum()/(len(ids)*(len(ids)-1))) if len(ids)>1 else np.nan
                for label,m in [('enclosed',e),('extended',x)]:
                    mk=m['layout_id'] if m else ''
                    rr['medoid_d_'+label]=distance(cache[rep],cache[mk]) if mk in cache else np.nan
                    rr['mean_d_'+label]=np.mean([distance(cache[i],cache[mk]) for i in ids]) if mk in cache else np.nan
            cr.append(rr)
    save('analysis/membership_checks.csv',membership_checks);cl=pd.DataFrame(cr);save('analysis/existing_cluster_proximity.csv',cl)
    coverage=[]
    for scope,vv in [('all_computable_clusters',cl),('unique_supported_complete',cl[(cl.original_support>=2)&(cl.projected_support==cl.original_support)&(cl.partition_status=='unique')])]:
      for t in [.025,.05,.1]:
        v=vv.dropna(subset=['medoid_d_enclosed','medoid_d_extended'])
        coverage.append(dict(scope=scope,exploratory_radius=t,clusters=len(v),both_close=int(((v.medoid_d_enclosed<=t)&(v.medoid_d_extended<=t)).sum()),neither_close=int(((v.medoid_d_enclosed>t)&(v.medoid_d_extended>t)).sum()),only_E=int(((v.medoid_d_enclosed<=t)&(v.medoid_d_extended>t)).sum()),only_X=int(((v.medoid_d_extended<=t)&(v.medoid_d_enclosed>t)).sum()),interpretation='geometric_proximity_only_no_semantics'))
    save('analysis/cluster_template_coverage.csv',coverage)
    ext=contexts.merge(parts[parts.version=='extended73'][['context_key','cluster_count','partition_status','structure_status']],on='context_key',how='inner',validate='one_to_one')
    ext['cluster_count']=ext.cluster_count.astype(int)
    save('analysis/extended73_metrics.csv',ext)
    assoc=[];rng=np.random.default_rng(SEED)
    subsets={'extended73':ext,'extended73_atleast80percent_projected':ext[(ext.projected_count>=3)&(ext.projected_count>=.8*ext.raw_count)],'all_contexts_n3':contexts[contexts.projected_count>=3],'extended73_without_synthetic':ext[ext.initialization_source_kind!='trap_synthetic_disjoint_source']}
    for name,df in subsets.items():
        groups=[('all',df)]+[(f'{s}|{c}',g) for (s,c),g in df.groupby(['stage','condition'])]
        for group,g in groups:
            for xx,yy in [('bi_gap','d_human_mean'),('bi_linear_same_support','d_human_linear'),('bi_solid_angle_gap','d_human_solid'),('bi_gap','cluster_count')]:
                if yy not in g:continue
                d=g.dropna(subset=[xx,yy]);rho=rank_corr(d[xx],d[yy]);bs=sorted(d.building_id.unique());draw=[]
                if rho is not None and len(bs)>=3:
                    ar=d[[xx,yy]].to_numpy(float);bid=d.building_id.to_numpy();by=[np.flatnonzero(bid==b) for b in bs]
                    for j in range(1000):
                        ii=np.concatenate([by[h] for h in rng.integers(0,len(bs),len(bs))])
                        q=rank_corr(ar[ii,0],ar[ii,1])
                        if q is not None:draw.append(q)
                bm=d.groupby('building_id')[[xx,yy]].mean()
                assoc.append(dict(scope=name,stratum=group,x=xx,y=yy,n_contexts=len(d),n_images=d.image_id.nunique(),n_buildings=len(bs),spearman=rho,conditional_building_ci_low=np.quantile(draw,.025) if draw else np.nan,conditional_building_ci_high=np.quantile(draw,.975) if draw else np.nan,building_mean_spearman=rank_corr(bm[xx],bm[yy]),interval_scope='historical_workers_conditional_not_new_worker_generalization'))
    save('analysis/associations.csv',assoc)
    # Leave-one-worker-out is a sensitivity range, not an inferential interval.
    prow=pd.DataFrame(pairrows);am=ann.set_index('canonical_annotation_id');prow['wa']=prow.left.map(am.worker_id);prow['wb']=prow.right.map(am.worker_id)
    wr=[]
    for w in sorted(ann.worker_id.unique()):
        q=prow[(prow.wa!=w)&(prow.wb!=w)].groupby('context_key').d_projected.mean()
        z=ext[['context_key','bi_gap','stage','condition']].merge(q.rename('target'),on='context_key')
        wr.append(dict(omitted_worker=w,contexts=len(z),rho=rank_corr(z.bi_gap,z.target),role='sensitivity_not_independent_replicates'))
    save('analysis/leave_one_worker_sensitivity.csv',wr)
    h30={r['image_id']:r['review_id'] for r in js(P/'archive/human30.json')['items']}
    a50={r['image_id']:r.get('review_id','R50-'+str(i+1).zfill(3)) for i,r in enumerate(js(P/'archive/ai50_selection.json')['items'])}
    census=images.merge(modeldf.drop(columns=['building_id','population_role']),on='image_id',validate='one_to_one')
    counts=ann.groupby('image_id').agg(historical_rows=('canonical_annotation_id','size'),historical_workers=('worker_id','nunique'),historical_contexts=('context_key','nunique'))
    census=census.merge(counts,on='image_id',how='left');census[['historical_rows','historical_workers','historical_contexts']]=census[['historical_rows','historical_workers','historical_contexts']].fillna(0).astype(int)
    ix=contexts.groupby('image_id').agg(human_projected_mean=('d_human_mean','mean'),raw_projected_count=('projected_count','sum'))
    census=census.merge(ix,on='image_id',how='left');census['human30_id']=census.image_id.map(h30).fillna('');census['ai50_id']=census.image_id.map(a50).fillna('')
    census['extended73_partitions']=census.image_id.map(parts[parts.version=='extended73'].groupby('image_id').size()).fillna(0).astype(int)
    census['historical42_partitions']=census.image_id.map(parts[parts.version=='historical42'].groupby('image_id').size()).fillna(0).astype(int)
    census['bi_numeric_gap_status']=np.where(census.bi_gap.notna(),'computable','not_evaluable_original_order_preserved')
    save('census/images_380.csv',census)
    save('census/by_building.csv',census.groupby(['building_id','population_role']).agg(images=('image_id','size'),annotation_rows=('historical_rows','sum'),bi_equal=('bi_raw_equal','sum'),human30=('human30_id',lambda s:(s!='').sum()),ai50=('ai50_id',lambda s:(s!='').sum())).reset_index())
    checks=[]
    square=np.array([[-3,-1,-3],[3,-1,-3],[3,-1,3],[-3,-1,3]],float)
    def topbottom(f):
        t=f.copy();t[:,1]=.875;arr=np.empty((2*len(f),2));arr[::2]=project(t);arr[1::2]=project(f);return arr
    a=topbottom(square);extra=np.insert(square,1,(square[0]+square[1])/2,axis=0);b=topbottom(extra)
    checks.append(dict(test='collinear_insertion',projected_distance=distance(bands(a),bands(b)),linear_distance=distance(bands(a,projected=False),bands(b,projected=False))))
    for kind,aa in [('cycle_shift',np.roll(a,2,axis=0)),('cycle_reversal',a.reshape(-1,2,2)[::-1].reshape(-1,2))]:
        checks.append(dict(test=kind,projected_distance=distance(bands(a),bands(aa))))
    assert max(abs(c['projected_distance']) for c in checks)<1e-10
    dump('measurement/math_checks.json',checks)
    summary=dict(input_commit='29f628fd5a9c4d3e2064ffffec32bbffb324776c',images=len(census),historical_images=int((census.historical_rows>0).sum()),buildings=census.building_id.nunique(),canonical_rows=len(ann),raw_projectable=sum(k in cache for k in points),normalized_projectable=sum('norm|'+k in cache for k in points),models=len(models),reference_variants=len(refs),partitions=len(parts),extended73=int((parts.version=='extended73').sum()),membership_count_mismatches=sum(not r['count_match'] for r in membership_checks),raw_only_memberships=sum(r['raw_only'] for r in membership_checks),human30_coverage=int((census.human30_id!='').sum()),ai50_coverage=int((census.ai50_id!='').sum()),source_inputs_modified=False,classification_or_scope_decisions=False)
    dump('ANALYSIS_QA.json',summary)
    save('census/input_sha256.csv',[dict(path=str(f.relative_to(P)),sha256=digest(f),bytes=f.stat().st_size) for f in sorted(P.rglob('*')) if f.is_file()])
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
