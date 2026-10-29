"""Create a durable download directory from verified successful save receipts.

This is delivery metadata only. Scientific outputs are read, never modified.
File IDs come from actual helper receipts/xattrs; no URL or ID is invented.
"""
from pathlib import Path
import hashlib
import html
import json
import os

ROOT = Path(__file__).resolve().parents[1]

DESCRIPTIONS = {
    'HOHONET_v21_personnel_research_report_ZH.pdf': ('先读', '19页完整研究报告，含采用判断、参数追溯、人员名单、容量漏斗、幅度与方向、反例和证据键。'),
    'HOHONET_v21_personnel_research_report_ZH.docx': ('先读', '可编辑的完整中文报告，与PDF和HTML正文一致。'),
    'HOHONET_v21_personnel_research_report_ZH.html': ('先读', '单文件报告，内嵌正文示例图。'),
    'HOHONET_v21_seven_cases_viewer_ZH.html': ('先读', '七张全景图、八个实体ABC的单文件案例浏览页；ERP/BEV/局部图、原答和票账。'),
    'PERSONNEL_ROSTER_ALL_WITH_HISTORY.csv': ('名单与查数', '62人ALL描述名单、历史支持与缺失；实际事件请用对应建筑的LOBO标签。'),
    'ADOPTED_METHODS_LABELS_ALL_LOBO.csv.gz': ('名单与查数', '正式采用及互补方法的ALL和全部留楼外标签。'),
    'ALL60_CURRENT_ADOPTION_DECISIONS.csv': ('名单与查数', '旧45配置和新增15配置的逐项采用决定；60不是60种独立分类思想。'),
    'MAIN_COMPARISON_READING_TABLES.csv': ('名单与查数', '2404个可回连数值，含精确源值、过滤条件、分母、字段及来源SHA。'),
    'ALL236_FOUR_GRID_CAPACITY_FUNNEL.csv': ('名单与查数', '全部236个普通Manual合法池的四主格人数—历史—类别—执行—可评漏斗。'),
    'FINAL_REPLACEMENT_BAND_COVERAGE.csv': ('名单与查数', '固定7/8人、恰半、过半、大队ABC和AC分别统计；容量/执行/可评并集。'),
    'EVENTS_EXACT.csv.gz': ('逐事件与几何', '6548条新增严格ABC，含真实互斥D/X/Y/Z成员及端点键。'),
    'EVENT_METRICS.csv.gz': ('逐事件与几何', '6548事件×769列的完整指标；缺失Q保持缺失。'),
    'ENDPOINT_GEOMETRY.jsonl.gz': ('逐事件与几何', '16818个唯一端点的完整几何与失败状态；16810个真正新增实体团队。'),
    'HOHONET_v21_reaudit_stage00_intake.zip': ('完整分阶段包', '版本、数据/范围合同、原采用表与原参数快照；来源保留。'),
    'HOHONET_v21_reaudit_stage01_classification.zip': ('完整分阶段包', '全部参数变体、23折拟合、标签、支持门槛、原答几何与相关代码。'),
    'HOHONET_v21_reaudit_stage02_comparison.zip': ('完整分阶段包', '旧全量比较、新旧ABC合并、共同支持、Q/QT控制、同配比残余；原报告和显示勘误并存。'),
    'HOHONET_v21_reaudit_stage02_capacity.zip': ('完整分阶段包', '逐池容量、所有n/m分带、执行与失败漏斗、AC独立统计及代码。'),
    'HOHONET_v21_reaudit_stage03_completed_ABC.zip': ('完整分阶段包', '冻结设计、新增ABC事件、端点标量/完整几何、指标、原生运行与测量回执。'),
    'HOHONET_v21_reaudit_stage04_cases.zip': ('完整分阶段包', '七图八ABC完整原答、全景、矢量/栅格图、full_state、219组与2066条票账。'),
    'HOHONET_v21_reaudit_stage05_final_synthesis.zip': ('完整分阶段包', '完整报告、全部名单、60配置采用表、152主表原始行提取、位置与尺度的既有结果补充、证据索引及视觉QA。'),
    'LOCATION_SCALE_READING.csv': ('名单与查数', '位置、面积、平均高度的已有幅度与方向精确值及各自可评支持；没有新增融合。'),
    'LOCATION_SCALE_READING_ZH.txt': ('名单与查数', '位置与尺度结果的独立补充阅读；以相机高归一，扩张不自动等于升质。'),
    'HOHONET_v21_reaudit_stage06_reproducible_sources.zip': ('完整分阶段包', '最终复现输入与实际依赖闭包；373来源文件、环境版本、参数化运行说明。'),
    'HOHONET_v21_reaudit_code.zip': ('完整分阶段包', '本轮根研究、导出、报告、案例浏览、复现及完整性验证代码。'),
    'HOHONET_v21_reaudit_stage07_validation.zip': ('完整分阶段包', '逐文件SHA与可读性、逐压缩成员CRC/内部gzip检查、证据回连及保存清单。'),
    'REPRODUCTION_README_ZH.txt': ('复现说明', '分层复现命令、源依赖、路径布置、版本和旧全量研究的外部输入边界。'),
    'HOHONET_v21_reaudit_stage03_frozen_design.zip': ('阶段检查点（保留）', '团队结果之前冻结的候选与严格ABC设计；不要用后验结果重写。'),
    'HOHONET_v21_reaudit_stage06_inputs_and_engine.zip': ('阶段检查点（保留）', '初始输入/引擎快照；复现请优先使用最终stage06_reproducible_sources包。'),
    'HOHONET_v21_reaudit_stage05_synthesis.zip': ('阶段检查点（保留）', '完整主报告的先行快照；最终final_synthesis包另含位置与尺度补充阅读。'),
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def collect():
    saved_path = ROOT / 'SAVED_ARTIFACTS.json'
    saved = json.loads(saved_path.read_text())
    folders = ['deliverables', 'stage05_synthesis', 'stage03_completed_abc',
               'stage04_cases', 'stage06_reproduction',
               'stage02_capacity/completed_supplement']
    candidates = [p for folder in folders for p in (ROOT / folder).glob('*') if p.is_file()]
    by_name = {p.name: p for p in candidates}
    known = {row['library_file_id'] for row in saved}
    for p in candidates:
        try:
            file_id = os.getxattr(p, 'user.library-file-id').decode()
        except OSError:
            continue
        if file_id.startswith('libfile_') and file_id not in known:
            saved.append({'file_name': p.name, 'library_file_id': file_id,
                          'relative_path': str(p.relative_to(ROOT)), 'stage': p.parent.name})
            known.add(file_id)
    rows = []
    for entry in saved:
        name = entry['file_name']
        if name == '00_DOWNLOAD_DIRECTORY_ZH.html':
            continue
        p = ROOT / entry['relative_path'] if entry.get('relative_path') else by_name.get(name)
        if p is None or not p.is_file():
            raise FileNotFoundError(name)
        group, description = DESCRIPTIONS.get(name, ('其他已保存文件', '补充研究材料。'))
        rows.append({**entry, 'relative_path': str(p.relative_to(ROOT)),
                     'bytes': p.stat().st_size, 'sha256': sha(p), 'group': group,
                     'description': description,
                     'url': 'https://chatgpt.com/library?file_id=' + entry['library_file_id'] + '&account_id=personal'})
    saved_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + '\n')
    return rows


