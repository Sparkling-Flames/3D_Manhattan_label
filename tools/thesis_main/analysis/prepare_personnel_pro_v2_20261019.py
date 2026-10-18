"""登记可随 main 提交的匿名研究输入与 Release 原图映射；不打 ZIP、不上传。"""
import csv
import gzip
import io
import json
import shutil
import zipfile
from pathlib import Path

from .build_research_workbench_v2_20261019 import ROOT, QUALITY, INPUT, EVIDENCE, STATS, read
from .v2_evidence_audit_20261019 import public_value

OUT = ROOT/'research/workers/pro_personnel_v2_20261019'
RELEASE = 'https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015'


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    data = read(INPUT/'data.json.gz')
    context = public_value(dict(data_release='v2', reference_catalog=read(QUALITY/'reference_catalog.json'),
                          difficulty_records=read(QUALITY/'difficulty_records.json'), room_registry=data['room_registry']))
    (OUT/'analysis_context.json.gz').write_bytes(gzip.compress(json.dumps(context,ensure_ascii=False,allow_nan=False).encode('utf-8'),mtime=0))
    (STATS/'tables.json.gz').write_bytes(gzip.compress((STATS/'tables.json').read_bytes(),mtime=0))
    old = ROOT/'research/workers/pro_personnel_handoff_20261018/Pro_personnel_QT_difficulty_clusters_20261018.zip'
    with zipfile.ZipFile(old) as package:
        release_rows = list(csv.DictReader(io.StringIO(package.read('IMAGE_INDEX.csv').decode('utf-8-sig'))))
        current_rows = list(csv.DictReader(io.StringIO(package.read('IMAGE_COVERAGE.csv').decode('utf-8-sig'))))
    release_map = {r['image_id']:r for r in release_rows}
    rows=[]
    current_ids={r['image_id'] for r in context['difficulty_records']}
    assert current_ids == {r['image_id'] for r in current_rows}
    for r in current_rows:
        source=release_map.get(r['image_id'])
        preview=None
        if not source:
            target=OUT/'previews'/Path(r['preview_path']).name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/r['preview_path'],target)
            preview=target.relative_to(ROOT).as_posix()
        rows.append(dict(image_id=r['image_id'],image_code=r['image_code'],source_path=r['source_path'],
                         archive=source['archive'] if source else None,archive_path=source['archive_path'] if source else None,
                         preview_path=preview,original_status='release_manifest_listed' if source else 'not_in_existing_release_manifest'))
    with (OUT/'IMAGE_INDEX.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    required=[EVIDENCE/'records.json.gz',EVIDENCE/'COVERAGE.json',EVIDENCE/'field_contract.json',
              STATS/'tables.json.gz',STATS/'REPRO_CONTEXT.json.gz',STATS/'COVERAGE.json',STATS/'CONSUMER_INTERFACE.json',OUT/'analysis_context.json.gz',OUT/'IMAGE_INDEX.csv',
              ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip',
              ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py']
    for path in required:
        if not path.is_file():raise FileNotFoundError(path)
    manifest=dict(schema='pro_personnel_v2_main_inputs_v1',data_release='v2',delivery='prompt_plus_user_published_github_main_no_zip',
                  files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size) for p in required],
                  counts=read(EVIDENCE/'COVERAGE.json'),original_images_release=RELEASE,
                  original_images_in_release_manifest=sum(r['archive'] is not None for r in rows),
                  preview_only_images=[r['image_code'] for r in rows if r['archive'] is None],
                  scope='Sufficient for new analysis from audited frozen rows/geometry; not a claim to replay acquisition and all local audit sources.',
                  upstream_rebuild='INPUTS.json under evidence and CONSUMER_INTERFACE under statistics describe local-only audit inputs.',
                  privacy='Pseudonymous worker IDs; source account/name fields and machine paths removed. No new raw exports published.')
    (OUT/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    assert len(rows)==261 and len(read(EVIDENCE/'records.json.gz')['records'])==10439
    print(json.dumps(dict(images=len(rows),preview_only=manifest['preview_only_images'],files=len(required)),ensure_ascii=True))


if __name__=='__main__':run()
