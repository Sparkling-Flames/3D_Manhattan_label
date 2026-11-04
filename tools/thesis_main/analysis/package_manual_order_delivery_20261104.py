"""Package immutable, numbered repository overlays with per-file SHA256.

The first two batches were already delivered. These remaining batches preserve
repository-relative paths and include complete outputs, including replay caches.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from .apply_manual_ring_orders_20261104 import ROOT, BASE_COMMIT

IMPACT=ROOT/'research/fusion/manual_order_impact_20261104'
DELIVER=ROOT.parent/'deliverables'
SITE=ROOT/'research/statistics/research_explorer_v1_r2_20261017'
SCRIPTS=ROOT/'tools/thesis_main/analysis'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',choices=['03','04','05'],required=True)
    args=ap.parse_args();batch=args.batch
    files=set()
    def add(path):
        if path.is_dir():
            for p in path.rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.tmp']:
                    files.add(p)
        elif path.is_file():files.add(path)
        else:raise FileNotFoundError(path)
    if batch=='03':
        title='配比、纯类联盟、人数曲线与旧角色策略'
        suffix='composition_alliances_population_policy'
        for name in ['composition','alliances','natural','policy']:add(IMPACT/name)
        for name in ['evaluate_manual_order_composition','evaluate_manual_order_alliances','evaluate_manual_order_natural','evaluate_manual_order_policy','summarize_manual_order_selected_statistics']:
            add(SCRIPTS/f'{name}_20261104.py')
        scope='包含四个模块的完整原/辅助统计、真实下游消费者、逐条结论、来源/完整性回执及独立联盟坐标候选；策略原生重抽缓存一并提供。主固定坐标分支仍56/57，坐标候选单列。'
    elif batch=='04':
        title='AC与同房的完整实际下游'
        suffix='ac_same_room'
        for name in ['ac','same_room']:add(IMPACT/name)
        for p in SCRIPTS.glob('*manual_order_ac*_20261104.py'):add(p)
        add(SCRIPTS/'evaluate_manual_order_same_room_20261104.py')
        scope='包含AC的七类敏感性、共同池/背景、漏斗与strict桥，以及当前/原native同房、角点、成员和历史Q消费者；完整原/辅助支持、来源核查和独立AC坐标候选均保留。'
    else:
        title='全链总交付、预处理、研究台与最终验收'
        suffix='final_report_workbench_validation'
        for p in IMPACT.iterdir():
            if p.is_file():add(p)
        for name in ['endpoints','half_qonly','preprocessing_audit','dependencies','coordinate_candidate','workbench_validation']:add(IMPACT/name)
        for name in ['ac','same_room','composition','alliances','natural','policy']:
            for p in (IMPACT/name).rglob('*'):
                if p.is_file() and (p.suffix=='.md' or p.name in ['CHECKS.json','CONCLUSIONS.csv','AC_IMPACT_RECEIPT.json','INPUT_MANIFEST.json','FILE_INTEGRITY.csv','GZIP_INTEGRITY.csv','SOURCE_VERSION_CHECKS.csv']):add(p)
        add(SITE/'v21-manual-order.html');add(SITE/'v21-manual-order')
        for name in ['index.html','v21-results.html','v21-reselection.html']:add(SITE/name)
        for p in SCRIPTS.glob('*manual*20261104.py'):add(p)
        for name in ['test_manual_ring_orders_20261104.py','test_manual_order_half_qonly_20261104.py']:add(ROOT/'tests'/name)
        for name in ['docs/README_INDEX.md','docs/PROJECT_MAP_CLEAN_20260308.md','docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md','research/data/releases/v2.1/README.md','research/data/releases/v2.1/final_classification_downstream/README.md','research/data/releases/v2.1/personnel_reselection_dependencies/README.md','research/data/releases/v2.1/research_readiness_20261031/WORKBENCH_HANDOFF.md']:add(ROOT/name)
        scope='最终总报告、逐条总判断、9模块矩阵、完整预处理、22张原图离线研究台、修订后的半队回执与全部最终检查。此批含前两批端点/半队数据的最终版本及所有脚本；第03/04批的全量统计继续保留于对应包。'
    assert files
    DELIVER.mkdir(exist_ok=True)
    name=f'HOHONET_v21_manual_order_batch{batch}_{suffix}_20261104.zip'
    target=DELIVER/name
    if target.exists():raise FileExistsError(f'Immutable delivery already exists: {target}')
    readme=f'''# HOHONET v2.1 第{batch}批：{title}

{scope}

基线提交：`{BASE_COMMIT}`。原自动结果不覆盖；只有文档/研究台入口和本次辅助目录新增或更新。所有科学Q缺失保持缺失，不设0，人工劳动未计时。

## 使用

将本包的仓库相对路径解压叠加到`D:/Work/HOHONET`。所有批次使用同一根目录。按批号叠加，最终第05批包含回执勘误及文档入口。无需删除原自动研究数据，也无需再次排序。

总入口：`research/fusion/manual_order_impact_20261104/README.md`（第05批）。研究台：`research/statistics/research_explorer_v1_r2_20261017/v21-manual-order.html`（第05批），可直接离线打开。

本包每个实体文件的SHA256和字节数列在本目录`BATCH{batch}_SHA256_MANIFEST.csv`。ZIP自身SHA256记录在外部交付回执，避免自引用哈希。
'''
    rows=[]
    for p in sorted(files):
        rows.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
    prefix='research/fusion/manual_order_impact_20261104/delivery_receipts/'
    metadata=dict(batch=batch,title=title,source_commit=BASE_COMMIT,files=len(rows),uncompressed_bytes=sum(r['bytes'] for r in rows),repository_overlay=True,automatic_experiments_preserved=True)
    tmp=target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr(prefix+f'BATCH{batch}_README_ZH.md',readme)
        z.writestr(prefix+f'BATCH{batch}_SHA256_MANIFEST.csv','\ufeff'+stream.getvalue())
        z.writestr(prefix+f'BATCH{batch}_CONTENTS.json',json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        for r in rows:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'],r['path']
    tmp.rename(target)
    receipt=metadata|dict(filename=name,bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),zip_crc_verified=True,all_member_sha256_verified=True,members=len(rows)+3)
    (DELIVER/f'BATCH{batch}_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
