#!/usr/bin/env python3
"""Read six saved native states, draw metric-correct ERP curves and local votes.

No score, fusion, class, reference or member change. Project uses the frozen
corner_distance.project convention; ERP edges sample straight 3D wall edges.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_first_abc_mpl')
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

COLORS={'A':'#2166ac','B':'#e08214','C':'#1b9e77','GT':'#111111'}
EVENT='ABC_0001066d44f97b218867'

def project(points):
    # Byte-level mathematical convention from frozen corner_distance.project.
    p=np.asarray(points,float);top,bottom=p[::2],p[1::2]
    phi=2*np.pi*(bottom[:,0]/1024-.5);r=1/np.tan(np.pi*(bottom[:,1]/512-.5))
    y=r*np.tan(np.pi*(.5-top[:,1]/512));b=np.column_stack((r*np.sin(phi),-np.ones(len(r)),-r*np.cos(phi)));t=b.copy();t[:,1]=y
    return b,t

def inverse(xyz):
    v=np.asarray(xyz,float);u=(np.arctan2(v[:,0],-v[:,2])/(2*np.pi)+.5)*1024
    y=(.5-np.arctan2(v[:,1],np.hypot(v[:,0],v[:,2]))/np.pi)*512
    return np.column_stack((u,y))

def curve_edges(points):
    b,t=project(points);edges=[]
    for vertices in [b,t]:
        for i in range(len(vertices)):
            f=np.linspace(0,1,161)[:,None];xyz=(1-f)*vertices[i]+f*vertices[(i+1)%len(vertices)];edges.append(inverse(xyz))
    for i in range(len(b)):edges.append(inverse(np.linspace(b[i],t[i],41)))
    return edges

def draw_erp(ax,points,color,lw=1.5,alpha=1,label=None,reference=False):
    # Source points are 1024x512, originals are 2048x1024. Break seam jumps.
    first=True
    for edge in curve_edges(points):
        cut=np.where(np.abs(np.diff(edge[:,0]))>512)[0]+1
        for segment in np.split(edge,cut):
            if len(segment)<2:continue
            l,=ax.plot(segment[:,0]*2,segment[:,1]*2,color=color,lw=lw,alpha=alpha,label=label if first else None,zorder=5 if reference else 6)
            if reference:l.set_path_effects([pe.Stroke(linewidth=lw+1.8,foreground='white'),pe.Normal()])
            first=False
    p=np.asarray(points);ax.scatter(p[:,0]*2,p[:,1]*2,s=7,c=color,alpha=alpha,zorder=7,edgecolors='white' if reference else 'none',linewidths=.4)

def draw_bev(ax,points,color,lw=1.5,alpha=1,label=None,ls='-'):
    b,_=project(points);q=np.vstack((b,b[0]));ax.plot(q[:,0],q[:,2],color=color,lw=lw,alpha=alpha,label=label,ls=ls);return b

def write(df,p):df.to_csv(p,index=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',type=Path,required=True);ap.add_argument('--originals',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);tables=a.out/'tables';figs=a.out/'figures';tables.mkdir(exist_ok=True);figs.mkdir(exist_ok=True)
    event=pd.read_csv(a.case/'STRICT_ABC_EVENT.csv.gz').iloc[0];assert event.event_id==EVENT
    pooldoc=json.load(gzip.open(a.case/'FROZEN_TWO_POOLS.json.gz','rt'));pools={p['pool_id']:p for p in pooldoc['images']}
    scalars=pd.read_csv(a.case/'native/ENDPOINT_SCALARS.csv.gz').set_index('team_key');states={};source_rows=[]
    for p in sorted((a.case/'native/parts').rglob('*.geometry_state.jsonl.gz')):
        with gzip.open(p,'rt') as f:
            for line_no,line in enumerate(f,1):
                z=json.loads(line);states[z['team_key']]=z;source_rows.append(dict(team_key=z['team_key'],source=p.relative_to(a.case).as_posix(),line_1based=line_no,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    assert len(states)==6
    ledgers=[];members=[];subgroups=[];edges=[];brackets=[];raw=[];viewindex=[];metrics=[];teams={};images={};rois={}
    for side in ['a','b']:
        pool=pools[event['pool_id_'+side]];rawby={r['worker_id']:r for r in pool['records']};image=event['image_'+side];image_id=event['image_id_'+side];impath=a.originals/(image_id+'.png');im=np.asarray(Image.open(impath));assert im.shape[:2]==(1024,2048);images[side]=im
        ref=np.asarray(pool['reference']['points_1024x512']);rb,rt=project(ref);assert np.allclose(rb[:,[0,2]],pool['reference']['floor_xz_h'],atol=1e-8)
        allbottom=[];used=set()
        for arm in ['A','B','C']:
            key=event['team_key_'+arm+'_'+side];z=states[key];state=z['full_state'];s=scalars.loc[key];points=np.asarray(state['candidate']['points']);b,t=project(points);assert np.allclose(b[:,[0,2]],state['candidate']['footprint'],atol=1e-8)
            teams[side,arm]=z;allbottom.extend(points[1::2]);ws=list(z['member_workers']);assert set(ws)==set(event[arm+'_members'].split('|'));used.update(ws)
            row=dict(event_id=EVENT,view=side,image=image,arm=arm,team_key=key,n=int(event.n),m=int(event.m),D_members=event.D_members,member_workers='|'.join(ws),source_role=event.source_role,target_role=event.target_role,minimum_support=state['minimum_support'],identity_groups=len(state['identity_groups']),selected_groups=sum(g['selected'] for g in state['identity_groups']),reference_area_h2=abs(np.sum(rb[:,0]*np.roll(rb[:,2],-1)-rb[:,2]*np.roll(rb[:,0],-1)))/2,reference_mean_height_h=float(np.mean(rt[:,1]+1)),candidate_mean_height_h=float(np.mean(t[:,1]+1)))
            for c in ['B8L2','D10','S_bottom_deg','dir','Hmean','Hcenter','iou_2d','omission','extension','boundary_loss','direction_loss','global_height_loss','local_height_loss','height_loss','floor_area_camera_h2','height_mean_h','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','recorded_time_total_seconds','recorded_time_eligible','time_source_kinds','score_status']:
                row[c]=s.get(c)
            metrics.append(row)
            for g in state['identity_groups']:
                c=np.asarray(g['center']);gb,gt=project(c);base=dict(event_id=EVENT,view=side,image=image,arm=arm,team_key=key,feature_id=g['feature_id'],feature_scope='team_local_not_cross_view_identity',n=len(ws),minimum_support=state['minimum_support'],selected=g['selected'])
                mr=g['members'];arr=np.asarray([x['points'] for x in mr]);md=np.median(arr,axis=0);match=np.allclose(md,c,rtol=0,atol=1e-8)
                ledgers.append({**base,'identity_support':g['support'],'top_support':g['top_support'],'bottom_support':g['bottom_support'],'joint_support':g['joint_support'],'member_workers':'|'.join(x['worker'] for x in mr),'center_top_u_1024':c[0,0],'center_top_v_512':c[0,1],'center_bottom_u_1024':c[1,0],'center_bottom_v_512':c[1,1],'center_bottom_x_h':gb[0,0],'center_bottom_z_h':gb[0,2],'center_top_y_h':gt[0,1],'maximum_top_angle_deg':g.get('maximum_top_angle'),'maximum_bottom_angle_deg':g.get('maximum_bottom_angle'),'center_equals_coordinate_medians':match})
                for member in mr:
                    p=np.asarray(member['points']);record=rawby[member['worker']];members.append({**base,'worker_id':member['worker'],'annotation_id':member['id'],'object_id':record['object_id'],'pair_index':member['pair_index'],'source_pair_index':member['source_pair_index'],'raw_top_u_1024':p[0,0],'raw_top_v_512':p[0,1],'raw_bottom_u_1024':p[1,0],'raw_bottom_v_512':p[1,1]})
                for coordinate,(rr,cc) in {'top_u':(0,0),'top_v':(0,1),'bottom_u':(1,0),'bottom_v':(1,1)}.items():
                    vals=arr[:,rr,cc];order=np.argsort(vals,kind='stable');lo=(len(vals)-1)//2;hi=len(vals)//2
                    brackets.append({**base,'coordinate':coordinate,'lower_worker':mr[order[lo]]['worker'],'upper_worker':mr[order[hi]]['worker'],'lower_value':vals[order[lo]],'upper_value':vals[order[hi]],'coordinate_median':md[rr,cc],'saved_center_value':c[rr,cc],'matches_saved_center':bool(abs(md[rr,cc]-c[rr,cc])<1e-8),'all_ordered_workers':'|'.join(mr[i]['worker'] for i in order),'all_ordered_values':'|'.join(format(vals[i],'.12g') for i in order)})
                for boundary in ['top','bottom']:
                    for gi,pg in enumerate(g.get(boundary+'_position_groups_9deg',[])):
                        subgroups.append({**base,'boundary':boundary,'position_group_index':gi,'radius_deg':9,'support':pg['support'],'members_json':json.dumps(pg['members'],ensure_ascii=False,separators=(',',':'))})
            for i,e in enumerate(state['ring_diagnostics']['edges']):edges.append(dict(event_id=EVENT,view=side,image=image,arm=arm,team_key=key,edge_index=i,feature_a=e['feature_ids'][0],feature_b=e['feature_ids'][1],direct_support=e['direct_support'],direct_workers='|'.join(e['direct_workers']),projected_support=e['projected_support'],projected_workers='|'.join(e['projected_workers']),selected_ring_policy=state['ring_diagnostics']['policy'],tied_best=state['ring_diagnostics']['tied_best'],ring_confirmed=state['ring_diagnostics']['ring_confirmed']))
        for w in sorted(used):
            r=rawby[w];raw.append(dict(event_id=EVENT,view=side,image=image,pool_id=pool['pool_id'],worker_id=w,object_id=r['object_id'],annotation_id=r['id'],arms='|'.join(arm for arm in 'ABC' if w in event[arm+'_members'].split('|')),block='D' if w in event.D_members.split('|') else next(k for k in 'XYZ' if w in event[k+'_members'].split('|')),points_1024x512_json=json.dumps(r['points'],separators=(',',':')),source_time_kind=r.get('time_source_kind'),source_time_seconds=r.get('source_time_seconds'),origin=r.get('origin')))
        # Choose a visible local diagnostic region by geometric spread only.
        # No Q is used. It is a separate image-local corner in each view.
        dist=[];allbottom=np.asarray(allbottom)
        for pt in ref[1::2]:
            offsets=allbottom-pt;offsets[:,0]=(offsets[:,0]+512)%1024-512;nearest=[]
            for arm in 'ABC':
                p=np.asarray(teams[side,arm]['full_state']['candidate']['points'])[1::2];u=(p[:,0]-pt[0]+512)%1024-512;v=p[:,1]-pt[1];nearest.append(float(np.min(np.hypot(u,v))))
            dist.append(max(nearest))
        ri=int(np.argmax(dist));center=ref[1::2][ri]*2;roi=[max(0,center[0]-135),min(2048,center[0]+135),max(0,center[1]-85),min(1024,center[1]+85)];rois[side]=roi
        viewindex.append(dict(event_id=EVENT,view=side,image=image,image_id=image_id,original_path='../originals/'+impath.name,original_width=2048,original_height=1024,original_sha256=hashlib.sha256(impath.read_bytes()).hexdigest(),reference_id=event['reference_id_'+side],reference_corner_index_zero_based=ri,roi_xmin_2048=roi[0],roi_xmax_2048=roi[1],roi_ymin_1024=roi[2],roi_ymax_1024=roi[3],roi_selection='largest nearest-floor-point displacement across ABC at a reference corner; no Q',coordinate_frame='local camera of this view; no cross-view registration'))
    for name,rows in [('IDENTITY_GROUPS',ledgers),('IDENTITY_MEMBERS',members),('POSITION_SUBGROUPS_9DEG',subgroups),('RING_EDGES',edges),('MEDIAN_BRACKETS',brackets),('USED_RAW_ANSWERS',raw),('VIEW_IMAGE_INDEX',viewindex),('SIX_TEAM_METRICS',metrics),('STATE_SOURCE_INDEX',source_rows)]:write(pd.DataFrame(rows),tables/(name+'.csv'))
    # Overview: actual release images with 3D-projected boundaries and camera BEV.
    fig,axes=plt.subplots(2,2,figsize=(15,10.4),gridspec_kw={'width_ratios':[2.5,1]},layout='constrained')
    for j,side in enumerate(['a','b']):
        pool=pools[event['pool_id_'+side]];ref=pool['reference']['points_1024x512'];ax,bev=axes[j];ax.imshow(images[side]);draw_erp(ax,ref,COLORS['GT'],lw=1.6,label='Reference',reference=True);draw_bev(bev,ref,COLORS['GT'],lw=2,label='Reference',ls='--')
        for arm in 'ABC':
            z=teams[side,arm];pts=z['full_state']['candidate']['points'];q=scalars.loc[z['team_key'],'B8L2'];draw_erp(ax,pts,COLORS[arm],lw=1.2,label=f'{arm}: Q={q:.2f}');draw_bev(bev,pts,COLORS[arm],lw=1.7,label=arm)
        x0,x1,y0,y1=rois[side];ax.add_patch(plt.Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='magenta',lw=1.2,ls='--'));ax.set_title(event['image_'+side]+' | actual release image + frozen reference/fusion');ax.set_xlim(0,2048);ax.set_ylim(1024,0);ax.set_xticks([]);ax.set_yticks([]);ax.legend(loc='upper left',ncol=4,fontsize=8,framealpha=.8)
        bev.plot(0,0,'k+',ms=8,label='Camera');bev.set_aspect('equal');bev.grid(alpha=.2);bev.set_xlabel('x / camera height h');bev.set_ylabel('z / camera height h');bev.set_title('BEV in this camera frame');bev.legend(fontsize=8)
    fig.suptitle('Same exact adjustment in two views: n=6, m=5, fixed core D={W109}\nA/B: 5 regular-turn + 1 more-turn; C: 6 more-turn. All six have 4 turns.',fontsize=12);fig.savefig(figs/'CASE_OVERVIEW_ERP_BEV.png',dpi=170);fig.savefig(figs/'CASE_OVERVIEW_ERP_BEV.pdf');plt.close(fig)
    # All raw worker polygons in every exact team, with fixed reference/fusion.
    fig,axes=plt.subplots(2,3,figsize=(15,9.5),layout='constrained')
    for j,side in enumerate(['a','b']):
        pool=pools[event['pool_id_'+side]];rawby={r['worker_id']:r for r in pool['records']};ref=pool['reference']['points_1024x512'];allcoords=[]
        for w in sorted(set('|'.join(event[a+'_members'] for a in 'ABC').split('|'))):allcoords.extend(project(rawby[w]['points'])[0][:,[0,2]])
        allcoords=np.asarray(allcoords);lo=allcoords.min(0)-.15;hi=allcoords.max(0)+.15
        for c,arm in enumerate('ABC'):
            ax=axes[j,c];z=teams[side,arm];ws=z['member_workers'];palette=plt.get_cmap('tab10')
            for wi,w in enumerate(ws):draw_bev(ax,rawby[w]['points'],palette(wi),lw=.85,alpha=.65,label=w+(' (D)' if w==event.D_members else ''))
            draw_bev(ax,ref,'black',lw=1.8,label='Reference',ls='--');draw_bev(ax,z['full_state']['candidate']['points'],COLORS[arm],lw=2.8,label=arm+' fusion');ax.plot(0,0,'k+',ms=6);ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.set_title(event['image_'+side]+f' | {arm}, Q={scalars.loc[z["team_key"],"B8L2"]:.2f}');ax.legend(ncol=2,fontsize=7,loc='best',framealpha=.85)
    fig.suptitle('Every exact member raw answer; no alignment or shape correction',fontsize=12);fig.savefig(figs/'ALL_MEMBERS_RAW_BEV.png',dpi=175);fig.savefig(figs/'ALL_MEMBERS_RAW_BEV.pdf');plt.close(fig)
    # Matching local windows for each arm within a view, preserving raw pixels.
    fig,axes=plt.subplots(2,3,figsize=(15,7.4),layout='constrained')
    for j,side in enumerate(['a','b']):
        pool=pools[event['pool_id_'+side]];rawby={r['worker_id']:r for r in pool['records']};ref=pool['reference']['points_1024x512'];x0,x1,y0,y1=rois[side]
        for c,arm in enumerate('ABC'):
            ax=axes[j,c];ax.imshow(images[side]);z=teams[side,arm]
            for w in z['member_workers']:draw_erp(ax,rawby[w]['points'],COLORS[arm],lw=.65,alpha=.28)
            draw_erp(ax,ref,'black',lw=2,reference=True);draw_erp(ax,z['full_state']['candidate']['points'],COLORS[arm],lw=2);ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(event['image_'+side]+' | '+arm+' raw (thin), fusion (thick), reference (black/white)',fontsize=9)
    fig.suptitle('Local floor-corner windows: 3D wall edges projected to ERP curves\nSame crop across A/B/C within each view; corners are view-local, not cross-view identity labels.',fontsize=11);fig.savefig(figs/'LOCAL_RAW_FUSION_REFERENCE.png',dpi=180);fig.savefig(figs/'LOCAL_RAW_FUSION_REFERENCE.pdf');plt.close(fig)
    # Local support: every identity group is retained, including any unselected.
    ledger=pd.DataFrame(ledgers);assert ledger.center_equals_coordinate_medians.all()
    fig,ax=plt.subplots(figsize=(11,4.7),layout='constrained');pivot=ledger.pivot(index=['image','arm'],columns='feature_id',values='identity_support');v=pivot.to_numpy();im=ax.imshow(v,vmin=0,vmax=6,cmap='Blues',aspect='auto')
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):ax.text(j,i,f'{int(v[i,j])}/6\nthreshold 3',ha='center',va='center',fontsize=9,color='white' if v[i,j]>=4 else 'black')
    ax.set_yticks(range(len(pivot)),[f'{i}  {arm}' for i,arm in pivot.index]);ax.set_xticks(range(len(pivot.columns)),pivot.columns);ax.set_xlabel('Native identity group (local to each team)');ax.set_title('All identities already exceed the frozen vote threshold\nThe response is in estimated positions / directions / scale, not node-count gain');fig.colorbar(im,ax=ax,label='Distinct worker support');fig.savefig(figs/'IDENTITY_SUPPORT.png',dpi=180);fig.savefig(figs/'IDENTITY_SUPPORT.pdf');plt.close(fig)
    receipt=dict(event_id=EVENT,stage='new_rebuilt_design_case_visualization_not_restored_original',new_fusion=0,new_scoring=0,new_labels=0,source_case=str(a.case),views=2,teams=len(states),used_distinct_raw_answers=len(raw),identity_groups=len(ledgers),identity_member_rows=len(members),position_groups=len(subgroups),ring_edges=len(edges),median_coordinate_rows=len(brackets),all_centers_equal_coordinate_medians=bool(ledger.center_equals_coordinate_medians.all()),thresholds=sorted(ledger.minimum_support.unique().tolist()),identity_support_counts=ledger.identity_support.value_counts().to_dict(),erp_projection='sample straight 3D floor/top wall edges then inverse equirectangular projection; split wrap seam',source_coordinates='1024x512; multiplied by 2 on real 2048x1024 originals',bev_units='camera height h, not metres',cross_view_registration=False,case_selection='first event_id lexicographically from frozen design; no Q selection')
    (a.out/'CASE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
