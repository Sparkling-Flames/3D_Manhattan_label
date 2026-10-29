#!/usr/bin/env python3
"""Pre-outcome v2.1 candidate labels, actual legal targets, frozen scoring unchanged."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[v]='1'
import argparse, gzip, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score,silhouette_score
sys.path.insert(0,'/tmp/hohonet_v21_deps')
from shapely.geometry import Polygon

ST=['turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9']
BD=['matched_top_bias_deg','matched_bottom_bias_deg','log_area_ratio','log_height']
METRICS=ST+BD+['B8L2','D10','log_time','bottom_bias_9','omission','extension','matched_horizontal_bias_deg','matched_boundary_abs_deg','matched_pair_fraction']
def cols(st,metrics):return ['m_'+st+'_'+x for x in metrics]
DOMAINS={
'M_STRUCTURE_LEVEL':cols('all',ST),
'M_STRUCTURE_DIFFICULTY':cols('hard',ST)+cols('hard_minus_easy',ST),
'M_STRUCTURE_CHALLENGE':cols('challenge',ST),
'M_STRUCTURE_OPP_RESPONSE':cols('opp_slope',ST),
'M_BOUNDARY_LEVEL':cols('all',BD),
'M_BOUNDARY_OPP_RESPONSE':cols('opp_slope',BD),
'M_QUALITY_OPP_RESPONSE':['m_all_B8L2','m_all_B8L2_p20','m_opp_slope_B8L2'],
'M_TIME_OPP_RESPONSE':['m_all_log_time','m_opp_slope_log_time'],
}
FAMILIES={
'TARGET_DSTRUCT':dict(ks=[2,3,4],domains=['M_STRUCTURE_LEVEL','M_STRUCTURE_DIFFICULTY'],gates=['manual_all','manual_difficulty'],sort=['m_hard_turn_n','m_hard_short_turn_edges','m_all_turn_n']),
'OPPSTRUCT':dict(ks=[2,3,4,5],domains=['M_STRUCTURE_LEVEL','M_STRUCTURE_CHALLENGE','M_STRUCTURE_OPP_RESPONSE'],gates=['manual_all','manual_challenge','manual_opportunity'],sort=['m_challenge_turn_n','m_all_turn_n','m_challenge_short_turn_edges']),
'OPPGEOM':dict(ks=[2,3,4],domains=['M_STRUCTURE_LEVEL','M_STRUCTURE_OPP_RESPONSE','M_BOUNDARY_LEVEL','M_BOUNDARY_OPP_RESPONSE'],gates=['manual_all','manual_opportunity'],sort=['m_all_turn_n','m_all_matched_bottom_bias_deg','m_all_log_area_ratio']),
'OPPJOINT':dict(ks=[2,3,4],domains=['M_STRUCTURE_OPP_RESPONSE','M_BOUNDARY_OPP_RESPONSE','M_QUALITY_OPP_RESPONSE','M_TIME_OPP_RESPONSE'],gates=['manual_all','manual_opportunity','manual_time'],sort=['m_all_B8L2','m_challenge_turn_n','m_all_log_time']),
}
CONFIG={
'commit':'a476461d7ede8db95da43de4139e612c05e618bc','data_release':'v2.1',
'formation_frozen_before_new_team_comparison':True,'families':FAMILIES,'domains':DOMAINS,
'feature_centering':'median by image_id,reference_id,condition; time also origin,time_source',
'history':'metric-valid records averaged within worker-target; targets equal within worker-image; images equal within worker-building; buildings equal; each LOBO recomputes supports',
'history_scope':'ordinary_manual and ordinary_semi legal target pools; doorway and special-range excluded from new fit, retained in inventory',
'opportunity_inputs':['log1p(max(ref_turn5-4,0))','log1p(ref_H)','log1p(ref_short_edges)'],
'opportunity_scaling':'training unique targets, equal image/building weighting; median,p85-p15(fallbackstd),clip3; equal-axis sum/sqrt(3)',
'opportunity_response':'weighted within-person covariance(peer residual,opportunity score)/weighted variance; no quality-outcome tuning',
'opportunity_support':'all>=12images3buildings;score variation>1e-5;at least2 distinct score levels; challenge-specific domain>=4images2buildings',
'known_difficulty':'only official target-aligned grades; unknown targets contribute all/opportunity, never easy/hard',
'manual_difficulty_support':'easy>=5images2buildings;hard>=4images2buildings',
'time_support':'at least12 positively timed images and3 buildings; variation in opportunity score',
'low_tail':'weighted empirical p20 using same hierarchical history weights on available quality rows',
'embedding':'per-domain median,p85-p15 fallbackstd then1,clip3,PCA<=2,domain RMS and equal-domain normalization',
'cluster':'Ward, one tree per family/fold; all registered K retained, no minimum class balance',
'new_fusion_for_label_formation':False,
}
def dump_json(x,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(d,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=d.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz': data=gzip.compress(data,compresslevel=6,mtime=0)
    temp=path.with_name(path.name+'.partial')
    with temp.open('wb') as handle:
        handle.write(data);handle.flush();os.fsync(handle.fileno())
    temp.replace(path)
def weighted_quantile(v,w,q):
    a=np.argsort(v);v=np.asarray(v)[a];w=np.asarray(w)[a]
    return float(v[min(np.searchsorted(np.cumsum(w),q*w.sum(),side='left'),len(v)-1)])
def weights(d):
    k=['worker_id','condition'];im=k+['building','image_id'];tar=im+['reference_id']
    return (1/d.groupby(tar).object_id.transform('size')/d.groupby(im).reference_id.transform('nunique')
            /d.groupby(k+['building']).image_id.transform('nunique')/d.groupby(k).building.transform('nunique')).to_numpy()
def geometry(points,reference):
    p=np.asarray(points,float);q=np.asarray(reference,float);out={}
    if len(p)%2 or len(q)%2:return out
    def unit(b):
        a=b[:,0]*2*np.pi/1024;b=(b[:,1]/512-.5)*np.pi
        return np.column_stack([-np.sin(a)*np.cos(b),-np.sin(b),np.cos(a)*np.cos(b)])
    co=np.degrees(np.arccos(np.clip(unit(p[1::2])@unit(q[1::2]).T,-1,1)))
    ii,jj=linear_sum_assignment(co)
    for t in (9,12):
        ok=co[ii,jj]<=t
        out[f'unmatched_ref_{t}']=1-ok.sum()/(len(q)//2)
        out[f'bottom_bias_{t}']=float(np.mean(p[1::2][ii[ok],1]-q[1::2][jj[ok],1])) if ok.any() else np.nan
    az=((p[::2,0,None]-q[None,::2,0]+512)%1024-512)*360/1024
    ii,jj=linear_sum_assignment(abs(az));ok=abs(az[ii,jj])<=9;ii,jj=ii[ok],jj[ok]
    out['matched_pair_fraction']=len(ii)/(len(q)//2)
    if len(ii):
        t=(p[2*ii,1]-q[2*jj,1])*180/512;b=(p[2*ii+1,1]-q[2*jj+1,1])*180/512
        out.update(matched_top_bias_deg=float(t.mean()),matched_bottom_bias_deg=float(b.mean()),matched_horizontal_bias_deg=float(az[ii,jj].mean()),matched_boundary_abs_deg=float(((abs(t)+abs(b))/2).mean()))
    def floor(a):
        r=1/np.tan((a[1::2,1]/512-.5)*np.pi);ang=a[1::2,0]*2*np.pi/1024
        return np.column_stack([-np.sin(ang)*r,np.cos(ang)*r]),r
    if not (p[1::2,1]>256).all():return out
    a,r=floor(p);poly=Polygon(a);edges=np.roll(a,-1,axis=0)-a;ln=np.linalg.norm(edges,axis=1)
    if not poly.is_valid or poly.area<=0 or (ln<1e-8).any():return out
    turn=np.degrees(np.arccos(np.clip((edges*np.roll(edges,1,axis=0)).sum(1)/(ln*np.roll(ln,1)),-1,1)))
    height=float(np.mean(1+r*np.tan((.5-p[::2,1]/512)*np.pi)))
    out.update(turn_n=int((turn>5).sum()),near_straight_nodes_5deg=int((turn<=5).sum()),short_turn_edges=int(((ln/ln.sum()<.04)&(turn>=15)&(np.roll(turn,-1)>=15)).sum()),log_area=float(np.log(poly.area)),log_height=float(np.log(height)) if height>0 else np.nan)
    if (q[1::2,1]>256).all():
        rf,_=floor(q);rp=Polygon(rf)
        if rp.is_valid and rp.area>0:
            out.update(log_area_ratio=float(np.log(poly.area/rp.area)),omission=1-poly.intersection(rp).area/rp.area,extension=poly.difference(rp).area/poly.area)
    return out
def prepare(repo,work,out):
    base=pd.read_csv(repo/'research/data/releases/v2.1/condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
    links=pd.read_csv(work/'targets/RECORD_TARGET_LINKS_AND_ALL_SUPPORT_WEIGHTS.csv.gz').rename(columns={'record_id':'object_id','worker':'worker_id','source_time_seconds':'source_active_time_seconds','time_source_kind':'time_source'})
    target=pd.read_csv(work/'targets/POOL_TARGET_CONDITIONS.csv')
    meta=['pool_id','ref_turn5','ref_H','ref_short_edges']
    links=links.merge(target[meta],on='pool_id',validate='many_to_one')
    existing=base[['object_id']+[x for x in list(dict.fromkeys(METRICS+['unmatched_ref_12','log_area'])) if x in base and x!='log_time']].copy()
    extra=[]
    inp=json.loads((repo/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json').read_text())
    for pool in inp['images']:
        for r in pool['records']: extra.append(dict(object_id=r['object_id'],**geometry(r['points'],pool['reference']['points_1024x512'])))
    g=pd.concat([existing,pd.DataFrame(extra)],ignore_index=True)
    # Q/D10 come from current exact target link, not the redundant old raw table.
    g=g.drop(columns=['B8L2','D10'],errors='ignore')
    raw=links.merge(g,on='object_id',how='left',validate='one_to_one')
    raw['log_time']=np.log(raw.source_active_time_seconds.where(raw.source_active_time_seconds>0))
    for c in METRICS:
        group=['image_id','reference_id','condition']+(['origin','time_source'] if c=='log_time' else [])
        raw[c+'_peer']=raw[c]-raw.groupby(group,dropna=False)[c].transform('median')
    raw['history_eligible']=raw.layer.isin(['ordinary_manual','ordinary_semi'])
    save(raw,out/'RAW_TARGET_RESPONSE_RECORDS.csv.gz')
    # Necessary numerical correspondence check for newly implemented raw feature extraction:
    main=json.loads((repo/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text())
    checks=[]
    chosen=[]
    for pool in main['images']:
        if len(chosen)>=60:break
        # varied structure and people rather than the first60 from one picture
        for r in pool['records'][:2]:chosen.append((pool,r))
    bm=base.set_index('object_id')
    for pool,r in chosen:
        ff=geometry(r['points'],pool['reference']['points_1024x512'])
        for c in ST+BD+['omission','extension','matched_pair_fraction']:
            v=ff.get(c,np.nan);old=bm.loc[r['object_id'],c]
            checks.append(dict(object_id=r['object_id'],metric=c,new_value=v,existing_value=old,abs_difference=abs(v-old)))
    c=pd.DataFrame(checks);save(c,out/'RAW_FEATURE_CORRESPONDENCE_CHECK.csv')
    diff=c.groupby('metric').abs_difference.max()
    if not (diff.dropna()<1e-7).all():raise ValueError('Raw formula correspondence:'+str(diff))
    return raw,target
def aggregate(s,metric):
    z=s[['worker_id','building','image_id','reference_id',metric]].dropna(subset=[metric])
    # Each level explicitly handles metric-specific missingness without zero imputation.
    return z.groupby(['worker_id','building','image_id','reference_id'])[metric].mean().groupby(['worker_id','building','image_id']).mean().groupby(['worker_id','building']).mean().groupby('worker_id').mean()
def add_support(f,s,p):
    a=s.groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building','nunique'),targets=('reference_id','nunique'),records=('object_id','size'))
    for c in a:f[p+'_'+c]=a[c]
def opportunity(raw):
    t=raw.drop_duplicates(['image_id','reference_id'])[['object_id','building','image_id','reference_id','ref_turn5','ref_H','ref_short_edges']].copy()
    t['worker_id']='REFERENCE';t['condition']='pooled';w=weights(t)
    x=np.column_stack([np.log1p(np.maximum(t.ref_turn5.to_numpy()-4,0)),np.log1p(t.ref_H),np.log1p(t.ref_short_edges)])
    transform={};z=[]
    for i,c in enumerate(['ref_turn5_excess4','ref_H','ref_short_edges']):
        a=x[:,i];med=weighted_quantile(a,w,.5);scale=weighted_quantile(a,w,.85)-weighted_quantile(a,w,.15)
        if scale<=1e-9:scale=float(np.sqrt(np.average((a-np.average(a,weights=w))**2,weights=w)))
        if scale<=1e-9:scale=1.
        z.append(np.clip((a-med)/scale,-3,3));transform[c]={'median':med,'scale':scale}
    t['opportunity_score']=np.array(z).sum(0)/np.sqrt(3)
    return raw.merge(t[['image_id','reference_id','opportunity_score']],on=['image_id','reference_id'],validate='many_to_one'),transform
def history(raw,roster,fold):
    d=raw[raw.history_eligible].copy()
    if fold!='ALL':d=d[d.building!=fold]
    d,opptrans=opportunity(d)
    f=roster.set_index('worker_id').copy();f['heldout_building']=fold
    for cond,pref in [('manual','m'),('semi','s')]:
        dc=d[d.condition==cond]
        masks={'all':np.ones(len(dc),bool),'easy':dc.official_difficulty.eq('简单'),'medium':dc.official_difficulty.eq('中等'),'hard':dc.official_difficulty.eq('困难'),'challenge':dc.geometric_challenge.eq(True),'plain':dc.geometric_challenge.eq(False)}
        for stratum,mask in masks.items():
            s=dc.loc[mask]
            add_support(f,s,pref+'_'+stratum)
            for metric in METRICS:f[pref+'_'+stratum+'_'+metric]=aggregate(s,metric+'_peer')
        for metric in METRICS:f[pref+'_hard_minus_easy_'+metric]=f[pref+'_hard_'+metric]-f[pref+'_easy_'+metric]
        # Identical hierarchical support for responses and means; each metric separately.
        for metric in METRICS:
            z=dc.dropna(subset=[metric+'_peer','opportunity_score']).copy()
            z['w']=weights(z)
            slopes={};variances={};levels={}
            for worker,g in z.groupby('worker_id'):
                x=g.opportunity_score.to_numpy();y=g[metric+'_peer'].to_numpy();w=g.w.to_numpy()
                mx=np.average(x,weights=w);my=np.average(y,weights=w)
                var=np.average((x-mx)**2,weights=w)
                slopes[worker]=np.average((x-mx)*(y-my),weights=w)/var if var>1e-5 else np.nan
                variances[worker]=var;levels[worker]=len(np.unique(np.round(x,9)))
            f[pref+'_opp_slope_'+metric]=pd.Series(slopes,dtype=float)
            if metric=='turn_n':
                f[pref+'_opportunity_variance']=pd.Series(variances,dtype=float);f[pref+'_opportunity_levels']=pd.Series(levels,dtype=float)
            if metric=='B8L2':
                f[pref+'_all_B8L2_p20']=pd.Series({worker:weighted_quantile(g[metric+'_peer'].to_numpy(),g.w.to_numpy(),.2) for worker,g in z.groupby('worker_id')},dtype=float)
            if metric=='log_time':add_support(f,z,pref+'_timed')
    count=[c for c in f if any(c.endswith('_'+q) for q in ['images','buildings','targets','records'])]
    f[count]=f[count].fillna(0)
    f['manual_all']=f.m_all_images.ge(12)&f.m_all_buildings.ge(3)
    f['manual_difficulty']=f.m_easy_images.ge(5)&f.m_easy_buildings.ge(2)&f.m_hard_images.ge(4)&f.m_hard_buildings.ge(2)
    f['manual_challenge']=f.m_challenge_images.ge(4)&f.m_challenge_buildings.ge(2)
    f['manual_opportunity']=f.m_opportunity_variance.gt(1e-5)&f.m_opportunity_levels.ge(2)
    f['manual_time']=f.m_timed_images.ge(12)&f.m_timed_buildings.ge(3)&f.m_opp_slope_log_time.notna()
    f['manual_geometry']=f.manual_all&f.manual_difficulty
    f['semi_geometry']=f.s_all_images.ge(6)&f.s_all_buildings.ge(3)
    return f.reset_index(),opptrans
def embedding(g,domains):
    parts=[];trans={}
    for domain in domains:
        cs=DOMAINS[domain];a=g[cs].to_numpy(float);med=np.median(a,axis=0);scale=np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0)
        sd=np.std(a,axis=0);scale=np.where(scale>1e-9,scale,np.where(sd>1e-9,sd,1))
        z=np.clip((a-med)/scale,-3,3);p=PCA(n_components=min(2,len(cs),len(a)-1),svd_solver='full');pc=p.fit_transform(z)
        rms=np.sqrt(np.mean(np.sum(pc**2,axis=1)));rms=max(rms,1e-9)
        parts.append(pc/rms/np.sqrt(len(domains)))
        trans[domain]={'columns':cs,'median':med.tolist(),'scale':scale.tolist(),'components':p.components_.tolist(),'pca_mean':p.mean_.tolist(),'rms':rms}
    return np.column_stack(parts),trans
def fit(f):
    labels=[];centers=[];register=[];transforms={}
    numeric=[c for c in f.select_dtypes(include=[np.number]).columns if c!='k']
    for family,spec in FAMILIES.items():
        needed=list(dict.fromkeys(x for d in spec['domains'] for x in DOMAINS[d]))
        gates=f[spec['gates']].all(axis=1)
        known=gates&f[needed].notna().all(axis=1)
        g=f[known].copy()
        if len(g)<max(spec['ks'])+1:continue
        emb,tr=embedding(g,spec['domains']);tree=linkage(emb,method='ward',optimal_ordering=True)
        transforms[family]=tr
        coarse=None
        for k in spec['ks']:
            c=cut_tree(tree,n_clusters=k).ravel();g['raw_cluster']=c
            order=g.groupby('raw_cluster')[spec['sort']].mean().sort_values(spec['sort']).index.tolist()
            mp={v:'C'+str(i+1) for i,v in enumerate(order)};classes=pd.Series(c,index=g.index).map(mp)
            if k==2:coarse=classes
            method=f'{family}_K{k}'
            lab=f[['worker_id','origin','heldout_building','manual_geometry','manual_time','semi_geometry']].copy()
            lab['method']=method;lab['family']=family;lab['class_id']=None;lab.loc[g.index,'class_id']=classes
            lab['known']=known;lab['missing_reason']=''
            lab.loc[~known,'missing_reason']=f.loc[~known].apply(lambda r:';'.join([z for z in spec['gates'] if not r[z]]+(['missing_required_features'] if r[needed].isna().any() else [])),axis=1)
            lab['input_conditions']='manual';lab['evaluation_condition']='manual_and_semi_separately';lab['condition']='manual'
            lab['coarse_label']=None;lab.loc[g.index,'coarse_label']=coarse
            lab['fine_label']=lab.class_id;lab['k']=k;lab['underlying_data_version']='v2.1'
            lab['label_stage']='all_data_descriptive' if f.heldout_building.iloc[0]=='ALL' else 'leave_target_building_out'
            lab['history_scope']='all_admitted_targets_ordinary';lab['source_stage']='new_target_aware_candidates'
            labels.append(lab)
            gg=g.copy();gg['class_id']=classes
            for cl,part in gg.groupby('class_id'):
                row={'method':method,'family':family,'heldout_building':f.heldout_building.iloc[0],'class_id':cl,'k':k,'workers':len(part),'members':'|'.join(sorted(part.worker_id)),'input_conditions':'manual','source_stage':'new_target_aware_candidates'}
                row.update({x:float(part[x].mean()) if part[x].notna().any() else np.nan for x in numeric})
                centers.append(row)
            register.append({'method':method,'family':family,'heldout_building':f.heldout_building.iloc[0],'k':k,'known_workers':len(g),'unknown_workers':len(f)-len(g),'class_sizes':'|'.join(str(v) for v in gg.groupby('class_id').size()),'domains':'|'.join(spec['domains']),'input_conditions':'manual','silhouette':float(silhouette_score(emb,c)),'selection_status':'candidate_frozen_before_team_results'})
    return pd.concat(labels,ignore_index=True),pd.DataFrame(centers),pd.DataFrame(register),transforms
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);args=ap.parse_args()
    out=args.work/'classification';out.mkdir(parents=True,exist_ok=True)
    dump_json(CONFIG,out/'CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json')
    raw,target=prepare(args.repo,args.work,out)
    basenames=['condition_classification/LABELS_ALL_LOBO.csv.gz','scope_axis_classification/AXIS_METHOD_LABELS_ALL_LOBO.csv.gz','scope_axis_classification/SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz']
    baseline=pd.concat([pd.read_csv(args.repo/'research/data/releases/v2.1'/x) for x in basenames],ignore_index=True)
    baseline['history_scope']='official_v21_primary_history';baseline['source_stage']='reused_official_v21_forward20'
    save(baseline,out/'BASELINE20_LABELS_ALL_LOBO.csv.gz')
    roster=baseline[['worker_id','origin']].drop_duplicates().sort_values('worker_id').reset_index(drop=True)
    folds=['ALL']+sorted(target.building.unique())
    labs=[];centers=[];register=[];hist=[];trans={}
    import warnings
    warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
    for i,fold in enumerate(folds):
        f,opp=history(raw,roster,fold);lab,cen,reg,tr=fit(f)
        labs.append(lab);centers.append(cen);register.append(reg);hist.append(f);trans[fold]={'opportunity':opp,'families':tr}
        save(lab,out/'folds'/f'{fold}_LABELS.csv.gz');save(cen,out/'folds'/f'{fold}_CENTERS.csv.gz')
        save(pd.concat(labs,ignore_index=True),out/'NEW_LABELS_ALL_LOBO.csv.gz')
        save(pd.concat(centers,ignore_index=True),out/'NEW_CLASS_CENTERS_ALL_LOBO.csv.gz')
        save(pd.concat(register,ignore_index=True),out/'NEW_CANDIDATE_REGISTRY.csv')
        save(pd.concat(hist,ignore_index=True),out/'HISTORY_FEATURES_ALL_LOBO.csv.gz')
        dump_json(trans,out/'TRANSFORMS_ALL_LOBO.json')
        dump_json({'completed_folds':folds[:i+1],'total_folds':len(folds),'candidate_methods':13,'data':'v2.1','status':'running' if i+1<len(folds) else 'labels_frozen_complete'},out/'PROGRESS.json')
        print(f'completed {fold} {i+1}/{len(folds)} known={[int(x) for x in reg.known_workers]}',flush=True)
    lab=pd.concat(labs,ignore_index=True);cen=pd.concat(centers,ignore_index=True)
    save(lab[lab.heldout_building=='ALL'],out/'NEW_LABELS_ALL.csv')
    save(cen[cen.heldout_building=='ALL'],out/'NEW_CLASS_CENTERS_ALL.csv')
    save(pd.concat([baseline,lab],ignore_index=True),out/'FORWARD33_LABELS_ALL_LOBO.csv.gz')
    old=lab[lab.heldout_building=='ALL']
    stability=[]
    for m,g in lab[lab.heldout_building!='ALL'].groupby('method'):
        a=old[old.method==m]
        for fold,h in g.groupby('heldout_building'):
            c=a[a.known][['worker_id','class_id']].merge(h[h.known][['worker_id','class_id']],on='worker_id')
            stability.append({'method':m,'heldout_building':fold,'common_workers':len(c),'ARI_with_ALL':adjusted_rand_score(c.class_id_x,c.class_id_y)})
    save(pd.DataFrame(stability),out/'NEW_LABEL_STABILITY.csv')
    # Known labels are independent of all current team outcomes; record exact bytes now.
    files=[]
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name not in ['FILE_MANIFEST.csv']:
            files.append({'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    save(pd.DataFrame(files),out/'FILE_MANIFEST.csv')
if __name__=='__main__':main()

