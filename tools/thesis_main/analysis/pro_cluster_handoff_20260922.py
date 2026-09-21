"""打包本轮研究增量，或将基础包与增量展开到全新隔离目录。"""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/pro_research_handoff_20260921/pro_research_20260921.zip'
OUT = ROOT / 'analysis_results/pro_cluster_handoff_20260922'
EXTRA = OUT / 'pro_cluster_supplement_20260922.zip'
RECEIVED = 'analysis_results/panorama_research_received_20260921'
STEMS = ['audit_cluster_screen_20260922', 'audit_pro_research_20260921',
         'build_cluster_screen_20260921', 'cluster_threshold_audit_20260921',
         'worker_cluster_sensitivity_20260921', 'pro_cluster_handoff_20260922']


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not (destination / name).resolve().is_relative_to(destination.resolve()):
                raise ValueError(f'包内路径越界：{name}')
        z.extractall(destination)


def prepare(destination, base=BASE, extra=EXTRA):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError('请指定尚不存在的目录，避免覆盖既有研究')
    if not base.is_file() or not extra.is_file():
        raise FileNotFoundError('基础ZIP或本轮增量ZIP缺失，请从指定分支下载两者')
    destination.mkdir(parents=True)
    unpack(base, destination)
    unpack(base, destination / RECEIVED / 'local_recompute/source_work')
    unpack(extra, destination)
    for name in ('original_package', 'local_recompute'):
        folder = destination / RECEIVED / name
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base, folder / 'source_snapshot.zip')
    print(f'已准备独立研究目录：{destination}')


def build():
    from tools.thesis_main.analysis.pro_research_handoff_20260921 import code_closure
    folders = [RECEIVED, 'analysis_results/worker_cluster_sensitivity_20260921',
               'analysis_results/cluster_screen_20260921',
               'analysis_results/cluster_screen_reviewed_20260922']
    files = set()
    for folder in folders:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() and not {'__pycache__', 'source_work'} & set(p.parts) and p.suffix not in {'.zip', '.pyc', '.log'}:
                files.add(p)
    seeds = [ROOT / 'tools/thesis_main/analysis' / (s + '.py') for s in STEMS]
    files |= code_closure(seeds)
    files |= {ROOT / 'tests' / ('test_' + s + '.py') for s in STEMS}
    files |= {ROOT / p for p in [
        'tests/cluster_screen_browser.cjs',
        'tools/label_studio/official/ls_userscript_annotator.js',
        'tools/label_studio/ls_userscript.js', 'tools/label_studio/vis_3d.html',
        'docs/thesis_main/Pro提示词_分簇核验与不确定性_20260922.md',
        'docs/thesis_main/Pro云端资料入口_分簇核验_20260922.md',
        'docs/thesis_main/Pro提示词_人员构成与顺序重放_20260921.md',
        'docs/thesis_main/Pro云端资料入口_20260921.md',
        'docs/thesis_main/真人标注不确定性研究_当前状态.md']}
    # GT仅是已有审核的辅助资产，不参与新的聚类距离或解释变量。
    receipts = json.loads((ROOT / 'analysis_results/cluster_screen_reviewed_20260922/逐项接收.json').read_text(encoding='utf8'))
    files |= {ROOT / r['gt_path'] for r in receipts if r['gt_exists']}
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = dict(schema='pro_cluster_handoff_20260922_v1',
        branch='codex/pro-cluster-validation-20260922',
        base_archive=BASE.relative_to(ROOT).as_posix(),
        files=[dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size) for p in sorted(files)],
        notes='基础包保留原样；本轮增量覆盖维护代码与当前说明。含24图内嵌原图，不含完整原图库；排除日志、缓存、重复源ZIP及展开副本。GT和模型只作辅助参考。')
    with zipfile.ZipFile(EXTRA, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(files):
            z.write(p, p.relative_to(ROOT).as_posix())
    (OUT / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(files=len(files), archive_bytes=EXTRA.stat().st_size)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path, help='展开到尚不存在的独立目录')
    args = parser.parse_args()
    prepare(args.prepare) if args.prepare else build()
