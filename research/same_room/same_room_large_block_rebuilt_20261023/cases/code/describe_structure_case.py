#!/usr/bin/env python3
"""Summarize the one preselected saved case, without native fusion or fitting.

B8 diagnostics re-express the frozen formula on the already saved measurements;
they do not replace scores or interpret nonlinear losses as causal percentages.
"""
from pathlib import Path
import argparse, gzip, importlib.util, json
import numpy as np
import pandas as pd
from PIL import Image

spec=importlib.util.spec_from_file_location('render_saved_case',Path(__file__).with_name('render_exact_case.py'))
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--case',type=Path,required=True);a=ap.parse_args()
    p=a.case;tables=p/'tables';figs=p/'figures'
    e=pd.read_csv(p/'STRICT_ABC_EVENT.csv.gz',keep_default_na=False).iloc[0]
    assert e.event_id=='ABC_0e2d9ba183c4f886c588','This explanation is specific to the frozen selected case.'
    outcomes=pd.read_csv(p/'EXACT_EVENT_EFFECTS.csv.gz').iloc[0]
    s=pd.read_csv(tables/'SIX_TEAM_METRICS.csv');groups=pd.read_csv(tables/'IDENTITY_GROUPS.csv')
    with gzip.open(p/'SIX_TEAM_NATIVE_GEOMETRY.jsonl.gz','rt') as f:states={z['team_key']:z for z in map(json.loads,f)}
    pools={z['pool_id']:z for z in json.load(gzip.open(p/'FROZEN_TWO_POOLS.json.gz','rt'))['images']}
    roles=pd.read_csv(p/'FROZEN_CLASS_ROLES_AND_MEMBERS.csv')
    classes={w:(r.class_id,r.role_zh,r.class_fold_key) for r in roles.itertuples() for w in r.members.split('|')}
    blocks={w:block for block in 'DXYZ' for w in e[block+'_members'].split('|')}
    pd.DataFrame([dict(event_id=e.event_id,worker_id=w,block=blocks[w],class_id=classes[w][0],role_zh=classes[w][1],class_fold_key=classes[w][2]) for w in sorted(blocks)]).to_csv(tables/'MEMBER_BLOCKS_AND_ROLES.csv',index=False)
    raw=[]
    for view in 'ab':
        for r in pools[e['pool_id_'+view]]['records']:
            if r['worker_id'] not in blocks:continue
            w=r['worker_id'];raw.append(dict(event_id=e.event_id,view=view,image=e['image_'+view],worker_id=w,block=blocks[w],class_id=classes[w][0],role_zh=classes[w][1],object_id=r['object_id'],raw_corner_pairs=len(r['points'])//2,raw_corner_pairs_are_not_necessarily_actual_turns=True,B8L2=r['B8L2'],D10=r['D10'],quality_usable=r['quality_usable'],source_time_kind=r['time_source_kind'],source_time_seconds=r['source_time_seconds'],source_order_status=r['order_status'],source_ring_confirmed=r['ring_confirmed']))
    pd.DataFrame(raw).to_csv(tables/'ACTUAL_MEMBERS_BY_VIEW.csv',index=False)
    comp=[]
    for row in s.itertuples():
        floor=1/row.iou_2d-1+row.S_bottom_deg**2/32
        direction=1.5*row.dir**2/(row.dir**2+8**2)
        glob=(row.Hmean/.8)**2;local=(row.Hcenter/.25)**2;pooled=float(np.hypot(floor,direction))
        check=100/(1+pooled+glob+local)
        assert abs(check-row.B8L2)<1e-8
        comp.append(dict(event_id=e.event_id,view=row.view,image=row.image,arm=row.arm,team_key=row.team_key,saved_B8L2=row.B8L2,B8_floor_fidelity_loss=floor,B8_direction_loss=direction,B8_pooled_geometry_loss=pooled,B8_global_height_loss=glob,B8_local_height_loss=local,B8_total_additive_denominator_loss=pooled+glob+local,recomposed_Q_diagnostic_only=check,diagnostic_absolute_difference=abs(check-row.B8L2),formula_version='WQ-B8L2-20261015',interpretation='frozen nonlinear formula diagnostic; not causal percentage; original scalar direction_loss is not relabelled B8'))
    comp=pd.DataFrame(comp);comp.to_csv(tables/'B8_FROZEN_DIAGNOSTIC_COMPONENTS.csv',index=False)
    joined=s.merge(comp[['team_key','B8_floor_fidelity_loss','B8_direction_loss','B8_pooled_geometry_loss','B8_global_height_loss','B8_local_height_loss']],on='team_key',validate='one_to_one')
    metrics=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','height_mean_h','B8_floor_fidelity_loss','B8_direction_loss','B8_pooled_geometry_loss','B8_global_height_loss','B8_local_height_loss']
    contrasts=[]
    for view in 'ab':
        z=joined[joined.view.eq(view)].set_index('arm')
        for to,fr in [('B','A'),('C','A'),('C','B')]:
            row=dict(event_id=e.event_id,view=view,image=e['image_'+view],comparison=to+fr,team_key_from=z.loc[fr,'team_key'],team_key_to=z.loc[to,'team_key'],n=e.n,m=e.m,all_six_score_available=True,recorded_time_pair_eligible=False,recorded_time_delta_seconds=np.nan,time_missing_reason='both incomplete per-worker time and mixed semantics; partial known sums are not team labor')
            row.update({metric:float(z.loc[to,metric]-z.loc[fr,metric]) for metric in metrics});contrasts.append(row)
    pd.DataFrame(contrasts).to_csv(tables/'CONTRASTS_BY_VIEW.csv',index=False)
    keep=['event_id','view','image','arm','team_key','member_workers','B8L2','D10','reference_nodes','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','score_available','complete_evaluable','score_status','recorded_time_eligible','source_time_known_n','k','time_source_kinds','source_time_total_seconds','source_time_known_sum_seconds']
    joined[[c for c in keep if c in joined]].to_csv(tables/'SIX_TEAMS_READABLE.csv',index=False)
    history=[dict(block=block,members=e[block+'_members'],history_q=outcomes['q_'+block],history_q_known_n=outcomes['q_'+block+'_known_n'],history_t=outcomes['t_'+block],history_t_known_n=outcomes['t_'+block+'_known_n'],history_semantics=outcomes.block_history_semantics,heldout_building=e.building) for block in 'DXYZ']
    pd.DataFrame(history).to_csv(tables/'BLOCK_HISTORY.csv',index=False)
    windows={'a':dict(original_pixel_bounds=[1740,1950,340,730],bottom_u_1024_interval=[900,950]),'b':dict(original_pixel_bounds=[1830,2048,250,790],bottom_u_1024_interval=[975,1000])}
    (p/'LOCAL_WINDOW_DEFINITION.json').write_text(json.dumps(dict(event_id=e.event_id,windows=windows,selection='post-selection image-local narrow wall segment inspection; no new cross-view physical identity ruling'),ensure_ascii=False,indent=2)+'\n')
    local=[]
    for view,wd in windows.items():
        lo,hi=wd['bottom_u_1024_interval'];q=groups[groups.view.eq(view)&groups.center_bottom_u_1024.between(lo,hi)].copy();q['case_local_feature_key']='LOCAL_'+view+'_NARROW_WALL';q['feature_key_status']='case-window membership; native identity IDs stay team-local';local.append(q)
    local=pd.concat(local,ignore_index=True);local.to_csv(tables/'LOCAL_IDENTITY_EVIDENCE.csv',index=False)
    fig,axes=R.plt.subplots(2,3,figsize=(13,9),layout='constrained')
    for j,view in enumerate('ab'):
        pool=pools[e['pool_id_'+view]];rawby={r['worker_id']:r for r in pool['records']};ref=pool['reference']['points_1024x512'];im=np.asarray(Image.open(p/'originals'/(e['image_id_'+view]+'.png')));h,w=im.shape[:2];scale=(w/1024,h/512);x0,x1,y0,y1=windows[view]['original_pixel_bounds']
        for col,arm in enumerate('ABC'):
            ax=axes[j,col];z=states[e[f'team_key_{arm}_{view}']];ax.imshow(im)
            for worker in z['member_workers']:R.erp(ax,rawby[worker]['points'],R.COLORS[arm],lw=.6,alpha=.22,scale=scale)
            R.erp(ax,ref,'black',lw=1.6,reference=True,scale=scale);R.erp(ax,z['full_state']['candidate']['points'],R.COLORS[arm],lw=2,scale=scale)
            loc=local[local.view.eq(view)&local.arm.eq(arm)].sort_values('center_top_v_512')
            for k,g in enumerate(loc.itertuples()):
                cx,cy=g.center_top_u_1024*scale[0],json.loads(g.center_json)[0][1]*scale[1]
                color=R.COLORS[arm] if g.selected else '#555555';marker='o' if g.selected else 'x'
                ax.scatter([cx],[cy],s=26,c=color,marker=marker,zorder=9)
                tx=x0+14;ty=y0+30+k*42
                ax.annotate(g.feature_id.replace('node_','n')+f': {g.identity_support}/11'+(' kept' if g.selected else ' dropped'),(cx,cy),xytext=(tx,ty),fontsize=7,color=color,ha='left',bbox=dict(fc='white',ec='none',alpha=.85,pad=1.5),arrowprops=dict(arrowstyle='-',color=color,lw=.7),zorder=10)
            ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(e['image_'+view]+f' | {arm}: threshold 6',fontsize=10)
    fig.suptitle('Image-local extra-corner identity support | frozen original answers, fusion and reference\nLabels are native team-local identities; nearby groups are not summed into one vote',fontsize=12)
    R.savefig(fig,figs,'EXTRA_TURN_IDENTITY_DETAIL')
    fig,axes=R.plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for ax,view in zip(axes,'ab'):
        ref=pools[e['pool_id_'+view]]['reference']['points_1024x512'];R.bev(ax,ref,'black',lw=1.8,label='Reference',ls='--')
        for arm in 'ABC':
            z=states[e[f'team_key_{arm}_{view}']];R.bev(ax,z['full_state']['candidate']['points'],R.COLORS[arm],lw=2,label=arm)
            loc=local[local.view.eq(view)&local.arm.eq(arm)]
            for g in loc.itertuples():
                b,_=R.project(json.loads(g.center_json));x,zz=b[0,0],b[0,2]
                ax.scatter([x],[zz],s=30,marker='o' if g.selected else 'x',facecolors=R.COLORS[arm] if g.selected else '#666666',zorder=5)
                if arm=='C':
                    offset={'node_006':(10,16),'node_007':(10,0),'node_008':(10,-14)}.get(g.feature_id,(5,6)) if view=='b' else (5,6)
                    ax.annotate(g.feature_id.replace('node_','n')+f' ({g.identity_support})',(x,zz),xytext=offset,textcoords='offset points',fontsize=7,color=R.COLORS[arm] if g.selected else '#666666')
        ax.set_xlim((1.1,3.6) if view=='a' else (-.1,2.2));ax.set_ylim((2.4,3.5) if view=='a' else (1.65,2.2));ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('x / camera height h');ax.set_ylabel('z / camera height h');ax.set_title(e['image_'+view]+' | local connection geometry');ax.legend()
    fig.suptitle('Local footprints: dots = selected centers, x = rejected centers\nTwo camera frames are not geometrically registered; native saved ring remains unchanged',fontsize=11)
    R.savefig(fig,figs,'LOCAL_BEV_CONNECTIVITY')
    receipt=dict(event_id=e.event_id,new_fusion=0,new_scoring_of_geometry=0,new_classification=0,diagnostic_formula_reexpression='fixed B8 measurements only, matches stored Q < 1e-8',local_windows=windows,local_identity_rows=len(local),raw_used_rows=len(raw),block_history_Q_range=float(outcomes.history_Q_block_range),all_time_pairs_ineligible=True,geometry_case_is_exploratory=True)
    (p/'EXPLANATION_READOUT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
