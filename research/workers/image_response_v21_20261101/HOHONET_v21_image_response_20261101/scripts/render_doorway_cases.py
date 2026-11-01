#!/usr/bin/env python3
"""Readable figures and complete vote/connection ledgers for the two verified cases."""
from pathlib import Path
import base64,json,math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from prepare_doorway_cases import save

ROOT=Path(__file__).resolve().parents[1]
LOW='#2878b5';HIGH='#d95f02';REF='#17212b'

def members(g):return {(x['id'],x['pair_index']) for x in g['members']}
def bottom(pair):
    x,y=np.asarray(pair,float)[1];r=1/np.tan(np.pi*(y/512-.5));u=2*np.pi*x/1024
    return np.array([-r*np.sin(u),r*np.cos(u)])
def overlay(ax,points,color,label=None,lw=1):
    p=np.asarray(points,float)
    for i in range(0,len(p),2):
        ax.plot(p[i:i+2,0],p[i:i+2,1],color=color,lw=lw,alpha=.9,label=label if i==0 else None)
        ax.scatter(p[i:i+2,0],p[i:i+2,1],s=8,c=color,edgecolor='white',linewidth=.25)
def savefig(fig,folder,name):
    for ext in ['png','pdf','svg']:fig.savefig(folder/(name+'.'+ext),dpi=190,bbox_inches='tight')
    plt.close(fig)

