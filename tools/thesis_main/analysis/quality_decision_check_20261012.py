"""16个既有参考上的定向复核与两对真实判别材料，不调参。"""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path

if __package__:
    from .quality_top_height_response_20261012 import profile_moments,read_json,save_json,validate_development_gates
    from .quality_local_profile_20261012 import exact_same_floor_centered
    from .quality_joint_response_20261012 import configurations,terms,spherical_sym_distance,flatness
else:
    from quality_top_height_response_20261012 import profile_moments,read_json,save_json,validate_development_gates
    from quality_local_profile_20261012 import exact_same_floor_centered
    from quality_joint_response_20261012 import configurations,terms,spherical_sym_distance,flatness
from audit_geometry import direction_axis,direction_residual


def perturb_reference(g,ratio,local,phase):
    mu=profile_moments(g)['mean']
    unit=deepcopy(g)
    for i,(b,t) in enumerate(zip(unit['bottom3d'],unit['top3d'])): t[1]=b[1]+2+(-1)**i
    p=profile_moments(unit)
    a=deepcopy(g)
    for t,h in zip(a['top3d'],p['heights']):
        t[1]+=(ratio-1)*mu+phase*(h-p['mean'])/p['std']*local*mu
    return a


def run(inputs,protocol,previous,design):
    validate_development_gates([dict(record_id=r['id']) for r in inputs['rows']],inputs['gates'])
    configs=configurations(inputs,protocol)
    refs={r['reference_object_id']:r for r in inputs['rows'] if r['applicability_confirmed']}
    controls,comparisons,reference_rows,errors,score_errors=[],[],[],[],[]
    for rid,row in sorted(refs.items()):
        g=inputs['geometries'][rid];mu=profile_moments(g)['mean']
        reference_rows.append(dict(reference_object_id=rid,image_id=row['image_id'],image_code=row['image_code'],building_id=row['building_id'],mean=mu,corners=len(g['top3d'])))
        d=direction_residual(g,direction_axis(g))
        for path,states in design['paths'].items():
            for phase in [-1,1]:
                case=[]
                for step,(ratio,local) in enumerate(states):
                    a=perturb_reference(g,ratio,local,phase)
                    minimum=min(p[1] for geo in (a,g) for p in geo['top3d'])
                    hc=exact_same_floor_centered(a,g);errors.append(abs(hc-local))
                    c=dict(id=f'{row["image_code"]}_{path}_{phase}_{step}',reference_object_id=rid,path=path,phase=phase,ratio=ratio,local=local,
                           minimum_top_y=minimum,status='available' if minimum>0 else 'out_of_camera_domain',effects=None,high_scores=None)
                    if minimum>0:
                        m=dict(iou_2d=1.,dir=d,flat=flatness(a,n=512)['flat'],Hmean=abs(profile_moments(a)['mean']/mu-1),Hcenter=hc,
                               height_mean_ratio=profile_moments(a)['mean']/mu,S_bottom_deg=0.,S_top_deg=float(spherical_sym_distance(a['top3d'],g['top3d'],n=2048)))
                        high=dict(m,flat=flatness(a,n=2048)['flat'],S_top_deg=float(spherical_sym_distance(a['top3d'],g['top3d'],n=8192)))
                        c.update(metrics=m,effects={n:terms(m,conf)['score'] for n,conf in configs.items()},high_scores={n:terms(high,conf)['score'] for n,conf in configs.items()})
                        score_errors.extend(abs(c['effects'][n]-c['high_scores'][n]) for n in configs)
                    controls.append(c);case.append(c)
                available=all(c['status']=='available' for c in case)
                comparisons.append(dict(reference_object_id=rid,image_code=row['image_code'],path=path,phase=phase,status='available' if available else 'out_of_camera_domain',
                                        before=case[0]['id'],after=case[1]['id'],delta={n:case[1]['effects'][n]-case[0]['effects'][n] for n in configs} if available else None,
                                        high_delta={n:case[1]['high_scores'][n]-case[0]['high_scores'][n] for n in configs} if available else None))
    valid=[p for p in comparisons if p['status']=='available']
    summary={n:dict(increases=sum(p['delta'][n]>1e-8 for p in valid),
                    increased_reference_count=len({p['reference_object_id'] for p in valid if p['delta'][n]>1e-8}),
                    high_increases=sum(p['high_delta'][n]>1e-8 for p in valid),
                    maximum_increase=max([0]+[p['delta'][n] for p in valid])) for n in configs}
    by_id={r['id']:r for r in inputs['rows']};review=[]
    for pair in design['review_pairs']:
        rows=[by_id[pair[k]] for k in ('A','B')]
        assert rows[0]['image_id']==rows[1]['image_id'] and rows[0]['reference_object_id']==rows[1]['reference_object_id']
        assert all(r['applicability_confirmed'] and r['id'] not in previous['reviewed_terms'] for r in rows)
        review.append(dict(id=pair['id'],records=rows,answer=None,confidence=None,
                           image_in_previous_review_material=any(r['metadata'].get('image_id')==rows[0]['image_id'] for table in inputs['previous_review']['tables'].values() for r in table if 'metadata' in r),
                           question='仅比较顶部边界/高度表现：A较好、B较好、近似，还是无法判断？差异是否明显？哪些可见位置支持判断？',
                           scope='已处理几何，不认证原始上下点语义对应；不是独立留出；不展示候选分数'))
    return dict(schema='quality_decision_check_results_v1',references=reference_rows,controls=controls,comparisons=comparisons,
                comparison_count=len(comparisons),available_comparisons=len(valid),summary=summary,review_pairs=review,
                verification=dict(maximum_Hcenter_target_error=max(errors),maximum_score_resolution_change=max(score_errors)),
                stopping_rule='定向复核到此停止，不扩参数网格；转少量真实判别，不由控制推断人工等级')


