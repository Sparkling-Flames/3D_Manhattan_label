"""Targeted support, member and background explanations from cached event scalars."""
from __future__ import annotations
from analyze_semi_adoption import *

def main():
    old=prepare(pd.read_csv(OLD/'SEMI_NATIVE_PREFERRED_DIRECTION_EVENTS.csv.gz',low_memory=False),'old')
    new=prepare(pd.read_csv(NEW/'EVENTS_COMPLETE.csv.gz',low_memory=False),'new')
    new=new[new.analysis_layer.eq('source_partition_expansion')].copy()
    rows=[]
    for (im,nn,mm,src,tgt,rid,bg),g in new.groupby(['image','n','m_AB','source_class','target_class','reservoir_id','common_background']):
        v=g[g.all_scored]
        f=g.iloc[0]
        row={k:f[k] for k in ['building','image','n','m_AB','source_class','target_class','reservoir_id','common_background','changed_count_block_Z','source_union']}
        row.update(physical_ABC=g.physical_triple_id.nunique(),oriented_scored=len(v),net_B8L2=v.net_B8L2.mean(),symmetric_B8L2=v.symmetric_B8L2.mean(),
                   net_time_pct=100*np.expm1(g.net_recorded_time_logratio.mean()),net_Q_up=int((v.net_B8L2>0).sum()),net_loss_gt5=int((v.net_B8L2<-5).sum()),
                   net_loss_gt10=int((v.net_B8L2<-10).sum()),C_B8L2=v.C_B8L2.mean(),source_mean_B8L2=v.source_mean_B8L2.mean(),
                   same_abs_B8L2=v.same_abs_B8L2.mean(),source_Q_min=v.B_B8L2.min(),source_Q_max=v.B_B8L2.max(),
                   failed_physical=g[g[['A_failure','B_failure','C_failure']].astype(bool).any(axis=1)].physical_triple_id.nunique())
        rows.append(row)
    bg=pd.DataFrame(rows);write('ALL_BACKGROUND_BLOCK_REPETITION.csv',bg)
    case=bg[bg.image.isin(['7y3sRwLe3Va-13','Z6MFQCViBuw-10'])&bg.m_AB.eq(4)&bg.n.isin([12,14])]
    write('CASE_BACKGROUND_BLOCKS.csv',case)
    rep=[]
    for (nn,mm),g in bg.groupby(['n','m_AB']):
        good=g[g.net_B8L2.notna()]
        rep.append(dict(n=nn,m=mm,background_reservoir_directions=len(g),evaluable_background_reservoir_directions=len(good),
                        net_Q_positive=int((good.net_B8L2>0).sum()),mean_time_lower=int((g.net_time_pct<0).sum()),
                        both_positive=int(((g.net_B8L2>0)&(g.net_time_pct<0)).sum()),
                        mean_Q_ge_minus1=int((good.net_B8L2>=-1).sum()),
                        mean_Q_ge_minus2=int((good.net_B8L2>=-2).sum()),
                        time_down_Q_ge_minus1=int(((g.net_time_pct<0)&(g.net_B8L2>=-1)).sum()),
                        mean_Q_loss_gt5=int((good.net_B8L2 < -5).sum()),images=g.image.nunique(),buildings=g.building.nunique()))
    write('N_M_BACKGROUND_REPETITION.csv',pd.DataFrame(rep))
    # At 7y-13/n12/m4 the full eligible source has exactly eight members and Z
    # exactly four; all nine common backgrounds and all 35 source partitions
    # are already present. These are no new fusions and no selected endpoints.
    o=old[old.image.eq('7y3sRwLe3Va-13')&old.n.eq(12)&old.m_AB.eq(4)]
    g=new[new.image.eq('7y3sRwLe3Va-13')&new.n.eq(12)&new.m_AB.eq(4)]
    same=g[g.common_background.isin(o.common_background)]
    stages=[('old_two_directed_paths',o,'net_B8L2'),('old_two_paths_symmetric',o,'symmetric_B8L2'),('same_two_D_and_Z_all_source_partitions',same,'symmetric_B8L2'),('all_nine_D_same_Z_all_source_partitions',g,'symmetric_B8L2')]
    dr=[]
    for name,d,metric in stages:
        b=d.groupby('common_background')[metric].mean()
        dr.append(dict(scope=name,Q=float(b.mean()),backgrounds=len(b),physical_ABC=d.physical_triple_id.nunique(),oriented_events=len(d),
                       evaluation_metric=metric,positive_backgrounds=int((b>0).sum()),exact_target_workers='W109|W115|W120|W127'))
    decomp=pd.DataFrame(dr);decomp['change_from_previous']=decomp.Q.diff();write('CASE_7Y13_N12M4_SUPPORT_DECOMPOSITION.csv',decomp)
    # Hold back the exact old physical triples, keeping all prespecified new
    # member/background cells. This checks expanded combinations, not new data.
    held=new[~new.physical_triple_id.isin(old.physical_triple_id)]
    oc,_=cells(old,'old');hc,_=cells(held,'new');nc,_=cells(new,'new')
    oldkeys=set(map(tuple,oc[CELL].itertuples(index=False,name=None)))
    checks=[]
    for label,d in [('all_new',nc),('remove_11_old_physical_triples',hc)]:
        mask=d[CELL].apply(tuple,axis=1).isin(oldkeys)
        for scope,c in [('same_14_cells',d[mask]),('all_69_cells',d)]:
            r,im,bu=summary(c,label+'__'+scope);checks.append(r)
    write('EXPANDED_COMBINATIONS_CHECK.csv',pd.DataFrame(checks))
    # Extract existing conditional member contributions; retain source identity.
    members=pd.read_csv(NEW/'SOURCE_MEMBER_BLOCK_ASSOCIATIONS.csv')
    members=members[members.image.isin(['7y3sRwLe3Va-13','Z6MFQCViBuw-10'])&members.n.eq(12)&members.m_AB.eq(4)]
    members['source_file']='personnel_exchange_closure_20261022/semi/SOURCE_MEMBER_BLOCK_ASSOCIATIONS.csv'
    write('CASE_CONDITIONAL_SOURCE_MEMBERS.csv',members)
    # Save both same-support size alternatives at exactly the same seven
    # picture/direction pairs. Member/background samples still differ.
    ss=pd.read_csv(HERE/'COMMON_DIRECTIONS_N12M4_VS_N14M3.csv');rr=[]
    for suffix in ['n12m4','n14m3']:
        fs=['net_B8L2','net_D10','net_recorded_time_logratio','loss_gt5','loss_gt10']
        z=ss[['building','image']+[f+'_'+suffix for f in fs]].rename(columns={f+'_'+suffix:f for f in fs})
        im=z.groupby(['building','image'])[fs].mean();bu=im.groupby('building')[fs].mean()
        row={'condition':suffix,'common_direction_cells':len(ss),'images':len(im),'buildings':len(bu)};row.update(bu.mean().to_dict());row['time_pct']=100*np.expm1(row['net_recorded_time_logratio']);rr.append(row)
    write('COMMON_SUPPORT_SIZE_COMPARISON.csv',pd.DataFrame(rr))
    # Usable roles keep building-fold class IDs separate; all worker sets below
    # are explicitly unions over registered blocks, not a universal class list.
    role_table=pd.read_csv(NEW/'CLASS_ROLES_AND_MEMBERS.csv')
    cell_table,_=cells(new,'new');role_rows=[]
    recommended=new[((new.n==12)&(new.m_AB==4))|((new.n==14)&(new.m_AB==3))|((new.n==16)&(new.m_AB==3))]
    for keys,z in recommended.groupby(CELL):
        row=dict(zip(CELL,keys));mask=pd.Series(True,index=cell_table.index)
        for k,v in row.items():mask &= cell_table[k].eq(v)
        summary_row=cell_table[mask].iloc[0]
        for metric in ['net_B8L2','net_D10','net_IoU3D100','net_iou_2d','net_S_bottom_deg','net_dir','net_Hmean','net_Hcenter','net_omission','net_extension','net_nodes','net_recorded_time_logratio','loss_gt5','loss_gt10','physical_ABC','backgrounds']:
            row[metric]=summary_row[metric]
        row['recorded_time_pct']=100*np.expm1(row['net_recorded_time_logratio'])
        for side,cl in [('source',row['source_class']),('target',row['target_class'])]:
            rc=role_table[role_table.heldout_building.eq(row['building'])&role_table.coarse_label.eq(cl)].iloc[0]
            for field in ['historical_members','historical_member_n','q_history','q_downside','t_history','turn_history','short_history','redundancy_history','n_images_minimum','n_buildings_minimum']:
                row[side+'_'+field]=rc[field]
        for role,field in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z'),('D','common_background')]:
            row['registered_'+role+'_workers_union']='|'.join(sorted(set('|'.join(z[field]).split('|'))))
        row['role_definition']='held-out-building Semi EQT class; membership unions are descriptive, exact teams use event link table'
        role_rows.append(row)
    write('RECOMMENDATION_ROLE_MEMBERS.csv',pd.DataFrame(role_rows))
    print(decomp.to_string(index=False));print(pd.DataFrame(rr).to_string(index=False))

if __name__=='__main__':main()
