"""独立Pro交接ZIP；显式范围、Python导入依赖闭包、原图Release外置。"""
import ast
import csv
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/workers/pro_personnel_handoff_20261018'
ZIP=OUT/'Pro_personnel_QT_difficulty_clusters_20261018.zip'
PACKAGES=[
 'research/data/processed_input_review_20261018',
 'research/difficulty/difficulty_current_20261017',
 'research/quality/quality_b8l2_d10_20261017',
 'research/quality/quality_ab_feedback_handoff_20261015',
 'research/workers/worker_difficulty_profiles_20261018',
 'research/workers/worker_b8l2_d10_20261017',
 'research/workers/worker_v1_composition_20261017',
 'research/workers/worker_v1_pro_integration_20261017',
 'research/workers/worker_fine_composition_20261018',
 'research/workers/worker_exchangeability_20261018',
 'research/workers/worker_quality_scope_review_20261018',
 'research/fusion/wall_consensus_v1_process_20261017',
 'research/fusion/worker_composition_fusion_20261018',
 'research/fusion/worker_exchangeability_fusion_20261018',
 'research/statistics/cluster_review_20261018',
]
SEEDS=['worker_difficulty_profiles_20261018','build_cluster_review_20261018','worker_annotation_similarity_20261018',
       'worker_exchangeability_20261018','worker_composition_fusion_20261018','worker_fine_composition_20261018']


