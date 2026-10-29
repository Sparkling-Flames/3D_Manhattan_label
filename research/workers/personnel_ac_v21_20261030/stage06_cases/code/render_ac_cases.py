"""Draw full original answers, current reference, native AC geometry and votes.

No fusion, scoring, filtering, ring repair or coordinate edits are performed.
Original corner order and the retained continuous projection are preserved.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import patheffects
from geometry_draw import read,save_figure,number,points3d,erp,bev,xyz_plot

COLORS={'A':'#2471a3','C':'#d95f28'}
def member_list(value):return value.split('|') if value else []
def present_points(row):return (row.get('geometry') or {}).get('points')
def get_group_points(group):
    value=group.get('center')
    return value if value is not None and np.shape(value)==(2,2) else None
def extent(points):
    floors=[points3d(p)[1][:,:2] for p in points if p and points3d(p) is not None]
    xy=np.concatenate(floors) if floors else np.array([[-2.,-2.],[2.,2.]])
    lo,hi=xy.min(0),xy.max(0);padding=.12*max(max(hi-lo),1.)
    return lo-padding,hi+padding
def setup_bev(ax,limits):
    lo,hi=limits;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal',adjustable='box')
    ax.plot(0,0,'k+',ms=7);ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.grid(alpha=.15)
def incomplete_text(row):
    status=row.get('score_status')
    if status=='no_connection' and any(g.get('selected') and g.get('center') is None for g in (row.get('full_state') or {}).get('identity_groups',[])):
        return '入选节点位置尚未确定：完整连接几何不可用'
    return {'below_four':'少于4节点：保留部分候选','no_connection':'无法连接成完整环：未补边',
            'invalid_floor':'底面无效：保留原候选','invalid_full_geometry':'完整几何不可评：保留原候选',
            'fusion_exception':'融合执行异常：没有可用候选','measurement_exception':'测量异常：不等同融合失败',
            'floor_only_reference':'参考仅支持底面评价'}.get(status,'')
def scalar_table(case):
    fields=['B8L2','D10','IoU3D100','iou_2d','boundary_loss','direction_loss','height_loss','nodes','fusion_turn_n','fusion_short_turn_edges',
            'ref_node_recall_9','ref_edge_recall_9','geometry_area_h2','centroid_x_h','centroid_z_h','height_mean_h',
            'source_time_total_seconds','minimum_support','score_status','geometry_status','geometry_reason','order_status']
    rows=[]
    for field in fields:
        A,C=[case['arms'][arm].get(field) for arm in ['A','C']]
        delta=C-A if isinstance(A,(int,float)) and isinstance(C,(int,float)) else None
        if field=='source_time_total_seconds':
            # A raw logged total can be shown, but an inferential contrast must
            # use the independently validated source-comparability mask.
            delta=(case.get('metrics') or {}).get('record_time_CA_seconds_source_matched')
        rows.append({'metric':field,'A':A,'C':C,'C_minus_A':delta})
    for field in ['record_time_CA_seconds_source_matched','record_time_CA_pct_source_matched',
                  'record_time_CA_seconds_single_source','record_time_CA_pct_single_source',
                  'record_time_per_member_CA_seconds_single_source','record_time_per_member_CA_pct_single_source']:
        rows.append({'metric':field,'A':None,'C':None,'C_minus_A':(case.get('metrics') or {}).get(field)})
    return pd.DataFrame(rows)

def vote_rows(case):
    D=set(member_list(case['event'].get('D_workers','')));own={r['object_id']:r['worker_id'] for r in case['pool']['records']};out=[]
    for arm,row in case['arms'].items():
        for group in (row.get('full_state') or {}).get('identity_groups',[]):
            people={m.get('worker') or own[m['id']] for m in group['members']};p=get_group_points(group)
            out.append({'arm':arm,'group':group['feature_id'],'support':len(people),'D_support':len(people&D),'replacement_support':len(people-D),
                        'selected':bool(group['selected']),'azimuth_px':p[1][0] if p is not None else np.nan,'location_resolved':p is not None})
    return pd.DataFrame(out)

def render_case(path,out,originals):
    case=read(path);event=case['event'];image=case['pool']['meta']['image'];eid=event['event_id'];folder=out/eid;folder.mkdir(parents=True,exist_ok=True)
    image_path=originals/(image+'.png');assert image_path.exists(),image_path
    canvas=np.array(Image.open(image_path).convert('RGB').resize((1024,512),Image.Resampling.LANCZOS))
    reference=case['reference']['points_1024x512'];rows=case['arms'];records={r['worker_id']:r for r in case['pool']['records']}
    D=member_list(event.get('D_workers',''));blocks={'A':member_list(event.get('X_workers','')),'C':member_list(event.get('Z_workers',''))}
    all_members=sorted(set(D+blocks['A']+blocks['C']));raw=[records[w]['points'] for w in all_members]
    outputs=[reference]+[present_points(rows[k]) for k in ['A','C']]
    all_limits=extent(outputs+raw);focused_limits=extent(outputs)
    fig,axes=plt.subplots(2,3,figsize=(18,10.5),gridspec_kw={'height_ratios':[1.,1.15]})
    for index,arm in enumerate(['A','C']):
        row=rows[arm];color=COLORS[arm];p=present_points(row);team=sorted(D+blocks[arm]);ax=axes[0,index]
        ax.imshow(canvas,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0)
        for worker in D:erp(ax,records[worker]['points'],'white',.5,.20)
        for worker in blocks[arm]:erp(ax,records[worker]['points'],color,.75,.40)
        erp(ax,reference,'#111111',1.4,.95,'--');erp(ax,p,color,2.0,1.)
        ax.set_title(f"{arm}：n={len(team)}；D={len(D)}，替换块={len(blocks[arm])}\nB8L2={number(row.get('B8L2'))}，D10={number(row.get('D10'))}，节点={row.get('nodes')}")
        ax.set_xlabel('ERP 水平像素');ax.set_ylabel('ERP 竖直像素')
        note=incomplete_text(row)
        if note:ax.text(.5,.05,note,transform=ax.transAxes,ha='center',color='#91222c',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'},fontsize=10)
        ax=axes[1,index]
        for worker in D:bev(ax,records[worker]['points'],'#8a939b',.5,.20)
        for worker in blocks[arm]:bev(ax,records[worker]['points'],color,.7,.25)
        bev(ax,reference,'#111111',1.7,.95,'--',True);bev(ax,p,color,2.3,1.,dots=True);setup_bev(ax,all_limits)
        ax.set_title(f'{arm} 底面总览：完整原答与候选输出')
    ax=axes[0,2];ax.imshow(canvas,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0)
    erp(ax,reference,'#111111',1.4,.95,'--')
    for arm in ['A','C']:erp(ax,present_points(rows[arm]),COLORS[arm],2.,1.)
    for i,point in enumerate(reference[1::2]):
        ax.text(point[0]+3,point[1]+12+(i%2)*8,'r'+str(i+1),fontsize=7,color='#111',path_effects=[patheffects.withStroke(linewidth=2,foreground='white')])
    ax.set_title('两队输出与当前目标参考');ax.set_xlabel('ERP 水平像素');ax.set_ylabel('ERP 竖直像素')
    ax=axes[1,2];bev(ax,reference,'#111111',1.8,.95,'--',True)
    for arm in ['A','C']:bev(ax,present_points(rows[arm]),COLORS[arm],2.5,1.,dots=True)
    refxyz=points3d(reference)
    if refxyz is not None:
        for i,point in enumerate(refxyz[1]):ax.annotate('r'+str(i+1),(point[0],point[1]),xytext=(3,4),textcoords='offset points',fontsize=8,path_effects=[patheffects.withStroke(linewidth=2,foreground='white')])
    setup_bev(ax,focused_limits);ax.set_title('输出底面细节（范围由两队与参考决定）')
    equal=int(event['n_A'])==int(event['n_C']);design='等人数直接 AC' if equal else '不等人数整类/联盟比较'
    title=f"{image} | {event['method']} | {event.get('condition','manual')} | {design}\n n: {event['n_A']}→{event['n_C']}，X: {event['m_X']}人，Z: {event['m_Z']}人；同一合法目标与参考"
    fig.suptitle(title,fontsize=13,y=.995)
    fig.legend(handles=[Line2D([0],[0],color='#111111',ls='--',lw=1.8,label='当前目标参考'),Line2D([0],[0],color=COLORS['A'],lw=2.5,label='A候选'),Line2D([0],[0],color=COLORS['C'],lw=2.5,label='C候选'),Line2D([0],[0],color='#8a939b',lw=.8,label='完整原答细线')],loc='lower center',ncol=4,frameon=False,bbox_to_anchor=(.5,.015))
    fig.tight_layout(rect=[0,.06,1,.95],h_pad=3.0);save_figure(fig,folder/'ERP_BEV_AC.png',dpi=160);save_figure(fig,folder/'ERP_BEV_AC.pdf');plt.close(fig)
    votes=vote_rows(case);fig=plt.figure(figsize=(14,10));grid=fig.add_gridspec(2,2,height_ratios=[1.1,1.],hspace=.28,wspace=.22)
    zvalues=[]
    for p in outputs:
        xyz=points3d(p) if p else None
        if xyz is not None:zvalues.append(np.vstack(xyz))
    xyz=np.concatenate(zvalues) if zvalues else np.array([[-2,-2,-1],[2,2,1]])
    zlo,zhi=xyz[:,2].min(),xyz[:,2].max();zpad=.15*max(zhi-zlo,1.)
    for index,arm in enumerate(['A','C']):
        row=rows[arm];p=present_points(row);color=COLORS[arm];ax=fig.add_subplot(grid[0,index],projection='3d')
        xyz_plot(ax,reference,'#111111',1.1,.8,'--');xyz_plot(ax,p,color,2.,1.)
        if not p:
            points=[get_group_points(g) for g in (row.get('full_state') or {}).get('identity_groups',[]) if g['selected']]
            for point in points:
                if point is None:continue
                # Draw each located node as an independent vertical segment;
                # no invented horizontal connection is shown.
                repeated=[*point,*point,*point];converted=points3d(repeated)
                if converted is not None:
                    top,bottom=converted;segment=np.vstack([top[0],bottom[0]])
                    ax.plot(segment[:,0],segment[:,1],segment[:,2],color=color,lw=1.2);ax.scatter(segment[:,0],segment[:,1],segment[:,2],color=color,s=20)
            ax.text2D(.02,.96,'只画实际可定位的入选节点，不补连接边',transform=ax.transAxes,fontsize=9,color='#91222c')
        lo,hi=focused_limits;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_zlim(zlo-zpad,zhi+zpad)
        ax.set_box_aspect((max(hi[0]-lo[0],.1),max(hi[1]-lo[1],.1),max(zhi-zlo+2*zpad,.1)))
        ax.view_init(24,-54);ax.set_xlabel('x/h');ax.set_ylabel('z/h');ax.set_zlabel('y/h');ax.set_title(arm+'三维候选：地面固定−1h')
        ax=fig.add_subplot(grid[1,index]);subset=votes[votes.arm.eq(arm)].sort_values('azimuth_px',na_position='last') if len(votes) else pd.DataFrame()
        if len(subset):
            for pos,vote in enumerate(subset.itertuples()):
                alpha=.95 if vote.selected else .25
                ax.bar(pos,vote.D_support,color='#8a939b',alpha=alpha)
                ax.bar(pos,vote.replacement_support,bottom=vote.D_support,color=color,alpha=alpha)
                ax.text(pos,vote.support+.15,str(vote.support),ha='center',fontsize=8)
            ax.set_xticks(range(len(subset)),[str(v).replace('node_','g') for v in subset.group],fontsize=7,rotation=40)
            ax.axhline(row['minimum_support'],color='#b22f39',ls='--',lw=1.3);ax.set_ylim(0,max(subset.support.max(),row['minimum_support'])+2)
        ax.set_title(arm+'全部对应组：浅色为未入选');ax.set_ylabel('独立人员支持票');ax.grid(axis='y',alpha=.15)
    fig.suptitle(image+'：节点、定位与连接分开检查',fontsize=14,y=.99)
    fig.legend(handles=[Line2D([0],[0],color='#8a939b',lw=8,label='共同背景D'),Line2D([0],[0],color=COLORS['C'],lw=8,label='替换块X或Z'),Line2D([0],[0],color='#b22f39',ls='--',label='冻结MV50门槛')],loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.005))
    save_figure(fig,folder/'THREED_ALL_VOTES_AC.png',dpi=160,bbox_inches='tight');save_figure(fig,folder/'THREED_ALL_VOTES_AC.pdf',bbox_inches='tight');plt.close(fig)
    scalar_table(case).to_csv(folder/'AC_COMPONENTS.csv',index=False,encoding='utf-8-sig')
    rawrows=[]
    for block,people in [('D',D),('X',blocks['A']),('Z',blocks['C'])]:
        for worker in people:
            record=records[worker]
            rawrows.append({'block':block,'worker_id':worker,'object_id':record['object_id'],'points_json':json.dumps(record['points'],separators=(',',':')),
                            'source_point_pairs':len(record['points'])//2,'target_individual_B8L2':record.get('B8L2'),'target_individual_D10':record.get('D10')})
    pd.DataFrame(rawrows).to_csv(folder/'FULL_RAW_ANSWERS.csv',index=False,encoding='utf-8-sig')
    provenance={'event_id':eid,'trace_file':str(path),'trace_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'original_file':str(image_path),'original_sha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),
                'reference_id':case['pool']['meta']['reference_id'],'reference_version':case['pool']['meta']['reference_version'],'no_scores_or_fusions_in_rendering':True,
                'no_ring_or_point_changes':True,'all_selected_persons_original_full_annotations_retained':True,'world_units':'camera-height h, not measured room meters','bev_distance_metric':'1-IoU, dimensionless'}
    (folder/'FIGURE_PROVENANCE.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    return {'event_id':eid,'image':image,'method':event['method'],'ERP_BEV_AC':str(folder/'ERP_BEV_AC.png'),'THREED_ALL_VOTES_AC':str(folder/'THREED_ALL_VOTES_AC.png')}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cases',nargs='+',required=True);ap.add_argument('--out',required=True);ap.add_argument('--originals',required=True);a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);index=[]
    for path in a.cases:
        index.append(render_case(Path(path),out,Path(a.originals)));pd.DataFrame(index).to_csv(out/'CASE_FIGURE_INDEX.csv',index=False,encoding='utf-8-sig')
        print('saved',index[-1]['event_id'],flush=True)

if __name__=='__main__':main()
