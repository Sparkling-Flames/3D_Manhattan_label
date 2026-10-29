"""Seven exact nonempty class unions on one preselected pool, without new teams.

This is a descriptive full-pool illustration. Unequal-n union contrasts change
both composition and team size; matched whole-class chains are separate.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from geometry_draw import erp,bev,save_figure,number,points3d
from render_ac_cases import extent,setup_bev,get_group_points,incomplete_text

ORDER=['C1','C2','C3','C1|C2','C1|C3','C2|C3','C1|C2|C3']
COLOR={'C1':'#336da3','C2':'#dd7526','C3':'#8e5ba1'}
UNION_COLOR=['#336da3','#dd7526','#8e5ba1','#248d8c','#596ab6','#b64e6a','#2d604d']
FIELDS=['B8L2','D10','IoU3D100','iou_2d','boundary_loss','direction_loss','height_loss',
        'nodes','fusion_turn_n','fusion_short_turn_edges','ref_node_recall_9','ref_edge_recall_9',
        'geometry_area_h2','centroid_x_h','centroid_z_h','height_mean_h','height_mean_ratio',
        'source_time_total_seconds','source_time_known_n','minimum_support','score_status','order_status']

def read(path):
    with gzip.open(path,'rt') as f:return json.load(f)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases-dir',required=True);ap.add_argument('--registered-teams',required=True)
    ap.add_argument('--original',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    source=Path(a.cases_dir);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    cases=[read(p) for p in sorted((source/'traces').glob('*.json.gz'))]
    assert len(cases)==21
    image=cases[0]['event']['image'];pool=cases[0]['pool'];reference=cases[0]['reference']['points_1024x512']
    rows={r['team_key']:r for c in cases for r in c['arms'].values()};assert len(rows)==7
    registered=pd.read_csv(a.registered_teams,dtype=str,keep_default_na=False)
    registered=registered[registered.image.eq(image)];assert len(registered)==7
    teams={}
    for row in registered.to_dict('records'):
        counts=json.loads(row['class_counts']);label='|'.join(sorted(counts))
        assert label not in teams;native=rows[row['team_key']]
        assert set(row['member_workers'].split('|'))==set(native['member_workers'])
        teams[label]=(row,native)
    assert set(teams)==set(ORDER)
    person_class={w:label for label in ['C1','C2','C3'] for w in teams[label][1]['member_workers']}
    raw={r['worker_id']:r for r in pool['records']}
    canvas=np.array(Image.open(a.original).convert('RGB').resize((1024,512),Image.Resampling.LANCZOS))
    endpoints=[]
    for label in ORDER:
        reg,row=teams[label];endpoints.append(dict(alliance=label,**reg,**{k:row.get(k) for k in FIELDS}))
    pd.DataFrame(endpoints).to_csv(out/'SEVEN_ALLIANCE_ENDPOINTS.csv',index=False,encoding='utf-8-sig')
    # Restore the original, named union direction from selection signs. This is
    # not the lexicographic endpoint orientation used for storage deduplication.
    contrasts=[]
    for case in cases:
        s=case['selection'];sign=int(s['input_orientation_sign']);left,right=('A','C') if sign==1 else ('C','A')
        A,C=case['arms'][left],case['arms'][right]
        assert teams[s['A_alliance']][1]['team_key']==A['team_key']
        assert teams[s['C_alliance']][1]['team_key']==C['team_key']
        entry={'event_id':case['event']['event_id'],'physical_pair_id':case['event']['physical_pair_id'],
               'from_alliance':s['A_alliance'],'to_alliance':s['C_alliance'],'n_from':A['k'],'n_to':C['k'],
               'from_team_key':A['team_key'],'to_team_key':C['team_key'],'input_orientation_sign':sign,
               'equal_n':A['k']==C['k'],'from_status':A['score_status'],'to_status':C['score_status']}
        for key in FIELDS:
            av,cv=A.get(key),C.get(key)
            entry['from_'+key]=av;entry['to_'+key]=cv
            if key!='source_time_total_seconds':entry['to_minus_from_'+key]=cv-av if isinstance(av,(int,float)) and isinstance(cv,(int,float)) else None
        metrics=case['metrics']
        entry['labor_same_single_source_valid']=metrics['time_comparable_single_source_AC']
        entry['labor_source_count_matched_valid']=metrics['time_comparable_source_count_AC']
        for validity,field in [('single_source','time_comparable_single_source_AC'),('source_count_matched','time_comparable_source_count_AC')]:
            av,cv=A.get('source_time_total_seconds'),C.get('source_time_total_seconds')
            valid=metrics[field] and isinstance(av,(int,float)) and isinstance(cv,(int,float))
            entry['labor_seconds_'+validity]=cv-av if valid else None
            entry['labor_pct_'+validity]=100*(cv/av-1) if valid and av>0 else None
        entry['geometry_bev_distance_1_minus_iou']=metrics.get('geometry_bev_distance_AC')
        entry['geometry_centroid_distance_h']=metrics.get('geometry_centroid_distance_AC')
        contrasts.append(entry)
    pd.DataFrame(contrasts).to_csv(out/'ALL_21_CONTRASTS_ORIGINAL_ORIENTATION.csv',index=False,encoding='utf-8-sig')
    # Reference plus all seven outputs; full original answers are available in
    # trace data and can be inspected one by one in the paired HTML viewer.
    fig,axes=plt.subplots(2,4,figsize=(20,7.8));axes=axes.flat
    for index,ax in enumerate(axes):
        ax.imshow(canvas,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0)
        erp(ax,reference,'#111',1.3,1.,'--')
        if index==0:
            for worker in sorted(person_class):erp(ax,raw[worker]['points'],COLOR[person_class[worker]],.4,.18)
            erp(ax,reference,'#111',1.5,1.,'--');ax.set_title('当前目标参考与35人完整原答\nC1=17人 / C2=10人 / C3=8人')
        else:
            label=ORDER[index-1];row=teams[label][1];color=UNION_COLOR[index-1]
            erp(ax,(row.get('geometry') or {}).get('points'),color,2.0,1.)
            ax.set_title(label.replace('|','+')+f"：n={row['k']}，MV50={row['minimum_support']}\nB8L2={number(row.get('B8L2'))}；D10={number(row.get('D10'))}；节点={row['nodes']}")
            note=incomplete_text(row)
            if note:ax.text(.5,.05,note,transform=ax.transAxes,ha='center',fontsize=8,color='#91222c',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
        ax.set_xlabel('ERP水平像素');ax.set_ylabel('ERP竖直像素')
    fig.suptitle(image+'：事前容量指定的全部七个类别联盟（OPPJOINT K3）\n联盟人数不同；人数与构成的联合变化不能直接等同等人数替换效应',fontsize=15,y=.995)
    fig.tight_layout(rect=[0,.01,1,.92],h_pad=2.5)
    for suffix in ['png','pdf']:save_figure(fig,out/('SEVEN_ALLIANCES_ERP.'+suffix),dpi=160)
    plt.close(fig)
    limits=extent([reference]+[(r.get('geometry') or {}).get('points') for _,r in teams.values()])
    fig,axes=plt.subplots(2,4,figsize=(18,6.3));axes=axes.flat
    for index,ax in enumerate(axes):
        if index==0:
            for worker in sorted(person_class):bev(ax,raw[worker]['points'],COLOR[person_class[worker]],.6,.18)
            bev(ax,reference,'#111',1.6,1.,'--',True);ax.set_title('参考与全部完整原答\n黑虚线为同一正式参考')
        else:
            label=ORDER[index-1];row=teams[label][1];bev(ax,reference,'#111',1.3,.9,'--',True)
            bev(ax,(row.get('geometry') or {}).get('points'),UNION_COLOR[index-1],2.,1.,dots=True)
            ax.set_title(label.replace('|','+')+f"：n={row['k']}\nB8L2={number(row.get('B8L2'))}，节点={row['nodes']}")
        setup_bev(ax,limits)
    fig.suptitle(image+'：统一底面范围下的七个联盟输出\n坐标以相机高度h归一化；没有将底面形状按各队单独缩放',fontsize=15,y=.995)
    fig.tight_layout(rect=[0,.01,1,.92],h_pad=2.6)
    for suffix in ['png','pdf']:save_figure(fig,out/('SEVEN_ALLIANCES_BEV.'+suffix),dpi=160)
    plt.close(fig)
    groups=[];fig,axes=plt.subplots(2,4,figsize=(18,9.2));axes=axes.flat
    axes[0].axis('off');axes[0].text(.02,.94,'全部候选对应组\n\n颜色表示冻结楼外类别。\n浅色表示该队未入选组。\n红虚线是该队MV50门槛。\n\n组编号只在队内有效；\n跨队通过完整原答观测追踪。\n\n没有省略低票组或未选组。',ha='left',va='top',fontsize=13)
    for index,label in enumerate(ORDER):
        ax=axes[index+1];row=teams[label][1]
        items=(row.get('full_state') or {}).get('identity_groups',[])
        items=sorted(items,key=lambda g:(get_group_points(g) or [[0,0],[np.inf,0]])[1][0])
        for position,group in enumerate(items):
            workers=[m['worker'] for m in group['members']];bottom=0
            for cl in ['C1','C2','C3']:
                count=sum(person_class[w]==cl for w in workers)
                ax.bar(position,count,bottom=bottom,color=COLOR[cl],alpha=.95 if group['selected'] else .25);bottom+=count
            assert bottom==group['support'];ax.text(position,bottom+.3,str(bottom),ha='center',fontsize=8)
            groups.append({'alliance':label,'team_key':row['team_key'],'group':group['feature_id'],'support':bottom,'selected':group['selected'],
                           'minimum_support':row['minimum_support'],**{cl+'_support':sum(person_class[w]==cl for w in workers) for cl in COLOR},
                           'all_workers':'|'.join(sorted(workers)),'all_fields_json':json.dumps(group,ensure_ascii=False,separators=(',',':'))})
        ax.axhline(row['minimum_support'],color='#b22f39',ls='--',lw=1.1);ax.set_ylim(0,row['k']+3)
        ax.set_xticks(range(len(items)),[g['feature_id'].replace('node_','g') for g in items],rotation=35,fontsize=7)
        ax.set_title(label.replace('|','+')+f"：n={row['k']}，门槛={row['minimum_support']}");ax.set_ylabel('独立人员票');ax.grid(axis='y',alpha=.14)
    fig.suptitle(image+'：七联盟的全部候选组票账',fontsize=15,y=.99)
    fig.legend(handles=[Line2D([0],[0],color=COLOR[c],lw=7,label=c) for c in COLOR],loc='lower center',ncol=3,frameon=False)
    fig.tight_layout(rect=[0,.05,1,.95],h_pad=2.)
    for suffix in ['png','pdf']:save_figure(fig,out/('SEVEN_ALLIANCES_ALL_VOTES.'+suffix),dpi=160)
    plt.close(fig)
    pd.DataFrame(groups).to_csv(out/'SEVEN_ALLIANCES_ALL_GROUPS.csv',index=False,encoding='utf-8-sig')
    receipt={'image':image,'preselected_by_capacity_before_results':True,'unique_teams':7,'all_pairs':21,
             'all_members_retained':len(person_class),'all_native_identity_groups':len(groups),'new_fusions':0,'new_scores':0,
             'original_sha256':hashlib.sha256(Path(a.original).read_bytes()).hexdigest(),'union_direction_restored_by_input_orientation_sign':True,
             'unequal_team_sizes_not_treated_as_equal_n':True,'notes':'All seven class-union teams were fixed before results. All endpoints reuse registered completed teams.'}
    (out/'ALLIANCE_FIGURE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
