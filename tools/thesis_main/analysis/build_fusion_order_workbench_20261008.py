"""复用点对拖拽排序台和墙线归类台；固定当前融合快照，独立保存审核。"""
import json
import os
from .consensus_delivery_20261008 import OUT as DELIVERY, POP, read
from .research_artifact_io import ROOT, write_json
from .build_order_studio_20260926 import geometry_variant, encode

OUT=DELIVERY/'order_workbench'


def fusion_source(code,result):
    nodes=result['node_consensus']['nodes'];points=[p for n in nodes for p in n['points']]
    ids=[n['feature_id'] for n in nodes];candidate=result['candidate']
    order=[ids.index(fid) for fid in candidate['feature_ids']]
    assert sorted(order)==list(range(len(nodes)))
    return dict(object_id='fusion:'+code,object_kind='fusion',canonical_annotation_id='fusion:'+code,
        image_id=result['image_id'],worker_id='全员融合',raw_condition=str(result['n'])+'人',
        processing_status='固定融合位置；仅调整顺序',role='annotation',points=points,effective_points=points,
        effective_point_labels=['F'+str(i+1) for i in range(len(points))],
        original_point_ids_1based=[None]*len(points),links_zero_based=[[2*i,2*i+1] for i in range(len(nodes))],
        preprocessing='frozen_consensus_shared_x',default_preview_order=order,ring_confirmed=False,
        feature_ids=ids,node_supports=[n['support'] for n in nodes],review={})


def build():
    OUT.mkdir(exist_ok=True)
    inputs={r['image']:r for r in read(POP/'inputs.json')['images']}
    current={r['image']:r for r in read(DELIVERY/'outputs.json')}
    history={r['image']:r for r in read(DELIVERY/'order_followup/history_order_audit.json')}
    cases=[];images={};catalog=[];excluded=[]
    candidates=[]
    for code,r in current.items():
        package=read(DELIVERY/(code+'.json'));state=package['assisted'] or package['automatic']
        diag=state['ring_diagnostics']
        if r['n']==2:excluded.append(code);continue
        if r['candidate']['ring_confirmed']:continue
        if code in history or diag['tied_best'] or len(diag['alternatives'])>1 or not r['candidate']['feature_ids']:
            candidates.append((code,r))
    candidates.sort(key=lambda item:(not history.get(item[0],{}).get('priority',False),item[0]))
    for code,r in candidates:
        package=read(DELIVERY/(code+'.json'));r=dict(r,image_id=package['image_id'])
        # No fabricated initial ring: unresolved node-only cases stay in correspondence review.
        if not r['candidate']['feature_ids']:continue
        s=fusion_source(code,r);catalog.append(s)
        variant=geometry_variant('融合共识 · '+str(r['n'])+'人',s,s['points'],s['links_zero_based'])
        reason='历史人工改序图' if code in history else '候选来源顺序存在分歧'
        if code=='yqstnuAEVhm-25':reason+='；已有局部3→遮挡角→左右可见角连接确认保留'
        cases.append(dict(title=code,image_id=r['image_id'],category=reason,variants=[variant],room_id=''))
        photo=next(ROOT.glob('data/mp3d_layout/*/img/'+r['image_id']+'.png'))
        url=os.path.relpath(photo,OUT).replace(os.sep,'/')
        images[len(cases)-1]=dict(original=url,texture=url)
    dataset=dict(cases=cases,counts=dict(cases=len(cases),variants=len(cases)),manifest=dict(
        export_schema='fusion_order_review_20261008_v1',examples_only=False,review_round='fusion_20261008',formal_data_connected=False))
    (OUT/'data.js').write_text('window.STUDIO_IMAGES='+encode(images)+';window.STUDIO_DATA='+encode(dataset)+';',encoding='utf-8')
    page=(ROOT/'analysis_results/order_studio_20260926/index.html').read_text(encoding='utf-8')
    for name in ['studio.js','studio.css','three.min.js','OrbitControls.js','order_studio.js','order_studio.css']:
        path=ROOT/('tools/thesis_main/analysis/order_studio_20260926.'+name.split('.')[-1] if name.startswith('order_studio') else 'analysis_results/order_studio_20260926/'+name)
        page=page.replace('"'+name+'"','"'+os.path.relpath(path,OUT).replace(os.sep,'/')+'"')
    page=page.replace('</head>','<script defer src="fusion_order.js"></script></head>')
    (OUT/'index.html').write_text(page,encoding='utf-8')
    (OUT/'fusion_order.js').write_text("""'use strict';
document.title='融合共识排序复核';document.querySelector('h1').textContent='融合共识 · 点对排序';
document.querySelector('.order-editor p').textContent='只调整完整融合点对的顺序，票数和坐标不改。两人池不在本次队列。节点归属有问题时请标记，不必强行连线。';
$('order-restore').textContent='恢复当前来源建议';$('pairing-problem').textContent='节点归属需复核';
$('pairing-note').placeholder='请填写节点编号及问题（可选）';
const baseDescription=describeSource;describeSource=function(){baseDescription();const s=activeSource();identity.textContent='融合节点票数：'+s.node_supports.map((n,i)=>'对'+(i+1)+'='+n+'票').join('，')+'。对N是固定节点编号；拖动改变连接顺序。';};
describeSource();
const info=document.createElement('p');info.innerHTML='复用原排序台：拖动卡片或输入完整排列→确认→导出JSON。无需修改时直接确认；不确定可暂留。<a href="residual_review.html" target="_blank">另开：两处残余墙线归属复核</a>';
document.querySelector('.study-heading').after(info);
$('download-orders').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema:reviewSchema,examples_only:false,records:saved},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='融合共识排序审核_20261008.json';a.click();URL.revokeObjectURL(url);};
""",encoding='utf-8')
    write_json(OUT/'sources.json',dict(schema='fusion_order_review_20261008_v1',objects=catalog,
        two_person_excluded=excluded,policy='Only N>=3, unconfirmed fused rings. No GT; fixed points, pairing and votes. Export binding includes coordinates, labels and links. No direct writeback.'))
    build_residual(inputs,current)
    print('order workbench',len(cases),'two-person excluded',len(excluded))


