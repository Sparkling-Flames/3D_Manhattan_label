"""Combine saved prior ABC events with this turn's supplement, preserving stages.

Comparisons use the same original A: |C-A|-|B-A|. Across methods, common pool,
n/m and historical-axis ranks are aligned; actual A/D may differ and are flagged.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd

METHODS=['DSTRUCT_K3','TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2','V21_DSTRUCT_RAW3_K3']
GRIDS={(14,7),(20,7),(12,8),(16,8),(12,4),(10,7),(18,7),(20,6),(12,6),(20,5),(24,4),(26,3),(20,4)}
SCALARS=['B8L2','D10','IoU3D100','S_bottom_deg','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
         'geometry_area_h2','height_mean_h','boundary_loss','direction_loss','height_loss','omission','extension','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg']
GEOM=['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
META=['event_id','pool_id','image','building','condition','layer','scope','method','heldout_building','source_class','target_class','n','m','pool_n','background_id','block_id','A_team_key','B_team_key','C_team_key','A_failed','B_failed','C_failed','ABC_scored']

def read_old_scalar_reconstructions(repo,already,out):
    """Include fixed-A and all other old ABC registrations, without new fusion.

    Angular/boundary pair geometry requires saved polygons and is not inferred
    from scalar Q. Centroid and log-area distances are exactly reconstructible
    from saved valid footprint summaries; unavailable diagnostics stay NaN.
    """
    w=repo/'research/workers/personnel_v21_reselection_20261029'
    identity=['method','pool_id','n','m','A_team_key','B_team_key','C_team_key']
    present=set(map(tuple,already[identity].to_numpy()))
    extras=[];source_rows=[]
    for path in sorted((w/'experiment').glob('*_design/EVENTS_EXACT.csv.gz')):
        z=pd.read_csv(path,low_memory=False)
        if 'B_team_key' not in z:continue
        z=z[z.method.isin(METHODS)&z.condition.eq('manual')&z.layer.eq('ordinary_manual')&z.B_team_key.notna()]
        z=z[[tuple(v) in GRIDS for v in z[['n','m']].to_numpy()]]
        z=z[[tuple(v) not in present for v in z[identity].to_numpy()]]
        if not len(z):continue
        present.update(map(tuple,z[identity].to_numpy()))
        z['scope']=np.where(z.analysis_scope.eq('other_admitted_target'),'other','primary')
        z['source_stage']='existing_'+path.parent.name.removesuffix('_design')
        extras.append(z)
        source_rows.append(dict(kind='design',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),selected_events=len(z)))
    if not extras:return pd.DataFrame()
    d=pd.concat(extras,ignore_index=True)
    needed=set(d.A_team_key)|set(d.B_team_key)|set(d.C_team_key)
    scalar_paths=[w/'additional_delivery/packages/05A/experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz']+sorted((w/'experiment').glob('*_endpoints/ENDPOINT_SCALARS.csv.gz'))
    fields=['team_key']+SCALARS+['centroid_x_h','centroid_z_h','source_time_total_seconds','recorded_time_total_seconds','record_time_by_kind_json']
    ss=[]
    for path in scalar_paths:
        z=pd.read_csv(path,usecols=lambda c:c in fields,low_memory=False)
        z=z[z.team_key.isin(needed)]
        if not len(z):continue
        ss.append(z);source_rows.append(dict(kind='scalar',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),selected_endpoints=len(z)))
    scal=pd.concat(ss,ignore_index=True)
    qr=scal.groupby('team_key').B8L2.agg(['min','max'])
    assert not ((qr['max']-qr['min']).abs()>1e-8).any()
    scal=scal.drop_duplicates('team_key').set_index('team_key')
    assert needed<=set(scal.index)
    for c in fields:
        if c not in scal and c!='team_key':scal[c]=np.nan
    def time_sig(value):
        if pd.isna(value):return '',False
        x=json.loads(value)
        sig=json.dumps(sorted((k,v.get('n',0)) for k,v in x.items()),separators=(',',':'))
        known=all(v.get('known_n')==v.get('n') and v.get('total_seconds') is not None and v.get('total_seconds')>=0 for v in x.values())
        return sig,known
    tt=[time_sig(x) for x in scal.record_time_by_kind_json]
    scal['time_sig']=[v[0] for v in tt];scal['time_known']=[v[1] for v in tt]
    arms={a:scal.reindex(d[a+'_team_key']).reset_index(drop=True) for a in 'ABC'}
    values={}
    for a in 'ABC':values[a+'_failed']=arms[a].B8L2.isna()
    values['ABC_scored']=~(values['A_failed']|values['B_failed']|values['C_failed'])
    for metric in SCALARS:
        for name,top,base in [('BA','B','A'),('CA','C','A'),('CB','C','B')]:
            values[metric+'_'+name]=pd.to_numeric(arms[top][metric],errors='coerce')-pd.to_numeric(arms[base][metric],errors='coerce')
    for name,top,base in [('BA','B','A'),('CA','C','A'),('CB','C','B')]:
        a,b=arms[top],arms[base]
        okay=a.time_known&b.time_known&a.time_sig.eq(b.time_sig)&b.source_time_total_seconds.gt(0)
        values['record_time_'+name+'_pct_source_matched']=(100*(a.source_time_total_seconds/b.source_time_total_seconds-1)).where(okay)
        values['record_time_'+name+'_pct_single_source']=(100*(a.recorded_time_total_seconds/b.recorded_time_total_seconds-1)).where(b.recorded_time_total_seconds.gt(0))
    for name,a,b in [('AB','A','B'),('AC','A','C'),('BC','B','C')]:
        aa,bb=arms[a],arms[b]
        values['geometry_centroid_distance_'+name]=np.hypot(aa.centroid_x_h-bb.centroid_x_h,aa.centroid_z_h-bb.centroid_z_h)
        values['geometry_log_area_distance_'+name]=np.abs(np.log(aa.geometry_area_h2/bb.geometry_area_h2)).where(aa.geometry_area_h2.gt(0)&bb.geometry_area_h2.gt(0))
    d=pd.concat([d.reset_index(drop=True),pd.DataFrame(values)],axis=1)
    pd.DataFrame(source_rows).to_csv(out/'ADDITIONAL_OLD_SOURCE_PROVENANCE.csv',index=False)
    d.to_csv(out/'ADDITIONAL_OLD_SCALAR_DERIVED_EVENTS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    return d

def read_effects(folder,stage):
    f=folder/'EVENT_EFFECTS_COMPLETE.csv.gz';cols=pd.read_csv(f,nrows=0).columns
    wanted=META+[m+'_'+s for m in SCALARS for s in ['BA','CA','CB']]+['record_time_'+s+'_pct_source_matched' for s in ['BA','CA','CB']]+['record_time_'+s+'_pct_single_source' for s in ['BA','CA','CB']]
    x=pd.read_csv(f,usecols=[c for c in wanted if c in cols],low_memory=False)
    x=x[x.method.isin(METHODS)&x.condition.eq('manual')&x.layer.eq('ordinary_manual')]
    x=x[[tuple(z) in GRIDS for z in x[['n','m']].to_numpy()]]
    pl=pd.read_csv(folder/'EVENT_PAIR_LINKS.csv.gz');pg=pd.read_csv(folder/'PAIR_GEOMETRY.csv.gz',usecols=['pair_id']+GEOM)
    z=pl[pl.event_id.isin(x.event_id)].merge(pg,on='pair_id',validate='many_to_one').pivot(index='event_id',columns='arm_pair',values=GEOM)
    z.columns=['_'.join(c) for c in z.columns]
    x=x.merge(z,on='event_id',validate='one_to_one');x['source_stage']=stage
    return x

def roles(repo,history,newlabels):
    w=repo/'research/workers/personnel_v21_reselection_20261029'
    role=pd.read_csv(w/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',low_memory=False)
    role=role[['method','heldout_building','class_id','k','hard_turn_rank_asc','challenge_turn_rank_asc','q_rank_asc','response_hard_turn_rank_asc','m_hard_turn_n','m_challenge_turn_n','m_all_B8L2']]
    l=pd.read_csv(newlabels);l=l[l.method.eq('V21_DSTRUCT_RAW3_K3')&l.known]
    h=pd.read_csv(history,usecols=['heldout_building','worker_id','m_hard_turn_n','m_challenge_turn_n','m_all_B8L2'])
    z=l.merge(h,on=['heldout_building','worker_id'],validate='many_to_one')
    nr=z.groupby(['method','heldout_building','class_id','k'])[['m_hard_turn_n','m_challenge_turn_n','m_all_B8L2']].mean().reset_index()
    for col,target in [('m_hard_turn_n','hard_turn_rank_asc'),('m_challenge_turn_n','challenge_turn_rank_asc'),('m_all_B8L2','q_rank_asc')]:
        nr[target]=nr.groupby(['method','heldout_building'])[col].rank(method='first')
    return pd.concat([role,nr],ignore_index=True)

def enrich(d,role):
    for prefix,key in [('source','source_class'),('target','target_class')]:
        rr=role.rename(columns={'class_id':key,**{c:prefix+'_'+c for c in role if c not in ['method','heldout_building','class_id']}})
        d=d.merge(rr,on=['method','heldout_building',key],how='left',validate='many_to_one')
    d['axis']=np.select([d.method.str.startswith('OPPSTRUCT'),d.method.str.startswith('OPPJOINT'),d.method.str.startswith('RFUSE')],['challenge_turn_rank_asc','q_rank_asc','response_hard_turn_rank_asc'],default='hard_turn_rank_asc')
    d['source_axis_rank']=np.nan;d['target_axis_rank']=np.nan
    for axis in d.axis.unique():
        take=d.axis.eq(axis);d.loc[take,'source_axis_rank']=d.loc[take,'source_'+axis];d.loc[take,'target_axis_rank']=d.loc[take,'target_'+axis]
    assert d.source_axis_rank.notna().all() and d.target_axis_rank.notna().all()
    d['rank_direction']=[f'{int(a)}/{int(k)}->{int(b)}/{int(k)}' for a,b,k in zip(d.source_axis_rank,d.target_axis_rank,d.source_k)]
    d['role_direction']=d.axis+':'+d.rank_direction
    metrics=[]
    for m in SCALARS:
        for arm in ['BA','CA','CB']:
            metrics.append(m+'_'+arm)
        valid=d[m+'_BA'].notna()&d[m+'_CA'].notna()&d[m+'_CB'].notna()
        d[m+'_same_origin_within']=d[m+'_BA'].abs().where(valid)
        d[m+'_same_origin_cross']=d[m+'_CA'].abs().where(valid)
        d[m+'_same_origin_gap']=(d[m+'_CA'].abs()-d[m+'_BA'].abs()).where(valid)
        d[m+'_symmetric_cross']=((d[m+'_CA'].abs()+d[m+'_CB'].abs())/2).where(valid)
        d[m+'_symmetric_gap']=d[m+'_symmetric_cross']-d[m+'_same_origin_within']
        metrics += [m+'_'+s for s in ['same_origin_within','same_origin_cross','same_origin_gap','symmetric_cross','symmetric_gap']]
    for m in GEOM:
        valid=d[m+'_AB'].notna()&d[m+'_AC'].notna()
        d[m+'_same_origin_within']=d[m+'_AB'].where(valid);d[m+'_same_origin_cross']=d[m+'_AC'].where(valid)
        d[m+'_same_origin_gap']=(d[m+'_AC']-d[m+'_AB']).where(valid)
        metrics += [m+'_'+s for s in ['same_origin_within','same_origin_cross','same_origin_gap']]
    for s in ['BA','CA','CB']:
        for kind in ['source_matched','single_source']:metrics.append(f'record_time_{s}_pct_{kind}')
    for c in ['A_failed','B_failed','C_failed','ABC_scored']:
        d[c]=d[c].astype(str).str.lower().isin(['true','1','1.0']).astype(float);metrics.append(c)
    # Jointly scored Q directions, before averaging across backgrounds.
    qvalid=d.B8L2_BA.notna()&d.B8L2_CA.notna()&d.B8L2_CB.notna()
    for arm in ['BA','CA','CB']:d['joint_Q_'+arm]=d['B8L2_'+arm].where(qvalid);metrics.append('joint_Q_'+arm)
    return d,metrics

def aggregate(d,metrics,label):
    key=['method','scope','n','m','axis','rank_direction'];pk=key+['pool_id','image','building']
    blocks=d.groupby(pk+['block_id'],dropna=False)[metrics].mean().reset_index()
    pool=blocks.groupby(pk,dropna=False)[metrics].mean().reset_index()
    im=pool.groupby(key+['image','building'],dropna=False)[metrics].mean().reset_index()
    bu=im.groupby(key+['building'],dropna=False)[metrics].mean().reset_index()
    registered=d.groupby(key,dropna=False).agg(events=('event_id','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),blocks=('block_id','nunique'),backgrounds=('background_id','nunique'),jointly_scored_events=('ABC_scored','sum'),A_failed_events=('A_failed','sum'),B_failed_events=('B_failed','sum'),C_failed_events=('C_failed','sum')).reset_index()
    summaries=[];patterns=[]
    for kk,g in im.groupby(key,dropna=False):
        rr=dict(zip(key,kk));rr['stage_scope']=label
        b=bu
        for k,v in zip(key,kk):b=b[b[k].eq(v)]
        zz=g[metrics];bz=b[metrics]
        statistics={'mean_image':zz.mean(),'median_image':zz.median(),'p10_image':zz.quantile(.1),'p90_image':zz.quantile(.9),
                    'valid_images':zz.count(),'positive_images':zz.gt(1e-9).sum(),'negative_images':zz.lt(-1e-9).sum(),'near_zero_images':zz.abs().le(1e-9).sum(),
                    'mean_building':bz.mean(),'valid_buildings':bz.count(),'positive_buildings':bz.gt(1e-9).sum()}
        for suffix,values in statistics.items():rr.update({m+'_'+suffix:v for m,v in values.items()})
        summaries.append(rr)
        z=g[['joint_Q_BA','joint_Q_CA']].dropna()
        for eps in [.1,1.,2.]:
            ba=np.where(z.joint_Q_BA>eps,1,np.where(z.joint_Q_BA< -eps,-1,0));ca=np.where(z.joint_Q_CA>eps,1,np.where(z.joint_Q_CA< -eps,-1,0))
            pp=np.select([(ba==0)&(ca==0),(ba==0)&(ca!=0),(ba!=0)&(ca==0),ba*ca>0,ba*ca<0],['both_near_zero','cross_only','same_only','same_direction','opposite_direction'],default='unclassified')
            for pat in ['both_near_zero','cross_only','same_only','same_direction','opposite_direction']:
                patterns.append({**dict(zip(key,kk)),'stage_scope':label,'epsilon_Q':eps,'pattern':pat,'images':int((pp==pat).sum()),'valid_images':len(z)})
    sm=pd.DataFrame(summaries).merge(registered,on=key,validate='one_to_one');im['stage_scope']=label;pool['stage_scope']=label;bu['stage_scope']=label
    return sm,im,pool,bu,pd.DataFrame(patterns)

def main(args):
    repo=Path(args.repo);w=repo/'research/workers/personnel_v21_reselection_20261029';out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    older=[read_effects(w/'additional_delivery/packages/05A/analysis/global_screen_compact','existing_global'),read_effects(w/'analysis/focused_compact','existing_focused')]
    old=pd.concat(older,ignore_index=True)
    # Same event across the two source stages is one realized ABC.
    old=old.drop_duplicates('event_id',keep='first')
    extra=read_old_scalar_reconstructions(repo,old,out)
    old=pd.concat([old,extra],ignore_index=True)
    nc=pd.read_csv(args.new,nrows=0).columns
    keep=META+[m+'_'+s for m in SCALARS for s in ['BA','CA','CB']]+[m+'_'+s for m in GEOM for s in ['AB','AC','BC']]+['record_time_'+s+'_pct_'+kind for s in ['BA','CA','CB'] for kind in ['source_matched','single_source']]
    new=pd.read_csv(args.new,usecols=[c for c in keep if c in nc],low_memory=False);new=new[new.method.isin(METHODS)&new.layer.eq('ordinary_manual')&new.condition.eq('manual')].copy();new['source_stage']='this_turn_supplement'
    old_ids=set(old.event_id);new_overlap=int(new.event_id.isin(old_ids).sum())
    role=roles(repo,args.history,args.new_labels)
    d=pd.concat([old,new],ignore_index=True);d,metrics=enrich(d,role);d=d.copy()
    # Drop exact same oriented A/B/C experiment if re-registered under a new id.
    identity=['method','pool_id','n','m','A_team_key','B_team_key','C_team_key']
    duplicate=d.duplicated(identity,keep='first')
    duplicate_rows=d[duplicate][identity+['event_id','source_stage']]
    alltables=[];allimages=[];allpools=[];allbuildings=[];allpatterns=[]
    for stage,x in [('existing_only',d[d.source_stage.ne('this_turn_supplement')].drop_duplicates(identity)),('new_only',d[d.source_stage.eq('this_turn_supplement')].drop_duplicates(identity)),('combined_union',d[~duplicate])]:
        print('summarizing',stage,'events',len(x),flush=True)
        sm,im,pp,bb,pa=aggregate(x,metrics,stage);alltables.append(sm);allimages.append(im);allpools.append(pp);allbuildings.append(bb);allpatterns.append(pa)
    def save(tab,name):tab.to_csv(out/name,index=False,compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)
    sm=pd.concat(alltables,ignore_index=True);im=pd.concat(allimages,ignore_index=True);pp=pd.concat(allpools,ignore_index=True)
    save(sm,'ALL_STAGES_DIRECTION_N_M_SUMMARY.csv.gz');save(im,'ALL_STAGES_IMAGE_RESULTS.csv.gz');save(pp,'ALL_STAGES_POOL_RESULTS.csv.gz');save(pd.concat(allbuildings),'ALL_STAGES_BUILDING_RESULTS.csv.gz');save(pd.concat(allpatterns),'ALL_STAGES_DIRECTION_PATTERNS.csv')
    save(d[~duplicate],'COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz');save(duplicate_rows,'DUPLICATE_REGISTRATIONS.csv')
    save(role,'HISTORY_ROLE_RANKS_USED.csv')
    # Common-image comparison of RAW3 and the target DSTRUCT on identical semantic
    # rank direction. Pair quality/geometry are each required jointly available.
    pairrows=[];paired_images=[]
    use=pp[pp.scope.eq('primary')]
    a=use[use.method.eq('TARGET_DSTRUCT_K3')];b=use[use.method.eq('V21_DSTRUCT_RAW3_K3')]
    joined=a.merge(b,on=['stage_scope','scope','n','m','axis','rank_direction','pool_id','image','building'],suffixes=('_TARGET','_RAW3'))
    ckey=['stage_scope','scope','n','m','axis','rank_direction']
    for kk,g in joined.groupby(ckey):
        rr=dict(zip(ckey,kk));rr.update(common_pools=g.pool_id.nunique(),common_images=g.image.nunique(),common_buildings=g.building.nunique(),comparison='same exact target pool,n,m,historical-axis rank; A/D/member draws not identical across methods')
        for metric in metrics:
            good=g[metric+'_TARGET'].notna()&g[metric+'_RAW3'].notna();z=g[good]
            rr[metric+'_paired_pools']=len(z)
            zi=z.groupby(['image','building'])[[metric+'_TARGET',metric+'_RAW3']].mean()
            zb=zi.groupby(level='building').mean()
            rr[metric+'_paired_images']=len(zi);rr[metric+'_paired_buildings']=len(zb)
            for method in ['TARGET','RAW3']:
                rr[metric+'_'+method]=zi[metric+'_'+method].mean();rr[metric+'_'+method+'_positive_images']=int(zi[metric+'_'+method].gt(1e-9).sum())
                rr[metric+'_'+method+'_building_mean']=zb[metric+'_'+method].mean();rr[metric+'_'+method+'_positive_buildings']=int(zb[metric+'_'+method].gt(1e-9).sum())
            rr[metric+'_RAW3_minus_TARGET']= (zi[metric+'_RAW3']-zi[metric+'_TARGET']).mean()
            rr[metric+'_RAW3_greater_images']=int((zi[metric+'_RAW3']>zi[metric+'_TARGET']+1e-9).sum())
        pairrows.append(rr)
    save(pd.DataFrame(pairrows),'RAW3_TARGET_COMMON_IMAGE_N_M.csv');save(joined,'RAW3_TARGET_PAIRED_POOL_RESULTS.csv.gz')
    keycols=['stage_scope','method','scope','n','m','axis','rank_direction','events','pools','images','buildings','jointly_scored_events','A_failed_events','B_failed_events','C_failed_events']
    keymetrics=['B8L2_same_origin_within','B8L2_same_origin_cross','B8L2_same_origin_gap','B8L2_CA','B8L2_CB','fusion_turn_n_CA','geometry_pair_angle_same_origin_gap','geometry_bev_distance_same_origin_gap','record_time_CA_pct_source_matched']
    keycols += [m+'_'+s for m in keymetrics for s in ['mean_image','median_image','positive_images','valid_images','mean_building']]
    save(sm[keycols],'KEY_STAGED_RESULTS.csv')
    (out/'COMPLETION.json').write_text(json.dumps(dict(existing_events=len(old),new_events=len(new),new_ids_already_existing=new_overlap,duplicate_oriented_registrations=len(duplicate_rows),combined_events=int((~duplicate).sum()),
        stages=['existing_only','new_only','combined_union'],retained_n_m_grids=sorted(GRIDS),aggregation='mean backgrounds within exact XYZ block, blocks within pool, pools within image, images within building',
        quality_patterns='same jointly scored event support for BA and CA, descriptive epsilon 0.1/1/2 Q; not a validated meaningful-difference threshold',
        same_origin_magnitude='abs(C-A)-abs(B-A); original symmetric cross retained',new_fusions_in_this_script=0),indent=2))
    print(sm[keycols[:15]].to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--new',required=True);p.add_argument('--history',required=True);p.add_argument('--new-labels',required=True);p.add_argument('--out',required=True);main(p.parse_args())
