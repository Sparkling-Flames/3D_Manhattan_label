"""归档人工问卷，核对CSV/JSON，连接已人工撰写的AI视觉观察；不产生裁决。"""
import argparse
from collections import Counter
import csv
import html
import json
import os
from pathlib import Path

FIELDS = 'case_id image_id visibility scope human_difference annotation_assessment oos_assessment oos_reason factors notes status updated_at ai_advice_opened'.split()
LABELS = dict(visibility='可读性', scope='范围判断', human_difference='真人之间',
              oos_assessment='OOS意见', status='记录状态', factors='问题因素')
SCOPE_KINDS = dict(semantic_assignment='原文明确归类', potential_scope='潜在范围／预想',
                   observed_extent='已显示的范围描述', output_comparison='输出比较',
                   rule_condition='规则条件／偏好', scope_uncertainty='范围不确定性意见')
VALUES = dict(clear='看得清', partial='部分看得清', insufficient='信息不足',
              one_clear='有较明确范围', multiple_candidates='多个候选范围', rule_unclear='规则不清', uncertain='不确定',
              similar='大致相似', local='局部点位／结构', scope='范围', mixed='多种差异', not_applicable='不适用',
              some_plausible='至少一份可作候选', all_questionable='所有展示标注均有疑问', not_all_checked='未检查全部',
              in_scope='暂认为范围内', suspected='疑似OOS', reviewer_oos='审核者认为OOS',
              draft='草稿', deferred='暂缓', reviewed='本轮记录完成', reference='参考疑问', sequence='顺序',
              occlusion='遮挡', rule='规则', assumptions='几何假设')


def csv_value(value):
    if isinstance(value, list):
        value = '|'.join(value)
    elif isinstance(value, bool):
        value = str(value).lower()
    else:
        value = '' if value is None else str(value)
    return "'" + value if value[:1] in ('=', '+', '-', '@', '\t', '\r') else value


def unique(rows):
    result = {}
    for row in rows:
        case = row['case_id']
        if case in result:
            raise ValueError('duplicate case_id: ' + case)
        result[case] = row
    return result


def reconcile(bundle, csv_rows, identities, notes):
    if bundle.get('schema') != 'panorama_human_review_v1':
        raise ValueError('unknown questionnaire schema')
    records, csv_index, note_index = unique(bundle['records']), unique(csv_rows), unique(notes)
    if set(records) != set(csv_index) or set(records) != set(note_index) or set(records) != set(identities):
        raise ValueError('case identity coverage mismatch')
    joined, differences = [], []
    for case, record in sorted(records.items()):
        if record['image_id'] != identities[case] or csv_index[case]['image_id'] != identities[case]:
            raise ValueError('image identity mismatch: ' + case)
        if set(csv_index[case]) != set(FIELDS):
            raise ValueError('CSV fields mismatch')
        if set(record['answers']) != set(FIELDS) - {'case_id', 'image_id', 'updated_at', 'ai_advice_opened'}:
            raise ValueError('answer fields mismatch')
        if note_index[case].get('final_user_decision') is not None:
            raise ValueError('AI notes must not fill final_user_decision')
        for key in FIELDS:
            expected = csv_value(record['answers'].get(key, record.get(key)))
            if csv_index[case][key] != expected:
                differences.append(dict(case_id=case, field=key, json_csv_value=expected, csv_value=csv_index[case][key]))
        joined.append(dict(case_id=case, image_id=record['image_id'], human_record=record,
                           ai_followup=note_index[case], final_user_decision=None))
    return joined, differences


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def attach_scope_readings(rows, readings):
    """只连接人工阅读提取，不从模型名、候选选项或缺失评语推断范围。"""
    indexed = unique(readings)
    if set(indexed) != {r['case_id'] for r in rows}:
        raise ValueError('scope reading identity mismatch')
    for row in rows:
        reading = indexed[row['case_id']]
        if reading['final_user_decision'] is not None:
            raise ValueError('final decision must stay empty')
        seen = set()
        for s in reading['scope_statements'] + reading['quality_excerpts']:
            field = s['source_field']
            if field not in ('notes', 'oos_reason') or not s['quote'] or s['quote'] not in row['human_record']['answers'][field]:
                raise ValueError('quote not found in human text: ' + row['case_id'])
        for s in reading['scope_statements']:
            if s['statement_id'] in seen or s['kind'] not in SCOPE_KINDS:
                raise ValueError('duplicate statement or unknown kind')
            seen.add(s['statement_id'])
            if s['scope_label'] not in (None, 'enclosed', 'extended') or ((s['kind'] == 'semantic_assignment') != (s['scope_label'] is not None)):
                raise ValueError('semantic labels require explicit semantic assignment')
            if s['final_user_decision'] is not None or s['annotation_ids']:
                raise ValueError('decision or annotation identity cannot be auto-filled')
        row['scope_reading'] = reading


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def archive(source, target):
    data = source.read_bytes()
    if target.exists() and target.read_bytes() != data:
        raise ValueError('refuse to replace different archived source: ' + str(target))
    target.write_bytes(data)
    if target.read_bytes() != data:
        raise ValueError('archive byte mismatch')