def render_3d_reviews(inputs,out,study):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams['font.family']='Microsoft YaHei'
    for pair in out['review_pairs']:
        rows=pair['records']
        g=inputs['geometries'][rows[0]['reference_object_id']]
        geos=[inputs['geometries'][r['object_id']] for r in rows]
        def xyz(points):
            p=np.asarray(points)
            return np.column_stack([p[:,0],p[:,2],p[:,1]+1])
        all_points=np.concatenate([xyz(geo[k]) for geo in [g]+geos for k in ('top3d','bottom3d')])
        lo=all_points.min(0);hi=all_points.max(0);extent=hi-lo;pad=extent*.06
        fig=plt.figure(figsize=(14,10),layout='constrained')
        for view,azimuth in enumerate((30,120)):
            for i,a in enumerate(geos):
                ax=fig.add_subplot(2,2,view*2+i+1,projection='3d')
                for geo,color,label in [(g,'#218944','参考'),(a,'#d66c00','作答')]:
                    b,t=xyz(geo['bottom3d']),xyz(geo['top3d'])
                    for ring,style in [(b,'--'),(t,'-')]:
                        closed=np.vstack([ring,ring[:1]])
                        ax.plot(*closed.T,color=color,ls=style,lw=2,label=label if style=='-' else None)
                    for u,v in zip(b,t): ax.plot(*np.vstack([u,v]).T,color=color,alpha=.5,lw=.8)
                ax.scatter([0],[0],[1],marker='+',color='black',label='相机')
                ax.set(xlim=(lo[0]-pad[0],hi[0]+pad[0]),ylim=(lo[1]-pad[1],hi[1]+pad[1]),zlim=(lo[2]-pad[2],hi[2]+pad[2]),
                       xlabel='水平 x',ylabel='水平 z',zlabel='离底面高度',title=f'{pair["id"]} — {"AB"[i]} / 视角 {view+1}')
                ax.set_box_aspect(extent+2*pad);ax.set_proj_type('ortho');ax.view_init(elev=20,azim=azimuth);ax.legend(fontsize=9)
        fig.suptitle('同尺度三维声明几何：绿=参考，橙=作答；相机离底面高=1，非米制。两行是同一对象的不同视角。')
        fig.savefig(study/'review_assets'/f'{pair["id"]}_3d.png',dpi=140);plt.close(fig)


