"""Preserve the submitted review; publish a separate seeded correction workbench."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/data/doorway_review_20261030/first_review_audit'

def main():
    data = json.loads((BASE/'review102-data.js').read_text(encoding='utf8').split('=', 1)[1][:-1])
    submitted = json.loads((BASE/'USER_REVIEW_20261030.json').read_text(encoding='utf8'))
    seed = json.loads(json.dumps(submitted))
    with gzip.open(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz', 'rt', encoding='utf8') as f:
        evidence = {r['object_id']: r for r in json.load(f)['records']}
    full = json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])
    audit = []
    for c in full['cases']:
        for r in c['records']:
            e = evidence[r['id']]
            assert r['points'] == e['points_1024x512']
            audit.append(dict(image=c['image'],record_id=r['id'],worker=r['worker'],
                original_count=len(e['original_points']) if e['original_points'] is not None else None,
                received_count=len(e['received_processed_points'] or []),
                preprocessed_count=len(e['preprocessed_points'] or []),display_count=len(r['points'] or []),
                geometry_status=e['geometry_status']))
    assert len(audit)==708 and sum(bool(r['display_count']) for r in audit)==700
    assert sum(r['received_count']!=r['preprocessed_count'] for r in audit)==7
    (BASE/'ALL708_POINT_AUDIT.json').write_text(json.dumps(dict(n=708,with_display_points=700,
        preprocessing_unavailable_with_input=7,empty_source=1,workbench_coordinate_mismatch=0,
        note='original_count=null表示证据包没有该层，不能解释为原始空作答。700份非空点已另用现有WorkbenchCore.geometry验证可构造几何。',records=audit),ensure_ascii=False,indent=2),encoding='utf8')
    suggestions = {
        'W100': '空间2判断可以保留；形状失真不等于空间意图不明。',
        'W101': '主要圈住中央墙柱/凹口，不能据此认定完整空间；保留都不符合待查。',
        'W105': '建议重看为空间2：点位主要沿门口至右侧纵深，未覆盖卧室主体；斜边属于几何问题。',
        'W107': '建议重看为全部：卧室侧与右侧纵深均有点位；虽然局部缩小，跨两空间的意图仍可辨认。',
        'W127': '卧室有一对点、右侧也有点；可能意在全部但严重漏角，也可能范围不明，暂不改判。',
        'W132': '卧室有一对点、右侧也有点；不能只按俯视形状判乱标，全部是待比较解释。',
        'W106': '卧室有一对点、右侧也有点；可能跨两空间，但不足以认定完整范围，保留争议。',
    }
    recovered = []; missing = []; changed = []
    for c in data['cases']:
        u = seed['cases'][c['image_id']]
        assert u['reference_id'] == c['reference_id'] and u['reference_version'] == c['reference_version']
        assert set(u['answers']) <= {r['id'] for r in c['records']}
        c['cuts'] = u['cuts']
        if c['image'] == 'B6ByNegPMKs-42':
            # The second jamb face is a visual draft, not a metric thickness measurement.
            x = u['cuts'][0]['line'][0][0]
            c['cuts'] = [{'line': [[x,-100],[x,100]], 'side':1}, {'line':[[0.125,-100],[0.125,100]], 'side':-1}]
            u['cuts'] = c['cuts']
            c['proposal_note'] = '保留用户纵向切分；空间1停止边x=0.02245，空间2停止边暂拟x=0.125，留出门框带。后者按原图门框落地附近估计，非实测厚度，仍待复核。原7份选择保留旧边界快照并提示重看。'
            u['proposal_note'] = c['proposal_note'];changed.append(c['image'])
        if c['image'] in ['pRbA3pwrgk9-01', 'pRbA3pwrgk9-11']:
            c['status'] += ' · OOS与门洞重叠，单列诊断'
        if c['image'] == 'jtcxE69GiFV-12':
            c['status'] += ' · 用户指出勉强可标；不作为清晰门洞代表'
        for r in c['records']:
            if not r['points']:
                r['raw_points'] = evidence[r['id']]['original_points'] or None
                item = dict(image=c['image'],worker=r['worker'],record_id=r['id'])
                (recovered if r['raw_points'] else missing).append(item)
                r['visual_reason'] = ('已恢复原始散点，仅供范围判断；点对及环序未确认，不生成BEV/3D闭环。' if r['raw_points'] else '当前证据包原始点与预处理点均为空；保留缺失占位，不应据此判为乱标。')
            if c['image'] == 'jh4fc5c5qoQ-14':
                r['visual_reason'] = ('空间1孤立一对点不足以认定完整空间；接受用户看不懂判断，不再要求重审。' if r['worker'] in ['W127','W132','W106'] else suggestions[r['worker']])
    assert sum(len(c['answers']) for c in submitted['cases'].values()) == 75
    assert len(recovered) == 7 and len(missing) == 1
    assert all(seed['cases'][k]['answers'] == v['answers'] for k,v in submitted['cases'].items())
    (BASE/'followup-data.js').write_text('window.DOORWAY_DATA='+json.dumps(data,ensure_ascii=False)+';window.DOORWAY_SEED='+json.dumps(seed,ensure_ascii=False)+';',encoding='utf8')
    js=(BASE/'review102.js').read_text(encoding='utf8')
    js=js.replace('doorway_visual_102_recheck_v2','doorway_followup_20261030_v1')
    js=js.replace('let state={schema:D.schema,cases:{}}','let state=clone(window.DOORWAY_SEED)')
    js=js.replace('{points:r.points},null,null', '{points:r.points,raw_points:r.raw_points},null,null')
    js=js.replace("label:'GT参考',points:c.points,visible:false", "label:'GT参考',points:c.points,confirmed:true,visible:false")
    js += '\n' + Path(__file__).with_name('doorway_followup_filter.js').read_text(encoding='utf-8-sig')
    (BASE/'followup.js').write_text(js,encoding='utf8')
    page=(BASE/'review102.html').read_text(encoding='utf8').replace('review102-data.js','followup-data.js').replace('review102.js','followup.js')
    page=page.replace('102份视觉复核 · 空间归属','用户结果接续复核 · 已载入75份选择')
    page=page.replace('其中8份点对为空，不能据此认定乱标。','其中7份已补原始散点，1份仍缺失。保留原75份选择；B6-42边界修正后7份旧选择会提示重看。')
    page=page.replace('<main>', '<main><p>pRb-01与11归OOS，已从本轮门洞审核/分析范围排除。默认固定展示本轮17份复核清单，不因本地已保存选择而隐藏；已保存项目可重新选择。点击分类仅保存并停留；用下一份切换。原始散点未确认配对与环序时不显示布局连线。</p>')
    page=page.replace('<nav>', '<nav><label>筛选 <select id="reviewFilter"><option value="round">本轮复核清单（固定17份）</option><option value="pending">尚未处理（随保存更新）</option><option value="unreviewed">未审核</option><option value="disputed">有质疑</option><option value="changed">切分变化需重看</option><option value="all">门洞范围全部</option><option value="missing">无原始点（无需审核）</option></select></label><span id="filterCount"></span>',1)
    (BASE/'followup.html').write_text(page,encoding='utf8')
    (BASE/'FOLLOWUP_CHECKS.json').write_text(json.dumps(dict(saved=75,unselected=27,raw_recovered=recovered,still_missing=missing,cut_proposal=changed,labels_overwritten=0),ensure_ascii=False,indent=2),encoding='utf8')
    print('PASS: 75 choices preserved; 27 unselected; 7 raw displays restored; 1 missing; 1 proposed cut correction')

if __name__ == '__main__':
    main()

