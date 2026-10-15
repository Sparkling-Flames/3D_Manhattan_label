"""八张复核卡覆盖九组已讨论案例；只渲染固定几何，不调参。"""
from pathlib import Path
import json
import shutil
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/quality/quality_candidate_review_20261014'
PACK = ROOT/'research/quality/quality_pro_handoff_20261014/package'
CASES = [('P01',['R02015','R00637']),('J01',['R03346','R03347']),
         ('J04',['R03274']),('C02',['R03351','R03350']),
         ('T20_P04',['R00397','R00418']),('L01',['R01609','R02297']),
         ('Q02',['R02200','R00990']),('Q03',['R01501','R01191'])]


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def question(key, title, options):
    return dict(id=key,title=title,options=options)


COMPARE = [('A_clear','A明显更好'),('A_slight','A略好'),('close','接近，没有明确优劣'),
           ('B_slight','B略好'),('B_clear','B明显更好'),
           ('scope','目标范围不同，难以直接比较'),('uncertain','看不清／无法判断')]
SEVERITY = [('none','基本没有影响'),('minor','轻微：有偏差，但整体仍较好'),
            ('moderate','中等：问题清楚，其余部分仍有价值'),
            ('major','严重：整体几何已明显失真'),('uncertain','无法判断')]


def questions(case):
    if case=='T20_P04':
        return [question('height_A','A（T20）：只考虑高度，问题有多大？',SEVERITY),
                question('height_B','B（P04另一例）：只考虑高度，问题有多大？',SEVERITY),
                question('height_penalty','只比较高度问题，哪份应该扣得更多？',[
                    ('A_clear','A应明显多扣'),('A_slight','A应略多扣'),('close','应扣得差不多'),
                    ('B_slight','B应略多扣'),('B_clear','B应明显多扣'),
                    ('incomparable','不同图片／参考，无法作可靠比较'),('uncertain','看不清／无法判断')])]
    if case=='J04':
        return [question('floor','看照片与底面：位置、范围和形状偏差有多大？',SEVERITY),
                question('height','看两个三维视角：高度和顶部起伏问题有多大？',SEVERITY),
                question('overall','综合全部视图，这份标注属于哪种情况？',[
                    ('good','整体较好，只有轻微问题'),('local','有明显局部错误，但其余多数内容仍较好'),
                    ('widespread','多处明显错误，整体质量较差'),('unusable','整体已严重失真，难以使用'),
                    ('reference','参考／目标范围有问题，暂不能评'),('uncertain','无法判断')])]
    return [question('floor','只看照片和底面：范围、底点及墙体形状，哪份更好？',COMPARE),
            question('height','只看高度：整体高低及顶部不平，哪份问题更少？',COMPARE),
            question('overall','综合底面与高度，整体质量如何？',COMPARE)]