def render_reviews(inputs,out,study):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image
    root=Path(__file__).resolve().parents[3]
    plt.rcParams['font.family']='Microsoft YaHei'
    asset=study/'review_assets';asset.mkdir(exist_ok=True)
    for pair in out['review_pairs']:
        rows=pair['records'];image_id=rows[0]['image_id']
        paths=[root/'data/mp3d_layout'/split/'img'/f'{image_id}.png' for split in ('train','valid','test')]
        photo=next(p for p in paths if p.exists())
        pair['photo_source']=photo.relative_to(root).as_posix()
        img=Image.open(photo);w,h=img.size
        fig,axes=plt.subplots(2,2,figsize=(15,9),gridspec_kw={'height_ratios':[1,1]},layout='constrained')
        g=inputs['geometries'][rows[0]['reference_object_id']]
        def overlay(ax,geo,color):
            for key in ('top3d','bottom3d'):
                ring=np.asarray(geo[key]);points=np.concatenate([np.linspace(a,b,100) for a,b in zip(ring,np.roll(ring,-1,axis=0))])
                x=(np.arctan2(points[:,0],-points[:,2])/(2*np.pi)+.5)*w-.5
                y=(-np.arctan2(points[:,1],np.hypot(points[:,0],points[:,2]))/np.pi+.5)*h-.5
                jumps=np.r_[False,np.abs(np.diff(x))>w/2];x[jumps]=np.nan;y[jumps]=np.nan
                ax.plot(x,y,color=color,lw=1.5,ls='-' if key=='top3d' else '--')
        geos=[inputs['geometries'][r['object_id']] for r in rows]
        all_b=np.concatenate([np.asarray(geo['bottom3d'])[:,[0,2]] for geo in [g]+geos]);lo=all_b.min(0);hi=all_b.max(0);pad=max(hi-lo)*.12
        for i,a in enumerate(geos):
            ax=axes[0,i];ax.imshow(img);overlay(ax,g,'#32ff75');overlay(ax,a,'#ff9933')
            ax.set(title=f'{pair["id"]} — {"AB"[i]}：顶部实线 / 底部虚线',xlim=(0,w),ylim=(h,0));ax.axis('off')
            for geo,color,label in [(g,'#218944','参考'),(a,'#d66c00','作答')]:
                b=np.asarray(geo['bottom3d'])[:,[0,2]];b=np.vstack([b,b[:1]])
                axes[1,i].plot(b[:,0],b[:,1],color=color,label=label)
            axes[1,i].scatter([0],[0],c='black',marker='+',label='相机');axes[1,i].set_aspect('equal')
            axes[1,i].set(xlim=(lo[0]-pad,hi[0]+pad),ylim=(lo[1]-pad,hi[1]+pad));axes[1,i].legend(fontsize=8)
        fig.suptitle('绿色：现有参考；橙色：处理后作答。下排底面同尺度；观察声明几何，不推断原始点对正确。',fontsize=12)
        fig.savefig(asset/f'{pair["id"]}.jpg',dpi=120);plt.close(fig)
    render_3d_reviews(inputs,out,study)
    cards=''.join(f'<section><h2>{p["id"]}</h2><p>{p["question"]}</p><a href="review_assets/{p["id"]}.jpg"><img src="review_assets/{p["id"]}.jpg"></a><h3>同尺度三维对照</h3><a href="review_assets/{p["id"]}_3d.png"><img src="review_assets/{p["id"]}_3d.png"></a><p>三维为处理后声明几何，非房间实测；绿色参考也可能有误。请区分底面、二维顶部投影和三维高度判断。</p><p>答复格式：{p["id"]}：A / B / 近似 / 无法判断；差异：不明显 / 明显 / 不确定；位置与理由。</p></section>' for p in out['review_pairs'])
    (study/'REVIEW_PAIRS.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>质量研究：待判别材料</title><style>body{max-width:1450px;margin:30px auto;padding:20px;font:17px/1.65 sans-serif;background:#f5f5f3}section{background:white;padding:20px;margin:30px 0}img{width:100%}h1{font-size:26px}</style><h1>真实作答：整体偏差与局部不平的取舍</h1><p>人工回执按题目及观察视图另行保存；未展示候选分数，也没有预设正确答案。请按各题说明比较，近似或无法判断均为有效回答。绿色参考不是不可质疑的真值；如参考不可信请直接指出。这是既有开发图片，不是独立验证。图片是原照片上的声明几何投影，不推断边界可见性。</p>'+cards+'</html>',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,default=Path('research/quality_top_height_response_20261012'));p.add_argument('--reviews',action='store_true');args=p.parse_args();s=args.study
    inputs=read_json(s/'inputs.json');out=run(inputs,read_json(s/'protocol.json'),read_json(s/'results.json'),read_json(s/'decision_check_design.json'))
    if args.reviews: render_reviews(inputs,out,s)
    save_json(s/'decision_check.json',out);save_json(s/'review_pairs.json',dict(schema='quality_review_pairs_v1',pairs=out['review_pairs']))
    print(out['available_comparisons'],out['verification']);print(out['summary'])


if __name__=='__main__': main()