def build_residual(inputs,current):
    prior={r['image']:r for r in read(POP/'refine_20261008/user_review_20261008.json')['decisions']}
    selected={'rPc6DW4iMge-06':{'node_001','node_015','node_017'},'uNb9QFRL6hY-08':{'node_003','node_005'}}
    questions={
        'rPc6DW4iMge-06':'已确认P003第3对、P007第3对、P023第5对想标同一墙线；P023第3对是另一细节，不必重判。这里只补两个候选组内其他成员。点选同目标的具体来源后逐条记录；模棱两可者留不确定，不要求整组统一。',
        'uNb9QFRL6hY-08':'原话“最左边那份应与G06同停止位置”定位到P022/R02260第4对；另一单人组是P018/R01833第4对。请先选这两份，确认同一停止墙线／不同／不确定；其余人员如无新意见不用重判。'}
    images=[]
    for code,fids in selected.items():
        src=inputs[code];package=read(DELIVERY/(code+'.json'));state=package['assisted'] or package['automatic']
        observations=[];lookup={}
        for rec in src['records']:
            for k in range(len(rec['points'])//2):
                lookup[rec['id'],k]=len(observations)
                observations.append(dict(id=rec['id'],worker=rec['worker'],pair_index=k,source_pair_index=rec['source_pair_indices'][k],points=rec['points'][2*k:2*k+2]))
        groups=[]
        for g in state['identity_groups']:
            if g['feature_id'] in fids:
                groups.append(dict(label='G'+str(len(groups)+1).zfill(2),feature_id=g['feature_id'],members=[lookup[m['id'],m['pair_index']] for m in g['members']],support=g['support'],selected=g['selected'],center=g['center']))
        photo=next(ROOT.glob('data/mp3d_layout/*/img/'+src['image_id']+'.png'))
        images.append(dict(code=code,image_id=src['image_id'],n=len(src['records']),priority=True,question=questions[code],
            prior=prior.get(code,dict(note='已有局部判断见本页问题说明。',verdicts={},issues=[])),
            src=os.path.relpath(photo,OUT).replace(os.sep,'/'),observations=observations,states={'7.5':groups}))
    data=dict(schema='wall_identity_residual_20261008_v1',revision=True,priority_count=2,gaps=[7.5],images=images)
    page=(ROOT/'tools/thesis_main/analysis/wall_identity_review_20261007.html').read_text(encoding='utf-8')
    page=page.replace('/*__DATA__*/',encode(data)).replace("gaps=['7.5','9']","gaps=['7.5']")
    page=page.replace("'归类方案 '+(side?'B':'A')","'当前局部归类'")
    page=page.replace('墙线归类复审_20261008.json','墙线残余归属审核_20261008.json')
    page=page.replace('list();\n</script>',"list();$('rightLabel').style.display='none';$('leftLabel').firstChild.textContent='当前局部归类是否可用 ';$('panels').style.gridTemplateColumns='1fr';\n</script>")
    (OUT/'residual_review.html').write_text(page,encoding='utf-8')


if __name__=='__main__':build()
