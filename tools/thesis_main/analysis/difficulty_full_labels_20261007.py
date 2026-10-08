"""接入人工补标，仅重汇总已计算曲线；原始结果与审查台保留。"""
import json
import shutil
import sys
from pathlib import Path

from . import difficulty_full_20261007 as base


def overlay(row, decisions):
    row = dict(row)
    d = decisions.get(row['image'])
    if not d or not d['updated_at']:
        return row
    if d['difficulty']:
        row['difficulty'] = d['difficulty']
    if d['oos'] == '是':
        row['scene'] = 'oos'
    elif d['oos'] == '否' and d['doorway'] == '否':
        row['scene'] = 'ordinary'
    elif d['doorway'] == '是' and row['scene'] != 'doorway_annotatable':
        row['scene'] = 'doorway_difficult'
    return row


def run(source):
    original = base.OUT
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    assert data['schema'] == 'difficulty_full_review_20261007_v1'
    decisions = {d['image_code']: d for d in data['decisions']}
    roster = json.loads((original/'review_roster.json').read_text(encoding='utf-8'))
    assert len(decisions) == len(data['decisions'])
    assert set(decisions) == {r['image'] for r in roster['images']}
    out = original/'updated'
    out.mkdir(exist_ok=True)
    shutil.copyfile(source, out/'human_review.json')
    curves = []
    for name in ('coverage', 'curves', 'endpoints'):
        rows = [overlay(r, decisions) for r in base.read_csv(original/f'{name}.csv')]
        base.write_csv(out/f'{name}.csv', rows)
        if name == 'curves':
            curves = rows
    for r in curves:
        for key in ('n', 'k'): r[key] = int(r[key])
        for key in ('D', 'O', 'E', 'V'): r[key] = float(r[key])
        r['quality_compatible'] = r['quality_compatible'] == 'True'
    base.OUT = out
    base.summarize(curves)
    summary = base.read_csv(out/'summary.csv')
    lines = ['# 10图人工补标后的人数结果', '',
        '接入9份已填写判断；uNb-25空白保留。5张简单、2张中等（其中uNb-63为OOS）、2张困难门洞。原文件保存为human_review.json，备注逐字保留。', '',
        '用户随后说明门洞很难标但有人标得好，暂不确定，可先看作答。此回复未明确指向单张图片，因此不擅自补齐uNb-25难度，也不将两张“难标”升级为不可标。', '',
        '## 固定N≥20：原GT、MV50', '',
        '|面板|难度|图数|D1|D8|D16|D20|', '|---|---|---:|---:|---:|---:|---:|']
    scopes = {'ordinary_quality':'普通图', 'with_annotatable_door':'普通＋已明确可标门洞', 'with_labeled_door':'普通＋已有难度的门洞'}
    for scope, title in scopes.items():
        for label in base.LABELS:
            rs = {int(r['k']):r for r in summary if r['condition']=='manual' and r['scope']==scope and r['limit']=='20' and r['evaluation']=='original' and r['method']=='mv50' and r['difficulty']==label}
            if rs:
                lines.append(f"|{title}|{label}|{rs[1]['image_n']}|"+'|'.join(f"{float(rs[k]['D']):.4f}" for k in (1,8,16,20))+'|')
    lines += ['', 'D为参考面积归一化的对称差，越低越近；每行始终同一批图片。门洞合入只是描述性分层，不认证GT可靠或改变质量资格；OOS始终单列。', '',
        '## 判断', '',
        '- 已明确可标门洞面板增至33张N≥20图（15简单、9中等、9困难）；此前27张。本轮新增6张普通图，uNb-63转入OOS，不计入中等主组。',
        '- 原GT/MV50困难组8→16人仅由0.3793降至0.3767，20人回升至0.3778；简单组由0.1117降至0.1019、0.1002。补标后仍支持本面板的困难组后段收益小、残留高。',
        '- 采用可用修订GT后，困难组8/16/20人为0.2890/0.2827/0.2834，仍有后段停滞。严格多数的8→16人困难组改善大于简单组，因此不能推出困难在所有规则与阶段都更慢。',
        '- 简单也可能停滞：Uw-17从8人0.0515到全员0.0589略变差，保留用户“两种空间范围”的回忆，不据此认定两簇。B6-11虽标简单，全员D仍为0.2557；难度不是参考误差的同义词。',
        '- yq-25中等且有遮挡／遗漏备注，8人0.2764、全员0.2986；这为查看误差位置提供线索，尚不能将曲线归因于遮挡。', '',
        '## 本轮10图的实际全员结果', '', '|图片|场景|难度|人数|D8|全员D|', '|---|---|---|---:|---:|---:|']
    for r in base.read_csv(out/'per_image.csv'):
        if r['image'] in decisions and r['condition']=='manual' and r['method']=='mv50' and r['version']=='original':
            lines.append('|'+ '|'.join([r['image'],r['scene'],r['difficulty'],r['n'],f"{float(r['D8']):.4f}",f"{float(r['D_all']):.4f}"])+'|')
    lines += ['', '## 复用与下一步', '',
        '本轮仅覆盖人工标签与场景；6782行D/O/E/V、人员池、投票规则和实际几何均未改变。原始全量输出保留在上级目录。summary.csv含两规则、两参考政策及建筑等权；新增with_labeled_door明确包含已有难度但可标性未定的门洞。',
        '后续集中查看待定门洞的实际作答和全员共识，不要求为扩大样本强行补标签；先检验范围选择差异与边界定位困难。未新增人员类别或难度预测器。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    base.write_json(out/'field_contract.json', dict(
        source=str(source), labels='human_review.json; nonempty decisions overlay historical labels and scene only',
        geometry='../all_consensus.geojson; pool and method unchanged',
        pending='uNb-25 blank; doorway difficult is not unannotatable; uNb-63 OOS subtype unspecified',
        unchanged='All memberships, gates, D/O/E/V, rules and GT versions remain unchanged. Historical outputs stay in parent directory.'))


if __name__ == '__main__':
    run(Path(sys.argv[1]))
