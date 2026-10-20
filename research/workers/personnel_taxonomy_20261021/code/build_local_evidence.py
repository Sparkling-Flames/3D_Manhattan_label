"""New taxonomy overlays and localized opportunities from frozen annotations.

Runs after route_b/run_classification.py. All plotted target labels exclude the
entire target building. Selection uses training descriptors, never target Q.
No points, ring order, references, scores, or formal eligibility are changed.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import html
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
NAMES = {"M0":"常规或简化表达", "M1":"较多短转折表达", "S0":"常规或较少短转折终稿", "S1":"较多短转折终稿"}
COLORS = {"M0":"#ca447a", "M1":"#008ead", "S0":"#ca447a", "S1":"#008ead"}
CASES = [
    ("C01", "yqstnuAEVhm-01", "manual", "同一可见短转折：楼外类别叠加", [120,220,65,440]),
    ("C02", "pRbA3pwrgk9-12", "manual", "参考省略的真实凸起：类内仍有保留与简化", [75,220,60,425]),
    ("C03", "UwV83HsGsw3-22", "manual", "近处必要墙面转折：保留与合并", [430,610,105,445]),
    ("C04", "yqstnuAEVhm-01", "semi", "Semi独立终稿类别：不是Manual标签迁移", [120,220,65,440]),
    ("C05", "S9hNv5qa7GM-12", "manual", "已人工确认的必要窄转折：少数表达机会", [340,440,155,410]),
    ("C06", "jtcxE69GiFV-13", "manual", "浴室窄小转折：同图机会下的条件差异", [625,715,110,440]),
    ("C07", "jtcxE69GiFV-12", "manual", "门洞交界：目标范围差异单列", [410,1024,90,450]),
]
OPPORTUNITIES = [
    ("pRbA3pwrgk9-12","manual","left_projection",90,190,3,"real_detail_omitted_by_reference","已有comment_000062及本轮原图复核；GT暂停，几何表达不计正式质量"),
    ("yqstnuAEVhm-01","manual","left_short_step",140,215,3,"visible_structural_turn","已有图级评论与原图支持；窗口计数仅为表达代理"),
    ("yqstnuAEVhm-01","manual","seam_short_step",990,16,2,"visible_structural_turn","跨ERP接缝；保持处理后环序，窗口仅定位"),
    ("UwV83HsGsw3-22","manual","near_wall_step",440,600,3,"necessary_turn_reference_supported","既有M03原图解释，本轮复核近处围护墙体"),
    ("yqstnuAEVhm-01","semi","left_short_step",140,215,3,"visible_structural_turn","仅终稿表达；有精确初始化才报告编辑轨迹"),
    ("yqstnuAEVhm-01","semi","seam_short_step",990,16,2,"visible_structural_turn","仅终稿表达；不推定主动新增"),
    ("S9hNv5qa7GM-12","manual","necessary_narrow_step",360,435,3,"necessary_turn_user_confirmed","用户确认该图两处窄转折属于必要边界，GT已表达"),
    ("jtcxE69GiFV-13","manual","curtain_narrow_step",650,715,2,"reference_supported_weak_cue","既有难度实例；窗帘附近弱线索，未新增人工正确性认证"),
]

def read_json(path):
    if str(path).endswith('.gz'):
        return json.load(gzip.open(path,'rt',encoding='utf8'))
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write_json(path, data):
    # All arrays become ordinary JSON values; absent observations stay null.
    text=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)
    if str(path).endswith('.gz'):
        with gzip.open(path,'wt',encoding='utf8') as f:f.write(text)
    else:Path(path).write_text(text,encoding='utf8')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--photos',type=Path,action='append',required=True)
    ap.add_argument('--font',type=Path,required=True)
    args=ap.parse_args(); root=args.root
    try:import shapely
    except ImportError:sys.path.append('/tmp/hohonet_deps')
    spec=importlib.util.spec_from_file_location('taxonomy_case_visuals',root/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    plt=v.plt;v._configure_font(args.font)
    (HERE/'figures').mkdir(exist_ok=True);(HERE/'evidence').mkdir(exist_ok=True)
    expr=pd.read_csv(root/'research/workers/personnel_marking_patterns_20261020/record_expression.csv',low_memory=False)
    primary=set(expr.loc[expr.personal_comparison,'object_id'])
    records=read_json(root/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    records=[r for r in records if r['is_oos'] is False]
    label=pd.read_csv(HERE/'route_b/lobo_labels.csv')
    labelmap={(r['condition'],r['heldout_building'],r['worker_id']):r for r in label.to_dict('records')}
    final=pd.read_csv(HERE/'route_b/final_labels.csv')
    photomap={p.stem:p for folder in args.photos for p in folder.glob('*.png')}
    compact=[];figure_rows=[]
    keep=['object_id','worker_id','image_id','image_code','building_id','room_id','condition','origin','quality_usable','B8L2','D10','quality_use','quality_exclusion_reasons','independent_vote_eligible','cleaning_disposition','reference_id','reference_version','points_1024x512','original_points','raw_original_available','semi_evidence']
    for cid,code,cond,title,zoom in CASES:
        pool=[r for r in records if r['image_code']==code and r['condition']==cond and r['object_id'] in primary]
        first=pool[0];building=first['building_id'];image_id=first['image_id']
        ref=first['reference_evidence']; photo=np.asarray(Image.open(photomap[image_id]).convert('RGB'))
        groups={}
        for r in pool:
            lb=labelmap.get((cond,building,r['worker_id']),{})
            c=lb.get('coarse_class','unassigned')
            if c=='unassigned':continue
            groups.setdefault(c,[]).append(r)
        chosen={}
        # Up to five representative histories per class; labels and ranking use
        # no target-building observations. Full opportunity denominators below
        # retain every comparable person, independent of visualization selection.
        for c,rs in sorted(groups.items()):
            train=label[(label.condition==cond)&(label.heldout_building==building)&label.coarse_class.eq(c)].set_index('worker_id')
            cols=['turn_n_peer_delta','short_turn_edges_peer_delta']
            ctr=train[cols].mean();scale=label[(label.condition==cond)&label.heldout_building.eq(building)][cols].std().replace(0,1)
            distance=(((train[cols]-ctr)/scale)**2).sum(axis=1)
            rs=sorted(rs,key=lambda r:(float(distance.loc[r['worker_id']]),r['worker_id']))
            chosen[c]=rs[:5]
        fig=plt.figure(figsize=(14,13.2));gs=fig.add_gridspec(4,2,height_ratios=[1.0,1.45,1.35,1.45],hspace=.20,wspace=.15)
        allgeo=[v.viewer_geometry(r['points_1024x512']) for rs in chosen.values() for r in rs]
        refg=v.viewer_geometry(ref['points_1024x512']);allgeo.append(refg)
        bounds=v._bounds(allgeo);heights=v._heights(allgeo)
        for j,(c,rs) in enumerate(sorted(chosen.items())):
            color=COLORS[c]
            for row in [0,1]:
                ax=fig.add_subplot(gs[row,j]);v._erp_background(ax,photo,None if row==0 else zoom)
                v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1.2)
                for r in rs:v._erp_edges(ax,r['points_1024x512'],color,linewidth=1.05,alpha=.72,markers=True)
                if row==0:
                    ax.set_title(f'{c} {NAMES[c]} | 本图{len(groups[c])}人，展示{len(rs)}人\n'+', '.join(r['worker_id'] for r in rs),fontsize=10)
                else:ax.set_title('同一局部放大；黄色为既有参考',fontsize=9)
            ax=fig.add_subplot(gs[2,j])
            for r in rs:v._bev_ring(ax,v.viewer_geometry(r['points_1024x512'])['floor'],color,alpha=.62)
            v._bev_ring(ax,refg['floor'],'#222222',reference=True);v._style_bev(ax,bounds)
            ax.set_title('BEV；保留原处理环序',fontsize=9)
            ax=fig.add_subplot(gs[3,j],projection='3d')
            for r in rs:v._wire3d(ax,v.viewer_geometry(r['points_1024x512']),color)
            v._wire3d(ax,refg,'#222222',reference=True);v._style3d(ax,bounds,heights,{'elev':28,'azim':-54})
            ax.set_title('3D推导；相机高度=1，不是实测尺寸',fontsize=9,pad=2)
        fig.suptitle(f'{cid}  {code} / {cond}\n{title}',fontsize=15,y=.985)
        fig.text(.5,.013,'类别与选人均使用目标楼外历史。全体机会分母另表保存；此图未按本图分数或保留成功与否挑人。',ha='center',fontsize=9,color='#495769')
        fig.subplots_adjust(top=.92,bottom=.05)
        name=f'{cid}_{cond}_classes.png';fig.savefig(HERE/'figures'/name,dpi=140);plt.close(fig)
        shown=[r for rs in chosen.values() for r in rs]
        compact.append(dict(case_id=cid,image_code=code,image_id=image_id,condition=cond,building_id=building,title=title,zoom=zoom,reference=ref,
            records=[{**{k:r.get(k) for k in keep},'coarse_class_lobo':labelmap[(cond,building,r['worker_id'])]['coarse_class'],'fine_class_lobo':labelmap[(cond,building,r['worker_id'])]['fine_class']} for r in shown],
            selection='closest to own training-class mean, maximum five available persons per coarse class; no target Q or geometry selection',
            photo_release='quality-original-images-20261015',photo_member=f'images/{image_id}.png',figure=name))
        for c,rs in chosen.items():
            for r in rs:figure_rows.append(dict(case_id=cid,figure=name,worker_id=r['worker_id'],object_id=r['object_id'],condition=cond,building_id=building,coarse_class_lobo=c,fine_class_lobo=labelmap[(cond,building,r['worker_id'])]['fine_class'],quality_usable=r['quality_usable']))
    pd.DataFrame(figure_rows).to_csv(HERE/'evidence/figure_members.csv',index=False,encoding='utf-8-sig')
    write_json(HERE/'evidence/case_geometry.json.gz',compact)
    # Local expression proxies share the same declared visible opportunity.
    rows=[]
    for code,cond,feature,a,b,minimum,semantic,note in OPPORTUNITIES:
        for r in records:
            if r['image_code']!=code or r['condition']!=cond or r['object_id'] not in primary:continue
            p=np.asarray(r['points_1024x512'],float)[::2,0]%1024
            mask=(p>=a)&(p<=b) if a<=b else (p>=a)|(p<=b)
            lb=labelmap.get((cond,r['building_id'],r['worker_id']),{})
            rows.append(dict(image_code=code,building_id=r['building_id'],condition=cond,feature_id=feature,object_id=r['object_id'],worker_id=r['worker_id'],
                coarse_class_lobo=lb.get('coarse_class','unassigned'),fine_class_lobo=lb.get('fine_class','unassigned'),
                window_start=a,window_end=b,required_local_pairs=minimum,pairs_in_window=int(mask.sum()),pair_indices_1based='|'.join(map(str,np.flatnonzero(mask)+1)),
                localized_expression_proxy=bool(mask.sum()>=minimum),semantic_status=semantic,semantic_note=note,quality_usable=r['quality_usable']))
    opp=pd.DataFrame(rows);opp.to_csv(HERE/'evidence/local_opportunities.csv',index=False,encoding='utf-8-sig')
    sums=[]
    for level in ['coarse_class_lobo','fine_class_lobo']:
        g=opp.groupby(['image_code','condition','feature_id',level]).agg(
            n=('object_id','size'),n_expressed=('localized_expression_proxy','sum'),
            members=('worker_id',lambda x:'|'.join(x)),
            expressed_members=('worker_id',lambda x:'|'.join(x[opp.loc[x.index,'localized_expression_proxy']]))
        ).reset_index().rename(columns={level:'class_id'})
        g['level']=level;g['rate']=g.n_expressed/g.n;sums.append(g)
    pd.concat(sums).to_csv(HERE/'evidence/local_opportunities_by_class.csv',index=False,encoding='utf-8-sig')
    # A readable first checkpoint is created before the larger fusion experiment.
    members=pd.read_csv(HERE/'route_b/class_members_and_features.csv')
    body='<h1>HOHONET人员标法分类：阶段交付</h1><p>本版已完成独立Manual/Semi实际分类与楼外代表叠图。更大范围融合验证正在执行，阶段版不预写其结论。</p>'
    body+='<h2>实际类别和成员</h2>'+members[['condition','coarse_class','fine_class','fine_name_zh','n_people','members']].to_html(index=False,escape=True)
    body+='<h2>本版的分类含义</h2><p>用非近共线转折数与短转折边的同图同行残差建类，建筑等权。粗类优先表达保留倾向，细类表达程度；共线分段、范围与高度作为独立解释。Q与时间不参与本分类。普通历史至少12图、4栋建筑才赋类。楼外表完全排除目标建筑；全数据表只作最终描述。当前工作分类来自探索，楼外检查不是全新外部数据验证。</p>'
    body+='<h2>代表原答叠图</h2><p>ERP使用Release真实原图；BEV/3D复用既有连续坐标投影，原环序不变。每类最多显示五位在目标楼外历史最靠近该类均值、且本图有作答的成员。其余成员在机会表中保留，不按目标结果挑选。</p>'
    for c in compact:
        p=HERE/'figures'/c['figure'];data=base64.b64encode(p.read_bytes()).decode()
        body+=f'<h3>{html.escape(c["title"])} · {html.escape(c["image_code"])}</h3><img src="data:image/png;base64,{data}" alt="{c["case_id"]}">'
    body+='<h2>同一局部机会</h2><p>窗口内多点计数是局部表达代理，不能自动认定具体墙角正确。必要性来自单列的人审/原图来源，参考暂停图只用于标法解释。</p>'+pd.concat(sums).to_html(index=False,float_format=lambda x:f'{x:.3f}')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>人员标法分类阶段交付</title><style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;max-width:1150px;margin:40px auto;color:#172435;line-height:1.65;padding:0 22px}h1,h2,h3{color:#133d57}table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}td,th{border:1px solid #d5dde6;text-align:left;padding:7px;overflow-wrap:anywhere}th{background:#edf3f7}img{width:100%;height:auto}p{max-width:100ch}</style>'+body+'</html>'
    (HERE/'STAGE1_CLASSIFICATION.html').write_text(page,encoding='utf8')
    write_json(HERE/'evidence/EVIDENCE_RECEIPT.json',dict(overlays=len(compact),displayed_records=len(figure_rows),opportunity_records=len(opp),target_labels='leave_one_building_out',point_modification=False,semantic_correctness_scoring=False,staged_before_fusion=True))
    print(json.dumps({'overlays':len(compact),'displayed_records':len(figure_rows),'local_opportunities':len(opp),'stage_html':str(HERE/'STAGE1_CLASSIFICATION.html')},ensure_ascii=False))

if __name__=='__main__':main()