def report(rows, out, review):
    esc = html.escape
    cards = []
    ordered = sorted(rows, key=lambda r: ({'user':0,'assistant':1,'rule':2,'none':3}[r['ai_followup']['next_action']['actor']], not r['ai_followup']['next_action']['required_now'], r['case_id']))
    for r in ordered:
        case, a, n = r['case_id'], r['human_record']['answers'], r['ai_followup']
        action = n['next_action']
        supplement = r.get('human_supplement')
        supplement_html = ''
        if supplement:
            supplement_html = f'<section class="supplement"><h3>2026-09-08 你的补充原文（当前意见）</h3><blockquote>{esc(supplement["original_text"])}</blockquote><p><b>整理理解：</b>{esc(supplement["assistant_interpretation"])}</p><p>{esc(supplement["interpretation_limits"])}</p></section><p class="quality"><b>以下为补充之前的问卷选项、原评语及旧解读，保留历史。旧文字里的“尚未说明／待确认”不再构成当前待办；当前意见以上方补充为准。</b></p>'
        folder = review / 'cases' / case
        link = lambda p: Path(os.path.relpath(p, out)).as_posix()
        fields = []
        for key, label in LABELS.items():
            value = a[key]
            value = '、'.join(VALUES.get(v, v) for v in value) if isinstance(value, list) else VALUES.get(value, value)
            fields.append(f'<span><b>{label}：</b>{esc(value or "未填写")}</span>')
        images = ''.join(f'<a href="{esc(link(folder / f), quote=True)}">{esc(f)}</a> ' for f in n['evidence_viewed'])
        reading = r['scope_reading']
        statements = ''.join(f'<tr><td>{esc(SCOPE_KINDS[s["kind"]])}<br><b>{esc(s["target"])}</b></td><td class="quote">{esc(s["quote"])}</td><td>{esc(s["interpretation"])}<br><small>{esc(s["qualification"])}</small></td></tr>' for s in reading['scope_statements'])
        scope_html = ('<div class="table-scroll"><table class="scope-table"><thead><tr><th>描述对象与性质</th><th>你的原句</th><th>我的整理（待确认）</th></tr></thead><tbody>' + statements + '</tbody></table></div>') if statements else '<p>本条评语没有明确的范围解释条目。留空，不根据模型头名称或旧选项补成enclosed／extended。</p>'
        quality = '；'.join(esc(q['quote']) for q in reading['quality_excerpts']) or '本栏未摘录单独的质量表述；不表示标注没有问题。'
        legacy = VALUES.get(a['annotation_assessment'], a['annotation_assessment']) or '未填写'
        action_class = 'question' if action['actor'] == 'user' else 'quality'
        cards.append(f'''<article id="{case}"><h2>{case} · {esc(action['state'])}</h2>
<div class="next-action {action_class}" data-actor="{action['actor']}"><b>{esc(action['task'])}</b><br>{esc(action['how_to_answer'])}</div>
{supplement_html}
<div class="fields">{''.join(fields)}</div>
<h3>你的原文（不改写）</h3><blockquote>{esc(a['notes'] or '（评语空白）')}</blockquote>
<p><b>OOS原理由：</b>{esc(a['oos_reason'] or '未填写')}</p>
<details class="legacy"><summary>旧“候选”选项，仅归档，不用于筛选或判断冲突</summary><p>{esc(legacy)}。原题没有区分范围解释和几何质量；不要求选出一份，不要求修改此旧选项。</p></details>
<h3>评语中的范围解释</h3>{scope_html}
<p class="quality"><b>单独保留的质量原文：</b>{quality}</p>
<h3>我的辅助观察</h3><p>{esc(n['visual_observation'])}</p>
<details><summary>先前核对说明（不是新增人工待办）</summary><p>{esc(n['proposed_question'])}</p></details>
<p class="muted">实际查看的证据：{images}。对照图中读取失败的旧红线不作为标注墙边。</p>
<details><summary>展开高清原图（点击图片可放大）</summary><a href="{esc(link(folder/'hd/panorama.png'), quote=True)}"><img loading="lazy" src="{esc(link(folder/'hd/panorama.png'), quote=True)}" alt="{case} 原始全景" width="2048" height="1024"></a></details>
<p><a href="{esc(link(folder/'index.html'), quote=True)}">原案例页／3D预览</a> · <a href="#top">返回目录</a></p></article>''')
    nav = ' '.join(f'<a href="#{r["case_id"]}">{r["case_id"]}</a>' for r in rows)
    required = [r['case_id'] for r in rows if r['ai_followup']['next_action']['required_now']]
    pending_text = ('当前需补充：' + '、'.join(required)) if required else '本轮人工补充已收到，目前没有需要你立即重审的图。V15、V27继续保留不确定；V04、V48的具体范围意见已经记录。'
    (out/'逐图待确认.html').write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>50图问卷 · 辅助核对与待确认</title>
