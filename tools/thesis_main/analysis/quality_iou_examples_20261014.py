"""3D IoU机制示例：合成控制与冻结真人旁证分开，不拟合质量总分。"""
from pathlib import Path
import json
import shutil
import numpy as np
from shapely.geometry import Polygon
from lib.misc import post_proc

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/quality_iou_examples_20261014'
PACK=ROOT/'research/quality_pro_handoff_20261014/package'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def geometry(footprint,heights):
    return dict(bottom3d=[[x,-1.,z] for x,z in footprint],
                top3d=[[x,float(h)-1,z] for (x,z),h in zip(footprint,heights)])

def metrics(g,r):
    """Same polygon/vertex-mean prism formula as eval_layout.py; not a mesh IoU."""
    b,t=np.array(g['bottom3d']),np.array(g['top3d'])
    rb,rt=np.array(r['bottom3d']),np.array(r['top3d'])
    p,q=Polygon(b[:,[0,2]]),Polygon(rb[:,[0,2]])
    assert p.is_valid and q.is_valid and p.area>0 and q.area>0
    heights=t[:,1]-b[:,1];rh=rt[:,1]-rb[:,1]
    assert np.all(heights>0) and np.all(rh>0)
    ai=p.intersection(q).area;ha,hg=heights.mean(),rh.mean()
    inter=ai*min(ha,hg)
    return dict(iou2d=p.intersection(q).area/p.union(q).area,
                mean_height_prism_iou3d=inter/(p.area*ha+q.area*hg-inter),
                corner_mean_height_h=float(ha),height_range_h=float(np.ptp(heights)))

def official_primitives(g,r):
    # Independent ERP round trip through the author's coordinate/height functions.
    def recover(g):
        b,t=np.array(g['bottom3d']),np.array(g['top3d'])
        def erp(p):
            return np.c_[(np.arctan2(p[:,0],-p[:,2])/(2*np.pi)+.5)*1024-.5,
                         (-np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2]))/np.pi+.5)*512-.5]
        bc,tc=erp(b),erp(t)
        p=Polygon(post_proc.np_coor2xy(bc,-1.6,1024,512,floorW=1,floorH=1))
        h=abs(post_proc.get_z1(bc[:,1],tc[:,1],-1.6,512).mean()+1.6)
        return p,h
    p,h=recover(g);q,j=recover(r);v=p.intersection(q).area*min(h,j)
    return v/(p.area*h+q.area*j-v)

def controls():
    square=[[-2,-2],[2,-2],[2,2],[-2,2]];flat=geometry(square,[3]*4)
    shear=4*(1-.9)/(1+.9)
    notch=[[-2,-2],[2,-2],[2,2],[.1,2],[.1,1],[-.1,1],[-.1,2],[-2,2]]
    cases=[
      ('S01','平均高度相同，局部高度不同',flat,[('平顶',flat),('两侧倾斜',geometry(square,[2,4,4,2]))],
       '同底面、角点均高均为3h，两个均高棱柱IoU都是100%。B是连续斜平顶；在明确按此平面封顶时，真实体积IoU为11/13≈84.62%。这是均高实现的信息损失，不是任意3D IoU都看不见倾斜。'),
      ('S02','相同IoU，不同墙角规整性',flat,[('规整但略窄',geometry([[-1.8,-2],[1.8,-2],[1.8,2],[-1.8,2]],[3]*4)),('剪切成斜墙',geometry([[x+shear*z,z] for x,z in square],[3]*4))],
       '两者IoU都为90%。A墙角为90°；B偏离90°约11.89°。IoU能惩罚剪切引起的体积差，但相同分数没有表达两种错误的区别；本例不预设整体质量谁必须胜出。'),
      ('S03','小体积局部结构遗漏',geometry(notch,[3]*8),[('保留凹口',geometry(notch,[3]*8)),('省略凹口',flat)],
       '宽0.2h、深1h的凹口被填平，IoU仍为98.75%。它说明体积权重可能弱化局部结构遗漏；不说明该细节在每种任务中都应重罚。合成示意，不是真人错误。'),
      ('S04','不同目标范围：先确认任务口径',geometry([[-3,-2],[3,-2],[3,2],[-3,2]],[3]*4),[('外侧目标',geometry([[-3,-2],[3,-2],[3,2],[-3,2]],[3]*4)),('内侧目标',flat)],
       '对外侧参考，内侧IoU为66.67%；对完全相同的内侧参考则为100%。只有两个目标事先均被任务接受，才能解释为参考口径问题。不得事后挑最高IoU，也不以这个合成图认证任何真实范围。'),
      ('S05','反向对照：整体高度错误确实被识别',flat,[('正确高度3h',flat),('统一翻倍6h',geometry(square,[6]*4))],
       '同底面、平顶时，整体房高翻倍使3D IoU从100%降到50%。因此保留它作为参考体积接近度是有用的，不能声称它只衡量底面或完全不衡量高度。'),
      ('S06','排序反转：角点误差更大，IoU反而更高',flat,[('轻微整体偏高',geometry(square,[3.1]*4)),('明显两侧倾斜',geometry(square,[2,4,4,2]))],
       '同底面同参考，A四个顶部角点各错0.1h，B各错1h。角点高度RMSE为0.1h vs 1h，均高棱柱IoU却为96.77% vs 100%；按明确平面封顶的真实体积IoU为96.77% vs 84.62%。这是相对顶部定位误差与真实体积重合的排序反转，不借助拟合的新质量总分。')]
    return cases

