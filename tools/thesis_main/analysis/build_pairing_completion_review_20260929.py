"""15份配对补齐复核；保留原点身份，删除只作为显式预览方案。"""
import csv
import json
from collections import Counter
from .build_pairing_review_20260929 import ROOT, encode, read, dump
from .audit_x_pairing_20260929 import x_adjacent

OUT = ROOT/'analysis_results/pairing_completion_review_20260929'
DELETIONS = {'4d3e4911d8f07aa2': [[6]], 'f6bfdcf15004e457': [[2], [0]], '3a3dec28a207f0a0': [[10]]}


def proposal(points, locked, deleted):
    retained = [i for i in range(len(points)) if i not in deleted]
    if any(i in deleted for p in locked for i in p):
        raise ValueError('deletion_conflicts_with_explicit_pair')
    local = {i: j for j, i in enumerate(retained)}
    result = x_adjacent([points[i] for i in retained], [[local[a], local[b]] for a, b in locked])
    if result['pairs'] is None:
        raise ValueError('unresolved_candidate:'+result['status'])
    return dict(id='delete_'+ '_'.join(str(i+1) for i in deleted) if deleted else 'keep_all',
                label='预览删除 '+ '、'.join('P'+str(i+1) for i in deleted) if deleted else '保留全部点',
                deleted=deleted, pairs=[[retained[a], retained[b]] for a, b in result['pairs']],
                candidate_status=result['status'])


def build():
    audit=ROOT/'analysis_results/x_pairing_audit_20260929'
    with (audit/'34份逐项复核_只按明确OOS备注豁免.csv').open(encoding='utf-8-sig') as f:
        selected={r['object_id']:r for r in csv.DictReader(f) if r['review_result'] in
                  {'horizon_role_limit','x_completion_required','point_edit_pending'}}
    previous=read(audit/'evidence/pairing_return.json')['records']
    old=json.loads((ROOT/'analysis_results/pairing_review_20260929/data.js').read_text(encoding='utf-8').removeprefix('window.PAIRING_DATA=').removesuffix(';'))
    cases=[]
    for source in old['cases']:
        oid=source['object_id']
        if oid not in selected: continue
        review=previous[oid]
        expected=dict(object_id=oid,points=source['points'],labels=source['labels'],coordinate_source=source['coordinate_source'])
        if json.loads(review['binding'])!=expected: raise ValueError('source_binding:'+oid)
        cases.append(dict(source, note=review['note'], review_reason=selected[oid]['review_result'],
            explicit_pairs=review['pairs'], previous_review=review,
            proposals=[proposal(source['points'],review['pairs'],d) for d in DELETIONS.get(oid,[[]])]))
    if len(cases)!=15 or Counter(r['review_reason'] for r in cases)!=Counter(horizon_role_limit=6,x_completion_required=6,point_edit_pending=3):
        raise ValueError('queue_drift')
    data=dict(schema='pairing_completion_review_20260929_v1',review_mode='complete_pairing',cases=cases,
              images={r['image_id']:old['images'][r['image_id']] for r in cases})
    OUT.mkdir(exist_ok=True)
    (OUT/'data.js').write_text('window.PAIRING_DATA='+encode(data)+';',encoding='utf-8')
    html=(ROOT/'tools/thesis_main/analysis/pairing_review_20260929.html').read_text(encoding='utf-8')
    start=html.index('<p>本轮只配对，不排序。')
    end=html.index('</p>',start)+4
    html=html[:start]+('<p>本轮只配对，不排序。核对<strong>完整配对预览</strong>：绿色为你上轮明确配对，橙色为按原始x补齐，蓝色为本轮手动配对。'
        '有问题时解除该对，再依次选择上点、下点；正确时直接确认。灰色叉号为拟删除点，P点号始终不变。</p>'
        '<p><label>修点预览方案 <select id="proposal"></select></label> <span id="proposal-hint"></span></p>')+html[end:]
    html=html.replace('34份','15份').replace('<h1>上下点配对</h1>','<h1>补齐配对复核</h1>').replace('清空本轮修正','恢复当前预览配对').replace('本图检查完成','确认本图配对').replace('暂缓／需修点','仍有问题／暂缓')
    (OUT/'index.html').write_text(html,encoding='utf-8')
    dump(OUT/'field_contract.json',dict(schema=data['schema'],scope='pairing_only',order_confirmed=False,
        pairs='零基原始P点索引[上,下]；checked必须完整覆盖所有未删除点。完整配对不代表连接环序。',
        proposal_id='选择的只读预览方案；B6-33/W032必须明确选择删除P1或P3后确认。',
        deleted_source_indices='原始零基索引；只在本轮记录建议删除，不改原GT/导出/历史坐标；余下P号不重排。',
        binding='原始对象+坐标+标签+全部方案+上轮明确配对；独立缓存，新一轮状态不沿用旧checked',
        statuses=['draft','checked','deferred'],provenance='explicit_pairs为上轮明确配对；方案其余为x候选；最终pairs为本轮复核完整配对',
        rule='周期x相邻最小总差候选，先锁定明确配对；不以地平线上下划分角色；仍需用户复核。'))
    return dict(objects=len(cases),images=len(data['images']),reasons=dict(Counter(r['review_reason'] for r in cases)))


if __name__=='__main__': print(build())