<style>body{{font:17px/1.7 system-ui,sans-serif;max-width:1150px;margin:30px auto;padding:0 20px;color:#203042;background:#f5f7fa}}article,header{{background:white;padding:24px;margin:20px 0;border-radius:12px;border:1px solid #d9e0e8}}h2{{font-size:23px}}h3{{font-size:18px;margin-bottom:5px}}.fields{{display:flex;gap:7px 22px;flex-wrap:wrap;font-size:15px}}blockquote{{white-space:pre-wrap;margin:10px 0;padding:14px;background:#f3f5f7}}.question{{background:#fff1d5;padding:14px;border-left:4px solid #b77b14}}.muted{{font-size:14px;color:#596675}}a{{color:#17558c}}nav a{{display:inline-block;margin:4px 9px}}img{{width:100%;height:auto}}summary{{cursor:pointer}}table{{border-collapse:collapse;width:100%;font-size:15px}}td,th{{border:1px solid #d9e0e8;padding:10px;text-align:left;vertical-align:top;min-width:140px}}th{{background:#eaf2f5}}.table-scroll{{overflow-x:auto}}.quote{{white-space:pre-wrap}}small{{color:#596675}}.quality{{background:#f3f5f7;padding:12px}}.legacy{{font-size:14px;color:#596675}}</style>
<header id="top"><h1>50图问卷：复用已有判断，保留不确定</h1><p><b>{esc(pending_text)}</b>不要求50张重做。完整安排见<a href="人工下一步清单.md">人工下一步清单</a>。</p>
<p>你已表达清楚的意见直接保留，不需要等待AI认可才算有效。没有改写你的原选项和评语；“无需重审”也不等于所有布局绝对正确或已成为最终GT。</p>
<p><b>不需要挑选任何一份标注。</b>旧“候选”题仅保留归档，不用于筛选、GT认定或选项冲突判定。范围类型、局部质量、规则适用性和确定程度分别保留。</p>
<p>新增“评语中的范围解释”：逐条标出你的描述对象、原句和我的理解。enclosed／extended仅在原文明确归类时提取；模型头名称、预想扩展和潜在边界不自动当作语义标签或合规答案。</p>
<p>使用方式：通过图号查看当前补充和历史记录。无需重复回答已说明的问题；只有新证据或新的具体问题才重开。原问卷选项和旧提取仍保留，发生差异时应阅读后续补充，不把旧选项单独当作当前结论。详见<a href="范围解释整理说明.md">范围解释整理说明</a>。</p>
<p><b>点序勘误：</b>旧读取失败图的交叉红线由脚本生成，不能证明工人墙边自交。旧排序建议也不是工人标错的证明。详见<a href="README_ZH.md">审查报告</a>。</p>
<nav>{nav}</nav></header>{''.join(cards)}</html>''', encoding='utf-8')


def attach_supplements(rows, supplements):
    indexed = unique(rows)
    unique(supplements)
    for s in supplements:
        if s['case_id'] not in indexed or indexed[s['case_id']]['image_id'] != s['image_id']:
            raise ValueError('supplement identity mismatch')
        if not isinstance(s['original_text'], str) or not s['original_text'].strip():
            raise ValueError('missing supplement original text')
        indexed[s['case_id']]['human_supplement'] = s


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('json', 'csv', 'review', 'out'):
        parser.add_argument('--' + arg, required=True, type=Path)
    args = parser.parse_args()
    out, review = args.out.resolve(), args.review.resolve()
    out.mkdir(parents=True, exist_ok=True)
    archive(args.json, out/'原始问卷备份.json')
    archive(args.csv, out/'原始问卷汇总.csv')
    bundle = json.loads((out/'原始问卷备份.json').read_text(encoding='utf-8-sig'))
    notes = json.loads((out/'visual_followup_notes.json').read_text(encoding='utf-8'))
    selection = unique(read_csv(review/'selection.csv'))
    rows, differences = reconcile(bundle, read_csv(out/'原始问卷汇总.csv'), {k:v['image_id'] for k,v in selection.items()}, notes)
    attach_scope_readings(rows, json.loads((out/'scope_comment_readings.json').read_text(encoding='utf-8')))
    attach_supplements(rows, json.loads((out/'human_supplements_20260908.json').read_text(encoding='utf-8')))
    for r in rows:
        for asset in r['ai_followup']['evidence_viewed']:
            if not (review/'cases'/r['case_id']/asset).is_file():
                raise ValueError('missing evidence asset: ' + r['case_id'] + '/' + asset)
    dump(out/'CSV_JSON差异.json', differences)
    if differences:
        raise ValueError('CSV/JSON disagreement; see CSV_JSON差异.json; no merged report produced')
    dump(out/'reconciled_records.json', rows)
    counts = dict(records=len(rows), csv_json_differences=len(differences),
                  archive_bytes_verified=True, human_answers_changed=False, final_decisions_filled=0,
                  statuses=dict(Counter(r['human_record']['answers']['status'] for r in rows)),
                  oos_opinions=dict(Counter(r['human_record']['answers']['oos_assessment'] for r in rows)),
                  scope_opinions=dict(Counter(r['human_record']['answers']['scope'] for r in rows)),
                  selected_population=dict(Counter(selection[r['case_id']]['population_role'] for r in rows)),
                  ai_followup_priority=dict(Counter(r['ai_followup']['priority'] for r in rows)),
                  viewed_evidence_files=dict(Counter(f for r in rows for f in r['ai_followup']['evidence_viewed'])),
                  source_exported_at=bundle['exported_at'])
    counts['scope_reading'] = dict(
        schema='comment_scope_reading_v1',
        cases_with_statements=sum(bool(r['scope_reading']['scope_statements']) for r in rows),
        statement_kinds=dict(Counter(s['kind'] for r in rows for s in r['scope_reading']['scope_statements'])),
        explicit_semantic_assignment_cases=[r['case_id'] for r in rows if any(s['scope_label'] for s in r['scope_reading']['scope_statements'])],
        statements_are_human_confirmed=False, source_quotes_verified=True,
        legacy_candidate_field_used_for_filtering=False, new_visual_reviews=0)
    counts['next_actions'] = dict(actor_counts=dict(Counter(r['ai_followup']['next_action']['actor'] for r in rows)),
        required_now=[r['case_id'] for r in rows if r['ai_followup']['next_action']['required_now']],
        optional_now=[r['case_id'] for r in rows if r['ai_followup']['next_action']['actor']=='user' and not r['ai_followup']['next_action']['required_now']],
        replaces_legacy_priority_as_work_queue=True)
    counts['human_supplements'] = dict(date='2026-09-08', cases=[r['case_id'] for r in rows if 'human_supplement' in r], original_questionnaire_overwritten=False)
    dump(out/'VALIDATION.json', counts)
    report(rows, out, review)
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == '__main__':
    main()
