#!/usr/bin/env python3
"""Package the completed, frozen data-v1 study and verify delivery integrity.

This script does not fit models or alter input data. Run it only after all study
outputs and the report have been produced. Large regenerable caches are omitted.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
PREFIX = 'personnel_quality_v1'
COMMIT = 'c4dd8266c42a478c68b0dce8097c98e33e4b32b2'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def omitted(path: Path) -> bool:
    parts = path.parts
    return (
        '__pycache__' in parts or path.suffix == '.pyc'
        or parts[:2] == ('fusion', 'inputs')
        or parts[:2] == ('report', 'qa')
        or path.name in {'validated_annotations.json', 'validated_images.json', 'NotoSansSC-VF.ttf'}
        or path.name.endswith('measurement_records.json')
    )


def table_shape(path: Path) -> dict:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        return {'rows': len(rows), 'columns': len(reader.fieldnames or [])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--study', type=Path, default=HERE)
    ap.add_argument('--repo', type=Path, default=HERE.parent/'repo')
    ap.add_argument('--out', type=Path, default=HERE.parent/'deliverables')
    ap.add_argument('--attachment-dir', type=Path, default=HERE.parent/'brief')
    ap.add_argument('--attachment-zip', type=Path, default=HERE.parent/'upload/worker_quality_profile_brief_20261017.zip')
    ap.add_argument('--scope-note', type=Path, default=HERE.parent/'project_sources/01-scope-.md')
    args = ap.parse_args()
    study, repo, out = args.study.resolve(), args.repo.resolve(), args.out.resolve()
    required = [
        'README_ZH.md', 'requirements.txt', 'report/personnel_quality_v1_report_zh.pdf',
        'report/PDF_QA_RECEIPT.json', 'integration/personnel_profiles_v1.csv',
        'integration/personnel_profiles_full.csv', 'integration/FIELD_GUIDE_ZH.md',
        'integration/classification_candidates.csv', 'integration/event_evidence_union.csv',
        'q/RUN_RECEIPT.json', 'reliability/run_evidence.json',
        'reliability/reproduction_comparison_receipt.json', 'fusion/stage2/PERMUTATIONS.csv',
        'fusion/stage2/path_states.csv', 'fusion/stage2/RUN_RECEIPT.json',
        'q/INTEGRATION_AUDIT_RECEIPT.json', 'q/STAGE2_SCOPE_AUDIT_RECEIPT.json',
    ]
    assert all((study/p).is_file() for p in required), 'A required final deliverable is missing.'
    current = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    assert current == COMMIT, (current, COMMIT)
    status = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=no'], text=True)
    assert not status.strip(), 'Tracked repository content has changed.'

    integration = json.loads((study/'integration/INTEGRATION_RECEIPT.json').read_text())
    verified_inputs = []
    for rel, expected in integration['source_sha256'].items():
        assert digest(study/rel) == expected, f'Integrated input changed: {rel}'
        verified_inputs.append(rel)
    shapes = {p: table_shape(study/p) for p in [
        'integration/personnel_profiles_v1.csv', 'integration/personnel_profiles_full.csv',
        'integration/classification_candidates.csv', 'integration/event_evidence_union.csv',
        'fusion/stage2/PERMUTATIONS.csv', 'fusion/stage2/path_states.csv']}
    assert shapes['integration/personnel_profiles_v1.csv'] == {'rows': 27, 'columns': 47}
    assert shapes['integration/personnel_profiles_full.csv'] == {'rows': 27, 'columns': 226}
    assert shapes['integration/event_evidence_union.csv']['rows'] == 3222
    assert shapes['fusion/stage2/PERMUTATIONS.csv']['rows'] == 336
    assert shapes['fusion/stage2/path_states.csv']['rows'] == 2688
    qa = json.loads((study/'report/PDF_QA_RECEIPT.json').read_text())
    assert qa['pdf_sha256'] == digest(study/'report/personnel_quality_v1_report_zh.pdf')
    assert qa['pages'] == 17 and qa['status'] == 'completed'

    selected = [(p, f'{PREFIX}/study/{p.relative_to(study).as_posix()}')
                for p in sorted(study.rglob('*')) if p.is_file() and not omitted(p.relative_to(study))]
    selected.append((study/'README_ZH.md', f'{PREFIX}/README_ZH.md'))
    for p in sorted(args.attachment_dir.rglob('*')):
        if p.is_file():
            selected.append((p, f'{PREFIX}/sources/attachment/{p.relative_to(args.attachment_dir).as_posix()}'))
    for p in [args.attachment_zip, args.scope_note]:
        if p.is_file():
            selected.append((p, f'{PREFIX}/sources/{p.name}'))
    names = [arc for _, arc in selected]
    assert len(set(names)) == len(names)
    manifest = {
        'data_release': 'v1', 'repository_commit': COMMIT,
        'file_count': len(selected),
        'files': [{'path': arc, 'bytes': p.stat().st_size, 'sha256': digest(p)} for p, arc in selected],
        'omitted_regenerable_or_duplicate_material': [
            'reliability/validated_*.json', 'reliability/*measurement_records.json',
            'fusion/inputs/', '**/__pycache__/', 'report/qa/', 'report/assets/NotoSansSC-VF.ttf'],
        'self_reference_policy': 'This manifest and PACKAGE_VERIFICATION.json are not listed in their own content hash inventory.'
    }
    out.mkdir(parents=True, exist_ok=True)
    report_out = out/'personnel_quality_v1_report_zh.pdf'
    table_out = out/'personnel_profiles_v1.csv'
    zip_out = out/'personnel_quality_v1_reproducibility.zip'
    shutil.copy2(study/'report/personnel_quality_v1_report_zh.pdf', report_out)
    shutil.copy2(study/'integration/personnel_profiles_v1.csv', table_out)
    with zipfile.ZipFile(zip_out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        for p, arc in selected:
            archive.write(p, arc)
        archive.writestr(f'{PREFIX}/PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    with zipfile.ZipFile(zip_out) as archive:
        assert archive.testzip() is None
        assert len(archive.infolist()) == len(selected)+1
        for entry in manifest['files']:
            raw = archive.read(entry['path'])
            assert len(raw) == entry['bytes']
            assert hashlib.sha256(raw).hexdigest() == entry['sha256']

    verification = {
        'status': 'completed', 'data_release': 'v1', 'repository_commit': COMMIT,
        'tracked_repository_unchanged': True, 'integrated_source_hashes_verified': verified_inputs,
        'table_shapes': shapes, 'pdf_qa_completed': True, 'report_pages': qa['pages'],
        'content_files_checked_by_crc_and_sha256': len(selected),
        'manifest_included': True, 'all_required_entries_present': True,
        'standalone_report_sha256': digest(report_out), 'standalone_personnel_csv_sha256': digest(table_out),
        'no_model_retraining_during_packaging': True,
    }
    with zipfile.ZipFile(zip_out, 'a', compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        archive.writestr(f'{PREFIX}/PACKAGE_VERIFICATION.json', json.dumps(verification, ensure_ascii=False, indent=2)+'\n')
    with zipfile.ZipFile(zip_out) as archive:
        assert archive.testzip() is None
        assert len(archive.infolist()) == len(selected)+2
    print(json.dumps({
        'status': 'completed', 'data_release': 'v1', 'archive_content_files': len(selected),
        'archive_total_entries': len(selected)+2, 'all_crc_and_content_hash_checks_passed': True,
        'outputs': [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in [report_out, table_out, zip_out]],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