def render(card, geos, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    from PIL import Image
    plt.rcParams['font.family']='Microsoft YaHei'
    items=card['bindings']; n=len(items); pairs=[]
    for r in items:
        pairs.append((geos[r['reference_object_id']],geos[r['object_id']]))
    all_b=np.concatenate([np.asarray(g['bottom3d'])[:,[0,2]] for pair in pairs for g in pair]+[np.zeros((1,2))])
    lo=all_b.min(0);hi=all_b.max(0);pad=max(hi-lo)*.08
    fig,axes=plt.subplots(2,n,figsize=(8*n,9),squeeze=False,layout='constrained')
    def overlay(ax,g,color,w,h):
        for key in ('top3d','bottom3d'):
            ring=np.asarray(g[key]);p=np.concatenate([np.linspace(a,b,120) for a,b in zip(ring,np.roll(ring,-1,axis=0))])
            x=(np.arctan2(p[:,0],-p[:,2])/(2*np.pi)+.5)*w-.5
            y=(-np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2]))/np.pi+.5)*h-.5
            x[np.r_[False,np.abs(np.diff(x))>w/2]]=np.nan
            ax.plot(x,y,color=color,lw=1.6,ls='-' if key=='top3d' else '--')
    for i,(r,(ref,g)) in enumerate(zip(items,pairs)):
        photo=next((ROOT/'data/mp3d_layout'/s/'img'/f"{r['image_id']}.png" for s in ('train','valid','test') if (ROOT/'data/mp3d_layout'/s/'img'/f"{r['image_id']}.png").exists()))
        dest=out/'photos'/photo.name
        if not dest.exists():shutil.copy2(photo,dest)
        r['photo']='photos/'+photo.name
        with Image.open(photo) as im:
            w,h=im.size;axes[0,i].imshow(im);overlay(axes[0,i],ref,'#32ff75',w,h);overlay(axes[0,i],g,'#ff9933',w,h)
        axes[0,i].set_title(f"{r['label']} · {r['image_code']} · 原图叠线");axes[0,i].axis('off')
        ax=axes[1,i]
        for obj,color,label in [(ref,'#218944','参考'),(g,'#d66c00','作答')]:
            b=np.asarray(obj['bottom3d'])[:,[0,2]];ax.plot(*np.vstack([b,b[:1]]).T,color=color,lw=2,label=label)
        ax.scatter([0],[0],marker='+',s=90,c='black',label='相机');ax.annotate('相机',(0,0),xytext=(5,6),textcoords='offset points')
        ax.set(xlim=(lo[0]-pad,hi[0]+pad),ylim=(lo[1]-pad,hi[1]+pad),xlabel='水平 x / h',ylabel='水平 z / h',title=r['label']+' · 底面俯视')
        ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(fontsize=9,loc='upper right')
    fig.suptitle('绿＝参考，橙＝作答；顶部实线、底部虚线。俯视共同尺度；h为相机高度，不是米。')
    fig.savefig(out/'assets'/f"{card['id']}_2d.jpg",dpi=150);plt.close(fig)
    def xyz(p):
        p=np.asarray(p);return np.c_[p[:,0],p[:,2],p[:,1]+1]
    points=np.concatenate([xyz(g[k]) for pair in pairs for g in pair for k in ('top3d','bottom3d')]+[np.array([[0,0,1]])])
    lo=points.min(0);hi=points.max(0);span=hi-lo;pad=np.maximum(span*.06,.08)
    fig=plt.figure(figsize=(8*n,11),layout='constrained')
    for view,az in enumerate((30,120)):
        for i,(ref,g) in enumerate(pairs):
            ax=fig.add_subplot(2,n,view*n+i+1,projection='3d')
            for obj,color,label in [(ref,'#218944','参考'),(g,'#d66c00','作答')]:
                b,t=xyz(obj['bottom3d']),xyz(obj['top3d'])
                for ring,ls in [(b,'--'),(t,'-')]:ax.plot(*np.vstack([ring,ring[:1]]).T,color=color,lw=2,ls=ls,label=label if ls=='-' else None)
                for u,v in zip(b,t):ax.plot(*np.array([u,v]).T,color=color,lw=1,alpha=.6)
            ax.scatter([0],[0],[1],c='black',marker='+',s=75,label='相机');ax.text(0,0,1,' 相机',fontsize=9)
            ax.set(xlim=(lo[0]-pad[0],hi[0]+pad[0]),ylim=(lo[1]-pad[1],hi[1]+pad[1]),zlim=(lo[2]-pad[2],hi[2]+pad[2]),xlabel='水平 x / h',ylabel='水平 z / h',zlabel='离地高度 / h',title=f"{items[i]['label']} · 视角{view+1}")
            ax.set_box_aspect(span+2*pad);ax.set_proj_type('ortho');ax.view_init(elev=20,azim=az)
            for axis in (ax.xaxis,ax.yaxis,ax.zaxis):axis.set_major_locator(MaxNLocator(5))
            ax.legend(fontsize=9)
    fig.suptitle('同尺度静态三维 · 两行是相同几何的不同观察方向\n相机离地高＝1h；固定处理后几何，无修点、拉直或平顶拟合。')
    fig.savefig(out/'assets'/f"{card['id']}_3d.png",dpi=145);plt.close(fig)


def main():
    for folder in (OUT,OUT/'assets',OUT/'photos'):folder.mkdir(exist_ok=True)
    ledger=read(ROOT/'research/quality/quality_pro_return_review_20261014/evidence/effective_use_ledger.json')
    rows={r['record_id']:r for r in ledger['records']};objects=read(PACK/'data/objects.json')
    cards=[];private=[]
    for case,ids in CASES:
        selected=[rows[r] for r in ids]
        if case!='T20_P04':assert len({r['image_id'] for r in selected})==1
        card=dict(id=case,kind='height_cross_image' if case=='T20_P04' else 'single' if len(ids)==1 else 'pair',
                  title='T20 与 P04另一例 · 仅比较高度处罚' if case=='T20_P04' else case,
                  bindings=[dict(label='AB'[i],**{k:r[k] for k in ('record_id','object_id','image_id','image_code','reference_object_id')}) for i,r in enumerate(selected)],questions=questions(case))
        render(card,objects['geometries'],OUT)
        cards.append(card)
        private.append(dict(id=case,records=[{k:r[k] for k in ('record_id','source_layer','current_Q','working_Q','current_height_drop','working_height_drop','effective_use')} for r in selected]))
    (OUT/'manifest.json').write_text(json.dumps(dict(schema='quality_candidate_review_20261014_v1',cards=cards,score_blinded_initially=True,exposure='previously_reviewed_development_cases_not_independent_validation'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'score_provenance.json').write_text(json.dumps(private,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'data.js').write_text('const CARDS='+json.dumps(cards,ensure_ascii=False)+';\nconst SCORES='+json.dumps(private,ensure_ascii=False)+';\n',encoding='utf-8')
    ids={b[k] for c in cards for b in c['bindings'] for k in ('object_id','reference_object_id')}
    geometries={i:{k:objects['geometries'][i][k] for k in ('bottom3d','top3d')} for i in sorted(ids)}
    with (OUT/'data.js').open('a',encoding='utf-8') as f:f.write('const GEOMETRIES='+json.dumps(geometries)+';\n')
    shutil.copy2(ROOT/'research/quality_targeted_feedback_20261012/dist/geometry-core.js',OUT/'geometry-core.js')
    for source,target in [('quality_candidate_review_20261014.html','REVIEW.html'),('quality_candidate_review_20261014.js','app.js'),('quality_candidate_review_20261014_3d.js','viewer3d.js')]:
        shutil.copy2(Path(__file__).with_name(source),OUT/target)
    print('8张卡覆盖9组案例；15份作答；固定几何与原始参考，未改分数。')


if __name__=='__main__':main()
