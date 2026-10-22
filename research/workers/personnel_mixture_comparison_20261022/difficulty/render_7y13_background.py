#!/usr/bin/env python3
"""New mixed-population example from six cached endpoint geometries, no fusion.

Choose median members of declared effect strata, retaining the complete 924-pair
distribution. The path adds 13 background members and changes n; it is not a
fixed-n exchange and not an isolated causal effect of n.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_difficulty_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=HERE/'case_7y13_background'
PAIR=HERE.parent/'configurations/CASE_7y13_BACKGROUND_ADDITION_PAIRS.csv.gz'
ORIGINAL=ROOT/'research/workers/personnel_exchange_closure_20261022/mechanisms/originals/7y3sRwLe3Va_92fb09a83f8949619b9dc5bda2855456.png'
REFERENCE=ROOT/'research/workers/personnel_exchange_closure_20261022/semi/mechanism_cases/cases/semi_member_loss_qt_repair.json.gz'

def save(d,name):
    atomic_bytes(OUT/name,d.to_csv(index=False).encode('utf-8-sig'))

def atomic_bytes(path,data):
    tmp=path.with_name(path.name+'.partial')
    with open(tmp,'wb') as f:
        assert f.write(data)==len(data)
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    assert path.read_bytes()==data,(str(path),'incomplete saved bytes')

def savefig(fig,name,dpi=170):
    p=OUT/name;fmt=p.suffix.lstrip('.')
    buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi);data=buf.getvalue()
    if fmt=='png':Image.open(io.BytesIO(data)).load()
    atomic_bytes(p,data)
    if fmt=='png':Image.open(p).load()

def closed(points):
    p=np.asarray(points,dtype=float);return np.vstack([p,p[0]])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,default=ROOT.parent/'source_recovery/v3_finite/composition/batches/batch_001');args=ap.parse_args()
    OUT.mkdir(exist_ok=True)
    p=pd.read_csv(PAIR)
    specs=[('gain_gt5',p[p.delta_B8L2.gt(5)],'Larger positive change'),
           ('near_zero',p[p.delta_B8L2.abs().le(1)],'Near-zero change'),
           ('negative',p[p.delta_B8L2.lt(0)],'Negative change')]
    # These descriptive selection strata overlap only near-zero vs negative;
    # exact representatives remain different. Full counts explicitly retain this.
    rows=[]
    for name,g,label in specs:
        g=g.assign(distance_from_stratum_median=(g.delta_B8L2-g.delta_B8L2.median()).abs())
        row=g.sort_values(['distance_from_stratum_median','team_key_n20']).iloc[0].to_dict()
        row.update(case_id=name,title=label,selection_stratum_pairs=len(g),selection_stratum_median=float(g.delta_B8L2.median()))
        rows.append(row)
    selected=pd.DataFrame(rows);save(selected,'SELECTED_PAIRS.csv')
    keys=set(selected.team_key_n20)|set(selected.team_key_n33)
    geom=pd.read_csv(args.cache/'ENDPOINT_GEOMETRY.csv.gz',low_memory=False)
    geom=geom[geom.team_key.isin(keys)].copy();assert len(geom)==6
    scal=pd.read_csv(args.cache/'ENDPOINT_SCALARS.csv.gz',low_memory=False)
    scal=scal[scal.team_key.isin(keys)].copy();assert len(scal)==6
    save(geom,'ENDPOINT_GEOMETRY.csv');save(scal,'ENDPOINT_SCALARS.csv')
    with gzip.open(REFERENCE,'rt') as f:ref=json.load(f)['reference']
    atomic_bytes(OUT/'REFERENCE.json',(json.dumps(ref,ensure_ascii=False,indent=2)+'\n').encode())
    labels=pd.read_csv(ROOT/'research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz')
    labels=labels[labels.condition.eq('semi')&labels.heldout_building.eq('7y3sRwLe3Va')]
    allmembers=set('|'.join(scal.member_workers).split('|'))
    save(labels[labels.worker_id.isin(allmembers)],'FOLD_LABELS_AND_HISTORY.csv')
    raw_source=ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    with gzip.open(raw_source,'rt') as f:raw=json.load(f)['records']
    objects=set('|'.join(scal.member_object_ids).split('|'))
    kept=['object_id','worker_id','image_id','image_code','building_id','condition','origin',
          'data_release','current_class','quality_usable','quality_use','independent_vote_eligible',
          'B8L2','D10','reference_id','reference_version','source_active_time_seconds','time_evidence',
          'points_1024x512','geometry_status','order_status','ring_confirmed','measurements']
    raw=[{k:r.get(k) for k in kept} for r in raw if r['object_id'] in objects]
    assert len(raw)==len(objects)
    atomic_bytes(OUT/'RAW_MEMBER_GEOMETRY.json',(json.dumps(raw,ensure_ascii=False,separators=(',',':'))+'\n').encode())
    long=[];components=[]
    for _,r in selected.iterrows():
        a=scal[scal.team_key.eq(r.team_key_n20)].iloc[0];b=scal[scal.team_key.eq(r.team_key_n33)].iloc[0]
        ma=set(a.member_workers.split('|'));mb=set(b.member_workers.split('|'));v=set(r.selected_variable_workers.split('|'))
        assert ma<=mb and len(mb-ma)==13 and len(v)==6 and v<=ma
        for arm,s,workers in [('n20',a,ma),('n33',b,mb)]:
            for w in sorted(workers):
                role='variable_6_unchanged' if w in v else 'background_14_unchanged' if w in ma else 'background_13_added'
                long.append(dict(case_id=r.case_id,arm=arm,worker_id=w,member_role=role,team_key=s.team_key))
        for m in ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
                  'height_mean_h','geometry_area_h2','bottom_y_mean_px','top_y_mean_px','nodes','minimum_support']:
            components.append(dict(case_id=r.case_id,metric=m,n20=a[m],n33=b[m],n33_minus_n20=b[m]-a[m]))
    save(pd.DataFrame(long),'EXACT_MEMBERS.csv');save(pd.DataFrame(components),'COMPONENT_CHANGES.csv')
    # Exact disjoint effect strata for distribution, independently of figure case choices.
    p['effect_stratum']=np.select([p.delta_B8L2.lt(0),p.delta_B8L2.le(5)],['negative','positive_0_to_5'],default='gain_gt5')
    ds=p.groupby('effect_stratum').delta_B8L2.agg(['size','mean','median','min','max']).reset_index();save(ds,'ALL_924_EFFECT_STRATA.csv')
    # Save floor coordinate movements relative to the stored reference without rewriting ring order.
    coord=[]
    for _,r in selected.iterrows():
        for n in [20,33]:
            g=json.loads(geom[geom.team_key.eq(r[f'team_key_n{n}'])].geometry_json.iloc[0])
            for j,(xyz,uvtop,uvbottom) in enumerate(zip(g['footprint'],g['points'][::2],g['points'][1::2])):
                coord.append(dict(case_id=r.case_id,n=n,stored_corner_index=j,x_h=xyz[0],z_h=xyz[1],u=uvbottom[0],top_v=uvtop[1],bottom_v=uvbottom[1]))
    save(pd.DataFrame(coord),'STORED_CORNER_COORDINATES.csv')
    # True original image and cached geometric overlays. Coordinates use the 1024x512 reference frame.
    im=np.asarray(Image.open(ORIGINAL).convert('RGB'))
    fig,axs=plt.subplots(3,3,figsize=(13,10),gridspec_kw={'width_ratios':[1,2,1]},layout='constrained')
    plt.rcParams['svg.fonttype']='none'
    colors={20:'#D16A1D',33:'#007F90'};refp=np.asarray(ref['points_1024x512']);reff=closed(ref['floor_xz_h'])
    for i,(_,r) in enumerate(selected.iterrows()):
        ax=axs[i,0];ax.imshow(im,extent=[0,1024,512,0]);ax.set_xlim(230,284);ax.set_ylim(295,222)
        for j in [2,3]:ax.plot(refp[2*j:2*j+2,0],refp[2*j:2*j+2,1],'--',c='#FFD44F',lw=1.2)
        for n in [20,33]:
            g=json.loads(geom[geom.team_key.eq(r[f'team_key_n{n}'])].geometry_json.iloc[0]);pp=np.asarray(g['points'])
            for j in range(len(pp)//2):
                if 230<=pp[2*j,0]<=284:
                    ax.plot(pp[2*j:2*j+2,0],pp[2*j:2*j+2,1],c=colors[n],lw=1.6)
                    ax.scatter(pp[2*j:2*j+2,0],pp[2*j:2*j+2,1],s=18,c=colors[n],marker='o' if n==20 else 'x')
        ax.set_xlabel('ERP x (1024 frame)');ax.set_ylabel('ERP y');ax.set_title('Actual far-wall image crop',fontsize=10)
        for j in [1,2]:
            ax=axs[i,j];ax.plot(reff[:,0],reff[:,1],'--',c='#303D4A',lw=1.3,label='Reference')
            for n in [20,33]:
                g=json.loads(geom[geom.team_key.eq(r[f'team_key_n{n}'])].geometry_json.iloc[0]);pp=closed(g['footprint'])
                ax.plot(pp[:,0],pp[:,1],'-o',c=colors[n],lw=1.5,ms=3,label=f'n={n}')
            ax.grid(alpha=.2);ax.set_aspect('equal');ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height')
            if j==2:ax.set_xlim(-5.9,-5.25);ax.set_ylim(-.58,.58);ax.set_title('Far-wall BEV detail',fontsize=10)
            else:
                ax.set_xlim(-6.0,1.6);ax.set_ylim(-1.1,1.15)
                ax.set_title(f'{r.title}: Q {r.B8L2_n20:.2f} → {r.B8L2_n33:.2f} ({r.delta_B8L2:+.2f})\nFixed variable members: {r.selected_variable_workers}',fontsize=9)
                ax.legend(frameon=False,loc='lower center',ncol=3,fontsize=9)
    fig.suptitle('7y3sRwLe3Va-13 · Semi · background 14 → 27, same variable 6\nThree descriptive cases from all 924 paired endpoints; four actual turns in both teams',fontsize=13,weight='bold')
    savefig(fig,'ERP_BEV_three_paths.png');savefig(fig,'ERP_BEV_three_paths.svg');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.2),layout='constrained')
    ax.hist(p.delta_B8L2,bins=np.linspace(-3,35,39),color='#2B91A0',edgecolor='white')
    ax.axvline(p.delta_B8L2.mean(),c='#D16A1D',lw=2,label=f'Mean {p.delta_B8L2.mean():+.3f}')
    ax.axvline(p.delta_B8L2.median(),c='#304657',ls='--',lw=2,label=f'Median {p.delta_B8L2.median():+.3f}')
    ax.set_xlabel('B8L2: n33 minus n20 (same variable 6; +13 common-background members)');ax.set_ylabel('Paired actual member sets')
    ax.set_title('All 924 pairs: most gains are small; a subset loses large localization error',loc='left',fontsize=11)
    ax.legend(frameon=False);savefig(fig,'ALL_924_quality_change.png',dpi=175);plt.close(fig)
    receipt=dict(data_version='v2',source='cached v3 finite panel endpoints, batch_001',pairs_total=924,
        positive=int(p.delta_B8L2.gt(0).sum()),negative=int(p.delta_B8L2.lt(0).sum()),
        gain_gt5=int(p.delta_B8L2.gt(5).sum()),abs_change_le1=int(p.delta_B8L2.abs().le(1).sum()),
        mean_delta=float(p.delta_B8L2.mean()),median_delta=float(p.delta_B8L2.median()),
        selected_pairs=len(selected),stored_endpoints=len(geom),all_selected_team_sizes_nested=True,
        actual_added_members=13,actual_removed_members=0,variable_members_unchanged=6,
        note='The panel_id segment __v1__ means variable_panel_no=1; source_domain=all_formal. These full teams contain both origins.',
        selection='within each prespecified descriptive effect stratum choose closest to its median, deterministic team-key tiebreak',
        geometry_sha256=hashlib.sha256((OUT/'ENDPOINT_GEOMETRY.csv').read_bytes()).hexdigest(),
        source_image_sha256=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),new_fusion=0,new_scoring=0)
    atomic_bytes(OUT/'RECEIPT.json',(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
