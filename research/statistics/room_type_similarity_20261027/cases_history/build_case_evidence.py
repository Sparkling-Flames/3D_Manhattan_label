#!/usr/bin/env python3
"""Saved-answer room-use cases. No scoring, classification, or fusion is run.

Run from study directory or supply --cases and --source-root. All saved source
objects are frozen formal-v2 records. Geometry drawing derives 3-D rays from
their effective paired coordinates, without changing the scoring coordinates.
"""
from pathlib import Path
import argparse, gzip, json, hashlib
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CODES=['b8cTxDM8gDG-07','S9hNv5qa7GM-05','jtcxE69GiFV-13']
TITLES=['Bedroom | b8-07 | easy','Bathroom | S9-05 | medium','Bathroom | jtc-13 | medium']
COLORS={'reference':'#ffe34b','W107':'#ec57ba','W112':'#00d5e8'}

def geometry(points):
    p=np.asarray(points,float); yaw=(p[1::2,0]/1024-.5)*2*np.pi
    rad=1/np.tan((p[1::2,1]/512-.5)*np.pi)
    floor=np.c_[rad*np.sin(yaw),-rad*np.cos(yaw)]
    bot=np.c_[floor[:,0],-np.ones(len(floor)),floor[:,1]]
    top=bot.copy();top[:,1]=rad*np.tan((.5-p[::2,1]/512)*np.pi)
    return floor,bot,top

def projection(xyz):
    a=np.asarray(xyz)
    return np.c_[((np.arctan2(a[:,0],-a[:,2])/(2*np.pi)+.5)%1)*1024,
                 (.5-np.arctan2(a[:,1],np.hypot(a[:,0],a[:,2]))/np.pi)*512]

