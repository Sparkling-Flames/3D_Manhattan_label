#!/usr/bin/env python3
"""Draw one saved strict ABC bundle and expose identity/connection evidence.

No native fusion, scoring, or reference editing. All feature IDs are team-local.
The projection convention is frozen corner_distance.project; wall edges are
sampled in 3D before inverse ERP projection, including seam splitting.
"""
from pathlib import Path
import argparse,gzip,hashlib,io,json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_generic_case_mpl')
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

COLORS={'A':'#2166ac','B':'#e08214','C':'#1b9e77','GT':'#111111'}

def project(points):
    p=np.asarray(points,float);top,bottom=p[::2],p[1::2];phi=2*np.pi*(bottom[:,0]/1024-.5);r=1/np.tan(np.pi*(bottom[:,1]/512-.5));y=r*np.tan(np.pi*(.5-top[:,1]/512));b=np.column_stack((r*np.sin(phi),-np.ones(len(r)),-r*np.cos(phi)));t=b.copy();t[:,1]=y;return b,t

def inverse(xyz):
    v=np.asarray(xyz,float);return np.column_stack(((np.arctan2(v[:,0],-v[:,2])/(2*np.pi)+.5)*1024,(.5-np.arctan2(v[:,1],np.hypot(v[:,0],v[:,2]))/np.pi)*512))

def usable(points):
    if points is None:return False
    p=np.asarray(points);return p.ndim==2 and p.shape[1]==2 and len(p)>=6 and len(p)%2==0 and np.isfinite(p).all()

def erp(ax,points,color,lw=1.5,alpha=1,label=None,reference=False,scale=(2,2)):
    if not usable(points):return
    b,t=project(points);edges=[]
    for v in [b,t]:
        for i in range(len(v)):edges.append(inverse(np.linspace(v[i],v[(i+1)%len(v)],161)))
    for i in range(len(b)):edges.append(inverse(np.linspace(b[i],t[i],41)))
    first=True
    for edge in edges:
        cut=np.where(np.abs(np.diff(edge[:,0]))>512)[0]+1
        for segment in np.split(edge,cut):
            if len(segment)<2:continue
            line,=ax.plot(segment[:,0]*scale[0],segment[:,1]*scale[1],color=color,lw=lw,alpha=alpha,label=label if first else None,zorder=5 if reference else 6);first=False
            if reference:line.set_path_effects([pe.Stroke(linewidth=lw+1.8,foreground='white'),pe.Normal()])

def bev(ax,points,color,lw=1.5,alpha=1,label=None,ls='-'):
    if not usable(points):return
    b,_=project(points);q=np.vstack((b,b[0]));ax.plot(q[:,0],q[:,2],color=color,lw=lw,alpha=alpha,label=label,ls=ls);return b

