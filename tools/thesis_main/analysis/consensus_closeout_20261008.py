"""两个收尾问题的定向图件：旧排序的新节点复核、未达票节点来源。"""
import json
from .consensus_delivery_20261008 import OUT,POP,read
from .research_artifact_io import ROOT,write_json
from .direct_fusion_20261007 import draw_layout


def run():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    target=OUT/'closeout';target.mkdir(exist_ok=True)
    inputs={r['image']:r for r in read(POP/'inputs.json')['images']}
    outputs={r['image']:r for r in read(OUT/'outputs.json')}
    def axes(code,rows,cols):
        im=inputs[code];photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+im['image_id']+'.png')))
        fig,axs=plt.subplots(rows,cols,figsize=(20,5*rows),squeeze=False)
        for ax in axs.flat:ax.imshow(photo,extent=(0,1024,512,0));ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        return fig,list(axs.flat)
    def labeled(ax,points,labels,color='#ed145b'):
        draw_layout(ax,points,color)
        for p,label in zip(points[::2],labels):
            ax.text(p[0],p[1]-7,label,color='black',fontsize=10,bbox=dict(facecolor='white',alpha=.9,edgecolor=color))
    code='rPc6DW4iMge-06';obj=next(o for o in read(OUT/'order_workbench/sources.json')['objects'] if o['object_id']=='fusion:'+code)
    submitted=read(OUT/'order_workbench/user_order_review_20261008.json')['records']['fusion:'+code]['order']
    ids=[obj['feature_ids'][i] for i in submitted]
    mapped=['review_rpc_individual_targets_ABC_0' if fid=='node_015' else fid for fid in ids]
    nodes=outputs[code]['node_consensus']['nodes'];byid={n['feature_id']:n for n in nodes}
    confirmed_x=outputs[code]['candidate']['order_status']=='user_requested_x_sort'
    if confirmed_x:mapped=[n['feature_id'] for n in sorted(nodes,key=lambda n:n['points'][0][0])]
    points=[p for fid in mapped for p in byid[fid]['points']]
    legacy={fid:i+1 for i,fid in enumerate(obj['feature_ids'])}
    legacy['review_rpc_individual_targets_ABC_0']=legacy['node_015']
    labels=[str(i+1) for i in submitted]
    fig,axs=axes(code,1,2)
    labeled(axs[0],[p for i in submitted for p in obj['points'][2*i:2*i+2]],labels)
    labeled(axs[1],points,[str(i+1) for i in range(len(mapped))] if confirmed_x else [str(legacy[fid]) for fid in mapped])
    axs[0].set_title('已确认的旧快照 · 编号沿旧工作台')
    axs[1].set_title('最新：依用户指定按x递增（已确认）' if confirmed_x else '更新A18人中心后 · 沿用同一节点排列的待确认预览')
    fig.tight_layout();fig.savefig(target/'rpc_order_refresh.png',dpi=120);plt.close(fig)
    proposal=dict(image=code,manual_order=mapped,points=points,confirmed_by_user=confirmed_x,
                  note='User explicitly accepted x-ascending order.' if confirmed_x else 'Old node_015 maps to reviewed A18 identity; proposal only, not accepted automatically.')
    write_json(target/'rpc_order_proposal.json',proposal)
    # Keep the group labels used in the user's review; current outcome is explained below.
    code='UwV83HsGsw3-09';package=read(OUT/(code+'.json'));state=package['automatic']
    groups=state['identity_groups'];lookup={(m['id'],m['pair_index']):g for g in groups for m in g['members']}
    fig,axs=axes(code,3,2)
    r=outputs[code];labeled(axs[0],r['candidate']['points'],['输出'+str(i+1) for i in range(3)])
    axs[0].set_title('当前3节点 · 支持18/24、23/24、24/24 · 完整多数布局未形成')
    for g in groups:
        x,y=g['center'][0];color='#d31356' if g['selected'] else '#005bdd'
        draw_layout(axs[1],g['center'],color,closed=False)
        axs[1].text(x,y-8,g['feature_id'].replace('node_','G')+':'+str(g['support']),fontsize=8,color=color,bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
    axs[1].set_title('人审时的候选组号（两次合并前） · 门槛12人')
    for ax,worker in zip(axs[2:],['P004','P001','P019','P023']):
        rec=next(r for r in inputs[code]['records'] if r['worker']==worker)
        labeled(ax,rec['points'],[lookup[rec['id'],k]['feature_id'].replace('node_','G') for k in range(len(rec['points'])//2)],'#0068df')
        ax.set_title(worker+' / '+rec['id']+' 原答 · 按来源环，编号为算法组')
    fig.tight_layout();fig.savefig(target/'uw_missing_nodes.png',dpi=120);plt.close(fig)
    write_json(target/'uw_groups.json',dict(image=code,n=24,threshold=12,groups=groups,
        note='Pre-followup group labels used in the review. G002+G008 and G003+G009 were later merged to 3 votes each; current groups are in the parent image JSON. G001/G011/G010 are separately present in P023.'))
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>融合收尾两项复核</title>
<style>body{font:17px system-ui;max-width:1600px;margin:24px auto;padding:12px}img{width:100%}textarea{width:95%;min-height:80px}button,select{font:inherit;padding:12px}section{border-bottom:1px solid #aaa;padding:18px 0}</style>
<h1>只剩这两项新反馈需处理</h1><p>此前排序原件和35图工作台不改。这页不会改票数或自动补点；可保存不确定。</p>
<section><h2>1. rPc：新版位置，旧排列还能否沿用？</h2><p>左侧是你已确认的旧快照。右侧仅把旧9号换成A类18人的融合中心；请确认这个连接顺序仍可用。编号沿旧工作台。</p><a href="rpc_order_refresh.png" target="_blank"><img src="rpc_order_refresh.png"></a>
<select id="rpc"><option value="">未填写</option><option>新版可以沿用这个顺序</option><option>需要改顺序，见备注</option><option>不确定</option></select><textarea id="rpcNote" placeholder="可选：按编号填写排列"></textarea></section>
<section><h2>2. Uw-09：缺少哪个部位？</h2><p>当前只输出3个达票节点。另有11、9、7人等组未达12票。P023同时画出G001、G011、G010，不能为了补到四对便把它们相加。请指出缺少的位置／编号；若认为两个算法组其实应属同一目标，请写组号，模糊处可保留不确定。</p><a href="uw_missing_nodes.png" target="_blank"><img src="uw_missing_nodes.png"></a><textarea id="uwNote" placeholder="缺少的位置／组号，或其他判断"></textarea></section>
<button id="save">导出收尾判断JSON</button><span id="status"></span>
<script id="proposal" type="application/json">__PROPOSAL__</script><script>
const ids=['rpc','rpcNote','uwNote'],key='fusion_closeout_review_20261008_v1';
let values={};try{values=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
for(const id of ids){document.getElementById(id).value=values[id]||'';document.getElementById(id).oninput=()=>{values[id]=document.getElementById(id).value;localStorage.setItem(key,JSON.stringify(values));document.getElementById('status').textContent='已暂存';}}
document.getElementById('save').onclick=()=>{const data={schema:key,decisions:values,rpc_proposal:JSON.parse(document.getElementById('proposal').textContent)};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='融合收尾两项复核_20261008.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
</script></html>'''
    if confirmed_x:
        html=html.replace('只剩这两项新反馈需处理','rPc已完成；Uw反馈待澄清').replace('1. rPc：新版位置，旧排列还能否沿用？','1. rPc：已按你指定的x递增完成')
        html=html.replace('请确认这个连接顺序仍可用。编号沿旧工作台。','右侧现为你已指定的x递增顺序，并按连接顺序重新编号1—9，无需重填；左侧保留旧节点编号。')
        html=html.replace('<select id="rpc">','<select id="rpc" disabled>').replace('<option value="">未填写</option>','<option value="">已按x递增完成</option>')
        html=html.replace('2. Uw-09：缺少哪个部位？','2. Uw-09：你此前写的“缺少标点”指哪里？')
        html=html.replace('当前只输出3个达票节点。','“缺少标点”来自你上一份排序回执，不是要求每图必须补成四对。红色图是当前3个达票节点；其他图用来解释原标注和票数。')
    if confirmed_x and outputs[code]['candidate'].get('review_status')=='incomplete_consensus_observed':
        html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>融合收尾：已处理</title>
<style>body{font:17px system-ui;max-width:1600px;margin:24px auto;padding:12px}img{width:100%}p{line-height:1.7}</style>
<h1>两项反馈已处理，无需重复填写</h1><p><a href="../REPORT.md">当前交付报告</a>。保留当时图件用于理解判断来源。</p>
<h2>rPc：按用户指定x递增</h2><p>顺序已采用；没有改变节点、票数或位置。</p><img src="rpc_order_refresh.png">
<h2>Uw：保留未形成完整共识的结果</h2><p>G002＋G008、G003＋G009已按同一墙线合并，各为3/24，仍未达12票。当前仍为3个达票节点；不补成四对。这是当前人员池与规则下的结果，不证明未来增加人员也不收敛。</p>
<p>下面保留合并前组号，便于对应你的原判断；最新分组见<a href="../UwV83HsGsw3-09.json">完整结果</a>。此状态不等于所有身份或顺序均已认证。</p><img src="uw_missing_nodes.png"></html>'''
    (target/'review.html').write_text(html.replace('__PROPOSAL__',json.dumps(proposal,ensure_ascii=False)),encoding='utf-8')


if __name__=='__main__':run()
