"""制作修复方案；仅--apply-approved写入用户批准的独立有效层，原始标注不变。"""
import copy
import json
import shutil
from pathlib import Path
from collections import Counter
from .audit_review_return_20260927 import case_payload, read, dump
from .review_reconciliation_audit_20260925 import verify_raw

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'analysis_results/review_return_20260927'
OUT = ROOT / 'analysis_results/review_closeout_20260928'
INPUT = Path('C:/Users/ASUS/Downloads/全历史标注_定向补审_20260927.json')


def preview_operation(points, labels, delete=(), set_x_from=None):
    if len(points) != len(labels) or len(set(labels)) != len(labels):
        raise ValueError('point_label_binding_invalid')
    result = dict(zip(labels, copy.deepcopy(points)))
    for label in delete:
        if label not in result:
            raise ValueError('requested_point_missing:' + label)
        del result[label]
    if set_x_from:
        target, source = set_x_from
        result[target][0] = result[source][0]
    return dict(after_points=list(result.values()), after_labels=list(result))


def build(apply_approved=False):
    if (ROOT / 'analysis_results/review_final_20260928/effective_point_overrides.json').exists():
        raise ValueError('本轮修复语义已被最新审核纠正；请运行finalize_review_20260928，不能重放旧7项方案。')
    OUT.mkdir(exist_ok=True)
    (OUT / 'evidence').mkdir(exist_ok=True)
    target = OUT / 'evidence/returned_review.json'
    if target.exists() and target.read_bytes() != INPUT.read_bytes():
        raise ValueError('已有不同审核原件，请另建目录')
    shutil.copyfile(INPUT, target)
    returned = read(INPUT)
    if returned['schema'] != 'review_return_decisions_v2' or returned['binding'] != {'id':'review_return_20260927_v1'}:
        raise ValueError('review_binding_mismatch')
    s = (OLD / 'data.js').read_text(encoding='utf-8')
    data = json.loads(s.split('window.STUDIO_DATA=',1)[1].split(';\nwindow.STUDIO_IMAGES=',1)[0])
    cases, sources = {}, {}
    for c in data['cases']:
        cases[c['image_id']] = c
        for v in case_payload(OLD / c['history_script'])['variants']:
            if v['source']['role'] == 'annotation':
                sources[v['source']['canonical_annotation_id']] = v['source']
    if not set(returned['annotation_decisions']) <= sources.keys() or not set(returned['image_decisions']) <= cases.keys():
        raise ValueError('unknown_review_identity')
    traps = read(OLD / 'trap_inventory.json')['annotations']
    plans, cache = [], {}

    def add(cid, reason, options, readiness):
        src = sources[cid]
        record = src['audit']['source']
        path = record.get('mirror_path') or record['path']
        if path not in cache:
            cache[path] = {t['id']:t for t in read(ROOT / path)}
        task = cache[path][record['task']]
        ann = next(a for a in task['annotations'] if a['id'] == record['annotation'])
        verify_raw(record, src['raw_points'], task, ann)
        iid = traps[cid]['image_id']
        plans.append(dict(annotation_id=cid,image_id=iid,code=traps[cid]['code'],worker=src['worker_id'],
            status='proposal_not_applied', readiness=readiness, reason=reason,
            instruction=returned['annotation_decisions'][cid]['comment'], source=record, raw_verified=True,
            before_points=src['effective_points'],before_labels=src['effective_point_labels'],options=options,
            image_src=cases[iid]['return_review']['image_src']))

    def options(cid, groups):
        src=sources[cid]
        return [dict(name='删除'+ '/'.join(labels), **preview_operation(src['effective_points'],src['effective_point_labels'],labels)) for labels in groups]

    src=sources['5e3a87e01e8c7a68']
    add('5e3a87e01e8c7a68','按用户点名对齐p8.x到p7.x，仅变一个坐标。',
        [dict(name='p8.x = p7.x',**preview_operation(src['effective_points'],src['effective_point_labels'],set_x_from=['p8','p7']))],'ready_for_approval')
    for cid, labels, reason in [
        ('80a4655a847e5a65',['p7'],'明确去掉p7。'),
        ('f8c20f06811c7321e708',['p9','p10'],'明确点名多余p9/p10；不改变其较大空间方案。'),
        ('acf40c242b1e8bb29e98',['p13'],'用户允许p12/p13任删一个，本方案保留p12、删除p13。'),
        ('adb443cf2cd44a01',['p13'],'明确去掉p13。'),
        ('9117118c1ce15fc9',['p1'],'明确去掉p1后可保留。'),
        ('ef46460f29fb4a76',['p9'],'明确去掉p9；保留其最小空间方案。'),
    ]:
        add(cid,reason,options(cid,[labels]),'ready_for_approval')
    for cid, groups, reason in [
        ('new_95_3663_7443_W028',[['p11','p12'],['p13','p14']],'两端并非完全同坐标，未指定保留哪端。'),
        ('1623fbedf957f0be9421',[['p1','p2','p3','p4'],['p9','p10','p11','p12']],'两组二选一，未指定选择。'),
        ('2559d23544f7b937',[['p14'],['p17']],'p14/p17相差约25像素，不能视为相同点任删。'),
    ]:
        add(cid,reason,options(cid,groups),'needs_choice')
    for cid, point, reason in [
        ('af1ada91e5648762',[sources['af1ada91e5648762']['effective_points'][9][0],sources['af1ada91e5648762']['effective_points'][10][1]],
         '用户说在p10下方、大概与p11同高；先展示该具体坐标候选，须视觉确认。'),
        ('3d1c6d9fda198b1b',[654.0,65.0],
         '实际冻结初始化存在[654,65]，当前缺少该上点；这是恢复初始化的候选，不是人工真值。'),
    ]:
        src=sources[cid]
        if cid=='3d1c6d9fda198b1b' and point not in traps[cid]['model_check']['initial_points_1024x512']:
            raise ValueError('missing_initialization_evidence')
        add(cid,reason,[dict(name='补点候选',after_points=src['effective_points']+[point],after_labels=src['effective_point_labels']+['补点候选1'])],'needs_visual_confirmation')
    dump(OUT / 'repair_proposals.json',dict(schema='review_repair_proposals_20260928_v1',applied=False,
        instruction_source='evidence/returned_review.json',plans=plans))
    approved = []
    if apply_approved:
        # 本轮明确批准仅对应先前列出的7份操作；多方案和补点候选不在此范围。
        for plan in plans:
            if plan['readiness'] != 'ready_for_approval':
                continue
            if len(plan['options']) != 1:
                raise ValueError('approval_requires_single_option')
            option = plan['options'][0]
            approved.append(dict(annotation_id=plan['annotation_id'], image_id=plan['image_id'],
                code=plan['code'], worker=plan['worker'], source=plan['source'],
                raw_points=sources[plan['annotation_id']]['raw_points'],
                before_points=plan['before_points'], before_labels=plan['before_labels'],
                effective_points=option['after_points'], effective_point_labels=option['after_labels'],
                operation=option['name'], approval='用户2026-09-28：我明确批准；仅前述7份明确操作',
                instruction=plan['instruction'], status='applied_effective_override',
                geometry_status='修复后点集尚未重建3D或重新分簇，不沿用旧结果作为新点集结果'))
            plan['status']='applied_effective_override'
        if len(approved) != 7:
            raise ValueError('approved_operation_count_changed')
        dump(OUT / 'effective_point_overrides.json',dict(schema='review_effective_overrides_20260928_v1',
            applied=True, source_review='evidence/returned_review.json',
            annotations={r['annotation_id']:r for r in approved},
            merge_contract='按canonical annotation_id覆盖本轮有效坐标和标签；原始点及用户裁决不变；旧配对/3D/分簇不可冒充修复后结果'))
    clarifications=dict(source='用户2026-09-28本轮消息',gt_blank_policy='OOS/门洞GT空白不算漏审；非正交稳定可标x8同房例外。',
        stable_nonorthogonal_image_ids=['x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23','x8F5xyUWy9e_1be9a97aada84e4795f64583ac0e3b76'],
        image_analysis_holds=[dict(image_id=next(c['image_id'] for c in data['cases'] if c['code']=='jtcxE69GiFV-11'),code='jtcxE69GiFV-11',scope='全部分析暂缓',reason='用户无法判断GT正确性')])
    dump(OUT / 'clarifications.json',clarifications)
    model_rows=[{k:v for k,v in t.items() if k not in ('model_check','original_second_review')}|
        dict(review=returned['annotation_decisions'].get(cid),traits=returned['traits'].get('annotation:'+cid))
        for cid,t in traps.items() if t['condition']=='semi']
    dump(OUT / 'model_analysis_registry.json',dict(schema='model_review_registry_20260928_v1',rows=model_rows,
        interpretation='单独分析Trap与初始化保持/改动；保留来源和个人/图片身份，不直接推断人员低质量或模型因果影响。',
        summary=dict(total=len(model_rows),trap_status=dict(Counter(r['trap_status'] for r in model_rows)),model_edit_status=dict(Counter(r['model_edit_status'] for r in model_rows)))))
    payload=json.dumps(plans,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><meta charset="utf-8"><title>补删点方案核对</title><style>
body{font:16px system-ui;background:#f4f6f1;margin:24px;color:#24342b}article{background:white;padding:20px;margin:20px 0;border:1px solid #bbcbbd;border-radius:12px}canvas{width:100%;height:auto}select{padding:8px;margin:8px}p{line-height:1.6}</style>
<h1>补删点方案核对（尚未执行）</h1><p>7份操作已具体化待批准；另5份需选方案或确认补点位置。蓝色=修复前有效点，红色=执行结果／候选点。原点号不变；没有修改有效层、原始导出、GT或审核结论。</p>
<p><a href="定向补审语义核验.md">完成情况与空间差异</a> · <a href="同房对照.md">同房分类对照</a> · <a href="README.md">本轮汇总</a></p><main></main><script>
const rows=PAYLOAD;const make=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e};
for(const r of rows){const a=make('article');a.id=r.annotation_id;a.append(make('h2',r.code+' · '+r.worker),make('p',r.readiness==='ready_for_approval'?'具体操作待批准':'仍需选择／确认'),make('p','审核原话（修复前）：'+r.instruction),make('p',r.reason));const select=make('select');r.options.forEach((o,i)=>{const e=make('option',o.name);e.value=i;select.append(e)});a.append(select);const c=make('canvas');c.width=1024;c.height=512;a.append(c);const im=new Image();const draw=()=>{const x=c.getContext('2d');x.clearRect(0,0,1024,512);x.drawImage(im,0,0,1024,512);const o=r.options[+select.value];for(const [points,labels,color]of [[r.before_points,r.before_labels,'#1679c9'],[o.after_points,o.after_labels,'#db3d24']]){points.forEach(([px,py],i)=>{x.beginPath();x.arc(px,py,4,0,7);x.fillStyle=color;x.fill();x.strokeStyle='white';x.stroke();x.font='12px sans-serif';x.lineWidth=3;x.strokeText(labels[i],px+6,py-5);x.fillText(labels[i],px+6,py-5)})}};select.onchange=draw;im.onload=draw;im.onerror=()=>a.append(make('p','原图加载失败：'+r.image_src));im.src=r.image_src;document.querySelector('main').append(a)}
</script>'''.replace('PAYLOAD',payload)
    page=page.replace('im.onload=draw;',"im.onload=()=>{draw();c.dataset.loaded='true'};")
    if apply_approved:
        page=page.replace('补删点方案核对（尚未执行）','补删点执行结果与待选方案').replace('7份操作已具体化待批准；另5份需选方案或确认补点位置。','7份明确操作已写入本轮有效点修复层；另5份需选方案或确认补点位置。').replace('没有修改有效层、原始导出、GT或审核结论。','原始导出、GT和审核原件不变；旧3D和分簇未重算。').replace("r.readiness==='ready_for_approval'?'具体操作待批准'", "r.status==='applied_effective_override'?'已执行到本轮有效点修复层'")
    (OUT / 'index.html').write_text(page,encoding='utf-8')
    return dict(proposals=len(plans),applied=len(approved),needs_confirmation=5)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply-approved',action='store_true',help='仅应用用户2026-09-28明确批准的7份操作')
    print(build(parser.parse_args().apply_approved))
