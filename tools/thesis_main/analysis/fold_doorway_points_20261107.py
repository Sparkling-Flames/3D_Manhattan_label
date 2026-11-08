"""独立候选点折叠；不读取GT，不把遮挡推断点写回标注。"""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.label_studio.panorama_studio.geometry import analyze, project_pixel
from tools.label_studio.panorama_studio.build import build

WORK=ROOT/'docs/thesis_main/论文写作工作资料/门洞实景观察_20261107'
OUT=ROOT/'analysis_results/doorway_point_folding_20261107'
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
COLORS=['#087e93','#a04192','#bf7e24','#33885b']


def payload(points, flat=False):
    result={'width':2048,'height':1024,'coordinate_mode':'pixels','coordinate_convention':'continuous',
            'adoption':'research_draft_not_gt','ordered_pairs':[]}
    result['floor_point_basis']='flat_ceiling_hypothesis' if flat else 'manual_candidate_including_occlusion'
    if flat: result['assumed_ceiling_to_camera_over_camera_to_floor']=.7
    for p in points:
        top=p['top_uv'];bottom=p['floor_uv_candidate']
        if flat:
            # shortcut: 高度比暂取0.7，会影响宽高比例；精确建模需额外高度约束。
            lat=np.pi*(.5-top[1]/1024)
            bottom=[top[0],512+1024/np.pi*np.arctan(np.tan(lat)/.7)]
        result['ordered_pairs'].append({'source_pair_id':p['id'],'top':dict(zip(('x','y'),top)),
                                       'bottom':dict(zip(('x','y'),bottom))})
    return result


