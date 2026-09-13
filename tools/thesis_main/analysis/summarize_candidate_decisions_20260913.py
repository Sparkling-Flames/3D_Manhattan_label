"""按用户明确选用、人数备注与排除人员复算；不生成派发清单。"""
import argparse
import csv
from copy import deepcopy
import gzip
import json
import re
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'
SPATIAL = ROOT / 'analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json'
VIEW = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
EXCLUDED = {19, 26}
UPPER = {'0–8人': 8, '9–15人': 15, '16–20人': 20}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def apply_confirmations(original, confirmation):
    assert confirmation['schema'] == 'candidate_selection_user_confirmation_v1'
    effective = deepcopy(original)
    for c in confirmation['confirmations']:
        matches = [r for r in effective[c['target']]
                   if all(r[k] == v for k, v in c['selector'].items())]
        assert len(matches) == 1, c['selector']
        row = matches[0]
        assert all(row[k] == v for k, v in c['before'].items()), c['selector']
        row.update(c['after'])
    return effective


def oos_disposition(im, events):
    review = im['oos_review']
    direct = [events[e] for e in review['image_event_ids']]
    context = [events[e] for e in review['context_event_ids']]
    assert all(im['image_id'] in e['image_ids'] for e in direct)
    states = {e['state'] for e in direct}
    if '明确OOS' in states and '明确非OOS' not in states:
        disposition = '明确OOS排除'
    elif states & {'疑似', '存在争议', '局部待定位', '明确OOS'} or any(e['state'] == '局部待定位' for e in context):
        disposition = 'OOS待核实'
    else:
        disposition = '保留候选'
    return dict(disposition=disposition, review=review, direct_evidence=direct,
                context_evidence=context,
                note='仅本轮补充候选筛选；无OOS记录不等于已确认可标，疑似不当作明确OOS。')


def spatial_context(im, events):
    new = im['new_spatial_review']
    # 只整理已明确写出的主空间，其他沿用当前粗类；不按可见物体关键词猜类别。
    main_to_coarse = {'壁炉沙发起居区': '起居与休闲', '卧室为主': '卧室',
                      '卫浴为主': '卫浴', '长餐桌区及厨房开口': '厨房与用餐',
                      '上层卫浴入口': '卫浴'}
    current = im['current_coarse_review']['value']
    scene = main_to_coarse.get(new['main_space'], current)
    if scene in [None, '无法判断', '开放复合空间'] or '主区域待定' in new['main_space']:
        scene = '主空间待定'
    return dict(scene=scene,
                scene_basis='主要呈现空间的分析整理；原人工粗类及AI描述分别保留，不新增人工确认',
                spatial_source=str(SPATIAL),
                spatial_classification_original=im['spatial_classification'],
                current_coarse_review=im['current_coarse_review'],
                new_spatial_review=new,
                main_visual_space=new['main_space'],
                doorway=im['doorway_reconciliation']['current_working_label'],
                doorway_source=im['doorway_reconciliation']['source'],
                doorway_review=im['doorway_reconciliation'],
                oos=oos_disposition(im, events))


def plan_counts(decision, history_n, clean_n):
    target, basis = history_n, '仅复用：保留实际历史人数，空人数不作零'
    if decision['collection'] == '需要新增标注':
        target = UPPER[decision['target_band']]
        basis = '区间上限'
        note = decision['note'].strip()
        override = re.search(r'(?:补到|^)(\d+)人(?:尝试)?$', note)
        if override:
            target, basis = int(override[1]), '用户备注明确人数'
        elif re.search(r'\d+人', note):
            raise ValueError('人数备注需明确解释：' + note)
    elif decision['collection'] != '仅复用历史':
        raise ValueError('采用图采集安排仍未确定')
    planned = max(history_n, target)
    return dict(requested_endpoint=target, endpoint_basis=basis,
                planned_manual=planned, new_needed=planned-history_n,
                current_roster_cap=history_n+clean_n,
                capacity_shortfall=max(0, planned-history_n-clean_n),
                spare_people_at_target=max(0, history_n+clean_n-planned))


