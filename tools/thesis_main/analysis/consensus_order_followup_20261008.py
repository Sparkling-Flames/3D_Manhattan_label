"""复用当前融合输出，展示两人分歧并核对历史改序图的候选连接；不改变融合。"""
import csv
from collections import defaultdict
from pathlib import Path

from .consensus_delivery_20261008 import OUT, POP, read
from .direct_fusion_20261007 import draw_layout
from .research_artifact_io import ROOT, write_json, write_csv
from .union_branch_consensus_20260926 import _ring_key


def run():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    target=OUT/'order_followup';target.mkdir(exist_ok=True)
    inputs={r['image']:r for r in read(POP/'inputs.json')['images']}
    outputs={r['image']:r for r in read(OUT/'outputs.json')}
    palette=['#e51c3e','#00aeef','#9a22cc','#ff8c00','#008c68','#2255cc','#bb4400','#cc33aa','#779900']

    def axes_for(code,count):
        photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+inputs[code]['image_id']+'.png')))
        fig,axes=plt.subplots(count,1,figsize=(16,7*count),squeeze=False)
        axes=axes[:,0]
        for ax in axes:
            ax.imshow(photo,extent=(0,1024,512,0));ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        return fig,axes

    def nodes_on(ax,nodes,order=None):
        if order:
            byid={n['feature_id']:n for n in nodes}
            draw_layout(ax,[p for fid in order for p in byid[fid]['points']],'#e51c3e')
        ranks={n['feature_id']:j for j,n in enumerate(sorted(nodes,key=lambda n:n['points'][0][0]))}
        for i,n in enumerate(nodes):
            color=palette[i%len(palette)]
            draw_layout(ax,n['points'],color,closed=False)
            ax.annotate(str(i+1),xy=n['points'][0],xytext=(n['points'][0][0],22+30*(ranks[n['feature_id']]%3)),
                ha='center',fontsize=12,bbox=dict(facecolor='white',edgecolor=color),arrowprops=dict(arrowstyle='-',color=color))

    def save(fig,name):
        fig.tight_layout();fig.savefig(target/name,dpi=110);plt.close(fig)

    code='e9zR4mvMWw7-15';p=read(OUT/(code+'.json'));r=p['assisted'] or p['automatic']
    photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+inputs[code]['image_id']+'.png')))
    fig=plt.figure(figsize=(16,11));grid=fig.add_gridspec(2,2,height_ratios=[1,1.2])
    axes=[fig.add_subplot(grid[0,0]),fig.add_subplot(grid[0,1]),fig.add_subplot(grid[1,:])]
    for ax in axes:ax.imshow(photo,extent=(0,1024,512,0));ax.axis('off')
    for ax,fid,color,label in zip(axes[:2],['node_003','node_004'],['#ed1639','#00cfff'],['原4号：红色4人','原5号：青色4人']):
        group=next(g for g in p['automatic']['identity_groups'] if g['feature_id']==fid)
        for m in group['members']:draw_layout(ax,m['points'],color,.85,closed=False)
        ax.set_xlim(880,1024);ax.set_ylim(405,185);ax.set_title('e9z-15 '+label+'（接缝右侧放大）')
    nodes_on(axes[2],r['node_consensus']['nodes'],r['candidate']['feature_ids'])
    axes[2].set_title('按本次同墙线判断辅助合并：8/8支持，四节点；连接仍为来源建议')
    save(fig,'e9z15_sources_and_fusion.png')

    code='jh4fc5c5qoQ-12';r=read(OUT/(code+'.json'))['automatic']
    fig,axes=axes_for(code,3)
    for ax,rec,color in zip(axes[:2],inputs[code]['records'],['#0065ff','#ec6500']):
        draw_layout(ax,rec['points'],color)
        ax.set_title(f"{rec['worker']} / {rec['id']} 原答：{len(rec['points'])//2}对，沿既定原环")
    nodes=r['node_consensus']['nodes']
    for n in nodes:
        color='#b318dc' if n['support']==2 else ('#ec6500' if n['members'][0]['worker']=='P011' else '#0065ff')
        draw_layout(axes[2],n['points'],color,closed=False)
    axes[2].set_title('算法匹配的4个2/2节点：紫色；5个1/2节点：来源色。全部按MV50保留，未拼接为九节点环。')
    save(fig,'jh4_two_sources.png')

    code='zsNo4HB9uLZ-05';r=outputs[code];fig,axes=axes_for(code,1)
    nodes_on(axes[0],r['node_consensus']['nodes'],r['candidate']['feature_ids'])
    axes[0].set_title('zs-05 按用户授权x递增连接；旧展示编号顺序1→2→5→4→3→1')
    save(fig,'zs05_ordered.png')

    hist=ROOT/'analysis_results/research_input_20260929/final_review'
    def csv_rows(name):
        with (hist/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    changes=defaultdict(list)
    for row in csv_rows('逐对象改序及审核来源.csv'):
        if row['change']=='adjacency_changed':changes[row['image_code']].append(row)
    for row in csv_rows('历史本人改序补充.csv'):
        changes[row['image_code']].append(dict(row,change='historical_adjacency_changed'))
    audit=[];panels=[]
    for code,r in outputs.items():
        if code not in changes:continue
        p=read(OUT/(code+'.json'));state=p['assisted'] or p['automatic']
        records=inputs[code]['records'];nodes=r['node_consensus']['nodes'];candidate=r['candidate']
        evidence={row['object_id']:row for row in changes[code]}
        in_pool=[rec for rec in records if rec['object_id'] in evidence]
        ids=candidate['feature_ids'];xids=[n['feature_id'] for n in sorted(nodes,key=lambda n:n['points'][0][0])]
        different=bool(ids) and _ring_key(ids)!=_ring_key(xids)
        diag=state['ring_diagnostics'];alts=diag['alternatives']
        reasons=[]
        if not ids:reasons.append('no_complete_source_ring')
        if different:reasons.append('source_connection_differs_from_x_order')
        if diag['tied_best']:reasons.append('tied_source_orders')
        if len(alts)>1:reasons.append('multiple_complete_source_orders')
        row=dict(image=code,n=r['n'],nodes=len(nodes),history_objects=len(evidence),changed_objects_in_pool=len(in_pool),
            history_annotation_objects=sum(x.get('object_kind','annotation')=='annotation' for x in evidence.values()),
            order_status=candidate['order_status'],order_confirmed=candidate['ring_confirmed'],
            differs_from_x_order=different,source_ring_support=alts[0]['support'] if alts else 0,
            complete_source_alternatives=len(alts),priority_reasons=';'.join(reasons),
            display_order=[next(i+1 for i,n in enumerate(nodes) if n['feature_id']==fid) for fid in ids])
        audit.append(row)
        # One corrected source is context, not proof that the fused ring is correct.
        reference=in_pool[0] if in_pool else records[0]
        fig,axes=axes_for(code,2)
        draw_layout(axes[0],reference['points'],'#0065ff')
        axes[0].set_title(code+' · 来源 '+reference['worker']+' / '+reference['id']+('（有实际改序记录）' if in_pool else '（改序证据来自当前池外对象）'))
        nodes_on(axes[1],nodes,ids)
        axes[1].set_title('当前融合：'+str(row['display_order'])+' · '+candidate['order_status']+'；来源建议不等于新环确认')
        save(fig,code+'.png')
        panels.append(dict(image=code,priority=bool(reasons),reasons=reasons,nodes=nodes,order=ids,history=changes[code]))
    write_csv(target/'history_order_audit.csv',audit);write_json(target/'history_order_audit.json',panels)
    links=[]
    labels={'no_complete_source_ring':'无完整来源环，先检查分歧节点',
            'source_connection_differs_from_x_order':'已保留与x排序不同的来源连接',
            'tied_source_orders':'来源顺序支持并列',
            'multiple_complete_source_orders':'存在多个完整来源顺序'}
    for row in sorted(audit,key=lambda r:(not bool(r['priority_reasons']),r['image'])):
        code=row['image'];reason='；'.join(labels[k] for k in row['priority_reasons'].split(';') if k) or '历史改序：候选连接与x环等价，仍未经新环人审'
        links.append(f'<details><summary>{code} · {reason}</summary><a href="{code}.png"><img loading="lazy" width="100%" src="{code}.png"></a></details>')
    (target/'history_order_review.html').write_text('<!doctype html><meta charset="utf-8"><title>历史改序图片融合检查</title><h1>历史改序图片：当前候选连接</h1><p>过去改过序只是复核线索；本页不自动改顺序。排在前面的图片不代表连错或必须重审。yq-25已有局部顺序确认继续保留。可以回复图片名及新编号顺序，也可以指出节点问题。</p>'+''.join(links),encoding='utf-8')
    small=[r for r in outputs.values() if r['n']==2]
    summary=dict(history_images_in_inventory=len(changes),history_images_in_delivery=len(audit),
        changed_source_in_current_pool=sum(r['changed_objects_in_pool']>0 for r in audit),
        priority_images=[r['image'] for r in audit if r['priority_reasons']],
        two_person_images=len(small),two_person_nodes=sum(len(r['node_consensus']['nodes']) for r in small),
        two_person_single_supported_nodes=sum(n['support']==1 for r in small for n in r['node_consensus']['nodes']),
        interpretation='History is a review trigger, not proof of current error. Candidate source order is not whole-ring majority. No coordinates, votes or order altered by this audit.')
    write_json(target/'summary.json',summary)
    print(summary)


if __name__=='__main__':run()
