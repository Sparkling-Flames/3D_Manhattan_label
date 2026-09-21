"""选定研究资料打包与隔离复算；不改变研究方法。"""
import argparse
import ast
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/pro_research_handoff_20260921'
SUFFIXES = {'.json', '.jsonl', '.gz', '.csv', '.md', '.txt', '.npz', '.npy'}
FOLDERS = {
    'analysis_results/new_manual_reviewed_20260921': 'current',
    'analysis_results/new_manual_analysis_20260921': 'historical_baseline',
    'analysis_results/clustering_release_local_20260920/current/inputs': 'frozen_history_input',
    'analysis_results/clustering_release_local_20260920/current/input/supplement': 'frozen_model_features',
    'analysis_results/worker_four_block_exploration_20260910_v1': 'personnel_training_and_history',
    'analysis_results/worker_rule_triad_20260910_v1': 'personnel_training_and_history',
    'analysis_results/clustering_numeric_received_20260920/results/personnel': 'personnel_holdout_history',
    'analysis_results/clustering_numeric_received_20260920/results/sensitivity3d': 'conditional_3d_history',
    'analysis_results/clustering_numeric_received_20260920/results/model_bridge': 'model_history',
    'analysis_results/local_point_clustering_20260920/evidence': 'human_review',
    'analysis_results/scene_image_exploration_20260910_v1': 'scene_and_room_evidence',
    'analysis_results/spatial_dimensions_review_20260913_v2': 'scene_evidence',
}
OMIT = {
    'analysis_results/new_manual_analysis_20260921/memberships.json',
    'analysis_results/new_manual_analysis_20260921/coverage_curves.json',
    'analysis_results/new_manual_analysis_20260921/convergence_and_composition/curves.json',
    'analysis_results/new_manual_analysis_20260921/convergence_and_composition/matched_horizon_curves.json',
    'analysis_results/new_manual_analysis_20260921/convergence_and_composition/subtype_endpoint_curves.json',
    'analysis_results/worker_four_block_exploration_20260910_v1/predictions.csv.gz',
    'analysis_results/worker_four_block_exploration_20260910_v1/subtype_stage_validation/named_paired_curves.csv.gz',
    'analysis_results/worker_four_block_exploration_20260910_v1/subtype_stage_validation/paired_curves.csv.gz',
    'analysis_results/worker_rule_triad_20260910_v1/predictions.csv.gz',
    'analysis_results/clustering_numeric_received_20260920/results/personnel/subtype_prefix_nodes.csv.gz',
    'analysis_results/clustering_numeric_received_20260920/results/personnel/fixed_roster_group_curves.csv.gz',
}
DOCS = ['Pro提示词_人员构成与顺序重放_20260921.md', 'Pro云端资料入口_20260921.md',
        '研究讨论线程交接_20260921.md', '真人标注不确定性研究_当前状态.md',
        '分簇工作版_统一数据入口_20260920.md', '相似场景标注稳定性分析SOP.md',
        '图片分类与同房间收敛预测研究SOP.md', '第一阶段执行与人员分类续研说明_20260913.md',
        '用户研究要求核对清单_20260913.md']


def code_closure(seeds):
    """静态本地导入闭包，动态路径的历史脚本按文件保留，不冒充可执行入口。"""
    pending = list(seeds); found = set()
    while pending:
        path = pending.pop()
        if path in found or not path.is_file():
            continue
        found.add(path)
        for parent in path.parents:
            if parent == ROOT:
                break
            init = parent / '__init__.py'
            if init.is_file() and init not in found:
                pending.append(init)
        if path.suffix != '.py':
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node, ast.Import):
                bases = [(ROOT, alias.name) for alias in node.names if alias.name.startswith('tools.')]
            elif isinstance(node, ast.ImportFrom):
                base = path.parent
                if node.level:
                    for _ in range(node.level - 1):
                        base = base.parent
                else:
                    base = ROOT
                module = node.module or ''
                bases = [(base, module)] + [(base, '.'.join(filter(None, [module, a.name]))) for a in node.names]
            else:
                continue
            for base, module in bases:
                dest = base.joinpath(*module.split('.'))
                if dest.is_relative_to(ROOT / 'tools'):
                    pending.extend([dest.with_suffix('.py'), dest / '__init__.py'])
    return found


