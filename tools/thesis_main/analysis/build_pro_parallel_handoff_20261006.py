"""为用户手动上传Pro导出八图原图、现行坐标、用途和最新解释。"""
import json
from pathlib import Path
import shutil

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
from .research_round_20260929 import prepare_record, reconstruct

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/pro_parallel_handoff_20261006'
CODES = {'x8F5xyUWy9e-01','x8F5xyUWy9e-09','uNb9QFRL6hY-47','jtcxE69GiFV-12',
         'rPc6DW4iMge-06','yqstnuAEVhm-32','7y3sRwLe3Va-04','UwV83HsGsw3-09'}


def public_excerpt(value):
    """公开摘录省略原评论、原对象映射和内部来源；保留既有裁决。"""
    if isinstance(value, dict):
        return {key: public_excerpt(item) for key, item in value.items()
                if key not in {'image_comment', 'object_id', 'source'}}
    if isinstance(value, list):
        return [public_excerpt(item) for item in value]
    return value


def build():
    bundle = load_current_bundle()
    panel, mapping = project_bundle(bundle)
    originals = {mapping['records'][r['object_id']]: r for r in bundle['data']['objects']}
    metadata = {r['image_code']:r for r in bundle['research']['images']}
    cases, provenance = [], []
    (OUT/'images').mkdir(parents=True,exist_ok=True)
    for im in panel['images']:
        if im['code'] not in CODES:
            continue
        for field in ('annotations','references'):
            prepared = []
            for record in im[field]:
                original = originals[record['id']]
                r = prepare_record(dict(record, source_pair_indices=original['ordered_source_pair_indices']))
                geom = reconstruct(r)
                state = geom['representations']['declared_footprint']
                r.update(footprint=geom['floor'].tolist() if state['status']=='ok' else None, footprint_state=state)
                prepared.append(r)
                provenance.append(dict(record=r['id'], object_id=original['object_id'], image=im['code'],
                                       source=original['source'], ordered_source_pair_indices=original['ordered_source_pair_indices']))
            im[field] = prepared
        meta = metadata[im['code']]
        label = ROOT / meta['references']['gt_original'].split(':',2)[2]
        photo = label.parent.parent/'img'/f"{meta['image_id']}.png"
        shutil.copy2(photo, OUT/'images'/f"{im['code']}.png")
        im.update(image_file=f"images/{im['code']}.png", image_id=meta['image_id'],
                  scene_evidence={k:meta[k] for k in ('image_comment','stable_nonorthogonal','scene_categories','gt_evidence',
                                                     'expected_annotation_extent','scope_existing_ledger','detail_existing_ledger')})
        cases.append(im)
    assert len(cases)==len(CODES)
    public_cases = public_excerpt(cases)
    public_sources = [{key: row[key] for key in ('record', 'image', 'ordered_source_pair_indices')}
                      for row in provenance]
    for original, public in zip(provenance, public_sources):
        if isinstance(original['source'], dict):
            public['source'] = {key: original['source'][key] for key in ('worker', 'condition')}
    source_manifest = dict(panel['source_manifest'], privacy='Public excerpt: original comments, object mappings and machine source identifiers omitted.')
    (OUT/'cases.json').write_text(json.dumps(dict(schema='pro_parallel_cases_v1', images=public_cases,
        source_manifest=source_manifest, coordinate_frame=bundle['data']['coordinate_frame'],
        preprocessing=bundle['data']['preprocessing'], record_sources=public_sources, publication={'kind': 'public_excerpt_v1'}),ensure_ascii=False,indent=2),encoding='utf-8')
    files = [
        'docs/thesis_main/研究模型_人员图片与融合不确定性_20261006.md',
        'docs/thesis_main/CONTEXT.md',
        'docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md',
        'docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json',
        'analysis_results/difficulty_consensus_20261006/user_review.json',
        'analysis_results/difficulty_consensus_20261006/updated/REPORT.md',
        'analysis_results/worker_count_composition_20261006/CONCLUSIONS.md',
        'analysis_results/consensus_response_20261006/REPORT.md',
        'analysis_results/consensus_response_20261006/all_pool_summary.csv',
        'analysis_results/consensus_response_20261006/field_contract.json',
        'analysis_results/consensus_response_20261006/common10_all_consensus.geojson',
        'analysis_results/consensus_response_20261006/common10_reference_curves.png',
        'analysis_results/consensus_response_20261006/common10_all_consensus.png',
        'research/fast_research_return_20261006/README.md',
        'research/fast_research_return_20261006/pro_original/REPORT_ZH.md',
        'research/fast_research_return_20261006/pro_original/src/lee_excerpt.py',
        'research/fast_research_return_20261006/pro_original/src/arc_excerpt.py',
    ]
    for name in files:
        dest=OUT/name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/name,dest)
    # Export only case-relevant derived rows; keep complete pools within each case.
    import csv
    for name in ('individual_reference.csv','pairwise_distances.csv','uniform_curves.csv'):
        with (ROOT/'analysis_results/consensus_response_20261006'/name).open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f); rows=[r for r in reader if r['image'] in CODES]; fields=reader.fieldnames
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    (OUT/'CONTENTS.json').write_text(json.dumps(dict(images=len(cases),source_files=files,
        annotations=sum(len(c['annotations']) for c in cases),
        note='cases含保留及历史/排除记录；计算须沿independent、consensus_eligible、condition与gate分池。原图已复制，不需要联网找图。'),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(path=str(OUT),images=len(cases),annotations=sum(len(c['annotations']) for c in cases))))


if __name__=='__main__':
    build()