def code_closure(seeds):
    found=set();queue=[ROOT/('tools/thesis_main/analysis/'+s+'.py') for s in seeds]
    def resolve(parts):
        base=ROOT.joinpath(*parts)
        return next((p for p in [base.with_suffix('.py'),base/'__init__.py'] if p.is_file()),None)
    while queue:
        p=queue.pop()
        if p in found:continue
        found.add(p)
        rel=p.relative_to(ROOT).with_suffix('').parts
        for node in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
            modules=[]
            if isinstance(node,ast.Import):modules=[n.name.split('.') for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                parts=list(rel[:-node.level]) if node.level else []
                parts+=(node.module or '').split('.') if node.module else []
                modules=[parts]+[parts+n.name.split('.') for n in node.names if n.name!='*']
            for parts in modules:
                target=resolve(parts)
                if target and target not in found:queue.append(target)
        for parent in p.parents:
            if parent==ROOT:break
            init=parent/'__init__.py'
            if init.is_file() and init not in found:queue.append(init)
    return found


def main():
    from .research_round_20260929 import prepare_record
    from ..data_prep.consolidate_research_input import load_current_bundle
    from ..data_prep.project_public_research_20260929 import project_bundle
    import numpy as np
    import pandas as pd
    OUT.mkdir(parents=True,exist_ok=True)
    files=set()
    for folder in PACKAGES:
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(code_closure(SEEDS))
    for name in ['worker_difficulty_profiles_20261018','cluster_review_20261018','worker_annotation_similarity_20261018']:
        files.add(ROOT/f'tests/test_{name}.py')
    for path in ['research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip',
                 'research/statistics/annotation_gallery_20261017/gallery.json',
                 'research/quality/geometry_quality_review_20261018/REVIEW.md',
                 'research/quality/geometry_quality_review_20261018/README.md']:
        files.add(ROOT/path)
    docs=['PAPER_A_METHOD_CONTRACT_CURRENT.json','PAPER_A_METHOD_CONTRACT_CURRENT.md','CONTEXT.md',
          '研究模型_人员图片与融合不确定性_20261006.md','研究数据说明_来源预处理与用途_20261006.md',
          '人员分类与作答分簇讨论记录_20261018.md','处理修订核验与人员细分类收尾_20261018.md',
          '人员可替换性与多人组合核验_20261018.md']
    files.update(ROOT/'docs/thesis_main'/p for p in docs)
    page=ROOT/'research/statistics/research_explorer_v1_r2_20261017'
    pagefiles=['workbench.css','workbench-core.js','geometry-view.js','cluster_review.html','cluster-review.js',
               'cluster-overlay.js','cluster-review-data.js','personnel_difficulty.html','personnel-difficulty.js',
               'personnel-difficulty-data.js','personnel_composition.html','personnel-composition-data.js',
               'personnel-composition.js','personnel_exchangeability.html','exchangeability-data.js','exchangeability.js']
    files.update(page/p for p in pagefiles if (page/p).is_file())
    gallery=json.loads((ROOT/'research/statistics/annotation_gallery_20261017/gallery.json').read_text(encoding='utf-8'))
    files.update(ROOT/i['thumbnail_path'] for i in gallery['images'])
    imageindex=ROOT/'analysis_results/quality/quality_scope_model_handoff_20261015/original_images/IMAGE_INDEX.csv'
    index=pd.read_csv(imageindex)
    missing_images=[i for i in gallery['images'] if i['image_id'] not in set(index.image_id)]
    files.update(ROOT/i['original_path'] for i in missing_images)
    photo_map={i['original_path']:i['thumbnail_path'] for i in gallery['images']}
    original=json.loads((ROOT/'research/fusion/wall_consensus_v1_process_20261017/input_snapshot.json').read_text(encoding='utf-8'))
    revised=json.loads((ROOT/'research/fusion/worker_composition_fusion_20261018/input_snapshot.json').read_text(encoding='utf-8'))
    pools={p['pool_id']:p for p in original['images']}
    pools.update({p['pool_id']:p for p in revised['images']})
    bundle=load_current_bundle(ROOT/'research/data/processed_input_review_20261018/manifest.json')
    projected,_=project_bundle(bundle)
    needed={r['id'] for p in pools.values() for r in p['records']}
    current={r['id']:prepare_record(r) for im in projected['images'] for r in im['annotations'] if r['id'] in needed}
    checks=0
    for p in pools.values():
        for r in p['records']:
            assert np.array_equal(np.array(r['points']),np.array(current[r['id']]['points'])),r['id']
            checks+=1
    extras={p.name:p.read_bytes() for p in OUT.glob('*.md')}
    extras['smoke_core.py']=(OUT/'smoke_core.py').read_bytes()
    extras['IMAGE_INDEX.csv']=imageindex.read_bytes()
    image_rows=[]
    for im in gallery['images']:
        hit=index[index.image_id.eq(im['image_id'])]
        image_rows.append(dict(image_id=im['image_id'],image_code=im['image_code'],preview_path=im['thumbnail_path'],
            source_path=im['original_path'],original_in_this_zip=hit.empty,
            release_archive='' if hit.empty else hit.iloc[0]['archive'],
            release_archive_path='' if hit.empty else hit.iloc[0]['archive_path']))
    extras['IMAGE_COVERAGE.csv']=pd.DataFrame(image_rows).to_csv(index=False).encode('utf-8-sig')
    extras['CURRENT_POOLS.json']=json.dumps(dict(input_manifest='research/data/processed_input_review_20261018/manifest.json',
        note='按pool_id以修订九池覆盖旧池；池存在不代表自动获得质量资格，读取records与layer用途；难度连接当前image_metadata.csv',
        images=list(pools.values())),ensure_ascii=False).encode('utf-8')
    extras['requirements.txt']=b'numpy\npandas\nscipy\nshapely\npytest\nPillow\n'
    extras['research/statistics/research_explorer_v1_r2_20261017/index.html']=('<!doctype html><meta charset="utf-8"><h1>Pro研究包</h1>'+''.join(f'<p><a href="{p}">{t}</a></p>' for p,t in [('personnel_difficulty.html','全量人员×难度'),('cluster_review.html','分簇叠加审查'),('personnel_composition.html','旧八图构成实验'),('personnel_exchangeability.html','旧八图多人替换')])).encode('utf-8')
    entries={}
    for p in sorted(files):
        assert p.is_file(),p
        name=p.relative_to(ROOT).as_posix()
        assert 'label_studio_received_20261017' not in name and '__pycache__' not in name
        content=p.read_bytes()
        if (p.parent==page and p.suffix=='.js') or name=='research/statistics/cluster_review_20261018/review.json':
            s=content.decode('utf-8')
            for a,b in photo_map.items():s=s.replace('../../../'+a,'../../../'+b)
            content=s.encode('utf-8')
        entries[name]=content
    entries.update(extras)
    inventory=[dict(path=p,bytes=len(b)) for p,b in entries.items()]
    entries['PACKAGE_FILES.json']=json.dumps(inventory,ensure_ascii=False,indent=2).encode('utf-8')
    checks=dict(prepared_pool_count=len(pools),prepared_record_occurrences_checked=checks,
        preview_images=len(gallery['images']),release_index_images=len(index),release_current_coverage=len(gallery['images'])-len(missing_images),
        supplemental_originals_in_zip=[i['image_code'] for i in missing_images],
        python_source_files=sum(p.endswith('.py') for p in entries),files_before_manifest=len(entries),
        original_images_external=True,github_updated=False,simulation_data_included=False)
    (OUT/'BUILD_CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    entries['BUILD_CHECKS.json']=json.dumps(checks,indent=2).encode('utf-8')
    with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,content in entries.items():archive.writestr(name,content)
    with zipfile.ZipFile(ZIP) as archive:assert archive.testzip() is None
    print(json.dumps(dict(**checks,zip_mb=ZIP.stat().st_size/1e6,path=str(ZIP)),ensure_ascii=False))


if __name__=='__main__':main()