def draw_edges(ax, points, color, lw=1.5, alpha=1):
    floor,bot,top=geometry(points)
    for arr in [bot,top]:
        for j in range(len(arr)):
            xyz=np.linspace(arr[j],arr[(j+1)%len(arr)],120)
            uv=projection(xyz);bad=np.where(np.abs(np.diff(uv[:,0]))>512)[0]+1
            for seg in np.split(uv,bad):
                if len(seg)>1:ax.plot(seg[:,0],seg[:,1],color=color,lw=lw,alpha=alpha)
    p=np.asarray(points,float)
    for j in range(0,len(p),2):ax.plot(p[j:j+2,0],p[j:j+2,1],color=color,lw=lw,alpha=alpha)
    ax.scatter(p[:,0],p[:,1],s=12,facecolor=color,edgecolor='black',linewidth=.3,zorder=5)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[2]/'hohonet_source_20261027')
    a=ap.parse_args();out=a.cases
    source_records=out/'case_records.json.gz'
    if source_records.exists():
        with gzip.open(source_records,'rt',encoding='utf8') as h:records=json.load(h)
    else:
        source_records=out/'case_records.json'
        records=json.loads(source_records.read_text())
    frozen=next((p for p in [out/'case_frozen_features.csv',a.source_root/'research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz'] if p.exists()))
    feat=pd.read_csv(frozen,low_memory=False);feat=feat[feat.object_id.isin([r['object_id'] for r in records])]
    feat.to_csv(out/'case_frozen_features.csv',index=False)
    f=feat.set_index('object_id'); by={r['object_id']:r for r in records}; rows=[];geoms=[]
    for r in records:
        x=f.loc[r['object_id']]
        m=r['measurements']['same_reference_measurements']
        row={k:r[k] for k in ['object_id','image_code','image_id','building_id','worker_id','condition','reference_id','reference_version','quality_usable','B8L2','D10','source_active_time_seconds']}
        row.update(room_type=r['image_evidence']['room_spatial_classification']['coarse_type'],difficulty=r['current_class'],time_source=r['time_evidence']['source_kind'],annotation_turn5=x['annotation_turn5'],ref_turn5=x['ref_turn5'],ref_H=x['ref_H'],ref_short_edges=x['ref_short_edges'],short_span_deg=x['ref_short_min_horizontal_deg'],reduced=x['reduced'],floor_iou=m['iou_2d'],bottom_deg=m['S_bottom_deg'],own_orthogonality_deg=m['dir'],height_mean_relative=m['Hmean'],height_center_relative=m['Hcenter'])
        rows.append(row)
        floor,bot,top=geometry(r['points_1024x512'])
        geoms.append({'object_id':r['object_id'],'worker_id':r['worker_id'],'image_code':r['image_code'],'reference_id':r['reference_id'],'effective_points_1024x512':r['points_1024x512'],'received_processed_points':r['received_processed_points'],'raw_original_available':r['raw_original_available'],'annotation_floor_xz_h':floor.tolist(),'annotation_bottom3d_h':bot.tolist(),'annotation_top3d_h':top.tolist(),'reference':r['reference_evidence']})
    d=pd.DataFrame(rows);d['relative_Q_loo']=d.groupby('image_code').B8L2.transform(lambda s:s-(s.sum()-s)/(len(s)-1));d.to_csv(out/'CASE_ALL_FORMAL_ANSWERS.csv',index=False,encoding='utf-8-sig')
    d[d.worker_id.isin(['W107','W112'])].to_csv(out/'CASE_FEATURED_ANSWERS.csv',index=False,encoding='utf-8-sig')
    with gzip.open(out/'CASE_GEOMETRY.jsonl.gz','wt',encoding='utf8') as h:
        for r in geoms:h.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary=[]
    for im,g in d.groupby('image_code'):
        x=g.iloc[0]
        summary.append(dict(image_code=im,room_type=x.room_type,difficulty=x.difficulty,reference_id=x.reference_id,n=len(g),workers=g.worker_id.nunique(),Q_mean=g.B8L2.mean(),Q_sd=g.B8L2.std(ddof=1),D10_mean=g.D10.mean(),reduced_n=int(g.reduced.sum()),reduction_rate=g.reduced.mean(),ref_turn5=x.ref_turn5,ref_H=x.ref_H,short_edges=x.ref_short_edges,short_span_deg=x.short_span_deg))
    pd.DataFrame(summary).to_csv(out/'CASE_IMAGE_SUMMARY.csv',index=False,encoding='utf-8-sig')
    pairs=[]
    for left,right in [(CODES[0],CODES[2]),(CODES[1],CODES[2])]:
        z=d[d.image_code.eq(left)].merge(d[d.image_code.eq(right)],on='worker_id',suffixes=('_left','_right'))
        z['pair_id']=left+'__'+right
        z['Q_change']=z.B8L2_right-z.B8L2_left
        z['relative_Q_change']=z.relative_Q_loo_right-z.relative_Q_loo_left
        z['turn_change']=z.annotation_turn5_right-z.annotation_turn5_left
        pairs.append(z)
    p=pd.concat(pairs,ignore_index=True);p.to_csv(out/'CASE_COMMON_PERSON_COMPARISONS.csv',index=False,encoding='utf-8-sig')
    pair_summary=[]
    for pid,g in p.groupby('pair_id'):
        pair_summary.append(dict(pair_id=pid,image_left=g.image_code_left.iloc[0],image_right=g.image_code_right.iloc[0],same_use=bool(g.room_type_left.iloc[0]==g.room_type_right.iloc[0]),different_buildings=True,common_people=len(g),Q_mean_left=g.B8L2_left.mean(),Q_mean_right=g.B8L2_right.mean(),Q_mean_change=g.Q_change.mean(),mean_absolute_person_Q_change=g.Q_change.abs().mean(),Q_pearson=g.B8L2_left.corr(g.B8L2_right),Q_spearman=g.B8L2_left.corr(g.B8L2_right,method='spearman'),fewer_turns_on_right=int(g.turn_change.lt(0).sum()),same_turns=int(g.turn_change.eq(0).sum()),more_turns_on_right=int(g.turn_change.gt(0).sum()),interpretation='Selected mechanism example; not an independent estimate of average room-type effect'))
    pd.DataFrame(pair_summary).to_csv(out/'CASE_PAIR_SUMMARY.csv',index=False,encoding='utf-8-sig')
    plt.rcParams.update({'font.size':11,'axes.titlesize':13,'savefig.facecolor':'white'})
    fig,axs=plt.subplots(3,3,figsize=(20,15),gridspec_kw={'height_ratios':[1,1.1,1.2]})
    fig.suptitle('Room use is not a fixed annotation response: complete answers and the frozen reference',fontsize=18,y=.99)
    zooms=[]
    for j,(code,title) in enumerate(zip(CODES,TITLES)):
        rr=[r for r in records if r['image_code']==code];rf=rr[0]['reference_evidence'];ref=np.asarray(rf['floor_xz_h'])
        imagepath=next((out/'images').rglob(rr[0]['image_id']+'.png'));photo=np.asarray(Image.open(imagepath))
        pp=np.asarray(rf['points_1024x512']);edge=np.linalg.norm(np.roll(ref,-1,axis=0)-ref,axis=1);idx=int(np.argmin(edge))
        lo,hi=sorted([pp[2*idx,0],pp[2*((idx+1)%len(ref)),0]]); assert hi-lo<512
        zoom=(max(0,lo-65),min(1024,hi+65),45,465);zooms.append({'image_code':code,'zoom_1024x512':zoom,'short_edge_zero_based':idx,'original_image_path':str(imagepath.relative_to(out))})
        for i in [0,1]:
            ax=axs[i,j];ax.imshow(photo,extent=(0,1024,512,0));draw_edges(ax,rf['points_1024x512'],COLORS['reference'],2.6)
            for w in ['W107','W112']:
                r=next(x for x in rr if x['worker_id']==w);draw_edges(ax,r['points_1024x512'],COLORS[w],1.55)
            if i==0:ax.set_xlim(0,1024);ax.set_ylim(512,0)
            else:ax.set_xlim(zoom[0],zoom[1]);ax.set_ylim(zoom[3],zoom[2])
            ax.set_xticks([]);ax.set_yticks([])
        x=next(x for x in summary if x['image_code']==code)
        axs[0,j].set_title(title+'\n'+f"{x['reduced_n']}/{x['n']} fewer turns; mean Q {x['Q_mean']:.2f}")
        axs[1,j].set_title(f"Shortest reference wall: horizontal span {x['short_span_deg']:.2f} deg")
        ax=axs[2,j]
        z=np.vstack([ref,ref[0]]);ax.plot(z[:,0],z[:,1],color='#b68b00',lw=3,label='Frozen reference: 6 turns')
        for w in ['W107','W112']:
            r=next(x for x in rr if x['worker_id']==w);fl,_,_=geometry(r['points_1024x512']);z=np.vstack([fl,fl[0]]);x=d[d.object_id.eq(r['object_id'])].iloc[0]
            ax.plot(z[:,0],z[:,1],'-o',color=COLORS[w],lw=1.7,ms=4,label=f"{w}: {int(x.annotation_turn5)} turns, Q {x.B8L2:.2f}")
        ax.scatter([0],[0],marker='x',c='black',label='Camera');ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.legend(fontsize=9,loc='best')
    fig.text(.5,.018,'Yellow: frozen reference | Pink: W107 | Cyan: W112. Same people; different physical rooms/buildings.\nAll points and references retained. S9-05 and jtc-13 share bathroom use, medium difficulty, six reference turns and H=0.',ha='center',fontsize=11)
    fig.tight_layout(rect=(0,.05,1,.97));fig.savefig(out/'C01_COMPLETE_ANSWERS.png',dpi=150);plt.close(fig)
    (out/'CASE_VISUAL_LOCATIONS.json').write_text(json.dumps(zooms,ensure_ascii=False,indent=2)+'\n')
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,(pid,g) in zip(axs,p.groupby('pair_id',sort=False)):
        v=g.groupby(['annotation_turn5_left','annotation_turn5_right']).size().reset_index(name='people')
        ax.scatter(v.annotation_turn5_left,v.annotation_turn5_right,s=v.people*35,c='#23577c',alpha=.75)
        for _,r in v.iterrows():ax.annotate(str(int(r.people)),(r.annotation_turn5_left,r.annotation_turn5_right),ha='center',va='center',color='white',fontsize=11)
        ax.plot([3.7,6.3],[3.7,6.3],ls='--',c='gray');ax.set(xlim=(3.7,6.3),ylim=(3.7,6.3),xticks=[4,5,6],yticks=[4,5,6],xlabel=g.image_code_left.iloc[0]+' turns',ylabel=g.image_code_right.iloc[0]+' turns',title=f'Common people: {len(g)}; fewer turns on right: {(g.turn_change<0).sum()}')
        ax.grid(alpha=.2)
    fig.suptitle('Same-person expression: the common-person panel, not independent pair samples',fontsize=13);fig.tight_layout();fig.savefig(out/'C02_COMMON_PERSON_TURNS.png',dpi=150);plt.close(fig)
    source_files=[frozen,source_records]
    (out/'CASE_COMPUTE_RECEIPT.json').write_text(json.dumps({'data_release':'v2','source_commit':'b9bcec809fbaec8ab055931a1abb7baa5db44dac','operation':'extract saved formal answer geometry; reuse frozen structural features and quality; compute common-person descriptive tables and render','new_fusion_endpoints':0,'new_scores':0,'records':len(d),'images':d.image_code.nunique(),'buildings':d.building_id.nunique(),'people':d.worker_id.nunique(),'featured_records':int(d.worker_id.isin(['W107','W112']).sum()),'sources':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in source_files]},ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(summary).to_string(index=False));print(pd.DataFrame(pair_summary).to_string(index=False))

if __name__=='__main__':main()