def main():
    out=ROOT/'stage04_doorway_cases';design=json.loads((out/'CASE_DESIGN_BEFORE_REPLAY.json').read_text())
    all_groups=[];all_members=[];all_flow=[];all_edges=[];all_rings=[];all_positions=[];viewer=[]
    summaries=[]
    for meta in design['cases']:
        folder=out/'cases'/meta['case_id'];lo=json.loads((folder/'low_VERIFIED_FULL_TRACE.json').read_text());hi=json.loads((folder/'high_VERIFIED_FULL_TRACE.json').read_text())
        assert lo['all_parity'] and hi['all_parity']
        states=[lo['full_state'],hi['full_state']];traces=[lo,hi]
        ref=json.loads((folder/'FINAL_TARGET_REFERENCE.json').read_text());raw=json.loads((folder/'ALL_IMAGE_ORIGINAL_ANSWERS.json').read_text())
        scalar=pd.read_csv(folder/'SELECTED_SCALARS.csv');groups=[];point_rows=[];flows=[];edges=[];rings=[];positions=[]
        for side,state in zip(['low','high'],states):
            for g in state['identity_groups']:
                center=g.get('center');row={'case_id':meta['case_id'],'side':side,'k':state['n'],'feature_id':g['feature_id'],
                     'support':g['support'],'threshold':state['minimum_support'],'margin':g['support']-state['minimum_support'],
                     'selected':g['selected'],'center_json':json.dumps(center),'workers':'|'.join(x['worker'] for x in g['members']),
                     'includes_entering_worker':any(x['worker']==meta['new_worker'] for x in g['members']),
                     'top_support':g.get('top_support'),'bottom_support':g.get('bottom_support'),'joint_support':g.get('joint_support'),
                     'maximum_top_angle':g.get('maximum_top_angle'),'maximum_bottom_angle':g.get('maximum_bottom_angle')}
                groups.append(row)
                for x in g['members']:
                    point_rows.append({'case_id':meta['case_id'],'side':side,'feature_id':g['feature_id'],
                        'selected':g['selected'],'object_id':x['id'],'worker':x['worker'],'pair_index':x['pair_index'],
                        'source_pair_index':x.get('source_pair_index'),'top_x':x['points'][0][0],'top_y':x['points'][0][1],
                        'bottom_x':x['points'][1][0],'bottom_y':x['points'][1][1]})
            ring=state['ring_diagnostics']
            for edge in ring.get('edges',[]):
                edges.append({'case_id':meta['case_id'],'side':side,'from_group':edge['feature_ids'][0],
                              'to_group':edge['feature_ids'][1],'direct_support':edge.get('direct_support'),
                              'projected_support':edge.get('projected_support'),'direct_workers':'|'.join(edge.get('direct_workers',[])),
                              'projected_workers':'|'.join(edge.get('projected_workers',[]))})
            for i,alt in enumerate(ring.get('alternatives',[])):
                rings.append({'case_id':meta['case_id'],'side':side,'alternative':i,'support':alt.get('support'),
                              'feature_ids':'|'.join(alt['feature_ids']),'workers':'|'.join(alt.get('workers',[])),
                              'chosen':alt['feature_ids']==ring.get('feature_ids'),'policy':ring.get('policy'),
                              'tied_best':ring.get('tied_best')})
        matrix=np.zeros((len(states[0]['identity_groups']),len(states[1]['identity_groups'])),dtype=int)
        for i,a in enumerate(states[0]['identity_groups']):
            for j,b in enumerate(states[1]['identity_groups']):
                shared=members(a)&members(b);matrix[i,j]=len(shared)
                if not shared:continue
                flows.append({'case_id':meta['case_id'],'low_group':a['feature_id'],'high_group':b['feature_id'],
                              'shared_original_point_pairs':len(shared),'low_support':a['support'],'high_support':b['support'],
                              'low_selected':a['selected'],'high_selected':b['selected'],
                              'shared_members':'|'.join(f'{oid}:{ix}' for oid,ix in sorted(shared))})
            if matrix[i].max():
                b=states[1]['identity_groups'][int(matrix[i].argmax())];pa=np.asarray(a['center']);pb=np.asarray(b['center'])
                positions.append({'case_id':meta['case_id'],'low_group':a['feature_id'],'high_group_largest_overlap':b['feature_id'],
                                  'shared_original_point_pairs':int(matrix[i].max()),'low_support':a['support'],'high_support':b['support'],
                                  'low_selected':a['selected'],'high_selected':b['selected'],
                                  'bottom_center_displacement_h':float(np.linalg.norm(bottom(pa)-bottom(pb))),
                                  'top_vertical_pixel_change':float(pb[0,1]-pa[0,1]),
                                  'bottom_vertical_pixel_change':float(pb[1,1]-pa[1,1]),
                                  'note':'Largest shared-source overlap; not an assumption that feature ids or group membership are fixed.'})
        for filename,rows in [('IDENTITY_GROUPS.csv',groups),('IDENTITY_GROUP_MEMBER_POINTS.csv',point_rows),
                             ('SHARED_POINT_GROUP_FLOW.csv',flows),('CONNECTION_EDGES.csv',edges),
                             ('COMPLETE_RING_ALTERNATIVES.csv',rings),('GROUP_POSITION_CHANGES.csv',positions)]:
            pd.DataFrame(rows).to_csv(folder/filename,index=False)
        all_groups+=groups;all_members+=point_rows;all_flow+=flows;all_edges+=edges;all_rings+=rings;all_positions+=positions
        photo=np.asarray(Image.open(folder/'ORIGINAL_PANORAMA.png'))
        fig,axs=plt.subplots(2,2,figsize=(15,10),gridspec_kw={'height_ratios':[.8,1.15]})
        for ax,label,trace,color in zip(axs[0],['Before','After'],traces,[LOW,HIGH]):
            ax.imshow(photo,extent=[0,1024,512,0]);overlay(ax,ref['points_1024x512'],REF,'Reference',1.6)
            overlay(ax,trace['full_state']['candidate']['points'],color,'Fused corner pairs',1.1)
            ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([0,256,512,768,1024]);ax.set_yticks([0,256,512])
            ax.set_title(f"{label}: k={trace['full_state']['n']}, B8L2={trace['score']['B8L2']:.2f}",fontweight='bold')
            ax.legend(loc='lower left',fontsize=8);ax.set_xlabel('Panorama x (1024-pixel coordinates)');ax.set_ylabel('Panorama y')
        ax=axs[1,0]
        for floor,color,label,ls in [(ref['floor_xz_h'],REF,'Adopted whole reference','--'),
             (states[0]['candidate']['footprint'],LOW,f'Before (k={meta["low_k"]})','-'),
             (states[1]['candidate']['footprint'],HIGH,f'After (k={meta["high_k"]})','-')]:
            a=np.asarray(floor);a=np.vstack([a,a[0]]);ax.plot(a[:,0],a[:,1],ls,color=color,lw=2,marker='o',ms=3,label=label)
        ax.scatter([0],[0],c='k',marker='x',s=45,label='Camera');ax.axis('equal');ax.grid(alpha=.2)
        ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height');ax.set_title('Saved floor geometry');ax.legend(fontsize=9)
        ax=axs[1,1];x=np.arange(3)
        for offset,t,color,label in [(-.18,lo,LOW,'Before'),(.18,hi,HIGH,'After')]:
            vals=[t['score'][q] for q in ['B8L2','D10','IoU3D100']];bars=ax.bar(x+offset,vals,.34,color=color,label=label)
            ax.bar_label(bars,fmt='%.2f',fontsize=10,padding=3)
        ax.set_xticks(x,['B8L2','D10','IoU3D100']);ax.set_ylim(0,105);ax.set_ylabel('Quality score');ax.legend();ax.grid(axis='y',alpha=.2)
        ax.set_title(f"New member: {meta['new_worker']} | nodes {len(states[0]['node_consensus']['nodes'])} → {len(states[1]['node_consensus']['nodes'])}")
        fig.suptitle(f"{meta['image']}: late population response ({meta['low_k']} → {meta['high_k']}, N={meta['N']})",fontsize=16,fontweight='bold')
        fig.tight_layout();savefig(fig,folder,'LATE_RESPONSE_OVERVIEW')
        fig,ax=plt.subplots(figsize=(11,9));im=ax.imshow(matrix,cmap='Blues',vmin=0)
        ax.set_xticks(range(matrix.shape[1]),[f"{g['feature_id'].replace('node_','n')} | {g['support']} {'+' if g['selected'] else '-'}" for g in states[1]['identity_groups']],rotation=60,ha='right',fontsize=8)
        ax.set_yticks(range(matrix.shape[0]),[f"{g['feature_id'].replace('node_','n')} | {g['support']} {'+' if g['selected'] else '-'}" for g in states[0]['identity_groups']],fontsize=8)
        for i,j in zip(*np.nonzero(matrix)):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>matrix.max()*.5 else 'black',fontsize=8)
        ax.set_xlabel('After: group id | support | selected (+) / not selected (-)');ax.set_ylabel('Before: group id | support | selected (+) / not selected (-)')
        ax.set_title(f"{meta['image']}: source point pairs shared across identity groups\nNew member point pairs are excluded from this flow matrix")
        fig.colorbar(im,ax=ax,label='Shared original point pairs',shrink=.8);fig.tight_layout();savefig(fig,folder,'SHARED_SOURCE_POINT_FLOW')
        pd.DataFrame(matrix,index=[g['feature_id'] for g in states[0]['identity_groups']],columns=[g['feature_id'] for g in states[1]['identity_groups']]).to_csv(folder/'SHARED_SOURCE_POINT_FLOW_PLOT_DATA.csv')
        measures=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension']
        comparison=[{'metric':m,'before':lo['score'].get(m),'after':hi['score'].get(m),
                     'delta':hi['score'][m]-lo['score'][m]} for m in measures]
        pd.DataFrame(comparison).to_csv(folder/'METRIC_COMPONENT_COMPARISON.csv',index=False)
        summaries.append({'case_id':meta['case_id'],**meta,'low_nodes':len(states[0]['node_consensus']['nodes']),
                          'high_nodes':len(states[1]['node_consensus']['nodes']),
                          'low_threshold':states[0]['minimum_support'],'high_threshold':states[1]['minimum_support'],
                          'low_best_complete_ring_support':max(x['support'] for x in states[0]['ring_diagnostics']['alternatives']),
                          'high_best_complete_ring_support':max(x['support'] for x in states[1]['ring_diagnostics']['alternatives'])})
        viewer.append({'meta':meta,'photo':'data:image/png;base64,'+base64.b64encode((folder/'ORIGINAL_PANORAMA.png').read_bytes()).decode(),
                       'reference':ref,'raw':raw,'low':lo,'high':hi,'groups':groups,'flow':flows,'metrics':comparison})
    pd.DataFrame(summaries).to_csv(out/'CASE_SUMMARY.csv',index=False)
    for name,rows in [('ALL_IDENTITY_GROUPS.csv',all_groups),('ALL_MEMBER_POINT_VOTES.csv',all_members),
                      ('ALL_SHARED_POINT_FLOW.csv',all_flow),('ALL_CONNECTION_EDGES.csv',all_edges),
                      ('ALL_RING_ALTERNATIVES.csv',all_rings),('ALL_GROUP_POSITIONS.csv',all_positions)]:
        pd.DataFrame(rows).to_csv(out/name,index=False)
    save(out/'CASE_VIEWER_DATA.json',viewer)
    print('Rendered',len(viewer),'cases; 12 PNG/PDF/SVG figures; complete point and connection ledgers.',flush=True)

if __name__=='__main__':main()
