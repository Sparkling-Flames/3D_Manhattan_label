"""Compare preserved Semi phases on aligned support; never call fusion or refit labels."""
from __future__ import annotations
import json, math, os
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKERS = HERE.parents[1]
OLD = WORKERS / 'personnel_effective_exchange_conditions_20261022/joint_exchange'
NEW = WORKERS / 'personnel_exchange_closure_20261022/semi'
CELL = ['building','image','pool_id','source_class','target_class','n','m_AB']
COMP = ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','ref_node_recall_9','ref_edge_recall_9','height_mean_h','top_y_mean_px','bottom_y_mean_px']
METRICS = [f'{p}_{c}' for p in ['same','cross','net'] for c in COMP]
METRICS += [f'{p}_recorded_time_logratio' for p in ['same','cross','net']]
METRICS += ['A_B8L2','B_B8L2','C_B8L2','source_mean_B8L2','symmetric_B8L2','symmetric_D10','symmetric_logtime', 'same_abs_B8L2','symmetric_cross_abs_B8L2','loss_gt5','loss_gt10','A_failure','B_failure','C_failure']
IDENTITY = ['event_id','physical_triple_id','team_A','team_B','team_C','A_member_workers','B_member_workers','C_member_workers','common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z']

def write(name, frame):
    path=HERE/name; tmp=path.with_name(path.name+'.atomic')
    if isinstance(frame,pd.DataFrame):
        payload=frame.to_csv(index=False).encode('utf-8-sig')
        if str(path).endswith('.gz'):
            import gzip
            payload=gzip.compress(payload,mtime=0)
    else: payload=(json.dumps(frame,ensure_ascii=False,indent=2)+'\n').encode()
    with open(tmp,'wb') as out:
        out.write(payload);out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)

def prepare(d,phase):
    d=d.copy();d['phase']=phase
    for c in ['all_scored','A_failure','B_failure','C_failure','recorded_time_single_source']:
        d[c]=d[c].astype(str).str.lower().eq('true')
    d['source_union']=d.apply(lambda r:'|'.join(sorted(set(r.outgoing_block_X.split('|'))|set(r.same_count_block_Y.split('|')))),axis=1)
    good=d.all_scored
    for arm in 'ABC':d[arm+'_B8L2']=pd.to_numeric(d[arm+'_B8L2'],errors='coerce')
    d['source_mean_B8L2']=(d.A_B8L2+d.B_B8L2)/2
    d['symmetric_B8L2']=d.C_B8L2-d.source_mean_B8L2
    d['symmetric_D10']=d.C_D10-(d.A_D10+d.B_D10)/2
    d['symmetric_logtime']=np.log(d.C_source_time_total_seconds)-.5*(np.log(d.A_source_time_total_seconds)+np.log(d.B_source_time_total_seconds))
    d['same_abs_B8L2']=(d.B_B8L2-d.A_B8L2).abs()
    d['symmetric_cross_abs_B8L2']=((d.C_B8L2-d.A_B8L2).abs()+(d.C_B8L2-d.B_B8L2).abs())/2
    d['loss_gt5']=np.where(good,(d.net_B8L2 < -5).astype(float),np.nan)
    d['loss_gt10']=np.where(good,(d.net_B8L2 < -10).astype(float),np.nan)
    for c in METRICS:
        if c not in d:d[c]=np.nan
        d[c]=pd.to_numeric(d[c],errors='coerce')
        if ('logtime' not in c and 'recorded_time' not in c and 'failure' not in c):d.loc[~good,c]=np.nan
    return d

def cells(d,phase):
    keys=CELL+(['reservoir_id'] if phase=='new' else [])+['common_background']
    bg=d.groupby(keys,dropna=False)[METRICS].mean().reset_index()
    if phase=='new':
        r=bg.groupby(CELL+['reservoir_id'],dropna=False)[METRICS].mean().reset_index()
        c=r.groupby(CELL,dropna=False)[METRICS].mean().reset_index()
    else:c=bg.groupby(CELL,dropna=False)[METRICS].mean().reset_index()
    count=d.groupby(CELL,dropna=False).agg(oriented_events=('event_id','size'),physical_ABC=('physical_triple_id','nunique'),backgrounds=('common_background','nunique'),scored_oriented=('all_scored','sum'),C_teams=('team_C','nunique')).reset_index()
    return c.merge(count,on=CELL,validate='one_to_one'), bg