def savefig(fig,out,name):
    # Validate the complete encoded image before replacing a saved artifact.
    # This protects this observed delivery path from a truncated PNG write.
    for ext in ['png','pdf']:
        buffer=io.BytesIO();fig.savefig(buffer,format=ext,dpi=175)
        payload=buffer.getvalue()
        if ext=='png':
            with Image.open(io.BytesIO(payload)) as im:im.load()
        target=out/(name+'.'+ext);temp=target.with_suffix(target.suffix+'.tmp')
        temp.write_bytes(payload);temp.replace(target)
    plt.close(fig)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--case',type=Path,required=True);ap.add_argument('--originals',type=Path,required=True);ap.add_argument('--roi-json',type=Path);a=ap.parse_args();figs=a.case/'figures';tables=a.case/'tables';figs.mkdir(exist_ok=True);tables.mkdir(exist_ok=True)
    e=pd.read_csv(a.case/'STRICT_ABC_EVENT.csv.gz',keep_default_na=False).iloc[0];E=e.event_id;n=int(e.n);states={}
    with gzip.open(a.case/'SIX_TEAM_NATIVE_GEOMETRY.jsonl.gz','rt') as f:
        for line in f:z=json.loads(line);states[z['team_key']]=z
    assert len(states)==6;s=pd.read_csv(a.case/'SIX_TEAM_NATIVE_SCALARS.csv.gz').set_index('team_key');pools={p['pool_id']:p for p in json.load(gzip.open(a.case/'FROZEN_TWO_POOLS.json.gz','rt'))['images']}
    teams={(v,r):states[e[f'team_key_{r}_{v}']] for v in 'ab' for r in 'ABC'};groups=[];members=[];brackets=[];edges=[];subgroups=[];raw=[];views=[];images={};rois={};metrics=[];manual_roi=json.loads(a.roi_json.read_text()) if a.roi_json else {}
    for v in 'ab':
        p=pools[e['pool_id_'+v]];rawby={r['worker_id']:r for r in p['records']};image_id=e['image_id_'+v];matches=list(a.originals.glob(image_id+'.*'));assert len(matches)==1,(image_id,'original_image_missing_or_ambiguous');impath=matches[0];im=np.asarray(Image.open(impath));h,w=im.shape[:2];images[v]=im;scale=(w/1024,h/512);ref=np.asarray(p['reference']['points_1024x512']);rb,_=project(ref);assert np.allclose(rb[:,[0,2]],p['reference']['floor_xz_h'],atol=1e-8);candidates=[];used=set()
        for arm in 'ABC':
            z=teams[v,arm];state=z.get('full_state') or {};cand=state.get('candidate') or {};pts=cand.get('points');ws=z['member_workers'];used.update(ws);assert set(ws)==set(e[arm+'_members'].split('|'))
            if usable(pts):
                cb,_=project(pts);assert np.allclose(cb[:,[0,2]],cand['footprint'],atol=1e-8);candidates.append(np.asarray(pts)[1::2])
            row=s.loc[z['team_key']].to_dict();row.update(event_id=E,view=v,arm=arm,team_key=z['team_key']);metrics.append(row)
            for g in state.get('identity_groups',[]):
                base=dict(event_id=E,view=v,image=e['image_'+v],arm=arm,team_key=z['team_key'],feature_id=g['feature_id'],feature_scope='team_local_not_cross_view_identity',n=n,minimum_support=state.get('minimum_support'),selected=g['selected']);center=np.asarray(g['center']);arr=np.asarray([x['points'] for x in g['members']]);med=np.median(arr,axis=0);equal=bool(np.allclose(med,center,atol=1e-8,rtol=0))
                groups.append({**base,'identity_support':g['support'],'top_support':g['top_support'],'bottom_support':g['bottom_support'],'joint_support':g['joint_support'],'member_workers':'|'.join(x['worker'] for x in g['members']),'center_top_u_1024':center[0,0],'center_top_v_512':center[0,1],'center_bottom_u_1024':center[1,0],'center_bottom_v_512':center[1,1],'center_equals_direct_coordinate_medians':equal,'center_json':json.dumps(g['center'],separators=(',',':'))})
                for member in g['members']:
                    rr=rawby[member['worker']];members.append({**base,'worker_id':member['worker'],'annotation_id':member['id'],'object_id':rr['object_id'],'pair_index':member['pair_index'],'source_pair_index':member['source_pair_index'],'points_1024x512_json':json.dumps(member['points'],separators=(',',':'))})
                for coordinate,(rr,cc) in {'top_u':(0,0),'top_v':(0,1),'bottom_u':(1,0),'bottom_v':(1,1)}.items():
                    vals=arr[:,rr,cc];order=np.argsort(vals,kind='stable');lo=(len(vals)-1)//2;hi=len(vals)//2
                    brackets.append({**base,'coordinate':coordinate,'lower_worker':g['members'][order[lo]]['worker'],'upper_worker':g['members'][order[hi]]['worker'],'lower_value':vals[order[lo]],'upper_value':vals[order[hi]],'direct_median':med[rr,cc],'saved_center':center[rr,cc],'equal':bool(abs(med[rr,cc]-center[rr,cc])<1e-8),'interpretation':'direct_coordinate_check; if unequal inspect seam/consensus rule, never replace saved center','all_ordered_workers':'|'.join(g['members'][i]['worker'] for i in order),'all_ordered_values':'|'.join(format(vals[i],'.12g') for i in order)})
                for boundary in ['top','bottom']:
                    for j,pg in enumerate(g.get(boundary+'_position_groups_9deg',[])):subgroups.append({**base,'boundary':boundary,'position_group_index':j,'support':pg['support'],'members_json':json.dumps(pg['members'],ensure_ascii=False,separators=(',',':'))})
            rd=state.get('ring_diagnostics') or {}
            for j,edge in enumerate(rd.get('edges',[])):edges.append(dict(event_id=E,view=v,image=e['image_'+v],arm=arm,team_key=z['team_key'],edge_index=j,feature_a=edge['feature_ids'][0],feature_b=edge['feature_ids'][1],direct_support=edge['direct_support'],direct_workers='|'.join(edge['direct_workers']),projected_support=edge['projected_support'],projected_workers='|'.join(edge['projected_workers']),ring_confirmed=rd.get('ring_confirmed'),tied_best=rd.get('tied_best'),policy=rd.get('policy')))
        for worker in sorted(used):
            rr=rawby[worker];block=next(b for b in 'DXYZ' if worker in e[b+'_members'].split('|'));raw.append(dict(event_id=E,view=v,image=e['image_'+v],pool_id=p['pool_id'],worker_id=worker,object_id=rr['object_id'],annotation_id=rr['id'],block=block,arms='|'.join(arm for arm in 'ABC' if worker in e[arm+'_members'].split('|')),points_1024x512_json=json.dumps(rr['points'],separators=(',',':')),source_time_kind=rr.get('time_source_kind'),source_time_seconds=rr.get('source_time_seconds')))
        if v in manual_roi:roi=manual_roi[v];selection='manually specified visible window; saved explicit pixel bounds'
        else:
            dist=[]
            for pt in ref[1::2]:
                near=[]
                for points in candidates:off=points-pt;off[:,0]=(off[:,0]+512)%1024-512;near.append(np.min(np.hypot(off[:,0],off[:,1])))
                dist.append(max(near) if near else 0)
            ci=int(np.argmax(dist));center=ref[1::2][ci]*scale;roi=[max(0,center[0]-.085*w),min(w,center[0]+.085*w),max(0,center[1]-.12*h),min(h,center[1]+.12*h)];selection='image-local reference corner with largest nearest candidate floor-corner gap; no Q threshold in crop rule'
        rois[v]=roi;views.append(dict(event_id=E,view=v,image=e['image_'+v],image_id=image_id,reference_id=e['reference_id_'+v],original_file=str(impath),original_sha256=hashlib.sha256(impath.read_bytes()).hexdigest(),width=w,height=h,roi_xmin=roi[0],roi_xmax=roi[1],roi_ymin=roi[2],roi_ymax=roi[3],roi_selection=selection,coordinate_frame='this_camera_only_no_cross_view_alignment'))
    for name,rows in [('IDENTITY_GROUPS',groups),('IDENTITY_MEMBERS',members),('MEDIAN_BRACKETS',brackets),('RING_EDGES',edges),('POSITION_SUBGROUPS_9DEG',subgroups),('USED_RAW_ANSWERS',raw),('VIEW_IMAGE_INDEX',views),('SIX_TEAM_METRICS',metrics)]:pd.DataFrame(rows).to_csv(tables/(name+'.csv'),index=False)
    fig,axes=plt.subplots(2,2,figsize=(15,10),gridspec_kw={'width_ratios':[2.5,1]},layout='constrained')
    for j,v in enumerate('ab'):
        p=pools[e['pool_id_'+v]];ref=p['reference']['points_1024x512'];im=images[v];h,w=im.shape[:2];scale=(w/1024,h/512);ax,bx=axes[j];ax.imshow(im);erp(ax,ref,'black',lw=1.6,label='Reference',reference=True,scale=scale);bev(bx,ref,'black',lw=1.8,label='Reference',ls='--')
        for arm in 'ABC':
            z=teams[v,arm];state=z.get('full_state') or {};pts=(state.get('candidate') or {}).get('points');sc=s.loc[z['team_key']];q=sc.get('B8L2');label=f'{arm}: Q={q:.2f}, turns={sc.get("fusion_turn_n",np.nan):g}' if pd.notna(q) else arm+': unscorable'
            if usable(pts):erp(ax,pts,COLORS[arm],lw=1.3,label=label,scale=scale);bev(bx,pts,COLORS[arm],lw=1.8,label=arm)
            else:ax.plot([],[],color=COLORS[arm],label=label)
        x0,x1,y0,y1=rois[v];ax.add_patch(plt.Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='magenta',ls='--',lw=1));ax.set_title(e['image_'+v]+' | actual Release image + frozen reference / saved teams');ax.set_xlim(0,w);ax.set_ylim(h,0);ax.set_xticks([]);ax.set_yticks([]);ax.legend(loc='upper left',fontsize=8,ncol=2,framealpha=.85);bx.plot(0,0,'k+',ms=7);bx.set_aspect('equal');bx.grid(alpha=.2);bx.set_xlabel('x / camera height h');bx.set_ylabel('z / camera height h');bx.legend(fontsize=8)
    fig.suptitle(f'Exact member adjustment across views | n={n}, m={int(e.m)}, fixed core size={int(e.D_n)}\nExploratory mechanism case {E}; no new fusion',fontsize=12);savefig(fig,figs,'CASE_OVERVIEW_ERP_BEV')
    fig,axes=plt.subplots(2,3,figsize=(15,10),layout='constrained')
    for j,v in enumerate('ab'):
        p=pools[e['pool_id_'+v]];rawby={r['worker_id']:r for r in p['records']};ref=p['reference']['points_1024x512'];coords=[]
        for worker in set('|'.join(e[arm+'_members'] for arm in 'ABC').split('|')):
            if usable(rawby[worker]['points']):coords.extend(project(rawby[worker]['points'])[0][:,[0,2]])
        co=np.asarray(coords);lo=co.min(0)-.15;hi=co.max(0)+.15
        for col,arm in enumerate('ABC'):
            ax=axes[j,col];z=teams[v,arm];palette=plt.get_cmap('tab20');state=z.get('full_state') or {};pts=(state.get('candidate') or {}).get('points')
            for wi,worker in enumerate(z['member_workers']):bev(ax,rawby[worker]['points'],palette(wi%20),lw=.75,alpha=.6,label=worker+(' (D)' if worker in e.D_members.split('|') else ''))
            bev(ax,ref,'black',lw=2,label='Reference',ls='--');bev(ax,pts,COLORS[arm],lw=2.8,label=arm+' fusion');ax.plot(0,0,'k+',ms=6);ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.set_title(e['image_'+v]+' | '+arm);ax.legend(ncol=max(2,(n+2)//9),fontsize=6,framealpha=.85)
    fig.suptitle('Every exact member raw answer; common limits within each view; no alignment or shape correction');savefig(fig,figs,'ALL_MEMBERS_RAW_BEV')
    fig,axes=plt.subplots(2,3,figsize=(15,7.5),layout='constrained')
    for j,v in enumerate('ab'):
        p=pools[e['pool_id_'+v]];rawby={r['worker_id']:r for r in p['records']};ref=p['reference']['points_1024x512'];h,w=images[v].shape[:2];scale=(w/1024,h/512);x0,x1,y0,y1=rois[v]
        for col,arm in enumerate('ABC'):
            ax=axes[j,col];z=teams[v,arm];state=z.get('full_state') or {};pts=(state.get('candidate') or {}).get('points');ax.imshow(images[v])
            for worker in z['member_workers']:erp(ax,rawby[worker]['points'],COLORS[arm],lw=.65,alpha=.25,scale=scale)
            erp(ax,ref,'black',lw=2,reference=True,scale=scale);erp(ax,pts,COLORS[arm],lw=2,scale=scale);ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(e['image_'+v]+' | '+arm+' raw / fusion / reference',fontsize=10)
    fig.suptitle('Same local window across A/B/C in each image; image-local corners, no inferred cross-view identity');savefig(fig,figs,'LOCAL_RAW_FUSION_REFERENCE')
    ledger=pd.DataFrame(groups);fig,axes=plt.subplots(2,3,figsize=(15,7.5),layout='constrained')
    for j,v in enumerate('ab'):
        for col,arm in enumerate('ABC'):
            ax=axes[j,col];q=ledger[ledger.view.eq(v)&ledger.arm.eq(arm)] if len(ledger) else ledger;z=teams[v,arm];threshold=(z.get('full_state') or {}).get('minimum_support');ax.bar(np.arange(len(q)),q.identity_support if len(q) else [],color=[COLORS[arm] if bool(x) else '#bbbbbb' for x in q.selected] if len(q) else [])
            if threshold is not None:ax.axhline(threshold,color='#b2182b',ls='--',label=f'threshold {threshold}')
            ax.set_ylim(0,n+1);ax.set_ylabel('Distinct worker support');ax.set_xticks(np.arange(len(q)),q.feature_id if len(q) else [],rotation=75,fontsize=7);ax.set_title(e['image_'+v]+' | '+arm);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Native identity groups are local to each team; gray = not selected\nEqual support, missing support and retained identities are shown without aligning node IDs');savefig(fig,figs,'IDENTITY_SUPPORT')
    receipt=dict(event_id=E,new_fusion=0,new_scoring=0,new_labels=0,views=2,endpoints=6,identity_groups=len(groups),identity_members=len(members),median_coordinates=len(brackets),direct_median_matches=int(pd.DataFrame(brackets).equal.sum()) if brackets else 0,ring_edges=len(edges),raw_answers=len(raw),erp='3D sampled edges inverse-projected with seam breaks',bev_units='camera height h',cross_view_geometry_registration=False,case_selection='read CASE_SELECTION.json; exploratory, not independent validation',figure_visual_inspection='pending_after_render')
    (a.case/'FIGURE_TABLE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
