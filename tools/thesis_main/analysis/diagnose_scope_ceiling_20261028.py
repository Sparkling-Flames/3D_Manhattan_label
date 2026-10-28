"""Equal-vertex least-squares horizontal ceiling sensitivity, never adopted implicitly."""
import gzip
import json
import numpy as np
import pandas as pd
from .adopt_orthogonal_references_20261028 import OUT as ADOPT
from .orthogonal_scope_references_20261028 import ROOT,geometry,points_for
from .scope_quality_scoring_20261016 import scoring_engine,score_task
from .quality_b8l2_d10_20261017 import dual_scores
OUT=ADOPT/'ceiling_diagnostic'


def main():
    OUT.mkdir(exist_ok=True)
    refs=json.loads((ADOPT/'ADOPTED_REFERENCES.json').read_text(encoding='utf-8'))
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:data=json.load(f)
    objects=[o for o in data['objects'] if o['object_kind']=='annotation' and o['condition']=='manual']
    candidates=[];audit=[];scores=[]
    with scoring_engine() as (engine,models):
        for ref in refs:
            g=geometry(ref['points_1024x512']);h=np.asarray(g['top3d'])[:,1]
            if np.ptp(h)<1e-8:continue
            bottom=np.asarray(ref['floor_xz_h']);height=float(h.mean())
            points=points_for(bottom,np.full(len(bottom),height))
            before=np.asarray(ref['points_1024x512']);after=np.asarray(points)
            np.testing.assert_allclose(before[1::2],after[1::2],atol=1e-8)
            candidate=dict(target_id=ref['target_id'],image=ref['image'],image_id=ref['image_id'],baseline_points=ref['points_1024x512'],points_1024x512=points,
                fitted_height_h=height,method='equal_vertex_3D_height_least_squares_horizontal_plane',adopted=False)
            candidates.append(candidate)
            audit.append(dict(image=ref['image'],target_id=ref['target_id'],nodes=len(h),height_min_h=h.min(),height_max_h=h.max(),height_range_h=np.ptp(h),fitted_height_h=height,max_height_move_h=np.abs(h-height).max(),max_top_y_move_px=np.abs(before[::2,1]-after[::2,1]).max(),adopted=False))
            for obj in objects:
                if obj['image_id']!=ref['image_id']:continue
                values={}
                for name,ps in [('preserved',ref['points_1024x512']),('flat',points)]:
                    task=dict(object_id=obj['object_id'],image_id=obj['image_id'],worker_id=obj['worker_id'],condition='manual',current_target_id=ref['target_id'],reference_version='ceiling_diagnostic_20261028:'+name,annotation_points=obj['points_1024x512'],reference_points=ps)
                    result=score_task(task,engine,models)
                    if result['score_status']=='complete':result.update(dual_scores(result,models))
                    values[name]=result
                row=dict(image=ref['image'],target_id=ref['target_id'],object_id=obj['object_id'],before_status=values['preserved']['score_status'],after_status=values['flat']['score_status'])
                for m in ['B8L2','D10','dir','Hmean','Hcenter','IoU3D100']:
                    a=values['preserved'].get(m);b=values['flat'].get(m)
                    row[m+'_before']=a;row[m+'_after']=b;row[m+'_delta']=b-a if a is not None and b is not None else None
                scores.append(row)
            print('ceiling diagnostic',ref['image'],flush=True)
    (OUT/'CANDIDATES.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame(audit).to_csv(OUT/'HEIGHT_AUDIT.csv',index=False,encoding='utf-8')
    d=pd.DataFrame(scores);d.to_csv(OUT/'SCORE_PAIRS.csv',index=False,encoding='utf-8')
    summary=[]
    for tid,z in d.groupby('target_id'):
        r=dict(target_id=tid,image=z.image.iloc[0],records=len(z),common_scored=int(z.B8L2_delta.notna().sum()))
        for m in ['B8L2','D10','IoU3D100']:
            r[m+'_mean_delta']=z[m+'_delta'].mean();r[m+'_max_abs_delta']=z[m+'_delta'].abs().max()
        summary.append(r)
    pd.DataFrame(summary).to_csv(OUT/'SCORE_SUMMARY.csv',index=False,encoding='utf-8')
    assert d.dir_delta.dropna().eq(0).all()
    print('diagnostic references',len(candidates),'pairs',len(scores),'adopted',0)
    figure(candidates)


def figure(candidates):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from tools.label_studio.panorama_studio.geometry import project_pixel
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    selected=[r for r in candidates if r['image'] in ['q9vSo1VnCiC-13','uNb9QFRL6hY-45','X7HyMhZNoso-05']]
    fig,axes=plt.subplots(len(selected),2,figsize=(15,10),layout='constrained',gridspec_kw={'width_ratios':[2.4,1]})
    for axs,r in zip(axes,selected):
        photo=ROOT/'data/mp3d_layout/img_v'/(r['image_id']+'.jpg');axs[0].imshow(Image.open(photo),extent=[0,1024,512,0])
        for key,color,label in [('baseline_points','#00dddd','已采用：保留逐点顶高'),('points_1024x512','#ff4488','未采用：水平顶面诊断')]:
            top=np.asarray(geometry(r[key])['top3d']);pixels=[]
            for a,b in zip(top,np.roll(top,-1,axis=0)):
                pixels.extend(project_pixel(a*(1-t)+b*t,1024,512) for t in np.linspace(0,1,100))
            pixels=np.asarray(pixels);pixels[np.flatnonzero(abs(np.diff(pixels[:,0]))>512)+1]=np.nan
            axs[0].plot(pixels[:,0],pixels[:,1],color=color,lw=1.3,label=label)
            axs[1].plot(np.arange(1,len(top)+1),top[:,1],color=color,marker='o',ms=3,label=label)
        axs[0].set_xlim(0,1024);axs[0].set_ylim(512,0);axs[0].axis('off');axs[0].legend(fontsize=8);axs[0].set_title(r['image'])
        axs[1].set_xlabel('保留点编号');axs[1].set_ylabel('相机以上顶高 / 相机高度');axs[1].grid(alpha=.2)
    fig.suptitle('水平顶面仅作诊断：不因分数变化自动判断真实顶面是否同高',fontsize=14)
    fig.savefig(OUT/'顶高诊断_叠线与逐点高度.png',dpi=140);plt.close(fig)


if __name__=='__main__':main()
