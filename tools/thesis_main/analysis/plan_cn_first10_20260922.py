"""中文9人首批各10图：终审人数、历史接触和探索性画像约束。"""
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from html import escape

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .build_collection_plan_20260921 import ROOT, CN, read

OUT = ROOT / 'analysis_results/cn_first10_20260922'
CURRENT = 'analysis_results/new_manual_reviewed_20260921'


def prepare():
    base = read('analysis_results/collection_plan_20260921/统计与安排.json')
    summary = read(CURRENT + '/SUMMARY.json')
    with gzip.open(ROOT / CURRENT / 'responses.jsonl.gz', 'rt', encoding='utf8') as f:
        responses = [json.loads(line) for line in f]
    seen = defaultdict(set)
    for r in responses:
        seen[r['image_id']].add(r['worker_id'])
    for path in ['historical_exposure.json', 'required_assignments.json']:
        for r in read('import_json/scene_stability_stage1_20260913_v2/' + path):
            seen[r['image_id']].add(f"W{r['worker_id']:03d}")
    raw = {}
    for source in summary['sources']:
        for task in read(source):
            iid = task['data']['base_task_id']
            for a in task['annotations']:
                seen[iid].add(f"W{a['completed_by']:03d}")
                raw[a['id']] = a
            for d in task['drafts']:
                match = re.search(r',\s*(\d+)\s*$', d.get('created_username', ''))
                if not match:
                    raise ValueError('草稿身份未知，不能忽略暴露')
                seen[iid].add(f'W{int(match[1]):03d}')
    # 终审派生视图必须仍对应当前导出；不静默消费被替换的旧文件。
    from .clustering_release.pipeline import raw_points
    for r in responses:
        if r['canonical_annotation_id'].startswith('new_'):
            a = raw[r['provenance']['annotation']]
            assert raw_points(a) == r['raw_points_1024x512']
    per = {r['identity']: r for r in read(CURRENT + '/per_image.json')}
    door = {r['image_id']: r for r in read('analysis_results/scene_image_exploration_20260910_v1/门洞人工与AI历轮核对_20260913.json')['rows']}
    candidates = []
    for r in base['images']:
        iid = r['image_id']; p = per.get(iid)
        n = p['manual_descriptive']['workers'] if p else 0
        predictive = p['unaided_prediction']['workers'] if p else 0
        old = r['october_low_sample'] and 0 < n < 12
        d = door[iid]; boundary = d['doorway']['current_working_label'] != '否'
        general = d.get('general_boundary') or ''
        boundary |= '交界' in general and '暂不归入' not in general
        note = (r['original_decision'] or {}).get('note', '')
        boundary |= '交界' in note
        new = (r['adopted'] and n == 0 and r['difficulty'] == '简单' and not boundary
               and (r['original_decision'] or {}).get('collection') == '需要新增标注')
        if old or new:
            candidates.append(dict(image_id=iid, code=r['code'], room=r['room'], image_path=r['image_path'],
                kind='旧图补足' if old else '已采用新图', current_n=n, predictive_n=predictive,
                capacity=12-predictive if old else 9, target=12 if old else 15,
                original_user=r['original_decision'], boundary=bool(boundary)))
    workers = [f'W{w:03d}' for w in CN]
    with (ROOT/'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_rosters.csv').open(encoding='utf-8-sig') as f:
        roster = list(csv.DictReader(f))
    profiles = {}
    for w in workers:
        counts = Counter(r['subtype'] for r in roster if r['worker'] == w and r['config'] == 'QT_3')
        label, support = counts.most_common(1)[0]
        profiles[w] = dict(stratum=label, support=support, folds=sum(counts.values()), memberships=dict(counts))
    return candidates, seen, profiles, summary['sources']