def main():
    rows = collect()
    (ROOT / 'DOWNLOAD_MANIFEST.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    esc = html.escape
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>HOHONET v2.1 人员分类研究完整下载目录</title>',
             '<style>body{max-width:1080px;margin:36px auto;padding:0 24px;font-family:system-ui,sans-serif;line-height:1.75;color:#111;background:#fff}h1{font-size:28px}h2{margin-top:36px;border-bottom:1px solid #aaa}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px 9px;border:1px solid #bbb;text-align:left;vertical-align:top}th{background:#eee}a{overflow-wrap:anywhere}small,code{font-size:12px;overflow-wrap:anywhere}code{background:#f3f3f3}li{margin:8px 0}</style><body>',
             '<h1>HOHONET v2.1 人员分类研究完整下载目录</h1>',
             '<p>2026-10-29｜普通Manual优先｜来源提交 <code>519c7447278dd16c3d69f505b807fb5b53792b36</code></p>',
             '<p><strong>正式采用：</strong>TARGET_DSTRUCT K3为主，K2为粗层、K4作条件性细层；OPPJOINT K3/K4用于联合画像；RAW3 K3用于原答定义敏感性与八人扩覆盖；RFUSE GEOM K2保留反向互补。</p>',
             '<p>本轮完成15项新参数配置、6548条严格ABC新增事件、16818个唯一端点。新旧完整结果与原采用快照分开保留。先读报告，再看七图案例，最后按证据键查表。缺失Q没有填零，有限配比方差解释没有称为预测准确率。</p>',
             '<p>完整阶段包可解压到同一父目录；每包自带对应的 <code>stageXX_*</code> 或 <code>code</code> 目录。若只阅读结论与案例，无需先下载全部源码。大文件均标注实际大小。</p>']
    groups = ['先读', '名单与查数', '逐事件与几何', '完整分阶段包', '复现说明', '阶段检查点（保留）', '其他已保存文件']
    order = {key: i for i, key in enumerate(DESCRIPTIONS)}
    for group in groups:
        subset = sorted([r for r in rows if r['group'] == group], key=lambda r: order.get(r['file_name'], 999))
        if not subset:
            continue
        parts += ['<h2>' + esc(group) + '</h2><table><thead><tr><th>文件</th><th>内容与用途</th><th>大小</th></tr></thead><tbody>']
        for r in subset:
            parts += ['<tr><td><a href="' + esc(r['url'], quote=True) + '">' + esc(r['file_name']) + '</a><details><summary>SHA256</summary><code>' + r['sha256'] + '</code></details></td><td>' + esc(r['description']) + '</td><td>' + format(r['bytes'] / 1048576, '.2f') + ' MiB</td></tr>']
        parts.append('</tbody></table>')
    parts += ['<h2>如何复核一个结果</h2><ol><li>在报告中找到E01–E23证据键，查报告的 <code>REPORT_EVIDENCE_INDEX.json</code>。</li>',
              '<li>主表的152条源行保存在 <code>REPORT_TABLE_EXTRACTIONS.csv</code>；常用指标另提供2404行 <code>MAIN_COMPARISON_READING_TABLES.csv</code>，包含精确筛选和分母。</li>',
              '<li>事件的 <code>event_id</code> 与 <code>pool_id / method / heldout_building</code> 回连具体D/X/Y/Z，再用 <code>team_key</code> 回连端点及几何。</li>',
              '<li>案例浏览页呈现原图、原答、完整几何与逐票账；失败只有失败状态，不补画成功多边形。当前v2.1范围已经裁定的S9不再重新请求范围判定。</li>',
              '<li>按复现说明运行需要的层级。完整旧89660事件的重新生成还需要原旧交付或冻结仓库相应目录；本次源包不冒称包含整部历史仓库。</li></ol>',
              '<p><strong>研究边界：</strong>五法四主格已补齐类别容量允许的池；任意n/m、每个成员组合和新的人员/建筑没有全部穷尽。只需人工判断的局部物理问题列在案例中，不用人工意见替代已有统计和算法机制。</p>',
              '<p>所有链接均使用已成功保存返回的文件标识。原版本与阶段检查点保留，最终源包名称含 <code>reproducible_sources</code>。</p></body></html>']
    target = ROOT / '00_DOWNLOAD_DIRECTORY_ZH.html'
    target.write_text('\n'.join(parts), encoding='utf-8')
    print(json.dumps({'download_files': len(rows), 'index': str(target),
                      'total_saved_bytes_with_standalone_duplicates': sum(r['bytes'] for r in rows)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