def aggregate(rows, field):
    grouped = defaultdict(list)
    for r in rows:
        grouped[r[field]].append(r)
    result = []
    for key, rr in grouped.items():
        result.append(dict(category=key, images=len(rr),
                           groups=len({r['group'] for r in rr}),
                           buildings=len({r['building'] for r in rr}),
                           **{f: sum(r[f] for r in rr) for f in [
                               'history_manual', 'history_raw_manual', 'history_semi',
                               'new_needed', 'planned_manual', 'capacity_shortfall']}))
    return result


def table(rows, columns):
    return '\n'.join(['| ' + ' | '.join(title for _, title in columns) + ' |',
                       '| ' + ' | '.join('---' for _ in columns) + ' |'] +
                      ['| ' + ' | '.join(str(r[k]).replace('|', '／').replace('\n', ' ') for k, _ in columns) + ' |' for r in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decisions', required=True, type=Path)
    parser.add_argument('--confirmations', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'analysis_results/candidate_selection_review_20260913_v2')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    source = args.decisions.read_bytes()
    snapshot = out/'用户审查原始记录.json'
    if snapshot.exists() and snapshot.read_bytes() != source:
        raise ValueError('已有用户快照与本次输入不同，请用新输出目录')
    snapshot.write_bytes(source)
    original_decisions, registry = read(args.decisions), read(REGISTRY)
    confirmation = read(args.confirmations)
    decisions = apply_confirmations(original_decisions, confirmation)
    original_user_rows = {d['image_id']: d for d in original_decisions['decisions']}
    spatial = read(SPATIAL)
    assert spatial['schema'] == 'spatial_dimensions_human_history_v2'
    events = {e['event_id']: e for e in spatial['oos_events']}
    assert decisions['schema'] == 'candidate_review_user_decisions_v5'
    assert decisions['budget_basis'] == 'pooled'
    payload = read(ROOT/'analysis_results/candidate_review_20260912_v2/candidate_payload.json')
    original = {r['image_id']: r for r in payload['images']}
    assert len(decisions['decisions']) == len(original) == 112
    assert len({r['image_id'] for r in decisions['decisions']}) == 112
    groups = {r['group']: r for r in decisions['groups']}
    assert set(groups) == {r['group'] for r in payload['groups']} and len(groups) == len(decisions['groups']) == 22
    images = {r['image_id']: r for r in spatial['images']}
    assert len(images) == len(spatial['images']) == 648
    assert set(images) == {r['image_id'] for r in registry['images']}
    active = set(decisions['participants'])
    assert not active & (EXCLUDED | {11}) and len(active) == 19
    with (ROOT/'analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_worker_roster.csv').open(encoding='utf-8-sig', newline='') as f:
        languages = {int(r['annotator_id']): r['language'] for r in csv.DictReader(f)}
    assert Counter(languages[w] for w in active) == {'en': 10, 'zh': 9}
    by_image = defaultdict(list)
    with gzip.open(VIEW, 'rt', encoding='utf-8') as f:
        records = [json.loads(line) for line in f]
    assert len(records) == len({r['canonical_annotation_id'] for r in records}) == 2501
    for r in records:
        by_image[r['image_id']].append(r)

    def history(iid):
        raw = by_image[iid]
        rr = [r for r in raw if int(r['worker_id']) not in EXCLUDED]
        manual = [r for r in rr if r['unassisted_manual_included']]
        assert len(manual) == len({int(r['worker_id']) for r in manual})
        semi = {int(r['worker_id']) for r in rr if r['assistance_exposure'] == 'model_preannotation'}
        raw_manual = {int(r['worker_id']) for r in rr if r['assistance_exposure'] == 'none'}
        clean = active - {int(r['worker_id']) for r in raw}
        return dict(history_manual=len(manual), history_raw_manual=len(raw_manual), history_semi=len(semi),
                    manual_workers=sorted(int(r['worker_id']) for r in manual),
                    semi_workers=sorted(semi), clean_workers=sorted(clean),
                    clean_english=sum(languages[w] == 'en' for w in clean),
                    clean_chinese=sum(languages[w] == 'zh' for w in clean),
                    manual_ids=sorted(r['canonical_annotation_id'] for r in manual))

    rows = []
    for d in decisions['decisions']:
        iid = d['image_id']
        assert (d['group'], d['number']) == (original[iid]['group'], original[iid]['number'])
        im, g = images[iid], groups[d['group']]
        assert d['selection'] in ['待定', '采用', '备选', '不采用']
        assert g['adoption'] in ['待定', '建议采用', '满足条件后采用', '暂不采用']
        status = ('确定采用' if g['adoption'] == '建议采用' else '条件采用' if g['adoption'] == '满足条件后采用' else '整组待定') if d['selection'] == '采用' else '图片'+d['selection']
        h = history(iid)
        plan = plan_counts(d, h['history_manual'], len(h['clean_workers'])) if d['selection'] == '采用' else {}
        rows.append(dict(image_id=iid, group=d['group'], number=d['number'], building=im['building'],
                         original_user_record=original_user_rows[iid], effective_user_record=d,
                         **spatial_context(im, events),
                         status=status, selection=d['selection'], group_adoption=g['adoption'],
                         collection=d['collection'], difficulty=d['difficulty'], target_band=d['target_band'],
                         image_note=d['note'], group_note=g['note'], preliminary_purposes=g['purposes'],
                         **h, **plan))
    main_rows = [r for r in rows if r['status'] == '确定采用']
    conditional = [r for r in rows if r['status'] == '条件采用']
    pending = [r for r in rows if r['status'] == '整组待定']
    scene = aggregate(main_rows, 'scene')
    totals = aggregate(main_rows, 'status')[0]
    assert sum(r['planned_manual'] for r in scene) == totals['history_manual'] + totals['new_needed']
    cap_rows = [r for r in main_rows if r['capacity_shortfall']]
    partial = [r for r in main_rows if r['new_needed'] and not r['spare_people_at_target']]
    supplemental = []
    selected_ids = {r['image_id'] for r in main_rows}
    for im in spatial['images']:
        doorway = im['doorway_reconciliation']
        if doorway['current_working_label'] not in ['确认', '疑似'] or im['image_id'] in selected_ids:
            continue
        supplemental.append(dict(image_id=im['image_id'], building=im['building'], number=im['number'],
                                 **spatial_context(im, events), path=im['path'],
                                 group_codes=im['group_codes'], **history(im['image_id'])))
    supplemental.sort(key=lambda r: (r['doorway'] != '确认', r['building'], r['number']))
    retained = [r for r in supplemental if r['oos']['disposition'] == '保留候选']
    oos_hold = [r for r in supplemental if r['oos']['disposition'] == 'OOS待核实']
    oos_excluded = [r for r in supplemental if r['oos']['disposition'] == '明确OOS排除']
    q_path = ROOT/'analysis_results/multibuilding_threshold_stability_20260909_v1/revised/without_workers/geometry/full_q_partitions.csv'
    with q_path.open(encoding='utf-8-sig', newline='') as f:
        saved_q = {r['image_id']: r for r in csv.DictReader(f) if float(r['threshold']) == .95}
    q_rows = []
    for r in main_rows:
        if not r['history_manual']:
            continue
        q = saved_q[r['image_id']]
        ids = {i for c in json.loads(q['candidate_partitions_json']) for cluster in c for i in cluster}
        assert ids <= set(r['manual_ids'])
        assert len(r['manual_ids']) == int(q['pointset_n']) and len(r['manual_ids'])-len(ids) == int(q['q_invalid_n'])
        q_rows.append(dict(group=r['group'], number=r['number'], n=r['history_manual'],
                           status=q['partition_status'],
                           status_display={'unique':'分簇结果唯一', 'not_evaluable':'分簇结果无法确定'}[q['partition_status']],
                           q_invalid=int(q['q_invalid_n']),
                           singletons=int(float(q['singleton_clusters'])) if q['singleton_clusters'] else None,
                           supported=int(float(q['supported_m2_clusters'])) if q['supported_m2_clusters'] else None,
                           note='既有q=.95完整历史分区；q可计算不等于3D合理，分区不等于持续稳定'))
    result = dict(schema='candidate_selection_planning_v2', status='DESIGN_REVIEW_NOT_ASSIGNMENT',
                  source_user=original_decisions, user_confirmations=confirmation,
                  effective_groups=decisions['groups'], spatial_source=str(SPATIAL),
                  source_decisions=str(args.decisions), registry=str(REGISTRY), calculation_view=str(VIEW),
                  excluded_workers=sorted(EXCLUDED), future_workers=sorted(active), totals=totals,
                  scene_totals=scene, difficulty_totals=aggregate(main_rows, 'difficulty'),
                  group_totals=aggregate(main_rows, 'group'), doorway_totals=aggregate(main_rows, 'doorway'),
                  conditional_totals=aggregate(conditional, 'scene'), pending_group_totals=aggregate(pending, 'scene'),
                  images=rows, capacity_shortfall_images=cap_rows,
                  no_dropout_spare_images=[(r['group'],r['number']) for r in partial],
                  existing_q_partitions=q_rows,
                  supplementary_doorway_candidates=retained,
                  supplementary_doorway_oos_hold=oos_hold,
                  supplementary_doorway_oos_excluded=oos_excluded,
                  supplementary_doorway_all_records=supplemental,
                  supplementary_clean_images_per_english_worker={str(w): sum(w in r['clean_workers'] for r in retained) for w in sorted(active) if languages[w]=='en'},
                  unresolved_user_corrections=[],
                  analysis_guidance=dict(
                      common_count_required_for_convergence=False,
                      observed_eight_person_valid_consensus='可判为收敛／统一共识，不要求补到20人或另观察5人；8是已明确例子，不是每图最低人数',
                      actual_counts_only=True, supported_cluster_min_distinct_people=2,
                      different_point_counts_must_separate=True,
                      valid_singletons='保留为未复现标法，不能因为不足2人而删除',
                      stable_multiple_clusters='仍属于稳定阶段',
                      convergence_status_recomputed=False),
                  limits='计划完成量，不是最终结果或保证；原始失败、Semi与Manual分列；研究用途暂选不作过滤。')
    assert result['source_user'] == read(snapshot)
    (out/'选用复核机器表.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    scene_cols = [('category','场景类型'),('images','图片'),('groups','展示组'),('buildings','楼'),('history_manual','已有Manual'),('new_needed','拟新增Manual'),('planned_manual','计划Manual总量'),('history_semi','另有Semi')]
    report = '# 选图结果、场景样本量与后续设计\n\n2026-09-13；排除W019／W026，不生成具体派发。每份指一个人对一张图的一次作答，不是不同人员或独立房间总数。\n\n'
    report += f"确定采用{totals['groups']}组{totals['images']}图，历史可用无辅助Manual {totals['history_manual']}份，拟新增{totals['new_needed']}份，计划达到{totals['planned_manual']}份；Semi {totals['history_semi']}份单列。\n\n"
    report += '## 各场景计划样本量\n\n'+table(scene,scene_cols)+'\n\n'
    report += '这里按主要呈现空间整理统计类：G015四图由旧“开放复合空间”整理为起居与休闲，G090-11按最新“卧室为主”整理为卧室；G207四图主要功能未明，合为主空间待定。原人工值、最新AI描述和分析归类分开保存，不新增人工确认。门洞是另一个交叉属性；图像里看得到的邻区不自动成为主类。同一展示组可含多类，组数跨行不可相加，也不冒称独立房间数。新增量假定达到所选上限或备注人数，未来缺失、无效作答和尚未招募人员均未兑现。\n\n'
    group_cols = [('category','组号')] + scene_cols[1:]
    report += '## 条件采用与未决采用\n\n'+table(aggregate(conditional,'group'),group_cols)+'\n\n'
    if pending:
        report += table(aggregate(pending,'group'),group_cols)+'\n\n'
    report += 'G165已由用户确认整组采用；G027-11已确认采用且仅复用历史，均计入本版主表。原填写未覆盖，确认原话另存。G014整组条件采用，但4图均待定，尚不计入。研究用途勾选仅作初步意向，不限制后续分析。\n\n'
    report += '## 当前人手达不到区间上限的图片\n\n'+table(cap_rows,[('group','组'),('number','图号'),('history_manual','历史'),('planned_manual','目标'),('current_roster_cap','现有人手最多'),('capacity_shortfall','差额')])+'\n\n'
    report += f'上述差额合计{sum(r["capacity_shortfall"] for r in cap_rows)}人图，不表示要招同样数量的人；同一新增人员可完成不同图片。{len(partial)}张拟补标图达到目标时无剩余现有人员可替补（含尚不可达图）。这是每图人员容量检查，未作逐人负载匹配。\n\n'
    report += '## 按难度与房间组复核工作量\n\n'+table(aggregate(main_rows,'difficulty'),[('category','预期难度')]+scene_cols[1:])+'\n\n'
    report += table(aggregate(main_rows,'group'),group_cols)+'\n\n'
    report += '## 人数例外与历史数据\n\n'+table([r for r in rows if r.get('endpoint_basis')=='用户备注明确人数'],[('group','组'),('number','图'),('status','采用状态'),('requested_endpoint','备注目标'),('history_manual','历史'),('new_needed','补充量')])+'\n\n'
    report += '仅复用历史图的空人数不作零；已有历史超过所填档位不删减。G237-26虽填需要新增，但排除后已有24人，高于8人计划，不再凭该填写新增。G207-40与G090-03仅有Semi，不能算成无辅助Manual；拟采用图的全部原始无辅助作答（含未进入计算视图）为'+str(totals['history_raw_manual'])+'份，计算视图仅计'+str(totals['history_manual'])+'份。后者不是3D正确数量，原始异常在质量／失败通道保留。\n\n'
    report += '## 已有单人标法证据\n\n'+table(q_rows,[('group','组'),('number','图'),('n','人数'),('status_display','分簇情况'),('singletons','单人组'),('supported','至少2人簇'),('q_invalid','无法计算几何相似度的作答')])+'\n\n'
    report += '这些是排除指定人员后的既有完整历史分区，不是本轮重新验证的3D或持续收敛结果。具体科学解释、30＋20工作量与低人数处理见[设计分析](设计分析.md)。\n\n'
    report += f'## 门洞补充候选与OOS复核\n\n当前确定采用之外的{len(supplemental)}张门洞确认／疑似记录，按历轮人工OOS范围排除{len(oos_excluded)}张，另{len(oos_hold)}张暂缓待核实，保留{len(retained)}张作为可进一步选择的候选；不表示全部要标。无OOS记录也不等于已确认可标。\n\n'
    oos_rows = [dict(building=r['building'], number=r['number'], doorway=r['doorway'],
                     disposition=r['oos']['disposition'], evidence='；'.join(e['text'] for e in r['oos']['direct_evidence']))
                for r in oos_excluded+oos_hold]
    report += table(oos_rows,[('building','楼'),('number','图号'),('doorway','门洞记录'),('disposition','本轮处理'),('evidence','人工原话')])+'\n\n'
    report += 'G014的明确OOS评论只作用于该组；G015四图有明确“不是oos”的原话，不能因壁炉凸起改为OOS。G196评论只说uNb-42疑似，不能传给61／82；wc-09／35／64的疑似意见也不扩及整栋。一般空间交界（如G179-10）与相机位于门洞分别保留，不扩充成确认门洞。见[更正后预览](门洞补充候选预览.html)。\n\n'
    report += '## 8人共识与原话保留\n\n实际8名独立人员已形成有效的统一标法，可以在本研究中判为“收敛／统一共识”，不以补到20人、统一截到共同人数或额外观察5人为前提。预期简单和计划8人不能自动生成这个结果；仍记录真实人数、单人标法和失败情况。收敛状态与确切起点分开：截至8人已收敛，不等于一定从第8人才开始。详见[本轮解释](设计分析.md)。\n\n'
    report += '新[机器表](选用复核机器表.json)完整保留source_user、逐图original_user_record、补充确认原话与effective_user_record。原JSON逐字节保存，最新主要空间、门洞与OOS来源单独连接；尚未重新运行收敛或预测实验。\n'
    (out/'样本量与复算报告.md').write_text(report, encoding='utf-8')
    cards=defaultdict(list)
    for r in supplemental:
        evidence = r['oos']['direct_evidence']+r['oos']['context_evidence']
        quotes = ''.join('<blockquote>'+escape(e['text'])+'</blockquote>' for e in {e['event_id']:e for e in evidence}.values())
        new = r['new_spatial_review']
        relations = ''.join('<li>'+escape(f"{p['region_a']}与{p['region_b']}：{p['relation']}。{p['evidence']}")+'</li>' for p in new['relations'])
        details = '<p>可见功能区：'+escape('、'.join(new['functional_regions']))+'</p><ul>'+relations+'</ul>'
        old_scene = r['current_coarse_review']['value'] or '未定'
        cards[r['oos']['disposition']].append(f'<article><h2>{escape(r["building"])} · {r["number"]:02} · 门洞{escape(r["doorway"])}</h2><a href="../../{escape(r["path"],quote=True)}" target="_blank"><img loading="lazy" alt="{escape(r["building"])}第{r["number"]}张全景图" src="../../{escape(r["path"],quote=True)}"></a><p><b>主要呈现空间：{escape(r["main_visual_space"])}</b></p><p>{escape(r["oos"]["review"]["status"])}；无辅助历史 {r["history_manual"]}份／半自动历史 {r["history_semi"]}份；可新增英文人员{r["clean_english"]}人</p><details><summary>来源、区域关系与复核原话</summary>{details}<p>原粗类：{escape(old_scene)}；门洞来源：{escape(r["doorway_source"])}；组号 {escape(str(r["group_codes"]))}</p>{quotes}</details></article>')
    html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>门洞补充候选｜已接续OOS复核</title><style>body{font:16px "Microsoft YaHei",sans-serif;max-width:1400px;margin:24px auto;padding:16px;background:#eef2f4}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}article{background:white;padding:16px;border-radius:8px}img{width:100%;height:auto}h2{font-size:18px}p{line-height:1.7}summary{cursor:pointer;padding:10px 0}blockquote{white-space:pre-wrap;border-left:3px solid #bbb;padding-left:12px}@media(max-width:800px){main{grid-template-columns:1fr}}</style><h1>门洞补充候选｜已接续OOS复核</h1>'
    html += f'<p>保留候选{len(retained)}张；OOS待核实{len(oos_hold)}张；明确OOS排除{len(oos_excluded)}张。此页只提供选择范围，不表示全部采用。</p><details><summary>查看判定口径</summary><p>主要呈现空间、可见功能区、区域关系及相机门洞位置分别记录。主空间描述沿用最新AI续审，人工来源另列；未重新裁定全部原图。无OOS记录不等于已确认可标，疑似OOS暂缓，明确OOS从本轮补充候选排除。一般交界不自动当作门洞。</p></details><main>'+''.join(cards['保留候选'])+'</main>'
    for label in ['OOS待核实', '明确OOS排除']:
        html += f'<details><summary>{label}（{len(cards[label])}张，展开查看原记录）</summary><main>'+''.join(cards[label])+'</main></details>'
    html += '</html>'
    (out/'门洞补充候选预览.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(totals=totals,conditional=aggregate(conditional,'group'),pending=aggregate(pending,'group'),no_spare=len(partial),doorway=aggregate(main_rows,'doorway'),supplemental=len(retained),oos_hold=len(oos_hold),oos_excluded=len(oos_excluded),supplemental_english=result['supplementary_clean_images_per_english_worker']),ensure_ascii=False))


if __name__ == '__main__':
    main()