def summary(c,label):
    im=c.groupby(['building','image'])[METRICS].mean().reset_index()
    bu=im.groupby('building')[METRICS].mean().reset_index()
    row={'scope':label,'cells':len(c),'images':len(im),'buildings':len(bu)}
    row.update(bu[METRICS].mean().to_dict())
    for p in ['same','cross','net']:row[p+'_time_pct']=100*np.expm1(row[p+'_recorded_time_logratio'])
    row['symmetric_time_pct']=100*np.expm1(row['symmetric_logtime'])
    for name,f in [('image',im),('building',bu)]:
        row[name+'_Q_up']=int((f.net_B8L2>0).sum());row[name+'_time_down']=int((f.net_recorded_time_logratio<0).sum())
        row[name+'_both']=int(((f.net_B8L2>0)&(f.net_recorded_time_logratio<0)).sum())
    return row,im,bu

def paper_old(d):
    bg=d.groupby(['building','image','pool_id','n','common_background'],dropna=False)[METRICS].mean().reset_index()
    nn=bg.groupby(['building','image','pool_id','n'])[METRICS].mean().reset_index()
    im=nn.groupby(['building','image'])[METRICS].mean().reset_index()
    bu=im.groupby('building')[METRICS].mean()
    return bu.mean()

def main():
    o=prepare(pd.read_csv(OLD/'SEMI_NATIVE_PREFERRED_DIRECTION_EVENTS.csv.gz',low_memory=False),'old')
    all_new=prepare(pd.read_csv(NEW/'EVENTS_COMPLETE.csv.gz',low_memory=False),'new')
    n=all_new[all_new.analysis_layer.eq('source_partition_expansion')].copy()
    oc,ob=cells(o,'old');nc,nb=cells(n,'new')
    write('OLD_EXACT_EVENTS.csv.gz',o[CELL+IDENTITY+['source_union','all_scored']+METRICS])
    write('NEW_MAIN_EVENT_LINKS.csv.gz',n[CELL+IDENTITY+['source_union','reservoir_id','background_id','all_scored']+METRICS])
    write('OLD_CELLS.csv',oc);write('NEW_CELLS.csv',nc)
    common=oc.merge(nc,on=CELL,suffixes=('_old','_new'),validate='one_to_one')
    for f in ['net_B8L2','symmetric_B8L2','source_mean_B8L2','C_B8L2','net_recorded_time_logratio','net_IoU3D100','net_S_bottom_deg','net_dir','net_Hmean']:
        common[f+'_new_minus_old']=common[f+'_new']-common[f+'_old']
    write('COMMON_14_CELL_COMPARISON.csv',common)
    oldkeys=set(map(tuple,oc[CELL].itertuples(index=False,name=None)))
    mask=nc[CELL].apply(tuple,axis=1).isin(oldkeys)
    same=nc[mask];oldimages=set(o.image)
    rows=[];image_frames=[];building_frames=[]
    sets=[('old_28_common_cell_weights',oc),('new_members_backgrounds_same_14_cells',same),('new_all_cells_on_old_5_images',nc[nc.image.isin(oldimages)]),('new_all_69_cells_7_images',nc),('new_2_images_only',nc[~nc.image.isin(oldimages)])]
    for name,c in sets:
        row,im,bu=summary(c,name);rows.append(row)
        im.insert(0,'scope',name);bu.insert(0,'scope',name);image_frames.append(im);building_frames.append(bu)
    reported=paper_old(o)
    write('SUPPORT_DECOMPOSITION.csv',pd.DataFrame(rows))
    write('SUPPORT_IMAGE_EFFECTS.csv',pd.concat(image_frames,ignore_index=True))
    write('SUPPORT_BUILDING_EFFECTS.csv',pd.concat(building_frames,ignore_index=True))
    # Every old event is associated with exact matching new support, without
    # using event IDs as if mirrors were independent new observations.
    alignment=[];matched=[]
    for _,a in o.iterrows():
        z=n
        for k in CELL:z=z[z[k].eq(a[k])]
        row={k:a[k] for k in CELL+IDENTITY}
        row.update(new_same_cell_oriented=len(z),old_net_Q=a.net_B8L2,old_symmetric_Q=a.symmetric_B8L2)
        for level,extra in [('D',['common_background']),('Z',['changed_count_block_Z']),('D_Z',['common_background','changed_count_block_Z']),('D_Z_source_union',['common_background','changed_count_block_Z','source_union'])]:
            t=z
            for k in extra:t=t[t[k].eq(a[k])]
            row['new_same_'+level+'_oriented']=len(t)
            row['new_same_'+level+'_physical']=t.physical_triple_id.nunique()
            row['new_same_'+level+'_net_Q']=t.loc[t.all_scored,'net_B8L2'].mean()
            row['new_same_'+level+'_symmetric_Q']=t.loc[t.all_scored,'symmetric_B8L2'].mean()
            if level=='D_Z_source_union' and len(t):
                tg=t[CELL+IDENTITY+['source_union','all_scored','symmetric_B8L2','net_B8L2','A_B8L2','B_B8L2','C_B8L2','same_abs_B8L2']].copy()
                tg.insert(0,'old_event_id',a.event_id);matched.append(tg)
        row['same_physical_retained']=bool(a.physical_triple_id in set(z.physical_triple_id));alignment.append(row)
    align=pd.DataFrame(alignment);write('OLD_NEW_EVENT_ALIGNMENT.csv',align)
    if matched:write('FIXED_D_Z_SOURCE_UNION_MATCHES.csv.gz',pd.concat(matched,ignore_index=True))
    # Same-cell comparisons at each supported size; these are actual support
    # contrasts, not an extrapolation of n12 to n14.
    nr=[]
    for size,c in nc.groupby(['n','m_AB']):
        row,im,bu=summary(c,f'n{size[0]}_m{size[1]}');row.update(n=size[0],m=size[1]);nr.append(row)
    write('CURRENT_N_M_RECOMMENDATIONS.csv',pd.DataFrame(nr))
    # Common n12/m4 images versus n14/m3; both use corresponding classes when
    # capacity permits. Compare sizes on fixed picture/direction, explicitly
    # changing member/background populations rather than claiming an n effect.
    sizekeys=['building','image','source_class','target_class']
    a=nc[nc.n.eq(12)&nc.m_AB.eq(4)];b=nc[nc.n.eq(14)&nc.m_AB.eq(3)]
    sizes=a.merge(b,on=sizekeys,suffixes=('_n12m4','_n14m3'),validate='one_to_one')
    for f in ['net_B8L2','net_D10','net_recorded_time_logratio','loss_gt5','loss_gt10']:
        sizes[f+'_n14m3_minus_n12m4']=sizes[f+'_n14m3']-sizes[f+'_n12m4']
    write('COMMON_DIRECTIONS_N12M4_VS_N14M3.csv',sizes)
    # Retain risks by actual picture and background; choice must not use target Q.
    risk=[]
    for (im,nn,mm,src,tgt),g in n.groupby(['image','n','m_AB','source_class','target_class']):
        v=g[g.all_scored]
        risk.append(dict(image=im,building=g.building.iloc[0],n=nn,m=mm,source_class=src,target_class=tgt,
                         physical_ABC=g.physical_triple_id.nunique(),scored_oriented=len(v),
                         loss_gt5=int((v.net_B8L2 < -5).sum()),loss_gt10=int((v.net_B8L2 < -10).sum()),
                         failed_physical=g[g[['A_failure','B_failure','C_failure']].astype(bool).any(axis=1)].physical_triple_id.nunique(),
                         C_fail_unique=g.loc[g.C_failure.astype(bool),'team_C'].nunique(),
                         all_loss_event_ids='|'.join(v.loc[v.net_B8L2 < -10,'event_id'])))
    write('RISK_BY_IMAGE_DIRECTION_N_M.csv.gz',pd.DataFrame(risk))
    # Save actual overlaps and validity before any interpretation.
    info=dict(main_commit='cf053a6e31d17393c0e8216ce15660fa37b8b7bb',data_version='v2',new_fusion_calls=0,
              old_oriented=len(o),new_main_oriented=len(n),new_main_physical=n.physical_triple_id.nunique(),
              common_cells=len(common),old_events_same_physical_in_new=int(align.same_physical_retained.sum()),
              old_events_same_D_Z=int((align.new_same_D_Z_oriented>0).sum()),
              old_paper_Q=float(reported.net_B8L2),old_paper_time_pct=float(100*np.expm1(reported.net_recorded_time_logratio)),
              old_paper_symmetric_Q=float(reported.symmetric_B8L2),
              source='preserved complete events, not author completion text',
              hierarchy='within background -> source reservoir (new) -> image-direction-n-m cell -> image -> building; common cell comparisons use identical cell list',
              evaluation='internal reuse of real v2; no external holdout claim')
    write('ANALYSIS_RECEIPT.json',info)
    print(json.dumps(info,ensure_ascii=False,indent=2))
    print(pd.DataFrame(rows)[['scope','cells','images','buildings','net_B8L2','symmetric_B8L2','net_time_pct']].to_string(index=False))

if __name__=='__main__':main()
