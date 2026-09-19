"""Build a standalone review from the existing Studio foundation; never edit old pages."""
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

from . import local_points as lp
from .precision_audit import stable_angles

REPO = Path(__file__).resolve().parents[4]
OUT = lp.ROOT / 'pro_followup_20260920'
FOUNDATION = REPO / 'analysis_results/panorama_studio_20260907_v3'
METHODS = ['OSPA1_6', 'Hausdorff_9', 'Bottleneck_equal_9']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def build():
    notes = read(OUT / 'visual_review.json')
    rows, _ = lp.load()
    by = {r['canonical_annotation_id']: r for r in rows}
    cache = read(lp.ROOT / 'local_recheck/cache.json')
    hs = (FOUNDATION / 'history_data.js').read_text(encoding='utf-8')
    summaries = json.JSONDecoder().raw_decode(hs.split('push(...', 1)[1])[0]
    lookup = {s['image_id']: s for s in summaries}
    review = OUT / 'review'
    review.mkdir(parents=True, exist_ok=True)
    cases, evidence, images = [], [], []
    for idx, note in enumerate(notes):
        keys = [k for k, g in cache.items() if g['code'] == note['code'] and k.endswith('|'+note['condition'])]
        assert len(keys) == 1, keys
        key = keys[0]; g = cache[key]; iid = key.split('|')[0]
        ids = g['ids']
        assert len(set(g['workers'])) == len(ids)
        raw = (FOUNDATION / lookup[iid]['history_script']).read_text(encoding='utf-8')
        payload = json.JSONDecoder().raw_decode(raw.split('],', 1)[1])[0]
        variants = {v['source']['canonical_annotation_id']: v for v in payload['variants']}
        vv = []
        for id in ids:
            v = variants[id]
            assert v['source']['effective_points'] == by[id]['effective_points_1024x512'], id
            assert v['source']['mode'].lower() == note['condition'], id
            vv.append(v)
        photo = raw[raw.index('{const image='):]
        photo = re.sub(r'STUDIO_IMAGES\[\d+\]', f'STUDIO_IMAGES[{idx}]', photo)
        images.append(photo)
        pairs = []
        for wa, wb in note['pairs']:
            ia, ib = g['workers'].index(wa), g['workers'].index(wb)
            a, b = by[ids[ia]], by[ids[ib]]
            f = lp.features(stable_angles(a['effective_points_1024x512'], b['effective_points_1024x512']))
            pairs.append(dict(workers=[wa, wb], ids=[ids[ia], ids[ib]],
                ospa1=float(f['ospa1']), hausdorff=float(f['hausdorff']),
                same_cluster={m: g['labels'][m][ia] == g['labels'][m][ib] for m in METHODS}))
        record = dict(note, key=key, image_id=iid, ids=ids, workers=g['workers'], counts=g['counts'],
                      labels={m:g['labels'][m] for m in METHODS}, pairs_detail=pairs,
                      user_decision=None, numerical_version='20260919 local_recheck frozen; no x-order experiment')
        evidence.append(record)
        cases.append(dict(image_id=iid, title=note['code']+' · '+note['condition'],
                          category='Pro续研 · '+note['purpose'], variants=vv, followup=record))
    write(OUT/'evidence.json', evidence)
    for name in ['studio.js','studio.css','three.min.js','OrbitControls.js','history.css']:
        shutil.copyfile(FOUNDATION/name, review/name)
    shutil.copyfile(Path(__file__).with_name('pro_followup_panel.js'), review/'followup.js')
    html = (FOUNDATION/'index.html').read_text(encoding='utf-8')
    html = re.sub(r'<script[^>]*src="(?:image_\d+|history_data|history)\.js"[^>]*></script>', '', html)
    html = html.replace('</head>', '<link rel="stylesheet" href="history.css"></head>')
    html = html.replace('</body>', '<script defer src="followup.js"></script></body>')
    html = html.replace('<title>空间标本 · 全景布局审查</title>', '<title>Pro续研 · 六图专项复核</title>')
    (review/'index.html').write_text(html, encoding='utf-8')
    (review/'data.js').write_text('window.STUDIO_DATA='+json.dumps(dict(cases=cases,counts={'cases':len(cases),'variants':sum(len(c['variants']) for c in cases)}),ensure_ascii=False)+';\nwindow.STUDIO_IMAGES={};\n'+'\n'.join(images),encoding='utf-8')
    return evidence


def package():
    """Explicit evidence allowlist; no raw logs, credentials, arbitrary repository copy."""
    files = set()
    def add(path):
        if path.is_dir():
            files.update(p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
        else:
            assert path.is_file(), path
            files.add(path)
    add(lp.ROOT/'inputs'); add(lp.ROOT/'INPUT_MANIFEST.json'); add(lp.ROOT/'received_results')
    for p in Path(__file__).parent.glob('*.py'):
        if p.stem not in ['pro_followup','pair_pilot']:add(p)
    add(lp.ROOT/'previous_pairing_time')
    add(REPO/'analysis_results/full_corpus_research_received_20260918/full_study_20260918/code/legacy_reproduction.py')
    for name in ['README.md','REPORT_ZH.md','独立审查与研究方向.md']:add(lp.ROOT/name)
    for name in ['pairwise.csv','memberships.csv','cache.json','REPRODUCTION_CHECK.json','NUMERICAL_SCOPE.json','precision_pairwise.csv','INDEPENDENT_CHECK.json']:
        add(lp.ROOT/'local_recheck'/name)
    add(lp.ROOT/'pair_pilot/evidence.json');add(lp.ROOT/'pair_pilot/用户_六图点对审核_原始.json');add(lp.ROOT/'pair_pilot/README.md')
    for name in ['用户_39图文字审核_原始.json','一正_39图审核_原始.json','用户_39图最终裁决_原始.json']:
        add(REPO/'analysis_results/human_review_reconciliation_20260918'/name)
    add(REPO/'analysis_results/cluster_review_extra_20260919/用户_12图审核_原始.json')
    for name in ['相似场景标注稳定性分析SOP.md','图片分类与同房间收敛预测研究SOP.md','真人标注不确定性研究_当前状态.md','用户研究要求核对清单_20260913.md']:
        add(REPO/'docs/thesis_main'/name)
    for name in ['README.md','visual_review.json','evidence.json','review','verify.py']:add(OUT/name)
    archive = OUT/'Pro续研_20260920.zip'
    manifest=OUT/'package_manifest.json'
    files.add(manifest)
    write(manifest,dict(files=[p.relative_to(REPO).as_posix() for p in sorted(files)],
          archive=archive.name, includes_original_runtime_exports=False, includes_raw_time_logs=False,
          source_paths_inside_records='provenance only; frozen inputs are included'))
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(REPO).as_posix())
        z.writestr('START_HERE.md', '# Pro续研入口\n\n请先阅读 analysis_results/local_point_research_received_20260919/pro_followup_20260920/README.md。\n\n从解压根目录运行：\n\n```\npython -B analysis_results/local_point_research_received_20260919/pro_followup_20260920/verify.py\n```\n')
    print('package', len(files), 'files', archive.stat().st_size, 'bytes')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',action='store_true');args=parser.parse_args()
    result=build();print('built',len(result),'cases',sum(len(r['ids']) for r in result),'responses')
    if args.package:package()
