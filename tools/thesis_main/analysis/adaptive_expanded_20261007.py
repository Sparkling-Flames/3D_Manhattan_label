"""固定旧137图名单，当前输入，9度三路线扩展；不拟合新规则。"""
import json
from collections import Counter
from statistics import mean

from .adaptive_point_20261007 import adaptive_candidate, evaluate
from .point_route_panel_20261005 import build_routes
from .research_artifact_io import ROOT, write_json, write_csv, read_csv

OUT=ROOT/'analysis_results/adaptive_point_20261007/expanded'


def summarize():
    rows=read_csv(OUT/'metrics.csv');coverage=read_csv(OUT/'coverage.csv')
    plan=json.loads((OUT/'PLAN.json').read_text(encoding='utf-8'))
    old=set(plan['development_images']);summary=[];comparisons=[]
    idx={(r['image'],r['route'],r['version']):r for r in rows}
    labels={r['image']:r for r in read_csv(ROOT/'analysis_results/difficulty_full_20261007/updated/coverage.csv') if r['condition']=='manual' and r['gate']=='main_candidate'}
    oos={code for code in plan['images'] if labels[code]['scene']=='oos'}
    write_csv(OUT/'image_conditions.csv',[dict(image=code,scene=labels[code]['scene'],difficulty=labels[code]['difficulty']) for code in plan['images']])
    high={r['image'] for r in coverage if int(r['n'])>=12}
    for panel,codes in [('all',set(plan['images'])),('additional',set(plan['images'])-old),('additional_non_oos',set(plan['images'])-old-oos),('additional_non_oos_n12',(set(plan['images'])-old-oos)&high),('oos',oos)]:
        for route in plan['routes']:
            cc=[r for r in coverage if r['image'] in codes and r['route']==route]
            summary.append(dict(panel=panel,route=route,attempts=len(cc),available=sum(r['status']!='unavailable' for r in cc),
                                reasons=dict(Counter(r['reason'] for r in cc if r['status']=='unavailable'))))
            for version in sorted({r['version'] for r in rows}):
                for metric in ('D','top_mae_deg','bottom_mae_deg'):
                    pairs=[(r,idx[r['image'],'paired',version]) for r in rows if r['image'] in codes and r['route']==route and r['version']==version]
                    pairs=[(a,b) for a,b in pairs if a[metric]!='' and b[metric]!='']
                    differences=[float(a[metric])-float(b[metric]) for a,b in pairs]
                    comparisons.append(dict(panel=panel,route=route,version=version,metric=metric,common=len(pairs),
                        mean_delta=mean(differences) if differences else None,better=sum(d<-1e-10 for d in differences),
                        worse=sum(d>1e-10 for d in differences),images='|'.join(a['image'] for a,b in pairs)))
    write_json(OUT/'summary.json',summary);write_csv(OUT/'paired_comparisons.csv',comparisons)
    lines=['# 固定137图三路线扩展','',
           '当前共享x基准输入、全员MV50、固定9°；不调选择规则或按GT选门限。九图开发面板之外的128图单列；它们仍是既有资料，不是独立盲测或新人验证。', '',
           '|实现|全137图有几何候选|新增128图有几何候选|','|---|---:|---:|']
    for route in plan['routes']:
        counts=[next(r['available'] for r in summary if r['panel']==p and r['route']==route) for p in ('all','additional')]
        lines.append(f'|{route}|{counts[0]}|{counts[1]}|')
    lines+=['','## 新增128图相对绑定：原GT、共同可计算集','',
            '|实现|分项|共同图数|平均差：负值较近|改善／变差|','|---|---|---:|---:|---:|']
    for r in comparisons:
        if r['panel']=='additional' and r['version']=='original' and r['route']!='paired':
            d=f"{r['mean_delta']:+.6f}" if r['mean_delta'] is not None else 'NA'
            lines.append(f"|{r['route']}|{r['metric']}|{r['common']}|{d}|{r['better']}／{r['worse']}|")
    lines+=['','旧137图名单包含最新补标OOS：'+', '.join(sorted(oos))+'。上表是固定旧面板的方法覆盖，不解释为普通场景难度效应；paired_comparisons.csv另存additional_non_oos与oos，image_conditions.csv保留最新场景／难度。', '',
            '排除该OOS后，新增普通图共同可计算125图：自适应D相对绑定24图改善、26图变差、75图相同，平均差−0.005879；不支持普遍优势。', '',
            '另作人数≥12的新增非OOS描述：47图中46图两法共同可算，自适应17改善／16变差／13相同，平均D差−0.004982。该分层只作结果解释，不据此调参或选方法。', '',
            '几何候选不是正确率；D是参考面积归一化对称差，上下MAE为同经度角误差（度）。各比较的共同集合不同，不能横向当统一排行榜。全部失败保留在覆盖分母，原／修参考分开。新环均未认证，不从点数或面积分数裁定实体对应。', '',
            '输入、候选、来源成员、局部选择和参考分别见inputs.json、candidates.json、references.json；本轮未重算晚共享x或新增门限。', '',
            '人工复核只针对会改变方法判断的具体目标／连接；既有判断直接保留。不要要求用户认证整个候选或重复审核旧九图。', '',
            '## 本轮局部人工判断', '',
            (OUT/'USER_REVIEW.md').read_text(encoding='utf-8') if (OUT/'USER_REVIEW.md').exists() else 'uNb-26和uNb-41同属G184房间，不作两个独立房间证据。两图各18人，自适应分别新增一对；上／下／联合支持为10／10／5和9／11／6。上下分别达票，但实体目标是否相同、柜体遮挡后的下端解释是否合理，尚待用户判断。原图、来源点及新增点对见同目录两张_review.png；review_requests.json保留完整来源，不以坐标分数裁定。', '',
            '复算：python -m tools.thesis_main.analysis.adaptive_expanded_20261007。复用原算法18项测试通过；运行中核对九图共享x／9°的45份候选坐标和状态保持。未运行无关全仓测试。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def review_examples():
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    states=json.loads((OUT/'candidates.json').read_text(encoding='utf-8'))['states']
    inputs={r['image']:r for r in json.loads((OUT/'inputs.json').read_text(encoding='utf-8'))['images']}
    reviews=[]
    # Highest-N additional ordinary scenes with a changed node count; no GT selection.
    for code,fid in [('uNb9QFRL6hY-26','hybrid_006'),('uNb9QFRL6hY-41','hybrid_007')]:
        values={r['route']:r['result'] for r in states if r['image']==code}
        g=next(g for g in values['adaptive_incidence_v1']['paired_identities'] if g['feature_id']==fid)
        im=inputs[code];records={r['id']:r for r in im['records']}
        photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+im['image_id']+'.png'))).convert('RGB')
        x=g['center'][0][0];lo=max(0,x-95);hi=min(1024,x+110)
        fig,axs=plt.subplots(2,3,figsize=(15,9))
        for ax in axs.flat:
            ax.imshow(photo,extent=(0,1024,512,0));ax.set_xlim(lo,hi);ax.set_ylim(470,45);ax.axis('off')
        axs[0,0].set_title('原图局部：只判断目标，不认证坐标')
        for ax,route,title in [(axs[0,1],'paired','绑定'),(axs[0,2],'adaptive_incidence_v1','自适应')]:
            pp=np.asarray(values[route]['candidate']['points']).reshape(-1,2,2)
            for pair in pp:ax.plot(pair[:,0],pair[:,1],'-o',color='#00ffff',lw=2,ms=3)
            if route=='adaptive_incidence_v1':
                pair=np.asarray(g['center']);ax.plot(pair[:,0],pair[:,1],'-o',color='#ff3030',lw=3,ms=5)
            ax.set_title(title+'端点对（未认证连接）')
        for ax,side,col,title in [(axs[1,0],'top','#ffcf00','上端来源'),(axs[1,1],'bottom','#00ffff','下端来源'),(axs[1,2],'joint','#ff3030','共同来源原点对')]:
            for member in g[side+'_members']:
                pair=np.asarray(records[member['id']]['points']).reshape(-1,2,2)[member['pair_index']]
                if side=='joint':ax.plot(pair[:,0],pair[:,1],'-o',color=col,lw=.9,ms=3,alpha=.6)
                else:
                    q=pair[0 if side=='top' else 1];ax.scatter(*q,color=col,s=20)
            ax.set_title(title+f"：{g[side+'_support']}人")
        fig.suptitle(code+f' 18人，固定9°；红色为新增融合点对；上下支持／联合支持分别计数',fontsize=12)
        fig.tight_layout();fig.savefig(OUT/(code+'_review.png'),dpi=150);plt.close(fig)
        reviews.append(dict(image=code,group=g,window=[lo,hi],status='pending_user_target_review',
                            question='红色新增上下点对是否表达同一处应保留的实体墙角？还是上下目标不同／不应连接／无法判断？'))
    write_json(OUT/'review_requests.json',reviews)


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    OUT.mkdir(parents=True,exist_ok=True)
    old=json.loads((ROOT/'analysis_results/lee_expanded_20261003/source_input.json').read_text(encoding='utf-8'))
    image_ids={r['code']:r['image_id'] for r in old['images']}
    development=json.loads((OUT.parent/'PLAN.json').read_text(encoding='utf-8'))['images']
    data,_=project_bundle(load_current_bundle());current={r['code']:r for r in data['images']}
    routes=['paired','split_unique','bottom_anchor','top_anchor','adaptive_incidence_v1']
    plan=dict(images=[r['code'] for r in old['images']],development_images=development,routes=routes,threshold=9,
              input='Current bundle; existing 137 image roster; independent Manual main_candidate full pools',
              purpose='Fixed method expansion; no GT selection; old nine vs additional images separate; geometry availability is not correctness')
    write_json(OUT/'PLAN.json',plan)
    states=[];inputs=[]
    for i,code in enumerate(plan['images']):
        im=current[code]
        records=sorted([r for r in im['annotations'] if r['independent'] and r['consensus_eligible'] and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        assert len({r['worker'] for r in records})==len(records)>0
        values=build_routes(records,9);values['adaptive_incidence_v1']=adaptive_candidate(records,9,values)
        states.extend(dict(image=code,n=len(records),view='shared_x',threshold=9,route=route,result=values[route]) for route in routes)
        inputs.append(dict(image=code,image_id=image_ids[code],records=records))
        print(i+1,code,len(records),flush=True)
    assert len(states)==len(plan['images'])*5
    previous=json.loads((OUT.parent/'candidates.json').read_text(encoding='utf-8'))['states']
    expected={(s['image'],s['route']):s['result']['candidate'] for s in previous if s['view']=='shared_x' and s['threshold']==9}
    for s in states:
        key=s['image'],s['route']
        if key in expected:
            c=s['result']['candidate'];b=expected[key]
            assert c['points']==b['points'] and c['status']==b['status'],key
    write_json(OUT/'inputs.json',dict(images=inputs));write_json(OUT/'candidates.json',dict(states=states))
    write_json(OUT/'references.json',dict(images=[dict(image=code,references=current[code]['references']) for code in plan['images']]))
    evaluate(OUT);summarize();review_examples()
    contract=json.loads((OUT.parent/'field_contract.json').read_text(encoding='utf-8'))
    contract.update(schema='adaptive_expanded_v1',states='137 images x 5 implementations, one fixed shared_x/9deg setting',
                    inputs='inputs.json from current bundle, existing Manual main_candidate pool policy; no late_x view',
                    comparisons='paired_comparisons.csv per panel/reference/metric; common images listed; negative delta favors route over paired')
    write_json(OUT/'field_contract.json',contract)


if __name__=='__main__':run()