def build():
    from .reviewed_manual_20260921 import SOURCES
    files = {}
    for folder, role in FOLDERS.items():
        for p in (ROOT / folder).rglob('*'):
            name = p.relative_to(ROOT).as_posix()
            if p.is_file() and p.suffix in SUFFIXES and name not in OMIT:
                files[name] = (p, role)
    exact = SOURCES + ['import_json/scene_stability_stage1_20260913_v2/' + n for n in
        ['historical_exposure.json', 'required_assignments.json']]
    exact += ['docs/thesis_main/' + n for n in DOCS]
    exact += ['tests/test_reviewed_manual_20260921.py', 'tests/test_new_manual_20260921.py',
        'analysis_results/local_point_research_received_20260919/pair_pilot/用户_六图点对审核_原始.json',
        'analysis_results/cluster_review_extra_20260919/用户_12图审核_原始.json',
        'analysis_results/pro_next_round_20260920/来源核对与最新要求.md',
        'analysis_results/pro_research_handoff_20260921/导师交流原文.txt',
        'tools/label_studio/vis_3d.html', 'tools/label_studio/ls_3d_logic.js']
    for name in exact:
        p = ROOT / name
        if not p.is_file():
            raise FileNotFoundError(name)
        files[name] = (p, 'source_or_context')
    seeds = [Path(__file__)] + [ROOT / 'tools/thesis_main/analysis' / n for n in
        ['reviewed_manual_20260921.py', 'room_convergence_20260921.py',
         'worker_four_block_exploration_20260910.py', 'worker_group_count_exploration_20260910.py',
         'worker_subtype_stages_20260910.py', 'worker_rule_triad_20260910.py']]
    seeds += list((ROOT / 'tools/thesis_main/analysis/clustering_numeric_research').glob('*.py'))
    seeds += list((ROOT / 'tools/label_studio/panorama_studio').glob('*.py'))
    for p in code_closure(seeds):
        files[p.relative_to(ROOT).as_posix()] = (p, 'code')
    # JS查看器本地脚本一并保留，浏览器第三方库及照片不是数值依赖。
    for p in (ROOT / 'tools/label_studio/panorama_studio').glob('*.js'):
        files[p.relative_to(ROOT).as_posix()] = (p, 'viewer_code')
    manifest = dict(schema='pro_research_handoff_v1', branch='codex/pro-research-20260921',
        current='analysis_results/new_manual_reviewed_20260921',
        files=[dict(path=n, role=role, bytes=p.stat().st_size) for n, (p, role) in sorted(files.items())],
        omitted_large_regenerable_tables=sorted(OMIT),
        excluded='原始active日志、凭据、原图、临时截图、历史UI与无关采集方案；历史脚本不保证所有旧路径齐全',
        verified_entry='python -B -m tools.thesis_main.analysis.pro_research_handoff_20260921 --verify')
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT / 'pro_research_20260921.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, (p, _) in sorted(files.items()):
            archive.write(p, name)
        archive.writestr('HANDOFF_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    (OUT / 'HANDOFF_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(files=len(files), archive_bytes=(OUT / 'pro_research_20260921.zip').stat().st_size)))


def verify():
    from . import reviewed_manual_20260921 as current
    reference = current.OUT
    current.OUT = OUT / 'recomputed'
    current.main()
    compared = []
    for p in reference.glob('*.json'):
        if p.name == '验证记录.json':
            continue
        other = current.OUT / p.name
        if json.loads(p.read_text(encoding='utf8')) != json.loads(other.read_text(encoding='utf8')):
            raise AssertionError('Reproduction differs: ' + p.name)
        compared.append(p.name)
    assert current.old.pipeline.rows_at(reference / 'responses.jsonl.gz') == current.old.pipeline.rows_at(current.OUT / 'responses.jsonl.gz')
    result = subprocess.run([sys.executable, '-B', '-m', 'pytest', 'tests/test_reviewed_manual_20260921.py',
                             'tests/test_new_manual_20260921.py', '-q'], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    info = dict(compared_json=compared, response_rows_equal=True, tests=result.stdout.strip(),
                source_reference_unchanged=True, raw_logs_required=False)
    (OUT / 'DELIVERY_CHECK.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    verify() if args.verify else build()
