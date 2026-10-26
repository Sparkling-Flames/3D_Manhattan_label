"""更新已有离线交付包；先运行研究台builder，不重算任何研究结果。"""
from pathlib import Path
import json
import posixpath
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
PAGE = Path('research/statistics/research_explorer_v1_r2_20261017')
DELIVERY = ROOT / 'analysis_results/research_workbench_delivery_20261026'
ZIP = DELIVERY / '全景标注研究台_20261026.zip'
SEVENZIP = Path('D:/7-Zip/7z.exe')


def local_reference(base, href):
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    target = posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(parsed.path)))
    if target.startswith('../') or target.startswith('/'):
        raise ValueError('archive reference escapes package: ' + href)
    return target


def refresh():
    assert ZIP.is_file() and SEVENZIP.is_file()
    pending = ZIP.with_suffix('.new.zip')
    assert not pending.exists(), '已有待检包，请先检查，禁止覆盖'
    receipt = json.loads((DELIVERY / '交付检查.json').read_text(encoding='utf-8-sig'))
    with tempfile.TemporaryDirectory(prefix='workbench256-', dir=ROOT / '.tmp') as temporary:
        stage = Path(temporary) / 'site'
        stage.mkdir()
        with ZipFile(ZIP) as old:
            names = set(old.namelist())
            runtime = [n for n in names if n.startswith(PAGE.as_posix() + '/')
                       and len(Path(n).parts) == len(PAGE.parts) + 1
                       and Path(n).suffix in {'.html', '.css', '.js'}]
            for name in runtime:
                dest = stage / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if name.endswith('/dataset-config.js'):
                    dest.write_bytes(old.read(name))  # 保持交付包仅v2的配置。
                else:
                    shutil.copy2(ROOT / name, dest)
            index_html = stage / PAGE / 'index.html'
            html = index_html.read_text(encoding='utf-8')
            html = re.sub(r'<option\b[^>]*value=["\']v1["\'][^>]*>.*?</option>', '', html)
            index_html.write_text(html, encoding='utf-8')
        for folder in ['v2-data', 'v2-resources']:
            for source in (ROOT / PAGE / folder).rglob('*.js'):
                if 'qa' not in source.relative_to(ROOT / PAGE / folder).parts:
                    dest = stage / source.relative_to(ROOT)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)

        def read_local(path):
            text = path.read_text(encoding='utf-8')
            return json.loads(text.split(']=', 1)[1].rstrip().removesuffix(';'))

        def write_local(path, data):
            prefix = path.read_text(encoding='utf-8').split(']=', 1)[0] + ']='
            path.write_text(prefix + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';', encoding='utf-8')

        index_path = stage / PAGE / 'v2-data/index.js'
        index = read_local(index_path)
        keep = {'personnel_classification_guide', 'current_class_evidence', 'personnel_main_interface',
                'personnel_main_figures', 'personnel_main_glossary', 'same_room_v2_prediction_20261019_r1'}
        index['documents'] = [d for d in index['documents'] if d['path'] in keep
                              or d.get('content', {}).get('schema') in keep]
        write_local(index_path, index)
        resources_path = stage / PAGE / 'v2-resources/index.js'
        resources = read_local(resources_path)
        resources.pop('dependencies', None)
        resources.pop('supplement_plan', None)
        write_local(resources_path, resources)
        evidence_path = stage / PAGE / 'v2-resources/research_evidence.js'

        def prune(value):
            if isinstance(value, dict):
                return {k: prune(v) for k, v in value.items()
                        if not (k in {'source', 'score_source'} and isinstance(v, str) and v.endswith('ENDPOINT_SCALARS.csv.gz'))}
            if isinstance(value, list):
                return [prune(v) for v in value if not (isinstance(v, str) and v.endswith('ENDPOINT_SCALARS.csv.gz'))]
            return value

        write_local(evidence_path, prune(read_local(evidence_path)))
        # 新图版的动态路径与源表：由页面声明提取，避免漏掉运行时拼接的依赖。
        script = (ROOT / PAGE / 'population-precision.js').read_text(encoding='utf-8')
        extension = Path('research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026')
        stems = re.findall(r"\['((?:analysis_precision26|analysis_geometry26|report26)/[^']+)'", script)
        assets = [extension / (stem + suffix) for stem in stems for suffix in ['.png', '.pdf']]
        assets += [extension / 'report26/figures/P02_policy32_Q_labor_support_SOURCE.csv',
                   Path('research/statistics/research_closeout_20261022/DATA_EVIDENCE_OVERVIEW_20261026.png')]
        for rel in assets:
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest)
        staged = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
        # 旧包中已有依赖继续保留；新增的HTML直接依赖必须在更新后的集合中存在。
        expected = names | staged
        for p in (stage / PAGE).glob('*.html'):
            for ref in re.findall(r'(?:src|href)=["\']([^"\']+)', p.read_text(encoding='utf-8')):
                target = local_reference(p.relative_to(stage).as_posix(), ref)
                assert target is None or target in expected, (p.name, ref)
        assert all(not n.endswith(('.md', '.py', '.zip', '.json')) for n in staged)
        for spec in index['tables']:
            assert all((PAGE / 'v2-data' / Path(part['path']).with_suffix('.js')).as_posix() in staged for part in spec['parts'])
        shutil.copy2(ZIP, pending)
        subprocess.run([str(SEVENZIP), 'u', str(pending), './*', '-mx=7', '-mmt=4', '-mcu=on', '-bsp0'],
                       cwd=stage, check=True, stdout=subprocess.DEVNULL)
        with ZipFile(pending) as archive:
            assert archive.testzip() is None
            assert all(archive.read(n) == (stage / n).read_bytes() for n in staged)
            final_names = archive.namelist()
        pending.replace(ZIP)
        receipt.update(files=sum(not n.endswith('/') for n in final_names), zip_MiB=round(ZIP.stat().st_size / 2**20, 1),
                       tables=len(index['tables']), parts=sum(len(t['parts']) for t in index['tables']),
                       refreshed='2026-10-27 自然256＋精确边际／历史策略32', population256_included=True,
                       natural_paths=256, policy_paths=32, semi='original version retained',
                       browser_visual_check='blocked: file URL browser policy; no workaround attempted',
                       runtime_byte_match=True, zip_integrity='CRC passed')
        (DELIVERY / '交付检查.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(receipt, ensure_ascii=True))


if __name__ == '__main__':
    refresh()