def paper_figure():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    _,_,ref,answers,_=controls()[-1]
    shapes=[ref,answers[0][1],answers[1][1]]
    labels=['(a) Exact annotation','(b) Small uniform bias','(c) Tilted ceiling']
    true_iou=[1,3/3.1,11/13]
    fig=plt.figure(figsize=(13.5,5.1))
    rows=[]
    def xyz(g,key):
        p=np.array(g[key]);return np.c_[p[:,0],p[:,2],p[:,1]+1]
    for i,(g,label) in enumerate(zip(shapes,labels)):
        ax=fig.add_subplot(1,3,i+1,projection='3d')
        roof=xyz(g,'top3d');ax.add_collection3d(Poly3DCollection([roof],facecolors='#e39b52',alpha=.16))
        for shape,color,lw in [(g,'#d66c00',2),(ref,'#218944',1)]:
            bottom,top=xyz(shape,'bottom3d'),xyz(shape,'top3d')
            for ring,style in [(bottom,'--'),(top,'-')]:ax.plot(*np.vstack([ring,ring[:1]]).T,color=color,lw=lw,ls=style)
            for b,t in zip(bottom,top):ax.plot(*np.array([b,t]).T,color=color,lw=lw*.6)
        ax.scatter([0],[0],[1],marker='+',c='black',s=60);ax.text(0,0,1,' Camera',fontsize=8)
        ax.set(xlim=(-2.4,2.4),ylim=(-2.4,2.4),zlim=(0,4.4),xlabel='x / h',ylabel='z / h',zlabel='Height / h')
        ax.set_xticks([-2,0,2]);ax.set_yticks([-2,0,2]);ax.set_zticks([0,1,2,3,4]);ax.set_box_aspect((4.8,4.8,4.4));ax.set_proj_type('ortho');ax.view_init(elev=20,azim=35)
        m=metrics(g,ref);rmse=float(np.sqrt(np.mean((np.array(g['top3d'])[:,1]-np.array(ref['top3d'])[:,1])**2)))
        ax.set_title(label,fontsize=12,pad=12)
        fig.text(.05+i*.325,.07,f"Mean-height prism IoU: {100*m['mean_height_prism_iou3d']:.2f}%\nCorner-height RMSE: {rmse:.2f}h\nPlanar-solid IoU: {100*true_iou[i]:.2f}%",fontsize=10)
        rows.append(dict(label=label,heights_h=(np.array(g['top3d'])[:,1]+1).tolist(),corner_height_rmse_h=rmse,mean_height_prism_iou3d=m['mean_height_prism_iou3d'],planar_solid_iou3d=true_iou[i]))
    fig.suptitle('Same footprint and reference: equal scores and reversed error ordering\nGreen: reference | Orange: annotation | Synthetic geometric counterexamples',fontsize=13)
    fig.subplots_adjust(left=.02,right=.97,top=.8,bottom=.29,wspace=.12)
    for ext in ['png','pdf']:fig.savefig(OUT/f'PAPER_COUNTEREXAMPLE.{ext}',dpi=200)
    plt.close(fig)
    (OUT/'paper_counterexample.json').write_text(json.dumps(dict(schema='quality_iou_paper_counterexample_v1',source='synthetic_fixed_footprint_planar_roofs',rows=rows),indent=2)+'\n',encoding='utf-8')