def show_wire(ax, geometry, title, bounds):
    f=np.asarray(geometry['raw']['floor']);c=np.asarray(geometry['raw']['ceiling'])
    for i in range(len(f)):
        j=(i+1)%len(f)
        for a,b in ((f[i],f[j]),(c[i],c[j]),(f[i],c[i])):
            ax.plot([a[0],b[0]],[-a[2],-b[2]],[a[1]+1,b[1]+1],color='#607e88',lw=1.2)
        ax.scatter(c[i,0],-c[i,2],c[i,1]+1,color=COLORS[i],s=25)
        ax.text(c[i,0],-c[i,2],c[i,1]+1.1,geometry['pairs'][i]['source_pair_id'],color=COLORS[i],fontsize=9)
    ax.scatter(0,0,1,color='#bc3b35',s=20)
    lo,hi=bounds
    ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_zlim(lo[2],hi[2])
    ax.set_box_aspect(hi-lo)
    ax.view_init(elev=25,azim=-50);ax.set_proj_type('ortho');ax.set_axis_off()
    ax.set_title(title,fontsize=12)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    bath=json.loads((WORK/'point_review/bathroom15_candidates.json').read_text(encoding='utf-8'))
    hall={'image_id':'2t7WUuJeko7_3be66dc4f0fb46449d63b07d92c74f3f',
          'points':[{'id':f'H{i+1}','top_uv':top,'floor_uv_candidate':bottom,
                     'floor_status':status} for i,(top,bottom,status) in enumerate([
              ([374,270],[374,783],'visible_plinth_near_far_door_rough_pick'),
              ([624,265],[624,757],'visible_plinth_near_far_door_rough_pick'),
              ([1404,235],[1404,796],'plinth_junction_candidate'),
              ([1703,237],[1703,815],'inferred_behind_open_door')])]}
    (OUT/'hall06_candidates.json').write_text(json.dumps(hall,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'schema_version':'panorama_studio_input_v1','selection':'候选点折叠，不是原答、GT或修订参考；两视角未配准。','cases':[]}
    audit=[]
    for number,name,case in [('15','浴室可见包络',bath),('06','走廊',hall)]:
        image_path=ROOT/'data/mp3d_layout/valid/img'/f"{case['image_id']}.png"
        spec={'image_id':case['image_id'],'title':f'{number} · {name} · 候选点',
              'category':'研究草稿：原始折叠与约束诊断分开；柜后端墙未确认',
              'image':str(image_path),'variants':[]}
        gs=[]
        for flat,title in [(False,'粗选底点（含遮挡推断）'),(True,'顶角约束的平顶候选（底点由假设推算）')]:
            data=payload(case['points'],flat)
            file=OUT/f'{number}_{"top_anchored" if flat else "rough_floor"}.json'
            file.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            g=analyze(data,compute_fit=False)
            assert g['raw']['surface_valid'],g['raw']['issues']
            for i,pair in enumerate(data['ordered_pairs']):
                for key,surface in [('top','ceiling'),('bottom','floor')]:
                    uv=project_pixel(g['raw'][surface][i],2048,1024)
                    assert np.allclose(uv,[pair[key]['x'],pair[key]['y']],atol=1e-8)
            if flat: assert np.ptp(np.array(g['raw']['ceiling'])[:,1])<1e-10
            gs.append(g)
            spec['variants'].append({'name':title,'path':str(file),'role':'research_draft'})
            audit.append({'image':number,'variant':title,'input_unchanged':True,
                          'surface_valid':True,'roundtrip_checked':True,'gt_used':False})
        manifest['cases'].append(spec)
        fig=plt.figure(figsize=(14,10))
        ax=fig.add_axes([.025,.51,.95,.43]);ax.imshow(Image.open(image_path))
        for i,p in enumerate(case['points']):
            t,b=np.asarray(p['top_uv']),np.asarray(p['floor_uv_candidate']);col=COLORS[i]
            ax.plot([t[0],b[0]],[t[1],b[1]],'--',color=col,lw=1)
            ax.scatter(*t,s=26,color=col,edgecolor='white',zorder=5)
            ax.scatter(*b,s=30,facecolor='white',edgecolor=col,zorder=5)
            ax.text(t[0]+7,t[1]-15,p['id'],color=col,fontsize=11,weight='bold',bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
        ax.axis('off')
        all_points=np.vstack([g['raw'][key] for g in gs for key in ('floor','ceiling')])
        display_points=all_points[:,[0,2,1]]*np.array([1,-1,1])+np.array([0,0,1])
        bounds=(display_points.min(axis=0),display_points.max(axis=0))
        for i,(g,title) in enumerate(zip(gs,['(a) 直接折叠粗选的上下点','(b) 固定顶角、平顶假设下的折叠'])):
            show_wire(fig.add_axes([.02+i*.49,.075,.47,.37],projection='3d'),g,title,bounds)
        fig.suptitle(f'{number} · {name}：照片选点 → 三维折叠',fontsize=18,y=.975)
        fig.text(.5,.045,'实心：顶部交界候选；空心：粗选底点；红点：相机。右图高度比是假设；同尺度显示，均未做正交吸附。',ha='center',fontsize=10,color='#566674')
        fig.savefig(WORK/f'folding_{number}.png',dpi=160,facecolor='white');plt.close(fig)
        # 模型可在Blender中直接查看，原顶点与几何一一对应。
        for suffix,g in zip(['rough_floor','top_anchored'],gs):
            vertices=np.vstack([g['raw']['floor'],g['raw']['ceiling']])
            obj=['# Research draft, relative camera-height units; +Y up; not GT']
            obj += ['v '+' '.join(f'{v:.9f}' for v in p) for p in vertices]
            n=len(g['pairs'])
            obj += [f'l {i+1} {(i+1)%n+1}' for i in range(n)]
            obj += [f'l {i+n+1} {(i+1)%n+n+1}' for i in range(n)]
            obj += [f'l {i+1} {i+n+1}' for i in range(n)]
            (OUT/f'{number}_{suffix}.obj').write_text('\n'.join(obj)+'\n',encoding='utf-8')
    result=build(manifest,OUT/'viewer')
    assert result['counts']['input_failed']==0
    # 复用的查看器提供拟合对照；页首明确拟合不是本轮采用的墙壳。
    page=OUT/'viewer/index.html';html=page.read_text(encoding='utf-8')
    html=html.replace('<main>','<main><p style="padding:12px;background:#fff3dd">本页是独立候选点草稿。左窗为直接折叠，右窗为自动正交拟合诊断，不代表确认布局。全景可展开查看点位；15的底角均受遮挡，柜后端墙未确定。两图尚未配准。</p>')
    html=html.replace('data-material="clay" class="active"','data-material="clay"').replace('data-material="wire"','class="active" data-material="wire"')
    page.write_text(html,encoding='utf-8')
    viewer_js=OUT/'viewer/studio.js';js=viewer_js.read_text(encoding='utf-8')
    for old,new in [('let materialMode="clay"','let materialMode="wire"'),
                    ('active?0xb97843:0x899481','active?0xb97843:0x486976'),
                    ('active?1:.45','active?1:.9')]:
        assert old in js,old
        js=js.replace(old,new)
    viewer_js.write_text(js,encoding='utf-8')
    (OUT/'CHECKS.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print('4 point-to-layout variants, 4 OBJ wireframes and offline viewer ready.')


if __name__=='__main__':main()
