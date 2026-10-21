"""Readable, independently downloadable file ledger from successful saves only."""
from pathlib import Path
import hashlib,json
import pandas as pd

HERE=Path(__file__).resolve().parent;V3=HERE.parent
RECEIPTS=Path('/tmp/hohonet_v3_library_20261021')

def identity(path):
    s=str(path)
    if 'restored_full_tables/N20_' in s:return '历史阶段2 n20','恢复完整表；无新融合'
    if 'personnel_global_composition_20261021/continuation_20261021/event_repair/' in s:return '历史阶段1 整体构成','修复完整事件；无新融合'
    if 'personnel_global_composition_20261021/composition/' in s:return '历史阶段1 整体构成','完整已有团队端点'
    if 'phase1_geometry_recovery' in s:return '历史阶段1 整体构成','恢复已有几何；无新融合'
    if '/composition/' in s:return '本轮阶段3 多人数/类别块','真实新团队与明确缓存复用；按文件阶段区分'
    if '/taxonomy/' in s:return '本轮阶段3 人员类别','新选型与新楼外标签/原答检查'
    if '/utility/' in s:return '本轮阶段3 实际用途','实际端点选择；不新增融合'
    if '/response/' in s:return '本轮阶段3 粗细/连续响应','已计算端点的配置和楼外分析'
    if '/evidence/' in s:return '本轮阶段3 机制','原答或已有团队票账重放；不重评分'
    return '整合/阶段快照','具体输入和完成身份见文件'

def main():
    rows=[]
    for receipt in sorted(RECEIPTS.glob('receipt_*.json')):
        try:d=json.loads(receipt.read_text())
        except (ValueError,OSError):continue
        for r in d.get('results',[]):
            if r.get('status')!='succeeded':continue
            p=Path(r['local_path']);stage,use=identity(p)
            location=str(p.relative_to(V3)) if p.is_relative_to(V3) else str(p).split('/research/workers/')[-1]
            checkpoint=any(x in p.name for x in ['冻结阶段','实际选队规则与冻结选择','规模覆盖与语义复用_阶段'])
            rows.append(dict(file_name=p.name,stage=stage,content_identity=use,
              topic_relative_path=location,read_role='较早阶段检查点；优先读取后续完成版' if checkpoint else '独立结果、完成包或来源回执；具体状态见文件',
              local_path=str(p),local_file_exists=p.exists(),bytes=p.stat().st_size if p.exists() else '',
              library_file_id=r['library_file_id'],saved_version=r.get('current_version_number'),
              direct_download_url=f"https://chatgpt.com/api/library/files/{r['library_file_id']}/download",
              sandbox_link='sandbox:'+str(p),save_receipt=receipt.name,
              note='ZIP与独立表可为相同内容的替代下载方式，不重复计作研究结果；阶段快照不自动等于最后状态'))
    # A version update retains file identity. The public directory points at
    # its latest successful version, while SAVED_FILES keeps the full history.
    d=pd.DataFrame(rows).drop_duplicates(['library_file_id'],keep='last')
    d.to_csv(HERE/'HOHONET_全部已保存文件_独立下载目录.csv',index=False,encoding='utf-8-sig')
    lines=['# HOHONET 人员分类与整体构成：已保存文件目录','','本目录只收录已保存成功的文件。完整表可独立下载，ZIP 是替代取得方式；同一结果的多种格式不重复计为实验。各阶段身份保留，阶段快照与最后完成版分别命名。','','CSV 索引含精确本地路径、专题相对路径、下载 URL、保存版本及字节数。同名 README/REPORT 按专题路径区分。最终证据表的 SHA256、行数和主键覆盖见各批次 `COMPLETION.json` 或恢复回执。这里的字节数为当前本地文件；若阶段表后来更新，以对应版本的保存回执和包内清单为准。','']
    primary=[('整合报告（含内嵌原图证据）','report/人员分类与整体构成_整合报告_20261021.html'),
      ('整合报告（独立Markdown）','report/人员分类与整体构成_整合报告_独立版_20261021.md'),
      ('Manual逐人标签','taxonomy/MANUAL_LABELS_EXPLAINED.csv'),('Semi逐人标签','taxonomy/SEMI_LABELS_EXPLAINED.csv'),
      ('最终分类采用矩阵','integration/taxonomy_adoption_synthesis/ADOPTION_MATRIX.csv'),
      ('26种变量域覆盖账','integration/PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv'),
      ('完整端点索引','composition/delivery/ENDPOINT_KEY_INDEX.csv.gz'),
      ('旧阶段完整表索引','integration/restored_full_tables/DIRECT_TABLE_INDEX.csv'),
      ('复现代码与必要小输入','integration/HOHONET_v3_复现代码与必要小输入_20261021.zip')]
    lines.extend(['## 优先入口',''])
    for label,rel in primary:
        found=d[d.local_path==str(V3/rel)]
        if len(found):lines.append(f'- [{label}]({found.iloc[-1].direct_download_url})')
    lines.append('')
    for stage,g in d.groupby('stage',sort=False):
        lines.extend(['## '+stage,'','|专题 / 文件|大小（MiB）|内容身份|','|---|---:|---|'])
        for r in g.itertuples():
            size=f'{int(r.bytes)/2**20:.2f}' if r.bytes!='' else '—'
            note='；较早阶段检查点' if '较早阶段' in r.read_role else ''
            lines.append(f'|[{r.topic_relative_path}]({r.direct_download_url})|{size}|{r.content_identity}{note}|')
        lines.append('')
    (HERE/'HOHONET_全部已保存文件_独立下载目录.md').write_text('\n'.join(lines)+'\n')
    (V3/'checkpoints/SAVED_FILES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'saved_files':len(d),'stages':d.groupby('stage').size().to_dict()},ensure_ascii=False))

if __name__=='__main__':main()