def main():
    OUT.mkdir(exist_ok=True)
    cards=[];geos={}
    for cid,title,ref,answers,note in controls():
        rid=cid+':ref';geos[rid]=ref;bindings=[]
        for i,(label,g) in enumerate(answers):
            oid=cid+':'+str(i);geos[oid]=g
            bindings.append(dict(label='AB'[i]+' · '+label,object_id=oid,reference_object_id=rid,metrics=metrics(g,ref)))
        cards.append(dict(id=cid,title=title,kind='synthetic_control',bindings=bindings,note=note))
    ledger={r['record_id']:r for r in read(ROOT/'research/quality_pro_return_review_20261014/evidence/effective_use_ledger.json')['records']}
    objects=read(PACK/'data/objects.json');identities={r['object_id']:r for r in objects['objects']}
    evidence=next(q for q in read(PACK/'preparation/EVIDENCE.json')['question_groups'] if q['group']=='P01')
    bindings=[]
    for i,record in enumerate(['R02015','R00637']):
        row=ledger[record];oid=row['object_id'];rid=row['reference_object_id']
        assert identities[oid]['condition']=='manual' and row['effective_use']=='ordinary_conditional_development'
        for key in [oid,rid]:geos[key]={k:objects['geometries'][key][k] for k in ['bottom3d','top3d']}
        m=metrics(geos[oid],geos[rid]);assert abs(m['mean_height_prism_iou3d']*100-row['iou3d_pct'])<1e-8
        bindings.append(dict(label='AB'[i]+' · '+['原B01','原B02'][i],record_id=record,object_id=oid,reference_object_id=rid,image_id=row['image_id'],condition='manual',effective_use=row['effective_use'],metrics=m))
    cards.append(dict(id='P01',title='真人旁证：既有整体偏好与IoU排序相反',kind='previously_exposed_manual_development',bindings=bindings,
        note='A（原B01）IoU=61.18%，B（原B02）=70.46%。用户此前在承认A范围偏小的同时仍偏好其整体质量；这是一条既有主观排序分歧，不是客观正确率或独立验证。未修正B底点，未新增参考。',
        evidence=evidence['original_and_interpretation'],photo_overlay='../quality_candidate_review_20261014/assets/P01_2d.jpg'))
    errors=[]
    for c in cards:
        for b in c['bindings']:
            errors.append(abs(b['metrics']['mean_height_prism_iou3d']-official_primitives(geos[b['object_id']],geos[b['reference_object_id']])))
    assert max(errors)<1e-9
    data=dict(schema='quality_iou_mechanism_examples_v1',cards=cards,geometries=geos,
              validation=dict(max_official_coordinate_roundtrip_error=max(errors),official_complete_pipeline_run=False),
              metric='eval_layout.py polygon plus vertex-mean-height prism IoU; not general mesh IoU')
    (OUT/'examples.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'data.js').write_text('const CARDS='+json.dumps(cards,ensure_ascii=False)+';\nconst GEOMETRIES='+json.dumps(geos)+';\n',encoding='utf-8')
    shutil.copy2(Path(__file__).with_suffix('.html'),OUT/'EXAMPLES.html')
    shutil.copy2(Path(__file__).with_name('quality_candidate_review_20261014_3d.js'),OUT/'viewer3d.js')
    shutil.copy2(ROOT/'research/quality_targeted_feedback_20261012/dist/geometry-core.js',OUT/'geometry-core.js')
    paper_figure()
    print(json.dumps(data['validation']))
    for c in cards:print(c['id'],[round(b['metrics']['mean_height_prism_iou3d']*100,4) for b in c['bindings']])

if __name__=='__main__':main()
