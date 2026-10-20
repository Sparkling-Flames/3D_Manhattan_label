"""Render exact original-answer and fusion examples for the taxonomy report.

Selection of these explanatory cases is post-result and is never an effect
estimator. Every target class comes from its whole-building-out fit. Frozen
points, reference, candidate ring, votes and scores are used unchanged.
"""
from __future__ import annotations
import argparse, gzip, importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from matplotlib.ticker import MaxNLocator

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[2]
PINK='#c63777'; BLUE='#078ba5'; INK='#263646'; GRAY='#818b96'

def read(p):
    return json.load(gzip.open(p,'rt')) if str(p).endswith('.gz') else json.loads(Path(p).read_text())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--photos',type=Path,action='append',required=True);ap.add_argument('--font',type=Path,required=True)
    args=ap.parse_args();sys.path.append('/tmp/hohonet_deps')
    spec=importlib.util.spec_from_file_location('taxonomy_visuals',args.root/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);v._configure_font(args.font);plt=v.plt
    photos={p.stem:p for d in args.photos for p in d.glob('*.png')}
    records=read(args.root/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    expr=pd.read_csv(args.root/'research/workers/personnel_marking_patterns_20261020/record_expression.csv',low_memory=False)
    valid=set(expr.loc[expr.personal_comparison,'object_id']);records=[r for r in records if r['object_id'] in valid]
    byid={r['object_id']:r for r in records}
    bl=pd.read_csv(HERE/'route_b/lobo_labels.csv');bm={(r.condition,r.heldout_building,r.worker_id):r for r in bl.itertuples()}
    pl=pd.read_csv(HERE/'route_b/semi_new_candidate/lobo_labels.csv');pl=pl[pl.candidate.eq('semi_position_scale')]
    pm={(r.heldout_building,r.worker_id):r.class_id for r in pl.itertuples()}
    extras=[]

    def compact_3d_ticks(ax):
        ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.yaxis.set_major_locator(MaxNLocator(3))
        ax.zaxis.set_major_locator(MaxNLocator(3))

    def savefig(fig,name):
        fig.savefig(HERE/'figures'/name,dpi=145,facecolor='white');plt.close(fig)

    def raw_panel(name,code,cond,title,groups,zoom=None,footnote=''):
        pool=[r for r in records if r['image_code']==code and r['condition']==cond]
        rr={r['worker_id']:r for r in pool};first=pool[0]
        ref=first['reference_evidence'];photo=np.asarray(Image.open(photos[first['image_id']]).convert('RGB'))
        selected=[rr[w] for _,workers in groups for w in workers]
        geos=[v.viewer_geometry(r['points_1024x512']) for r in selected];refg=v.viewer_geometry(ref['points_1024x512'])
        bounds=v._bounds(geos+[refg]);heights=v._heights(geos+[refg])
        rows=4 if zoom else 3;fig=plt.figure(figsize=(13,12 if zoom else 10))
        gs=fig.add_gridspec(rows,2,hspace=.24,wspace=.14,height_ratios=([1,1.15,1.2,1.4] if zoom else [1,1.3,1.5]))
        for j,(label,workers) in enumerate(groups):
            color=[PINK,BLUE][j];rs=[rr[w] for w in workers]
            for i in range(2 if zoom else 1):
                ax=fig.add_subplot(gs[i,j]);v._erp_background(ax,photo,zoom if i==1 else None)
                v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1)
                for r in rs:v._erp_edges(ax,r['points_1024x512'],color,alpha=.85,linewidth=1.2,markers=True)
                if i==0:
                    qs=' / '.join(f"{r['worker_id']} Q={r['B8L2']:.1f}" if r.get('B8L2') is not None else f"{r['worker_id']} Q暂停" for r in rs)
                    ax.set_title(label+'\n'+qs,fontsize=10)
                else:ax.set_title('同一可见结构放大',fontsize=9)
            i=2 if zoom else 1
            ax=fig.add_subplot(gs[i,j]);v._bev_ring(ax,refg['floor'],INK,reference=True)
            for r in rs:v._bev_ring(ax,v.viewer_geometry(r['points_1024x512'])['floor'],color,alpha=.85)
            v._style_bev(ax,bounds);ax.set_title('BEV：同一坐标尺度',fontsize=9)
            ax=fig.add_subplot(gs[i+1,j],projection='3d');v._wire3d(ax,refg,INK,reference=True)
            for r in rs:v._wire3d(ax,v.viewer_geometry(r['points_1024x512']),color)
            v._style3d(ax,bounds,heights,{'elev':26,'azim':-54});compact_3d_ticks(ax);ax.set_title('3D：相机高度=1',fontsize=9,pad=2)
        fig.suptitle(title+'\n'+code+' / '+cond,fontsize=15,y=.985)
        fig.text(.5,.018,footnote+'\n黄色ERP／黑色虚线BEV为既有参考；类别为目标楼外标签。案例为结果后解释性选取。',ha='center',fontsize=9,color=INK)
        fig.subplots_adjust(top=.90,bottom=.085);savefig(fig,name)
        extras.append({'figure':name,'image_code':code,'image_id':first['image_id'],'condition':cond,'title':title,'selection':'post_result_explanatory','groups':groups,'reference':ref,'records':[{k:r.get(k) for k in ['object_id','worker_id','origin','quality_usable','independent_vote_eligible','B8L2','D10','points_1024x512','reference_id']} for r in selected]})

    raw_panel('C08_A2_positive.png','7y3sRwLe3Va-21','manual','A2正例：相同6角对、同来源、相近Q，布局仍分成两组',
        [('A2-A02：W109 / W118',['W109','W118']),('A2-A03：W132 / W133',['W132','W133'])],
        footnote='展示两对类内绑定角距5.90°、8.93°；跨组52.54°–58.44°。本图不另行裁定目标范围。')
    raw_panel('C09_A2_counterexample.png','jtcxE69GiFV-28','manual','A2反例：同类成员在本图仍可采用明显不同布局',
        [('A2-A02：W107 / W125',['W107','W125']),('A2-A03：W117 / W133',['W117','W133'])],
        footnote='四人均6角对、同为新来源；本图类内分散度高于类间，不能把总体关系解释为逐图保证。')
    raw_panel('C10_Semi_height.png','7y3sRwLe3Va-13','semi','Semi独立几何类别：较低推导高度，拆开看顶部与底部',
        [('SP_L：W030（旧） / W119（新）',['W030','W119']),('SP_T：W013（旧） / W123（新）',['W013','W123'])],
        footnote='四人均4角对；W030/W013范围接近而推导高度有差别。推导高度不等于实测房高。')
    raw_panel('C11_Semi_height_counterexample.png','B6ByNegPMKs-18','semi','Semi类内反例：SP_L成员并非每图都产生较低高度',
        [('SP_L：W029 / W035',['W029','W035']),('SP_T：W002 / W013',['W002','W013'])],
        footnote='W029推导高度较低；同组W035在本图与两名常规成员相近。')
    raw_panel('C12_redundancy.png','B6ByNegPMKs-18','manual','辅助机制：总点数必须拆开实际转折与近共线分段',
        [('W037：重复近共线分段线索',['W037']),('W130：对照标注',['W130'])],
        footnote='材质／玻璃分隔处的近共线点不自动代表新的墙体转角；行为观察保留既有资格。')

    mechanisms=read(HERE/'fusion/MECHANISM_CASES.json.gz')
    def team_panel(case,name,panels,title,zoom=None,note=''):
        c=mechanisms[case];ts={t['panel']:t for t in c['teams']};ts=[ts[k] for k in panels]
        ref=c['reference'];refg=v.viewer_geometry(ref['points_1024x512']);photo=np.asarray(Image.open(photos[c['pool_meta']['image_id']]).convert('RGB'))
        geos=[v.viewer_geometry(t['geometry']['points'],t['geometry']['footprint']) for t in ts]
        bounds=v._bounds(geos+[refg]);heights=v._heights(geos+[refg]);ncol=len(ts)
        fig=plt.figure(figsize=(6*ncol,11));gs=fig.add_gridspec(3,ncol,hspace=.22,wspace=.12,height_ratios=[1,1.2,1.35])
        for j,(t,g) in enumerate(zip(ts,geos)):
            color=[PINK,BLUE,'#ac720d','#505dae'][j]
            ax=fig.add_subplot(gs[0,j]);v._erp_background(ax,photo,zoom)
            v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1.0)
            v._erp_edges(ax,t['geometry']['points'],color,linewidth=1.9,markers=True)
            composition=' + '.join(f'{num}位{cl}' for cl,num in t['coarse_counts'].items())
            prefix=('加入'+t['panel']) if case=='JTC26_same_fine_class_third_vote' else t['panel']
            ax.set_title(f"{prefix} | 团队Q={t['B8L2']:.2f}\n{t['nodes']}节点，{t['minimum_support']}票门槛；{composition}",fontsize=11)
            if case=='JTC26_same_fine_class_third_vote':
                grp=next(gp for gp in t['full_state']['identity_groups'] if gp['feature_id']=='node_004')
                pp=np.asarray(grp['center']);ax.scatter(pp[:,0],pp[:,1],s=65,facecolors='none',edgecolors='#ffef36',linewidths=2,zorder=9)
                ax.annotate(f"关键节点：{grp['support']} / 3票",pp.mean(axis=0),xytext=(-80,15),textcoords='offset points',fontsize=10,color='white',bbox={'facecolor':'#273544','alpha':.9,'pad':4})
            ax=fig.add_subplot(gs[1,j]);v._bev_ring(ax,refg['floor'],INK,reference=True);v._bev_ring(ax,g['floor'],color,linewidth=2);v._style_bev(ax,bounds)
            ax.set_title('融合BEV；虚线为既有参考',fontsize=10)
            ax=fig.add_subplot(gs[2,j],projection='3d');v._wire3d(ax,refg,INK,reference=True);v._wire3d(ax,g,color);v._style3d(ax,bounds,heights,{'elev':28,'azim':-54});compact_3d_ticks(ax)
            ax.set_title('融合3D；相机高度=1',fontsize=10,pad=2)
        fig.suptitle(title+'\n'+c['pool_meta']['image'],fontsize=16,y=.984)
        fig.text(.5,.02,note+'\n原始候选几何与节点票账均来自本轮冻结合同复算；展示前缀不充当总体效应估计。',ha='center',fontsize=10,color=INK)
        fig.subplots_adjust(top=.88,bottom=.09);savefig(fig,name)
    team_panel('JTC26_same_fine_class_third_vote','C13_jtc26_third_vote.png',['W113','W106'],'同类换人：个人Q下降，关键第三票使团队几何改善',note='固定W103、W104、W116、W128。W113个人Q39.55；W106个人Q10.30。两人B同为M01，A2同为A01。')
    team_panel('Uw22_complement_and_dilution','C14_Uw22_threshold.png',['C_n8','C_n9','C_n10'],'类别补充随人数变化：4票保留 → 5票门槛失选 → 新支持恢复',zoom=[420,630,75,460],note='n8：5M0+3M1；加M0 W116到n9，旧观察分组未变，必要节点因门槛升高失选；n10加M1 W112恢复。')
    team_panel('Semi_wc56_extra_nodes','C15_Semi_extra_nodes.png',['B_n12','C_n12','C_n13'],'Semi反例：较多结构终稿成员带来额外节点与质量下降',note='同背景n12换入两名S1后5节点变8节点；n13门槛从6升7后回到5节点。额外节点不自动有益。')
    # Complete predeclared path, not just favorable prefixes.
    c=mechanisms['Uw22_complement_and_dilution']
    steps=pd.read_csv(HERE/'fusion/NESTED_EVENTS.csv')
    # NESTED_TEAMS and requests are retained for exact member-level reproduction;
    # plotting uses the event table only if a matching path is available.
    if 'path_id' in steps:
        s=steps[steps.path_id.eq(c['path']['path_id'])].sort_values('n')
        cols=list(s.columns)
        extras.append({'complete_path_id':c['path']['path_id'],'event_rows':len(s),'event_columns':cols})
        fig,axs=plt.subplots(2,1,figsize=(12,7.2),sharex=True,gridspec_kw={'height_ratios':[1.4,1]})
        for arm,color,label in [('A',GRAY,'A 原类别块'),('B',PINK,'B 同类换人'),('C',BLUE,'C 换入M1类别块')]:
            axs[0].plot(s.n,s[arm+'_B8L2'],marker='o',ms=3.8,color=color,label=label)
            axs[1].plot(s.n,s[arm+'_nodes'],marker='o',ms=3.8,color=color,label=label)
        axs[1].step(s.n,s.C_minimum_support,where='mid',linestyle='--',color=INK,label='所需支持票数')
        axs[0].set_ylabel('B8L2质量分');axs[1].set_ylabel('节点数／门槛票数');axs[1].set_xlabel('团队人数 n；固定替换块 m=2，共同背景按冻结顺序增长')
        for ax in axs:
            ax.grid(color='#e5e9ef');ax.spines[['top','right']].set_visible(False);ax.legend(loc='best',fontsize=9,ncol=2)
        axs[1].set_xticks(s.n);axs[0].set_ylim(0,105)
        fig.suptitle('Uw-22完整人数路径：补充、失选、恢复与后续稀释',fontsize=16)
        fig.text(.5,.015,'同一路径三臂在每个n都有相同背景；成员顺序及全部前缀保存于NESTED_REQUESTS / NESTED_EVENTS。',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.04,1,.95));savefig(fig,'C16_complete_size_path.png')
    with gzip.open(HERE/'evidence/additional_case_geometry.json.gz','wt') as f:json.dump(extras,f,ensure_ascii=False)
    # Correct the phase wording: labels were saved before the large validation;
    # representative overlays were made while the validation ran in parallel.
    receipt=read(HERE/'evidence/EVIDENCE_RECEIPT.json');receipt.pop('staged_before_fusion',None)
    receipt.update(labels_frozen_before_main_fusion=True,overlays_created_while_validation_running=True,additional_figures=9)
    (HERE/'evidence/EVIDENCE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps({'additional_figures':9,'raw_cases':len([x for x in extras if 'figure' in x]),'points_changed':False},ensure_ascii=False))

if __name__=='__main__':main()
