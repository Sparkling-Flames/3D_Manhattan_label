#!/usr/bin/env python3
"""Trace existing selected corners from member observations to coordinate medians.

No rescoring or refitting: all centers and footprints come from the exact native
geometry replay. Shared-node correspondence uses immutable observation overlap.
"""
import importlib.util,itertools,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
import export_cases as e

HERE=e.HERE
sys.path.insert(0,'/tmp/hohonet_deps')
spec=importlib.util.spec_from_file_location('frozen_case_viewer',e.ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

def obs(g):return {(m['id'],int(m['pair_index'])) for m in g['members']}

def main():
    corners=[];ranks=[];pairs=[];critical=[];cases=[]
    for path in sorted((HERE/'cases').glob('*.json.gz')):
        c=e.gs.read(path);cases.append(c);byclass={r['worker_id']:r['class_id'] for r in c['members']}
        # Order of a selected node is native candidate order, not a guessed global
        # node ID. Positive shared observation overlap determines inter-arm links.
        states={}
        for t in c['teams']:
            gg=[g for g in t['full_state']['identity_groups'] if g['selected']]
            geom=v.viewer_geometry(t['geometry']['points'],t['geometry']['footprint'])
            fi={f:i for i,f in enumerate(t['geometry']['feature_ids'])};states[t['label']]=(t,gg,geom,fi)
            for g in gg:
                i=fi[g['feature_id']];z=g['center'];x,y=geom['floor'][i]
                row=dict(case_id=c['case_id'],arm=t['label'],feature_id=g['feature_id'],support=g['support'],threshold=t['minimum_support'],
                    top_x=z[0][0],top_y=z[0][1],bottom_x=z[1][0],bottom_y=z[1][1],floor_x_h=x,floor_z_h=y,
                    derived_height_h=float(geom['ceiling_xyz'][i,1]+1),bottom_depression_deg=(z[1][1]/512-.5)*180)
                corners.append(row)
                for coord,index in [('x',(0,0)),('top_y',(0,1)),('bottom_y',(1,1))]:
                    ms=sorted(g['members'],key=lambda m:(m['points'][index[0]][index[1]],m['worker']))
                    values=[m['points'][index[0]][index[1]] for m in ms];median=float(np.median(values))
                    # All relevant image coordinates are far from the ERP seam.
                    assert abs(median-z[index[0]][index[1]])<1e-8
                    middle={(len(ms)-1)//2,len(ms)//2}
                    for rank,m in enumerate(ms):
                        rr=dict(case_id=c['case_id'],arm=t['label'],feature_id=g['feature_id'],coordinate=coord,
                            rank_1_based=rank+1,support=len(ms),worker_id=m['worker'],object_id=m['id'],pair_index=m['pair_index'],
                            class_id=byclass[m['worker']],value=values[rank],median_value=median,
                            central_rank=rank in middle,median_weight=(1/len(middle) if rank in middle else 0))
                        ranks.append(rr)
                    # Far end lower corner is identified by spatial location.
                    if coord=='bottom_y' and x < -5 and y < 0:
                        critical.append(dict(row,central_workers='|'.join(ms[j]['worker'] for j in sorted(middle)),
                            central_values='|'.join(str(values[j]) for j in sorted(middle)),median_equals_center=True))
        for aa,bb in itertools.combinations(c['teams'],2):
            ta,ga,gea,ia=states[aa['label']];tb,gb,geb,ib=states[bb['label']]
            ov=np.array([[len(obs(a)&obs(b)) for b in gb] for a in ga]);ii,jj=linear_sum_assignment(-ov)
            for i,j in zip(ii,jj):
                a,b=ga[i],gb[j];assert ov[i,j]>0
                pa,pb=np.asarray(a['center']),np.asarray(b['center']);fa,fb=gea['floor'][ia[a['feature_id']]],geb['floor'][ib[b['feature_id']]]
                ha,hb=gea['ceiling_xyz'][ia[a['feature_id']],1]+1,geb['ceiling_xyz'][ib[b['feature_id']],1]+1
                pairs.append(dict(case_id=c['case_id'],arm_A=aa['label'],arm_B=bb['label'],A_feature_id=a['feature_id'],B_feature_id=b['feature_id'],
                    immutable_shared_observations=int(ov[i,j]),A_support=a['support'],B_support=b['support'],
                    delta_x_px=pb[0,0]-pa[0,0],delta_top_y_px=pb[0,1]-pa[0,1],delta_bottom_y_px=pb[1,1]-pa[1,1],
                    A_floor_x_h=fa[0],A_floor_z_h=fa[1],B_floor_x_h=fb[0],B_floor_z_h=fb[1],
                    floor_shift_h=float(np.linalg.norm(fb-fa)),delta_derived_height_h=float(hb-ha)))
    for name,rows in [('SELECTED_CORNER_GEOMETRY.csv',corners),('MEDIAN_ORDER_STATISTICS.csv',ranks),
        ('CORNER_POSITION_TRANSMISSION.csv',pairs),('CRITICAL_CORNER_MEDIANS.csv',critical)]:e.savecsv(name,pd.DataFrame(rows))
    # A compact graph exposes why unchanged vote counts need not fix a median.
    v._configure_font(e.ROOT/'research/workers/personnel_composition_study_20261019/analysis/fonts/NotoSansSC-Regular.ttf')
    fig,axes=v.plt.subplots(2,3,figsize=(14,8),sharey=True)
    colors={'S1':'#2276a0','S2':'#c88523','S3':'#3c9265'}
    rr=pd.DataFrame(ranks);cr=pd.DataFrame(critical)
    cases=sorted(cases,key=lambda c:'counterexample' in c['case_id'])
    for row,c in enumerate(cases):
        ref=np.asarray(c['reference']['points_1024x512']);ref_y=float(ref[7,1])
        for col,t in enumerate(c['teams']):
            ax=axes[row,col];cc=cr[(cr.case_id==c['case_id'])&(cr.arm==t['label'])].iloc[0]
            z=rr[(rr.case_id==c['case_id'])&(rr.arm==t['label'])&(rr.feature_id==cc.feature_id)&(rr.coordinate=='bottom_y')]
            ax.axhline(ref_y,color='#777',linestyle='--',lw=1,label='冻结参考')
            ax.axhline(cc.bottom_y,color='#121d30',lw=1.5,label='实际中位数')
            ax.scatter(z.rank_1_based,z.value,c=[colors[x] for x in z.class_id],s=np.where(z.central_rank,90,40),edgecolor='white',zorder=3)
            middle=z[z.central_rank]
            for ii,(_,r) in enumerate(middle.iterrows()):
                offset=(-36,-31) if len(middle)==2 and ii==0 else (8,9)
                ax.annotate(f"{r.worker_id}\n{r.value:.3f}",(r.rank_1_based,r.value),xytext=offset,textcoords='offset points',fontsize=8)
            ax.set_xticks(z.rank_1_based,z.worker_id,rotation=65,ha='right',fontsize=8)
            ax.set_ylim(278,292);ax.grid(alpha=.18);ax.set_axisbelow(True)
            ax.set_title(f"{'正例' if row==0 else '反例'} {t['label']} | Q={t['B8L2']:.2f} | 角点支持{cc.support}/12\n底点中位数 {cc.bottom_y:.3f}px",fontsize=10)
            if col==0:ax.set_ylabel('远端角底点 ERP y（像素）')
    fig.suptitle('同样保留四角，坐标中位数仍可跨过相邻人员的落点',fontsize=16,x=.07,ha='left')
    fig.text(.07,.015,'点色为目标楼外结构类：蓝S1、橙S2、绿S3；黑线为实际中位数，灰虚线为冻结参考。完整团队均为12人；未加入该角票组的人员不进入该角中位数。',fontsize=9,color='#4b5b6d')
    fig.tight_layout(rect=(.02,.055,.99,.93));(HERE/'figures').mkdir(exist_ok=True)
    fig.savefig(HERE/'figures/MEDIAN_TRANSMISSION.png',dpi=170,facecolor='white');v.plt.close(fig)
    e.gs.save(HERE/'MEDIAN_ANALYSIS_CONTRACT.json',dict(no_fusion_or_scores=True,
        comparison='Hungarian maximum immutable-observation overlap among selected groups; all matched overlaps positive',
        center_check='every selected x/top_y/bottom_y equals the frozen coordinate median to 1e-8 in these seam-free cases',
        heights='viewer paired-floor horizontal range, camera height=1, no measured absolute room height',
        note='nodes are local identifiers, only observation overlap creates correspondence'))
    print('Saved exact median ranks, native corner transmission and explanatory plot',flush=True)

if __name__=='__main__':main()
