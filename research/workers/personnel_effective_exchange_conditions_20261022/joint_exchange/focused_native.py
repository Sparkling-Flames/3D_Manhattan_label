"""Pre-registered Manual high-Q/faster direction: n/m, members, all outcomes."""
from __future__ import annotations
from summarize_joint import *

def run():
    d=pd.read_csv(HERE/'NATIVE_MANUAL_EVENTS_COMPLETE.csv.gz',low_memory=False);d=d[d.source_domain.eq('new_only_labelled')&d.training_QT_direction.eq('q_up__faster')].copy()
    for pre,a,b in [('same','A','B'),('cross','A','C'),('net','B','C')]:
        d[pre+'_B8L2_completion_lower']=d[b+'_B8L2'].fillna(0)-d[a+'_B8L2'].fillna(100);d[pre+'_B8L2_completion_upper']=d[b+'_B8L2'].fillna(100)-d[a+'_B8L2'].fillna(0)
    write(HERE/'NATIVE_PREFERRED_DIRECTION_EVENTS.csv.gz',d)
    rows=[];images=[];buildings=[];metrics=[c for c in PRIMARY if c in d]
    views=[('all',d)]+[('m='+str(m),g) for m,g in d.groupby('m_AB')]+[('n='+str(n),g) for n,g in d.groupby('n')]+[('m='+str(m)+';n='+str(n),g) for (m,n),g in d.groupby(['m_AB','n'])]+[('difficulty='+str(k),g) for k,g in d.groupby('difficulty')]
    for view,g in views:
        for scope,s in [('all_64_failure_denominator',g),('ABC_scored_time_common',g[g.all_scored&g.recorded_time_single_source])]:
            if s.empty:continue
            row,_,im,bu=summarise_group(s,dict(view=view,scope=scope),metrics);rows.append(row);images.append(im);buildings.append(bu)
    write(HERE/'NATIVE_PREFERRED_N_M_RESPONSE.csv',pd.DataFrame(rows));write(HERE/'NATIVE_PREFERRED_IMAGE_RESPONSES.csv.gz',pd.concat(images,ignore_index=True));write(HERE/'NATIVE_PREFERRED_BUILDING_RESPONSES.csv.gz',pd.concat(buildings,ignore_index=True))
    labs=pd.read_csv(TAX/'JOINT_LABELS_LOBO.csv.gz');roles=[]
    for (building,src,dst),g in d.groupby(['building','source_class','target_class']):
        fold=labs[labs.condition.eq('manual')&labs.heldout_building.eq(building)&labs.known]
        for side,cl in [('source',src),('target',dst)]:
            w=fold[fold.coarse_label.eq(cl)];r=dict(building=building,side=side,exact_fold_class=cl,selected_family=w.selected_family.iloc[0],workers='|'.join(sorted(w.worker_id)),historical_members=len(w),actual_block_workers='|'.join(sorted(set('|'.join(g['same_count_block_Y' if side=='source' else 'changed_count_block_Z']).split('|')))))
            for f in FEATURES:r[f]=float(w[f].mean())
            roles.append(r)
    write(HERE/'NATIVE_PREFERRED_CLASS_ROLES_AND_MEMBERS.csv',pd.DataFrame(roles))
    cols=['view','scope','events','images','buildings','same_B8L2','cross_B8L2','net_B8L2','net_recorded_time_geomean_pct','abs_Q_change_advantage','image_QT_both','image_QT_known','net_failure_difference']
    print(pd.DataFrame(rows)[cols].to_string(index=False),flush=True)

if __name__=='__main__':run()
