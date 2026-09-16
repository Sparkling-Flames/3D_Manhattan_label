"""全648图同房与采集覆盖盘点；只生成候选证据，不更改采用或派发。"""
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from tools.thesis_main.analysis.build_stage1_image_packages_20260913 import exposure, VIEW

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/unassigned_room_inventory_20260915'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def write(name, rows):
    (OUT / (name+'.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    if isinstance(rows, list) and rows:
        with (OUT / (name+'.csv')).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader()
            for r in rows:
                w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list,dict)) else v for k,v in r.items()})


def main():
    OUT.mkdir(exist_ok=True)
    registry = read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    spatial = {r['image_id']: r for r in read('analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json')['images']}
    selected = read('analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json')
    package = read('analysis_results/stage1_person_image_packages_20260913_v2/分配建议与核验.json')
    followup = read('analysis_results/english_followup_pool_20260915/共用追加候选池.json')
    original_pool = {r['image_id'] for r in selected['images']}
    follow_ids = {r['image_id'] for r in followup['common_pool']+followup['personal_topup_only']}
    required = {r['image_id'] for r in package['assignments']}
    optional = {r['image_id'] for r in package['optional_pool'] if r['ready_for_import']}
    proposed = original_pool | follow_ids | required | optional | {r['image_id'] for r in package['optional_pool']}
    with gzip.open(VIEW, 'rt', encoding='utf-8') as f:
        records = [json.loads(l) for l in f]
    seen, pairs, sources = exposure(records)
    manual, semi, submitted = defaultdict(set), defaultdict(set), defaultdict(set)
    for r in records:
        w,iid = int(r['worker_id']),r['image_id']
        if w in {19,26}: continue
        if r['unassisted_manual_included']: manual[iid].add(w)
        if r['assistance_exposure']=='model_preannotation': semi[iid].add(w)
    for (w,iid),r in pairs.items():
        if r['submissions']: submitted[iid].add(w)
    supported = defaultdict(set)
    for g in registry['groups']:
        if g['raw_current'].get('physical_same')=='支持':
            for iid in g['image_ids']: supported[iid].add(g['review_code'])
    images = []
    group_states={g['review_code']:g['raw_current'].get('physical_same') for g in registry['groups']}
    for im in registry['images']:
        iid=im['image_id'];sp=spatial[iid];k=len(manual[iid])
        images.append(dict(image_id=iid,code=f'{im["building"]}-{im["number"]:02d}',building=im['building'],scene=sp['current_coarse_review']['value'],scene_source='current_coarse_review；不采用未确认的新模型建议',display_groups=im['group_codes'],supported_groups=sorted(supported[iid]),room_state='无同房展示组' if not im['group_codes'] else ('已有支持同房关系' if supported[iid] else '仅待定或不支持同房关系'),manual_people=k,manual_band='0' if k==0 else ('1—2' if k<=2 else ('3—7' if k<=7 else '8+')),semi_people=len(semi[iid]),submitters_all_ids=len(submitted[iid]),no_saved_submission_or_draft=not bool(seen[iid]),unseen_english=sorted(set(range(28,38))-seen[iid]),in_original_112=iid in original_pool,in_any_current_candidate_pool=iid in proposed,in_required=iid in required,in_H=iid in optional,in_followup_proposal=iid in follow_ids,oos_status=sp['oos_review']['status'],image_path=im['path']))
    lookup={r['image_id']:r for r in images}
    for r in images:
        r['group_physical_same_states']={g:group_states[g] for g in r['display_groups']}
    no_groups=[r for r in images if not r['display_groups']]
    unresolved=[r for r in images if r['display_groups'] and not r['supported_groups']]
    outside=[r for r in images if not r['in_any_current_candidate_pool']]
    candidates=[];high_history=[];fingerprints=set()
    allowed_oos={'未见人工OOS记录','人工明确非OOS'}
    for c in registry['candidates']:
        ids=c['image_ids'];fingerprint=tuple(sorted(ids))
        if fingerprint in fingerprints:continue
        fingerprints.add(fingerprint)
        if c['physical_same_supported'] and max(len(manual[i]) for i in ids)>=16:
            targets=[lookup[i] for i in ids if not lookup[i]['in_any_current_candidate_pool'] and lookup[i]['manual_people']<=7]
            if targets:
                high_history.append(dict(candidate=c['candidate_id'],codes=[lookup[i]['code'] for i in ids],manual_counts=[len(manual[i]) for i in ids],scene_counts=dict(Counter(lookup[i]['scene'] for i in ids)),outside_targets=[r['code'] for r in targets],new_to_all_english_targets=[r['code'] for r in targets if len(r['unseen_english'])==10],old_comparable=c['comparable_for_prediction'],old_decision=c['raw_decision'],hold_reasons=c['selection_hold_reasons'],oos_pending=c['oos_pending'],oos_by_image={lookup[i]['code']:lookup[i]['oos_status'] for i in ids},review_state=c['review_state']))
        if not c['physical_same_supported'] or not c['comparable_for_prediction'] or c['oos_pending'] or c['selection_hold_reasons']:continue
        if any(lookup[i]['oos_status'] not in allowed_oos for i in ids):continue
        targets=[lookup[i] for i in ids if not lookup[i]['in_any_current_candidate_pool'] and lookup[i]['manual_people']<=7]
        if not targets:continue
        k=[len(manual[i]) for i in ids]
        candidates.append(dict(candidate=c['candidate_id'],building=c['building'],codes=[lookup[i]['code'] for i in ids],scene_counts=dict(Counter(lookup[i]['scene'] for i in ids)),manual_counts=k,semi_counts=[len(semi[i]) for i in ids],outside_low_count_targets=[r['code'] for r in targets],zero_saved_targets=[r['code'] for r in targets if r['no_saved_submission_or_draft']],one_two_targets=[r['code'] for r in targets if 1<=r['manual_people']<=2],new_to_all_english_targets=[r['code'] for r in targets if len(r['unseen_english'])==10],difficulty_similarity=c['difficulty_similarity'],old_priority=c['raw_decision'],review_state=c['review_state'],has_high_history=max(k)>=16,room_views=len(ids),overlap_note='候选子集可能互有重叠，不计为独立房间总数',image_ids=ids))
    candidates.sort(key=lambda r:(not r['has_high_history'],r['difficulty_similarity']!='预期相近',-len(r['new_to_all_english_targets']),-r['room_views'],r['candidate']))
    standalone=[r for r in outside if not r['supported_groups'] and r['manual_people']<=7 and r['oos_status'] in allowed_oos]
    counts=dict(total_images=len(images),no_display_group=len(no_groups),only_unresolved_or_rejected=len(unresolved),supported_image_count=sum(bool(r['supported_groups']) for r in images),not_in_required_or_H=sum(not(r['in_required'] or r['in_H']) for r in images),outside_original_112=sum(not r['in_original_112'] for r in images),outside_all_current_pools=len(outside),outside_manual_bands=dict(Counter(r['manual_band'] for r in outside)),outside_no_saved_activity=sum(r['no_saved_submission_or_draft'] for r in outside),screened_room_subsets=len(candidates),standalone_cross_room_candidates=len(standalone),historical_export_files=len(sources),limits='无历史仅指本地已核查提交/草稿；新项目无导出，W035完成H按用户陈述，H已整体排除。可比性/OOS筛查非新的采用决定。场景/同房工作判断沿用人工记录，不重新作视觉裁定。')
    assert len(images)==648 and len(lookup)==648
    assert len(no_groups)+len(unresolved)+counts['supported_image_count']==648
    assert sum(counts['outside_manual_bands'].values())==len(outside)
    counts['high_history_extension_subsets']=len(high_history)
    assert all(not lookup[i]['in_any_current_candidate_pool'] for c in candidates for i in c['image_ids'] if lookup[i]['code'] in c['outside_low_count_targets'])
    for name,rows in [('全648图同房与分配明细',images),('无同房展示组图片',no_groups),('同房关系待定或不支持图片',unresolved),('候选池外图片',outside),('池外同房补标候选',candidates),('池外无支持同房的相似场景候选',standalone),('统计汇总',counts)]:write(name,rows)
    write('高人数历史与池外视角待核对',high_history)
    write('有同房关系但未进当前必做或H', [r for r in images if r['supported_groups'] and not(r['in_required'] or r['in_H'])])
    report=['# 全部648张图：同房关系与后续补标盘点','',
        '## 统计口径','',
        '统计截至2026-09-15的本地资料。历史人数按可纳入的独立手工标注、同图同人去重，排除W019/W026；W011已完成的历史仍保留。Semi另列，不混入Manual人数。0名Manual不等于从未标过：可能有Semi、不可纳入的提交或草稿。新Project G/H缺少最新本地导出，不能据本表认定线上尚未完成；两项目已整体从追加池排除。',
        '同房依据沿用现有人工核对记录；本次没有重新看图裁定。场景沿用空间复核表，不采用未确认的新模型建议。展示组、候选子集、独立物理房间不是同一个计数单位，重叠子集不能当作多个独立房间。','',
        '## 1. 哪些图片没有同房分组或标注分配','',
        f'- 无同房展示组：{len(no_groups)}张。是记录中没有配对，不等于物理上不存在其他视角。',
        f'- 有展示组，但没有受到支持的同房关系：{len(unresolved)}张。待定和不支持仍需区分，详见机器表。',
        f'- 至少存在一条受到支持的同房关系：{counts["supported_image_count"]}张。',
        '- 其中421张没有进入当前必做或H新增分配，逐图见“有同房关系但未进当前必做或H”。这不代表都应新增标注。',
        f'- 不在当前必做37张和H20张中的图片：{counts["not_in_required_or_H"]}张。这个数包含仅复用历史、已有追加候选和未采用图，不能叫作“遗漏”。','',
        '下面列出全部71张无展示组图片；括号是历史Manual人数。其余两类逐图名单见同目录JSON/CSV。','',
        '| building | 图片编号（历史人数） |','|---|---|']
    for b in sorted({r['building'] for r in no_groups}):
        report.append('| '+b+' | '+'、'.join(r['code'].split('-')[-1]+'（'+str(r['manual_people'])+'）' for r in no_groups if r['building']==b)+' |')
    report += ['', '## 2. 候选池之外还有多少图','',
        '原逐图候选复核表有112张，池外536张。进一步排除当前必做/H、曾提出的H候选和31+5追加候选后，池外共523张。下文按这个较宽的去重范围统计，避免把已经讨论的图片又推荐为新候选。','',
        '| 可纳入历史Manual人数 | 池外图片数 |','|---|---|']
    report += [f'| {b} | {n} |' for b,n in counts['outside_manual_bands'].items()]
    report += ['', '其中355张在已核查的24份历史导出中没有提交或草稿记录。371张是没有可纳入Manual，两个数字含义不同。','',
        '## 3. 可先核对的同房补标组合','',
        '下面52个候选子集沿用旧记录的同房支持及可比性条件，并暂缓存在OOS或其他待处理标记的组。它们是供复核的清单，未自动采用，也没有自动设定8/15人的目标。旧“预期相近”只表示视角间难度可能接近，不等于简单或已经证实少人数收敛。','',
        '优先看历史只有1–2人的组合（例如G059/G138/G260），以及3–5张视角齐全且大多对英文人员全新的组合（例如G001/G063/G068/G130）。补标应尽量让一个房间形成多张可比较图片，而不是只增加孤立图。','',
        '| 候选 | 图片（同一building内编号） | 对应Manual人数 | 场景 | 对10名英文人员均无历史接触的池外图数 |','|---|---|---|---|---|']
    for c in candidates:
        report.append(f'| {c["candidate"]} | {c["building"]}：'+ '/'.join(x.split('-')[-1] for x in c['codes'])+' | '+ '/'.join(map(str,c['manual_counts']))+' | '+ '、'.join(s if s is not None else '场景未定' for s in c['scene_counts'])+f' | {len(c["new_to_all_english_targets"])} |')
    report += ['', '## 4. 不应漏掉高人数历史图的其他视角','',
        '以下组合支持物理同房，已有高人数历史图，同时有池外0–7人视角。旧表对主空间/呈现范围的可比性、OOS等作了不同标记，逐项保留如下。范围不同本身不应自动否决同房预测研究：它也可能是预测效果变化的解释变量；但明确或疑似OOS仍应单独复核。这里没有推翻原采用决定。','',
        '| 候选 | 图片 | 对应Manual人数 | 旧暂缓原因 | OOS核对 |','|---|---|---|---|---|']
    for c in high_history:
        flags=[code+'：'+s for code,s in c['oos_by_image'].items() if s not in allowed_oos]
        report.append('| '+c['candidate']+' | '+' / '.join(c['codes'])+' | '+'/'.join(map(str,c['manual_counts']))+' | '+'；'.join(c['hold_reasons'])+' | '+('；'.join(flags) or ('组内待定' if c['oos_pending'] else '未见上述OOS标记，非新裁决'))+' |')
    report += ['', '## 5. 与研究目的的关系','',
        '同房预测：优先补齐已有历史的其他视角，再加入多视角的新房间。保留预期一致和预期有差异的房间，不能先按“看起来会预测成功”筛选。2人的历史不够单独判定稳定，但原始标注可以复用，补足后再随机重排检验。',
        f'相似场景预测：另有{len(standalone)}张池外、0–7人、暂无受到支持同房关系且无上述OOS标记的图片，已单列。可以用来增加不同物理房间的覆盖；它们不能自动算成{len(standalone)}个独立房间，须避免未知同房造成重复计算。卧室/厨房等按主要呈现空间，门洞属性单独核对。',
        '人员分类与AABC组合：追加任务要保留多名人员在同一批图片上的重叠。只让一个完成较快的人标整批可以先启动采集，但不能单凭他的这些结果检验类内或混合人群收敛，也不能以完成速度给他确定质量类别。',
        '稳定可以是统一共识，也可以是稳定的多个标法簇；实际低人数共识保留，不伪造额外人数。有效单人标法另留记录，不因为没有第二人重复就删除。难收敛是待观测现象，不是看到少人数、无标注或视角差异就可以事先认定。','',
        '本轮只完成盘点和候选证据整理，没有生成新的派发、import或Project。完整逐图明细提供图片路径、同房组号、各池身份、历史人数、Semi人数、英文未接触人员和OOS记录。','',
        '## 复算入口','',
        '`D:/anaconda/python.exe -m tools.thesis_main.analysis.audit_unassigned_rooms_20260915`。运行内置检查：648图唯一性、同房三类互斥完备、池外人数分档总和，以及追加目标未混入现有池。输入为同房registry、空间复核表、原选用表、当前分配包、追加候选池和历史计算视图及其导出来源；不改写输入。']
    (OUT/'盘点说明.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(counts,ensure_ascii=False))
    for c in candidates[:18]:print(json.dumps({k:v for k,v in c.items() if k!='image_ids'},ensure_ascii=False))


if __name__=='__main__':main()
