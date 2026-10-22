"""Semi's supported efficiency direction, preserving every member-path tail."""
from __future__ import annotations
from summarize_joint import *

def run():
    d=pd.read_csv(HERE/'NATIVE_SEMI_EVENTS_COMPLETE.csv.gz',low_memory=False);preferred=d[d.source_domain.eq('new_only_labelled')&d.training_QT_direction.eq('q_up__faster')].copy()
    write(HERE/'SEMI_NATIVE_PREFERRED_DIRECTION_EVENTS.csv.gz',preferred)
    rows=[];images=[];buildings=[];metrics=[c for c in PRIMARY if c in d]
    for view,g in [('all',preferred)]+[('n='+str(n),g) for n,g in preferred.groupby('n')]+[('difficulty='+str(di),g) for di,g in preferred.groupby('difficulty')]:
        r,_,im,bu=summarise_group(g,dict(view=view,scope='ABC_scored_time_common'),metrics);rows.append(r);images.append(im);buildings.append(bu)
    write(HERE/'SEMI_NATIVE_PREFERRED_N_RESPONSE.csv',pd.DataFrame(rows));write(HERE/'SEMI_NATIVE_PREFERRED_IMAGE_RESPONSES.csv.gz',pd.concat(images,ignore_index=True));write(HERE/'SEMI_NATIVE_PREFERRED_BUILDING_RESPONSES.csv.gz',pd.concat(buildings,ignore_index=True))
    labs=pd.read_csv(TAX/'JOINT_LABELS_LOBO.csv.gz');roles=[]
    for (building,src,dst),g in preferred.groupby(['building','source_class','target_class']):
        fold=labs[labs.condition.eq('semi')&labs.heldout_building.eq(building)&labs.known]
        for side,cl in [('source',src),('target',dst)]:
            w=fold[fold.coarse_label.eq(cl)];r=dict(building=building,source_class=src,target_class=dst,side=side,exact_fold_class=cl,selected_family=w.selected_family.iloc[0],workers='|'.join(sorted(w.worker_id)),historical_members=len(w),actual_block_workers='|'.join(sorted(set('|'.join(g['same_count_block_Y' if side=='source' else 'changed_count_block_Z']).split('|')))))
            for f in FEATURES:r[f]=float(w[f].mean())
            roles.append(r)
    write(HERE/'SEMI_NATIVE_PREFERRED_CLASS_ROLES_AND_MEMBERS.csv',pd.DataFrame(roles))
    tail=preferred[['event_id','image','building','n','m_AB','path_seed','source_class','target_class','team_A','team_B','team_C','common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z','same_B8L2','cross_B8L2','net_B8L2','same_recorded_time_pct','cross_recorded_time_pct','net_recorded_time_pct','same_loss_gt5','cross_loss_gt5','net_loss_gt5','same_loss_gt10','cross_loss_gt10','net_loss_gt10']].copy();write(HERE/'SEMI_NATIVE_MEMBER_BACKGROUND_RESPONSES.csv',tail)
    print(pd.DataFrame(rows)[['view','events','images','buildings','same_B8L2','cross_B8L2','net_B8L2','net_recorded_time_geomean_pct','abs_Q_change_advantage','image_QT_both','image_QT_known']].to_string(index=False));print('actual_time_down_events',int(preferred.net_recorded_time_pct.lt(0).sum()),'of',len(preferred))

if __name__=='__main__':run()
