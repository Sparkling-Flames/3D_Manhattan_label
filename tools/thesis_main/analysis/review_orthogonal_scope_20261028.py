"""Saved-output checks and per-manual-GT review sheets; no fitting/scoring."""
import gzip
import html
import json
import numpy as np
import pandas as pd
from .orthogonal_scope_references_20261028 import ROOT,OUT,axis,geometry,floor,project_pixel,write


def main():
    refs=json.loads((OUT/'REFERENCES.json').read_text(encoding='utf-8'));lookup={r['target_id']:r for r in refs}
    a=pd.read_csv(OUT/'GEOMETRY_AUDIT.csv');d=pd.read_csv(OUT/'PAIRED_SCORES.csv');manual=pd.read_csv(OUT/'SAVED_MANUAL_GT_AUDIT.csv')
    assert len(manual)==30 and len(refs)==71
    assert a.after_axis_residual_deg.max()<1e-8
    assert d.loc[d.common_score,'dir_delta'].eq(0).all()
    failures=[]
    for line in (OUT/'PAIRED_MEASUREMENTS.jsonl').read_text(encoding='utf-8').splitlines():
        r=json.loads(line);before=r['results']['before'];after=r['results']['after']
        if before['score_status']!='complete' or after['score_status']!='complete':
            failures.append(dict(object_id=r['object_id'],target_id=r['target_id'],before_status=before['score_status'],after_status=after['score_status'],before_reasons=before['reasons'],after_reasons=after['reasons']))
    write('UNSCOREABLE_PAIRS.json',failures)
    for ref in refs:
        p=np.asarray(ref['floor_xz_h']);np.testing.assert_allclose(floor(ref['points_1024x512']),p,atol=1e-8)
        old=np.asarray(geometry(ref['original_points'])['top3d'])[:,1][np.asarray(ref['kept_1based'])-1]
        np.testing.assert_allclose(np.asarray(geometry(ref['points_1024x512'])['top3d'])[:,1],old,atol=1e-8)
    eligible=d[d.common_score & d.original_quality_usable & d.original_bound_target.eq(d.target_id)]
    ranks=[]
    for tid,g in eligible.groupby('target_id'):
        r=dict(target_id=tid,image=g.image.iloc[0],records=len(g),kind=g.kind.iloc[0])
        for metric in ['B8L2','D10']:
            shift=(g[metric+'_after'].rank(method='min')-g[metric+'_before'].rank(method='min')).abs()
            r[metric+'_changed_ranks']=int(shift.gt(0).sum());r[metric+'_max_rank_shift']=shift.max()
            r[metric+'_mean_delta']=g[metric+'_delta'].mean();r[metric+'_max_abs_delta']=g[metric+'_delta'].abs().max()
        ranks.append(r)
    pd.DataFrame(ranks).to_csv(OUT/'EXISTING_ELIGIBLE_BOUND_SENSITIVITY.csv',index=False,encoding='utf-8')
    checks=dict(references=71,saved_manual_inventoried=30,manual_status=manual.adoption.value_counts().to_dict(),all_rectilinear=True,heights_preserved=True,
        paired_rows=len(d),common_scored=int(d.common_score.sum()),unscoreable_pairs=len(failures),unscoreable_states_unchanged=all(r['before_status']==r['after_status'] for r in failures),
        dir_delta_max=float(d.dir_delta.abs().max()),new_fusion=0,formal_adoptions=0)
    write('VALIDATION.json',checks);print(checks)
    render_manual(manual,lookup)


def render_manual(manual,lookup):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:data=json.load(f)
    objects={o['object_id']:o for o in data['objects']};folder=OUT/'manual_gt_review';folder.mkdir(exist_ok=True)
    links=[]
    for row in manual.to_dict('records'):
        obj=objects[row['object_id']];ref=lookup.get(row['object_id']);photo=ROOT/'data/mp3d_layout/img_v'/(row['image_id']+'.jpg')
        fig,axs=plt.subplots(1,2,figsize=(13,4.5),layout='constrained',gridspec_kw={'width_ratios':[2.3,1]})
        if photo.exists():axs[0].imshow(Image.open(photo),extent=[0,1024,512,0])
        else:axs[0].text(512,220,'此预览路径无原图，仅显示几何',ha='center')
        variants=[(obj['points_1024x512'],'#00cbbb','用户保存修订')]
        if ref:variants.append((ref['points_1024x512'],'#ff4488','用户轴最小位移候选'))
        for points,color,label in variants:
            geo=geometry(points)
            for level in ['top3d','bottom3d']:
                vertices=np.asarray(geo[level]);pixels=[]
                for start,end in zip(vertices,np.roll(vertices,-1,axis=0)):
                    pixels.extend(project_pixel(start*(1-t)+end*t,1024,512) for t in np.linspace(0,1,100))
                pixels=np.array(pixels);jumps=np.flatnonzero(abs(np.diff(pixels[:,0]))>512)+1;pixels[jumps]=np.nan
                axs[0].plot(pixels[:,0],pixels[:,1],color=color,lw=.9,label=label if level=='bottom3d' else None)
            p=floor(points);c=np.vstack([p,p[0]]);axs[1].plot(c[:,0],c[:,1],color=color,lw=1.3,marker='o',ms=2,label=label)
        for i,(x,z) in enumerate(floor(obj['points_1024x512'])):axs[1].annotate(str(i+1),(x,z),fontsize=8)
        axs[0].set_xlim(0,1024);axs[0].set_ylim(512,0);axs[0].axis('off');axs[0].legend(fontsize=7)
        axs[1].set_aspect('equal');axs[1].grid(alpha=.2);axs[1].scatter([0],[0],color='black',s=12)
        fig.suptitle(f"{row['image']} | {row['adoption']} | 原最大轴残差 {row['axis_residual_deg']:.5f}°\n"+('未正交化：保留OOS原几何' if ref is None else '仅诊断候选；保留用户环序及逐点高度，不采用MP3D形状'))
        file=folder/(row['image']+'.png');fig.savefig(file,dpi=130);plt.close(fig)
        links.append(f'<li><a href="manual_gt_review/{html.escape(file.name)}">{html.escape(row["image"])} — {html.escape(row["adoption"])}</a></li>')
    (OUT/'MANUAL_GT_REVIEW.html').write_text('<!doctype html><meta charset="utf-8"><title>30份人工修订GT复核</title><h1>30份人工修订GT：原图叠线与候选</h1><p>未改变人员原答或正式采用状态。OOS只展示原几何；其它候选不得仅因Q变化采用。</p><ul>'+''.join(links)+'</ul>',encoding='utf-8')


if __name__=='__main__':main()