def allocate(candidates, seen, profiles):
    workers = list(profiles)
    edges = [(i,w) for i,r in enumerate(candidates) for w in workers if w not in seen[r['image_id']]]
    new_ids = [i for i,r in enumerate(candidates) if r['kind'] == '已采用新图']
    strata = sorted({p['stratum'] for p in profiles.values()})
    opens = {i:len(edges)+k for k,i in enumerate(new_ids)}
    cover = {(i,s):len(edges)+len(opens)+k for k,(i,s) in enumerate((i,s) for i in range(len(candidates)) for s in strata)}
    size = len(edges)+len(opens)+len(cover)
    rr, cc, vv, lower, upper = [], [], [], [], []
    def constraint(coeff, lo, hi):
        k=len(lower); lower.append(lo); upper.append(hi)
        for j,value in coeff.items(): rr.append(k); cc.append(j); vv.append(value)
    for w in workers:
        constraint({j:1 for j,(_,x) in enumerate(edges) if x==w},10,10)
        constraint({j:1 for j,(i,x) in enumerate(edges) if x==w and i in opens},1,10)
    for i,r in enumerate(candidates):
        indices={j:1 for j,(k,_) in enumerate(edges) if k==i}
        constraint(indices,0,r['capacity'])
        if i in opens: constraint({**indices,opens[i]:-9},-np.inf,0)
        for s in strata:
            constraint({**{j:1 for j,(k,w) in enumerate(edges) if k==i and profiles[w]['stratum']==s},cover[i,s]:-1},0,np.inf)
    objective=np.zeros(size)
    for j,(i,w) in enumerate(edges):
        objective[j]=(-10000 if i not in opens else 0)+i*1e-5+j*1e-8
    for j in opens.values(): objective[j]=100
    for j in cover.values(): objective[j]=-1
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(lower),size)).tocsr()
    result=milp(objective,integrality=np.ones(size),bounds=Bounds(0,1),
                constraints=LinearConstraint(matrix,lower,upper),options={'time_limit':60,'mip_rel_gap':0})
    if not result.success: raise RuntimeError(result.message)
    assignments=[dict(worker=w,**candidates[i]) for j,(i,w) in enumerate(edges) if result.x[j]>.5]
    assert len(assignments)==90 and Counter(a['worker'] for a in assignments)=={w:10 for w in workers}
    assert len({(a['worker'],a['image_id']) for a in assignments})==90
    assert all(a['worker'] not in seen[a['image_id']] for a in assignments)
    return assignments


