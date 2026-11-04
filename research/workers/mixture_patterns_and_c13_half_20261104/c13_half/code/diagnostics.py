"""Post-fusion descriptive diagnostics; no selection, scoring, or class changes.

The visibility-kernel subset is an explicitly additional diagnostic gate. It is
not part of the official Q acceptance contract and never replaces the primary
automatic estimates. Source-homogeneous time support is enumerated even if zero.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from design import ROOT,OUT,SEED,digest,csv,write_json
from analyze import aggregate,summary_metric,IDCOLS
from run_native import read_gz

def main():
    ev=pd.read_csv(OUT/'analysis/EVENT_METRICS.csv.gz',low_memory=False)
    geo=pd.read_csv(OUT/'audit/GEOMETRY_AUDIT.csv.gz');kernel=geo.set_index('team_key').camera_in_kernel.eq(True).to_dict()
    bundles=pd.read_csv(OUT/'design/PAIRED_BUNDLES.csv.gz')
    f4={r.bundle_id:all(kernel.get(getattr(r,a+'_team_key'),False) for a in 'PQRS') for r in bundles.itertuples()}
    ev['all_ABC_kernel']=ev.ABC_scored & pd.Series([all(kernel.get(e[a+'_team_key'],False) for a in 'ABC') for e in ev.to_dict('records')])
    ev['all_four_kernel']=ev.all_four_scored & ev.bundle_id.map(f4).eq(True)
    checks=[];ims=[];summary=[]
    core=['Q_W','Q_cross','Q_GA','Q_GS','Q_class_shift']
    for (study,direction),g in ev.groupby(['study','direction']):
        mainmask=g.ABC_scored if study=='main_8_4' else g.all_four_scored
        diagnostic=g.all_ABC_kernel if study=='main_8_4' else g.all_four_kernel
        checks.append(dict(study=study,direction=direction,registered_events=len(g),official_complete_events=int(mainmask.sum()),
                           kernel_complete_events=int(diagnostic.sum()),official_images=g[mainmask].image.nunique(),kernel_images=g[diagnostic].image.nunique(),
                           official_buildings=g[mainmask].building.nunique(),kernel_buildings=g[diagnostic].building.nunique(),
                           posthoc_diagnostic_not_official_gate=True))
        _,_,im,_=aggregate(g[diagnostic],core);ims.append(im)
        for m in core:
            z=summary_metric(im,m,int(digest([SEED,'kernel',study,direction,m])[:8],16))
            if z:summary.append(dict(study=study,direction=direction,gate='all_ABC_kernel' if study=='main_8_4' else 'all_four_kernel',**z))
    csv(OUT/'analysis/KERNEL_DIAGNOSTIC_SUPPORT.csv',pd.DataFrame(checks));csv(OUT/'analysis/KERNEL_DIAGNOSTIC_IMAGE.csv',pd.concat(ims));csv(OUT/'analysis/KERNEL_DIAGNOSTIC_SUMMARY.csv',pd.DataFrame(summary))
    # Balanced component shifts use the same two-source-arm baseline as Q_class_shift.
    comps=['IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','ref_node_recall_9','ref_edge_recall_9','diag_wall_coverage_05']
    for m in comps:ev[m+'_class_shift']=ev['C_'+m]-(ev['A_'+m]+ev['B_'+m])/2
    ims=[];sums=[]
    for (study,direction),g in ev.groupby(['study','direction']):
        mask=g.ABC_scored if study=='main_8_4' else g.all_four_scored
        _,_,im,_=aggregate(g[mask],[m+'_class_shift' for m in comps]);ims.append(im)
        for m in comps:
            s=summary_metric(im,m+'_class_shift',int(digest([SEED,'balanced_component',study,direction,m])[:8],16))
            if s:sums.append(dict(study=study,direction=direction,**s))
    csv(OUT/'analysis/BALANCED_COMPONENT_IMAGE.csv',pd.concat(ims));csv(OUT/'analysis/BALANCED_COMPONENT_SUMMARY.csv',pd.DataFrame(sums))
    # True unique endpoint support by replacement class, on all 576 paired bundles.
    scalar=pd.read_csv(OUT/'endpoints/ENDPOINT_SCALARS.csv.gz',low_memory=False).set_index('team_key')
    ep=[]
    for b in bundles.to_dict('records'):
        for arm in 'PQRS':
            r=scalar.loc[b[arm+'_team_key']]
            ep.append(dict(bundle_id=b['bundle_id'],pool_id=b['pool_id'],image=b['image'],building=b['building'],arm=arm,
                           replacement_class='C1' if arm in 'PQ' else 'C3',team_key=b[arm+'_team_key'],score_status=r.score_status,Q_available=pd.notna(r.B8L2),
                           camera_in_kernel=kernel.get(b[arm+'_team_key'],False)))
    ep=pd.DataFrame(ep);assert not ep.team_key.duplicated().any()
    csv(OUT/'analysis/PAIRED_ENDPOINT_SUPPORT.csv.gz',ep)
    z=ep.groupby('replacement_class').agg(endpoints=('team_key','nunique'),Q_available=('Q_available','sum'),images=('image','nunique'),buildings=('building','nunique'),kernel_and_Q=('camera_in_kernel','sum')).reset_index()
    z['Q_missing']=z.endpoints-z.Q_available;z['Q_missing_fraction']=z.Q_missing/z.endpoints
    csv(OUT/'analysis/PAIRED_ENDPOINT_SUPPORT_SUMMARY.csv',z)
    # Enumerate zero T support as well as available support; never pool mixed-source seconds.
    times=[]
    for key,g in ev.groupby(['study','direction']):
        for name,col in [('entire_ABC_same_single_source','time_ABC_single_source'),('XYZ_blocks_same_single_source','time_replacement_blocks_same_source')]:
            h=g[g[col]];times.append(dict(study=key[0],direction=key[1],time_support=name,registered_events=len(g),valid_events=len(h),valid_images=h.image.nunique(),valid_buildings=h.building.nunique(),
                                           source_kinds='|'.join(sorted(h.time_single_source_kind.dropna().astype(str).unique())) if name.startswith('entire') else '|'.join(sorted(h.time_replacement_block_source.dropna().astype(str).unique()))))
    csv(OUT/'analysis/TIME_SUPPORT.csv',pd.DataFrame(times))
    # Keep the replacement blocks fixed and compare the two D draws. Identical
    # D class vectors isolate changes in background member identity from changes
    # in background class counts (all teams retain the same n and 50% replacement).
    bg=pd.read_csv(OUT/'analysis/BACKGROUND_METRICS.csv.gz')
    bvec=ev.drop_duplicates(['study','direction','background_id']).set_index(['study','direction','background_id']).D_class_vector.to_dict()
    paired=[]
    for key,g in bg.groupby(['study','direction','support','pool_id','image','building','block_id']):
        if len(g)!=2:continue
        g=g.sort_values('background_id');a,b=g.iloc[0],g.iloc[1]
        r=dict(zip(['study','direction','support','pool_id','image','building','block_id'],key))
        va=bvec[(a.study,a.direction,a.background_id)];vb=bvec[(b.study,b.direction,b.background_id)]
        r.update(D1_class_vector=va,D2_class_vector=vb,same_D_class_vector=va==vb)
        for m in ['Q_GS','Q_class_shift']:
            r[m+'_absolute_difference']=abs(b[m]-a[m]);r[m+'_sign_flip']=float(a[m]*b[m]<0)
        paired.append(r)
    paired=pd.DataFrame(paired);csv(OUT/'analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL.csv.gz',paired)
    cols=['Q_GS_absolute_difference','Q_class_shift_absolute_difference','Q_GS_sign_flip','Q_class_shift_sign_flip']
    pim=paired.groupby(['study','direction','support','same_D_class_vector','pool_id','image','building'])[cols].mean().reset_index()
    ps=[]
    for key,g in pim.groupby(['study','direction','support','same_D_class_vector']):
        sub=paired[(paired.study==key[0])&(paired.direction==key[1])&(paired.support==key[2])&(paired.same_D_class_vector==key[3])]
        r=dict(zip(['study','direction','support','same_D_class_vector'],key));r.update(images=len(g),buildings=g.building.nunique(),blocks=len(sub))
        r.update({c:g[c].mean() for c in cols});ps.append(r)
    csv(OUT/'analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL_SUMMARY.csv',pd.DataFrame(ps))
    qnames=['time_ABC_single_source','time_replacement_blocks_same_source']
    common_time=ev[ev.study=='paired_6_3'].groupby('bundle_id')[qnames].all()
    write_json(OUT/'audit/ADDITIONAL_DIAGNOSTICS.json',dict(kernel_is_posthoc_diagnostic_only=True,official_estimates_unchanged=True,
              paired_bundles=len(bundles),paired_all_four_single_source_time_bundles=int(common_time.time_ABC_single_source.sum()),
              paired_all_four_same_source_replacement_block_bundles=int(common_time.time_replacement_blocks_same_source.sum()),
              reference_kernel_check='Source reference shapes retained; see REFERENCES_KERNEL.csv',
              directional_mean_quality_differences_are_linked='The two 6/3 signed class-shifts are exact opposites by the common four-endpoint construction; their own W and GS are separately evaluated'))
    refs=[]
    for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']:
        f=np.asarray(p['reference']['floor_xz_h'],float);f=f[:,:2] if f.ndim==2 else f
        a2=np.sum(f[:,0]*np.roll(f[:,1],-1)-np.roll(f[:,0],-1)*f[:,1]);e=np.roll(f,-1,axis=0)-f
        cross=(e[:,0]*(-f[:,1])-e[:,1]*(-f[:,0]))*np.sign(a2)
        refs.append(dict(pool_id=p['pool_id'],image=p['meta']['image'],reference_id=p['meta']['reference_id'],camera_in_reference_kernel=bool(np.all(cross>=-1e-10)),min_signed_edge_cross=float(cross.min())))
    csv(OUT/'audit/REFERENCES_KERNEL.csv',pd.DataFrame(refs))
    print(pd.DataFrame(summary).query("metric in ['Q_GS','Q_class_shift']").to_string(index=False));print(z.to_string(index=False));print(pd.DataFrame(times).to_string(index=False))

if __name__=='__main__':main()
