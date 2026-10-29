#!/usr/bin/env python3
"""All legal-target raw pairs once; frozen LOBO labels; no new scores or fusion."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import argparse,gzip,hashlib,itertools,json,sys,warnings
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,'/tmp/hohonet_v21_deps')
from shapely.geometry import Polygon
METRICS=['geometry_pair_angle','geometry_top_angle','geometry_bottom_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance','turn_difference','short_edge_difference','redundancy_difference','height_log_difference','Q_difference','D10_difference','azimuth_difference_deg_9','top_difference_deg_9','bottom_difference_deg_9','unmatched_fraction_9','time_peer_log_difference']
def save(d,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=d.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':data=gzip.compress(data,compresslevel=6,mtime=0)
    temp=path.with_name(path.name+'.partial')
    with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    temp.replace(path)
def dump(x,path):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def rays(points):
    u=2*np.pi*points[:,0]/1024;v=np.pi*(.5-points[:,1]/512)
    return np.column_stack([np.cos(v)*np.sin(u),np.sin(v),np.cos(v)*np.cos(u)])
def prepare_geom(r):
    p=np.asarray(r['points'],float)
    out={'points':p,'top_rays':rays(p[::2]),'bottom_rays':rays(p[1::2]),'poly':None}
    if len(p)>=6 and len(p)%2==0 and (p[1::2,1]>256).all():
        a=p[1::2,0]*2*np.pi/1024;rad=1/np.tan((p[1::2,1]/512-.5)*np.pi)
        floor=np.column_stack([-np.sin(a)*rad,np.cos(a)*rad]);poly=Polygon(floor)
        if poly.is_valid and poly.area>0:out['poly']=poly
    return out
def pair_geometry(a,b):
    p=a['points'];q=b['points'];out={}
    tc=np.degrees(np.arccos(np.clip(a['top_rays']@b['top_rays'].T,-1,1)))
    bc=np.degrees(np.arccos(np.clip(a['bottom_rays']@b['bottom_rays'].T,-1,1)))
    cost=np.maximum(tc,bc);ii,jj=linear_sum_assignment(cost)
    out.update(geometry_pair_angle=float(cost[ii,jj].mean()),geometry_top_angle=float(tc[ii,jj].mean()),geometry_bottom_angle=float(bc[ii,jj].mean()),geometry_unmatched_pairs=abs(len(p)-len(q))/2)
    pa,pb=a['poly'],b['poly']
    if pa is not None and pb is not None:
        inter=pa.intersection(pb).area;union=pa.union(pb).area
        out.update(geometry_bev_distance=1-inter/union,geometry_centroid_distance=float(pa.centroid.distance(pb.centroid)),geometry_log_area_distance=abs(np.log(pa.area/pb.area)))
    az=((p[::2,0,None]-q[None,::2,0]+512)%1024-512)*360/1024
    ii,jj=linear_sum_assignment(abs(az));ok=abs(az[ii,jj])<=9;ii,jj=ii[ok],jj[ok]
    out['unmatched_fraction_9']=1-2*len(ii)/((len(p)+len(q))/2)
    if len(ii):
        out.update(azimuth_difference_deg_9=float(abs(az[ii,jj]).mean()),top_difference_deg_9=float(abs(p[2*ii,1]-q[2*jj,1]).mean()*180/512),bottom_difference_deg_9=float(abs(p[2*ii+1,1]-q[2*jj+1,1]).mean()*180/512))
    return out
def build_pairs(repo,work,out):
    raw=pd.read_csv(work/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False).set_index('object_id')
    target=pd.read_csv(work/'targets/POOL_TARGET_CONDITIONS.csv').set_index('pool_id')
    pools=[]
    for name in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json']:
        pools+=json.loads((repo/'research/data/releases/v2.1'/name).read_text())['images']
    inventory=[];files=[];batch=[]
    for k,pool in enumerate(pools):
        meta=pool['meta'];pid=meta['pool_id'];t=target.loc[pid]
        records=pool['records'];geom=[prepare_geom(r) for r in records]
        expected=len(records)*(len(records)-1)//2
        for i,a in enumerate(records):
            for j in range(i+1,len(records)):
                b=records[j];ra=raw.loc[a['object_id']];rb=raw.loc[b['object_id']]
                z={'pool_id':pid,'image_id':meta['image_id'],'image':meta['image'],'building':meta['building'],'condition':meta['condition'],'layer':meta['layer'],'scope':t.scope,'official_difficulty':t.official_difficulty if pd.notna(t.official_difficulty) else '未分级','geometric_challenge':t.geometric_challenge,'pool_n':len(records),
                'worker_a':a['worker_id'],'worker_b':b['worker_id'],'object_a':a['object_id'],'object_b':b['object_id'],'corners_a':len(a['points'])//2,'corners_b':len(b['points'])//2,'same_corner_count':len(a['points'])==len(b['points']),'floor_a_valid':geom[i]['poly'] is not None,'floor_b_valid':geom[j]['poly'] is not None}
                z.update(pair_geometry(geom[i],geom[j]))
                for dst,src in [('turn_difference','turn_n'),('short_edge_difference','short_turn_edges'),('redundancy_difference','near_straight_nodes_5deg'),('height_log_difference','log_height'),('Q_difference','B8L2'),('D10_difference','D10'),('time_peer_log_difference','log_time_peer')]:
                    z[dst]=abs(ra[src]-rb[src])
                batch.append(z)
        inventory.append({'pool_id':pid,'condition':meta['condition'],'scope':t.scope,'layer':meta['layer'],'members':len(records),'expected_pairs':expected})
        if (k+1)%20==0 or k+1==len(pools):
            file=out/'pair_shards'/f'pairs_{len(files)+1:03d}.csv.gz';save(pd.DataFrame(batch),file);files.append(str(file.relative_to(out)));batch=[]
            dump({'stage':'raw_pairs','completed_pools':k+1,'total_pools':len(pools),'pair_files':files,'expected_pairs_so_far':sum(v['expected_pairs'] for v in inventory)},out/'PAIR_PROGRESS.json')
            print('pairs',k+1,'/',len(pools),'saved',files[-1],flush=True)
    save(pd.DataFrame(inventory),out/'PAIR_POOL_INVENTORY.csv')
    pairs=pd.concat([pd.read_csv(out/f) for f in files],ignore_index=True)
    assert len(pairs)==sum(x['expected_pairs'] for x in inventory)==134197
    assert not pairs.duplicated(['pool_id','object_a','object_b']).any()
    save(pairs,out/'RAW_PAIR_DISTANCES.csv.gz')
    dump({'pairs':len(pairs),'pools':len(pools),'unique_object_ids':raw.index.nunique(),'no_cross_target_pairs':True,'pair_geometry_calculated_once':True,'new_quality_scoring':False,'metrics':METRICS,'geometry_formula_source':'old measure_events.py geometry_metrics; original pair Hungarian spherical max(top,bottom), valid raw floor1-IoU; old feature-only azimuth9 separate'},out/'PAIR_COMPLETION.json')
    return pairs
def summarize_panel(g,lm,common,support,subset):
    aa=g.worker_a.map(lm);bb=g.worker_b.map(lm)
    mask=aa.notna()&bb.notna()
    if support=='common45_known':mask &=g.worker_a.isin(common)&g.worker_b.isin(common)
    if subset=='same_corner_count':mask &=g.same_corner_count
    z=g.loc[mask];aa=aa[mask];bb=bb[mask]
    within=aa.eq(bb).to_numpy();cross=~within
    base={'member_n':len(set(z.worker_a)|set(z.worker_b)),'all_pair_n':len(z),'within_pair_n':int(within.sum()),'cross_pair_n':int(cross.sum())}
    if within.sum()<4 or cross.sum()<4:
        return None,{**base,'reason':'fewer_than4_within_or_cross_raw_pairs'}
    data=z[METRICS].to_numpy(float)
    # Equal within-class and equal unordered cross-class-pair means; one metric may have fewer finite pairs.
    a=aa.to_numpy();b=bb.to_numpy();pairkeys=np.array(['|'.join(sorted([x,y])) for x,y in zip(a,b)])
    wk=np.unique(a[within]);ck=np.unique(pairkeys[cross])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        w=np.nanmean(np.vstack([np.nanmean(data[within&(a==cl)],axis=0) for cl in wk]),axis=0)
        c=np.nanmean(np.vstack([np.nanmean(data[cross&(pairkeys==cl)],axis=0) for cl in ck]),axis=0)
    row={**base,'within_class_n':len(wk),'cross_class_pair_n':len(ck)}
    for j,m in enumerate(METRICS):
        row[m+'_within']=w[j];row[m+'_cross']=c[j];row[m+'_gap']=c[j]-w[j]
        row[m+'_within_finite_pairs']=int(np.isfinite(data[within,j]).sum())
        row[m+'_cross_finite_pairs']=int(np.isfinite(data[cross,j]).sum())
    return row,None
def compare(pairs,work,out):
    labels=pd.read_csv(work/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    labels=labels[labels.known&labels.heldout_building.ne('ALL')]
    methods=sorted(labels.method.unique());maps={(m,b):g.set_index('worker_id').class_id.to_dict() for (m,b),g in labels.groupby(['method','heldout_building'])}
    common={b:set.intersection(*[set(maps[(m,b)]) for m in methods]) for b in sorted(labels.heldout_building.unique())}
    save(pd.DataFrame([{'heldout_building':b,'common_worker_n':len(ws),'common_workers':'|'.join(sorted(ws)),'methods':len(methods)} for b,ws in common.items()]),out/'COMMON45_KNOWN_WORKERS_BY_FOLD.csv')
    groups=list(pairs.groupby('pool_id',sort=False));files=[];missing=[]
    meta=['pool_id','image_id','image','building','condition','layer','scope','official_difficulty','geometric_challenge','pool_n']
    reused_methods=[]
    for mi,method in enumerate(methods):
        file=out/'comparison_shards'/f'{method}.csv.gz'
        if file.exists():
            cached=pd.read_csv(file)
            assert set(cached.method)=={method}
            assert not cached.duplicated(['pool_id','support','subset']).any()
            seen=set(zip(cached.pool_id,cached.support,cached.subset))
            # Restore the explicit missing-support denominator, which earlier
            # interrupted runs held only in memory. No pair metric is recalculated.
            for pid,g in groups:
                b=g.building.iloc[0];lm=maps[(method,b)];info={x:g.iloc[0][x] for x in meta}
                aa=g.worker_a.map(lm);bb=g.worker_b.map(lm)
                for support in ['method_all_known','common45_known']:
                    for subset in ['all_pairs','same_corner_count']:
                        if (pid,support,subset) in seen:continue
                        mask=aa.notna()&bb.notna()
                        if support=='common45_known':mask &=g.worker_a.isin(common[b])&g.worker_b.isin(common[b])
                        if subset=='same_corner_count':mask &=g.same_corner_count
                        z=g.loc[mask];same=aa[mask].eq(bb[mask]);nw=int(same.sum());nc=len(z)-nw
                        assert nw<4 or nc<4,(method,pid,support,subset,'unexpected missing estimable row')
                        missing.append({'method':method,'support':support,'subset':subset,**info,
                            'member_n':len(set(z.worker_a)|set(z.worker_b)),'all_pair_n':len(z),
                            'within_pair_n':nw,'cross_pair_n':nc,'reason':'fewer_than4_within_or_cross_raw_pairs'})
            files.append(str(file.relative_to(out)));reused_methods.append(method)
            dump({'completed_methods':mi+1,'methods':len(methods),'files':files,'reused_methods':reused_methods},out/'COMPARISON_PROGRESS.json')
            print('reused',mi+1,'/',len(methods),method,len(cached),flush=True)
            continue
        rows=[]
        for pid,g in groups:
            b=g.building.iloc[0];lm=maps[(method,b)];info={x:g.iloc[0][x] for x in meta}
            for support in ['method_all_known','common45_known']:
                for subset in ['all_pairs','same_corner_count']:
                    rr,mm=summarize_panel(g,lm,common[b],support,subset)
                    base={'method':method,'support':support,'subset':subset,**info}
                    if rr:rows.append({**base,**rr})
                    else:missing.append({**base,**mm})
        file=out/'comparison_shards'/f'{method}.csv.gz';save(pd.DataFrame(rows),file);files.append(str(file.relative_to(out)))
        dump({'completed_methods':mi+1,'methods':len(methods),'files':files},out/'COMPARISON_PROGRESS.json')
        print('compared',mi+1,'/',len(methods),method,len(rows),flush=True)
    table=pd.concat([pd.read_csv(out/f) for f in files],ignore_index=True)
    save(table,out/'RAW_CLASS_DISTANCE_BY_POOL.csv.gz')
    save(pd.DataFrame(missing),out/'RAW_CLASS_DISTANCE_UNESTIMABLE.csv.gz')
    summary=[];image_parts=[]
    key=['method','condition','layer','support','subset']
    # Targets equal within each image; image then building weights; all and exact difficulty strata separate.
    for group,gg in table.groupby(key,dropna=False):
        for scope in ['ALL_TARGETS','primary','other_admitted']:
            z=gg if scope=='ALL_TARGETS' else gg[gg.scope.eq(scope)]
            if z.empty:continue
            for difficulty in ['ALL','简单','中等','困难','未分级']:
                dz=z if difficulty=='ALL' else z[z.official_difficulty.eq(difficulty)]
                if dz.empty:continue
                scalarcols=[x+'_'+c for x in METRICS for c in ['within','cross','gap']]
                images=dz.groupby(['image_id','building'])[scalarcols].mean().reset_index()
                images['method']=group[0];images['condition']=group[1];images['layer']=group[2];images['support']=group[3];images['subset']=group[4]
                images['scope_summary']=scope;images['difficulty_summary']=difficulty
                image_parts.append(images)
                for metric in METRICS:
                    a=images.dropna(subset=[metric+'_within',metric+'_cross'])
                    if a.empty:continue
                    b=a.groupby('building')[[metric+'_within',metric+'_cross',metric+'_gap']].mean()
                    wc=a[metric+'_within'];cc=a[metric+'_cross'];gap=a[metric+'_gap']
                    row={**dict(zip(key,group)),'scope_summary':scope,'difficulty_summary':difficulty,'metric':metric,'images':len(a),'buildings':len(b),'pools':dz.pool_id.nunique(),
                     'image_within':wc.mean(),'image_cross':cc.mean(),'image_gap':gap.mean(),'image_ratio':cc.mean()/wc.mean() if wc.mean()>1e-12 else np.nan,
                     'image_gap_p25':gap.quantile(.25),'image_gap_median':gap.median(),'image_gap_p75':gap.quantile(.75),'images_cross_larger':int(gap.gt(1e-10).sum()),'images_cross_smaller':int(gap.lt(-1e-10).sum()),'images_no_gap':int(gap.abs().le(1e-10).sum()),
                     'building_within':b[metric+'_within'].mean(),'building_cross':b[metric+'_cross'].mean(),'building_gap':b[metric+'_gap'].mean(),'buildings_cross_larger':int(b[metric+'_gap'].gt(1e-10).sum()),
                     'within_finite_pairs':int(dz[metric+'_within_finite_pairs'].sum()),'cross_finite_pairs':int(dz[metric+'_cross_finite_pairs'].sum()),'minimum_member_n':int(dz.member_n.min())}
                    summary.append(row)
    result=pd.DataFrame(summary);save(result,out/'RAW_CLASS_DISTANCE_SUMMARY.csv')
    save(pd.concat(image_parts,ignore_index=True),out/'RAW_CLASS_DISTANCE_BY_IMAGE.csv.gz')
    # Method-independent common support paired comparison to Q baseline and DSTRUCT K3 on identical metric/image cells.
    wide=table[table.support.eq('common45_known')]
    comparisons=[]
    for baseline in ['Q_MEDIAN2','DSTRUCT_K3']:
        b=wide[wide.method.eq(baseline)]
        for method,g in wide.groupby('method'):
            if method==baseline:continue
            join=['pool_id','subset'];mer=g.merge(b,on=join,suffixes=('_candidate','_baseline'),validate='one_to_one')
            for _,r in mer.iterrows():
                for metric in ['geometry_pair_angle','geometry_bev_distance','geometry_top_angle','geometry_bottom_angle','turn_difference','redundancy_difference']:
                    cw=r[metric+'_within_candidate'];cc=r[metric+'_cross_candidate'];bw=r[metric+'_within_baseline'];bc=r[metric+'_cross_baseline']
                    if not np.isfinite([cw,cc,bw,bc]).all():continue
                    comparisons.append({'method':method,'baseline':baseline,'pool_id':r.pool_id,'image_id':r.image_id_candidate,'building':r.building_candidate,'condition':r.condition_candidate,'layer':r.layer_candidate,'scope':r.scope_candidate,'subset':r.subset,'metric':metric,'candidate_within':cw,'candidate_cross':cc,'candidate_gap':cc-cw,'baseline_within':bw,'baseline_cross':bc,'baseline_gap':bc-bw,'gap_gain':(cc-cw)-(bc-bw)})
    save(pd.DataFrame(comparisons),out/'COMMON45_BASELINE_PAIRED_BY_POOL.csv.gz')
    dump({'methods':len(methods),'raw_pairs':len(pairs),'compared_pool_rows':len(table),'reused_methods':reused_methods,'unestimable_panel_rows':len(missing),'summary_rows':len(result),'support':['method_all_known','common45_known'],'target_weighting':'available target contrasts equal within image; images equal; building equal also saved','class_weighting':'within class means equal; unordered cross-class-pair means equal','unknown_labels':'pairs excluded, never assigned fake class','same_count':'equal actual bottom-point count; retains position/shape distances','scope':'Manual/Semi separate; ordinary/doorway/special separate; other target grade stays unknown','interpretation':'descriptive class/raw-answer separation on heldout-building labels; not a fusion exchange result; input geometry reconstruction may explain its own class features'},out/'COMPLETION.json')
    print('complete summaries',len(result),flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--part',choices=['pairs','compare','all'],default='all');a=ap.parse_args()
    out=a.work/'raw_similarity';out.mkdir(parents=True,exist_ok=True)
    if a.part in ['pairs','all']:
        pairs=build_pairs(a.repo,a.work,out)
    else:pairs=pd.read_csv(out/'RAW_PAIR_DISTANCES.csv.gz')
    if a.part in ['compare','all']:compare(pairs,a.work,out)
if __name__=='__main__':main()