def main():
    candidates,seen,profiles,sources=prepare()
    assignments=allocate(candidates,seen,profiles)
    counts=Counter(a['image_id'] for a in assignments)
    images=[dict(r,added=counts[r['image_id']],expected_n=r['current_n']+counts[r['image_id']],
                 expected_predictive_n=r['predictive_n']+counts[r['image_id']],
                 workers=[a['worker'] for a in assignments if a['image_id']==r['image_id']])
            for r in candidates if counts[r['image_id']]]
    for w in profiles:
        items=sorted([a for a in assignments if a['worker']==w],key=lambda a:(a['kind']=='已采用新图',a['room'],a['code']))
        # 同房图穿插，避免连续呈现；不宣称完全消除熟悉影响。
        ordered=[]
        while items:
            choice=next((a for a in items if not ordered or a['room']!=ordered[-1]['room']),items[0])
            ordered.append(choice);items.remove(choice)
        for k,a in enumerate(ordered,1): a['order']=k
    result=dict(schema='cn_first10_candidate_v1',sources=sources,reviewed_source=CURRENT,
        status='本地候选清单，未创建LS任务或派发；图片代码不是运行时任务编号',
        profiles=profiles,profile_note='9月20日QT_3留建筑模态，仅用于分配多样性；不是稳定人格或新数据重拟合',
        images=images,assignments=assignments,
        remaining=[dict(r,remaining=max(0,r['capacity']-counts[r['image_id']])) for r in candidates if r['kind']=='旧图补足' and counts[r['image_id']]<r['capacity']])
    OUT.mkdir(exist_ok=True)
    (OUT/'分配明细.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# 中文9人首批各10张Manual','',
      '优先旧低人数图到12，至少每人1张已采用新图；不等待英文或新人。以最新终审视图为基线，W006补交已接入。',
      'e9-26描述人数8，但其中1份借用补点，不借用补点的预测人数7；因此按缺5份计算，不把借用点当额外独立证据。预计人数以新作答通过同口径验收为条件。',
      '画像采用已有QT_3的留建筑模态作辅助，优化补标人员类别覆盖，不改变历史类别，不强制每图三类齐全，也不把类别数字当质量等级；9月22日共享x分析未重拟合这些类别。',
      '优化顺序：尽量兑现旧图缺口，其次少开新图，再增加各图补标人员的候选类别覆盖。新图本批不足15的缺口明确保留，不承诺尚未确认的人手。',
      '', '|人员|旧图|新图|图片（按安排顺序）|','|---|---:|---:|---|']
    for w in profiles:
        a=sorted([a for a in assignments if a['worker']==w],key=lambda x:x['order'])
        lines.append(f"|{w}|{sum(x['kind']=='旧图补足' for x in a)}|{sum(x['kind']=='已采用新图' for x in a)}|"+'、'.join(x['code'] for x in a)+'|')
    lines+=['','|图片|描述/预测基线人数|本批增加|预计描述/预测人数|','|---|---:|---:|---:|']
    for r in images: lines.append(f"|{r['code']}|{r['current_n']}/{r['predictive_n']}|{r['added']}|{r['expected_n']}/{r['expected_predictive_n']}|")
    lines+=['','完整原文、逐人候选画像、逐图人员和剩余缺口见JSON；浏览版可按人员查看图片。',
      '本批74份旧图＋16份新图，共19张图片。15张旧图预计预测人数达到12；Z6-02与wc-54各到11（9人中各仅6人未接触），各余1份留待其他人员。两张新图2t7-02/03分别9人、7人，距离15人分别缺6、8；不把本次作为15人终点验收。',
      '验证：pytest tests/test_plan_cn_first10_20260922.py；检查每人10、90唯一人图、历史接触排除、旧图容量、借用补点口径及剩余缺口。图像路径存在性已核对；HTML仅内容检查，未做浏览器视觉验收。',
      '本轮不改导出、分簇、正式协议、LS配置或线上数据。仅生成候选，不包含GT、别人标注或画像的标注员任务页。实际导入和任务ID绑定尚未执行。']
    (OUT/'分配说明.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    html=['<!doctype html><meta charset="utf-8"><title>中文首批10图分配预览</title><style>body{font:16px system-ui;max-width:1200px;margin:30px auto}img{width:100%}summary{padding:14px;background:#eef3fa;cursor:pointer}figure{margin:18px 0}</style><h1>中文9人首批各10图：候选预览</h1><p>每人10张Manual；图片代码不是LS任务编号，尚未派发。展开人员查看原图和顺序。</p>']
    for w in profiles:
        html.append(f'<details><summary>{w} · 10张</summary>')
        for a in sorted([a for a in assignments if a['worker']==w],key=lambda x:x['order']):
            path='../../'+a['image_path'].replace('\\','/')
            assert (ROOT/a['image_path']).is_file()
            html.append(f'<figure><figcaption>{a["order"]}. {escape(a["code"])} · {a["kind"]}</figcaption><img loading="lazy" src="{escape(path,quote=True)}" alt="{escape(a["code"])}"></figure>')
        html.append('</details>')
    (OUT/'分配预览.html').write_text('\n'.join(html),encoding='utf8')
    print(json.dumps(dict(tasks=len(assignments),images=len(images),kinds=Counter(a['kind'] for a in assignments),remaining=result['remaining']),ensure_ascii=False))


if __name__=='__main__': main()
