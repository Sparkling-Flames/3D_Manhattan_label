#!/usr/bin/env python3
"""Package frozen research deliverables; no fitting, fusion or scoring.

Preserves repository-relative paths and keeps independently delivered event and
endpoint tables outside these two packages. Source-specific frozen manifests
are reused rather than discovering arbitrary working copies.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
NEW = HERE.parent
ROOT = NEW.parents[2]
OLD_ZIP = ROOT / 'research/workers/personnel_useful_taxonomy_v3_20261021/integration/HOHONET_v3_复现代码与必要小输入_20261021.zip'
CORE = 'CORE_RESEARCH_CODE_AND_SMALL_EVIDENCE.zip'
SMALL = 'SMALL_ANALYSIS_INPUTS.zip'
MANIFEST = HERE / 'CORE_PACKAGE_INPUTS.csv'
RECEIPT = HERE / 'CORE_PACKAGE_RECEIPT.json'
EXCLUDED_INTEGRATION = {
    'RECOMMENDED_EXCHANGE_CONDITIONS.csv',
    'RECOMMENDED_CONDITIONS_SCHEMA_ZH.md',
}
BAD_PARTS = {'__pycache__', 'runtime', 'checkpoints', 'event_parts',
             'extra_cells', 'rebuilt_event_inputs', 'recovery_adapter_check',
             '.git', 'venv', '.venv'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def allowed(p):
    rel = p.relative_to(NEW)
    name = p.name
    return (p.is_file() and not any(x in BAD_PARTS for x in rel.parts)
            and not name.startswith('.')
            and not any(x in name.upper() for x in ('PARTIAL', 'CHECKPOINT', 'PROGRESS'))
            and not name.endswith(('.tmp', '.zip', '.pyc', '.log', '.jsonl')))


def collect():
    selected = {}
    external = {}

    def add(p, archive=CORE, role='formal_small_evidence', expected_sha=None):
        p = Path(p)
        assert allowed(p), ('not_packable', str(p))
        rel = str(p.relative_to(ROOT))
        if rel in selected:
            assert selected[rel]['archive'] == archive, ('duplicate_archive_assignment', rel)
            if expected_sha:
                assert selected[rel]['sha256'] == expected_sha, ('frozen_source_changed', rel)
            return
        digest = sha(p)
        if expected_sha:
            assert digest == expected_sha, ('frozen_source_changed', rel)
        selected[rel] = dict(repo_path=rel, archive=archive, delivery_mode='included',
                             role=role, bytes=p.stat().st_size, sha256=digest,
                             hash_source='current frozen file', required_for=role,
                             source_identity='20261022 research round; real v2 data')

    def external_file(p, role, digest='', size='', hash_source='source delivery manifest', identity='existing independently delivered artifact'):
        p = Path(p)
        rel = str(p.relative_to(ROOT))
        if rel in selected:
            return
        external[rel] = dict(repo_path=rel, archive='', delivery_mode='external',
                             role=role, bytes=size, sha256=digest,
                             hash_source=hash_source, required_for=role, source_identity=identity)

    # All current research code; root report prose and volatile outputs excluded.
    for p in sorted(NEW.rglob('*.py')):
        if allowed(p) and p.name != 'build_download_catalog.py':
            add(p, role='research_code')

    # Cross-condition discovery uses its final explicit manifest, no checkpoints.
    tax = NEW / 'cross_condition_taxonomy'
    for r in csv_rows(tax / 'PACKAGE_MANIFEST.csv'):
        if allowed(tax / r['path']):
            add(tax / r['path'], role='frozen_taxonomy_labels_definitions_and_evidence', expected_sha=r['sha256'])
    for name in ['PACKAGE_MANIFEST.csv', 'DELIVERY_RECEIPT.json']:
        if (tax / name).exists():
            add(tax / name, role='taxonomy_source_manifest')

    # Screening retains selected conditions and held-out summaries. The complete
    # old event inventory and exhaustive candidate caches remain independent.
    screen = NEW / 'screening'
    excluded_screen = {'EVENTS_UNIFIED.csv.gz'}
    for p in sorted(screen.iterdir()):
        if allowed(p) and p.name not in excluded_screen:
            add(p, role='historical_screening_small_summary')
    for p in sorted((screen / 'views').rglob('*')):
        if allowed(p) and p.name in {'SELECTED_CONDITIONS.csv', 'COMPLETION.json'}:
            add(p, role='historical_screening_selected_conditions')
    for p in sorted((screen / 'lobo').rglob('*')):
        if allowed(p) and p.name in {'CONDITION_HELDOUT_SUMMARY.csv.gz', 'HELDOUT_SUMMARY.csv', 'COMPLETION.json'}:
            add(p, role='historical_screening_internal_heldout_summary')
    screen_manifest = json.loads((screen / 'FINAL_MANIFEST.json').read_text())
    for r in screen_manifest['files']:
        if r['path'] == 'EVENTS_UNIFIED.csv.gz':
            external_file(screen / r['path'], 'optional: reproduce old-event screening from all reused rows', r['sha256'], r['bytes'])

    # Joint-topic final manifest: keep official summaries and compact references.
    # Full request lists go in SMALL; all full events/endpoints stay external.
    joint = NEW / 'joint_exchange'
    joint_input_names = {
        'CACHED_EVENTS_REGISTERED.csv.gz', 'CROSS_MANUAL_EVENTS_REGISTERED.csv.gz',
        'CROSS_SEMI_EVENTS_REGISTERED.csv.gz', 'NATIVE_EVENTS_REGISTERED.csv.gz',
        'NATIVE_TEAM_REQUEST.csv.gz', 'NATIVE_ALL_TEAMS.csv.gz',
        'CACHED_ENDPOINT_REFERENCES.csv.gz', 'ALL_USED_TEAM_REFERENCES.csv.gz',
    }
    # These indexes are independently delivered; keeping them out avoids another
    # duplicate of every event's reference membership in a small-code package.
    joint_external_names = {
        'ALL_EVENT_REFERENCE_INDEX.csv.gz', 'PHYSICAL_TRIPLE_USE_INDEX.csv.gz',
        'ALL_USED_ENDPOINT_SCALARS.csv.gz', 'ALL_USED_ENDPOINT_GEOMETRY.csv.gz',
    }
    for r in csv_rows(joint / 'DELIVERY_MANIFEST.csv'):
        p = joint / r['file']
        if r['file'].startswith('results/'):
            continue
        if p.name.endswith('_EVENTS_COMPLETE.csv.gz') or p.name in joint_external_names:
            external_file(p, 'independent complete joint event/endpoint/reference table', r['sha256'], r['bytes'])
        elif p.name in joint_input_names:
            add(p, SMALL, 'joint_frozen_requests_and_endpoint_references', expected_sha=r['sha256'])
        elif allowed(p):
            add(p, role='joint_exchange_formal_summary_or_small_evidence', expected_sha=r['sha256'])
    for name in ['DELIVERY_MANIFEST.csv', 'DELIVERY_RECEIPT.json']:
        add(joint / name, role='joint_source_manifest')

    # Expanded final analysis is frozen in its own formal manifest.
    ex = NEW / 'expanded_blocks'
    am = ex / 'analysis/ANALYSIS_FINAL_MANIFEST.json'
    for r in json.loads(am.read_text())['files']:
        add(NEW / r['path'], role='expanded_final_analysis', expected_sha=r['sha256'])
    for name in ['ANALYSIS_FINAL_MANIFEST.json', 'ANALYSIS_FINAL_DELIVERY.json']:
        add(ex / 'analysis' / name, role='expanded_analysis_source_manifest')
    merged_requests = {'A2_relation_n17_m9_REGISTERED_EVENTS.csv.gz',
                       'M_structure_n10_m5_REGISTERED_EVENTS.csv.gz',
                       'M_structure_n10_m6_REGISTERED_EVENTS.csv.gz',
                       'V3_BEHAVIOR_n10_m7_REGISTERED_EVENTS.csv.gz'}
    for p in sorted(ex.iterdir()):
        if not allowed(p) or p.name in merged_requests or p.suffix == '.py':
            continue
        add(p, SMALL if p.name == 'ALL_TEAMS_REGISTERED.csv.gz' else CORE,
            'expanded_frozen_registration_and_capacity')
    parts = csv_rows(ex / 'REGISTERED_EVENT_PARTS.csv')
    assert len(parts) == 253, len(parts)
    for row in parts:
        add(ROOT / row['path'], SMALL, 'expanded_exact_frozen_event_request', expected_sha=row['sha256'])
        cell = ex / 'results' / row['cell_id']
        comp = json.loads((cell / 'COMPLETION.json').read_text())
        assert comp['status'] == 'complete'
        add(cell / 'PANEL_SUMMARY.csv.gz', SMALL, 'expanded_portable_panel_summary', expected_sha=comp['panel_summary']['sha256'])
        add(cell / 'COMPLETION.json', SMALL, 'expanded_portable_cell_completion')
    for batch in sorted((ex / 'batches').iterdir()):
        if not batch.is_dir() or not (batch / 'COMPLETION.json').exists():
            continue
        for name in ['REQUESTS.csv.gz', 'COMPLETION.json']:
            add(batch / name, SMALL, 'native_batch_frozen_request_and_completion')
        comp = json.loads((batch / 'COMPLETION.json').read_text())
        for name in ['ENDPOINT_SCALARS.csv.gz', 'ENDPOINT_GEOMETRY.csv.gz']:
            # Export metadata conventions differ between frozen generations;
            # use the actual file for these small per-batch digest lookups only.
            p = batch / name
            external_file(p, 'independent native batch endpoint table', sha(p), p.stat().st_size,
                          'final exported endpoint file', 'native frozen v2; no new computation')

    # Large event shards are referenced by their exact frozen chunk plan. The
    # small completion receipts make restored per-cell tables traceable.
    ed = HERE / 'expanded_events'
    add(ed / 'CHUNK_PLAN.json', SMALL, 'expanded_complete_event_chunk_plan')
    chunks = json.loads((ed / 'CHUNK_PLAN.json').read_text())['chunks']
    assert len(chunks) == 25
    for c in chunks:
        completion = ed / (c['chunk_id'] + '_COMPLETION.json')
        add(completion, SMALL, 'expanded_independent_event_shard_completion')
        cd = json.loads(completion.read_text())
        # Each completion is the authority for byte-level gzip identity.
        p = ed / (c['chunk_id'] + '_EVENTS_COMPLETE.csv.gz')
        info = cd.get('file', cd)
        external_file(p, 'independent complete expanded event shard',
                      info.get('sha256', cd.get('sha256', '')),
                      info.get('bytes', cd.get('bytes', '')),
                      str(completion.relative_to(ROOT)), '390208 rows across 25 full 487-column shards')

    # Integration tables are final except the two separately written condition
    # recommendations. Root's main report is always separately delivered.
    for p in sorted((NEW / 'integration').iterdir()):
        if allowed(p) and p.name not in EXCLUDED_INTEGRATION:
            add(p, role='method_identity_members_or_input_identity')
    for sub in ['mechanisms/b6_47_failure', 'mechanisms/positive_cases']:
        for p in sorted((NEW / sub).rglob('*')):
            if allowed(p):
                add(p, role='small_native_mechanism_state_votes_and_figure')
    for p in sorted((NEW / 'mechanisms/originals').glob('*.json')):
        add(p, role='selected_release_image_provenance')
    add(HERE / 'CORE_PACKAGE_GUIDE_ZH.md', role='core_package_readme')

    # Exact old package identity plus named dependencies not duplicated here.
    with zipfile.ZipFile(OLD_ZIP) as z:
        old_names = set(z.namelist())
        assert len(old_names) == 193 and sum(n.endswith('.py') for n in old_names) == 143
    external_file(OLD_ZIP, 'old V3/OLD code and small frozen inputs', sha(OLD_ZIP), OLD_ZIP.stat().st_size,
                  'actual prior archive', '193 files; 143 Python; preserve original study identity')
    for r in csv_rows(joint / 'INPUT_AND_CODE_DEPENDENCIES.csv'):
        p = ROOT / r['file']
        if str(p.relative_to(ROOT)) in selected:
            continue
        external_file(p, 'dependency for native/event replay or registration', r['sha256'], r['bytes'],
                      'joint_exchange/INPUT_AND_CODE_DEPENDENCIES.csv',
                      'included in old 193-file package' if r['file'] in old_names else 'base repository or previous independently delivered artifact')
    # Source overview explicitly names its own label/native-input dependencies.
    for r in csv_rows(NEW / 'integration/INPUT_REFERENCES.csv'):
        path = r.get('path', r.get('file', ''))
        if not path:
            continue
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_relative_to(ROOT):
            external_file(p, 'study source identity; see exact input-reference purpose', r.get('sha256', ''), r.get('bytes', ''),
                          'integration/INPUT_REFERENCES.csv')
    return selected, external


def build_archive(name, records, include_manifest=False):
    target = HERE / name
    tmp = target.with_suffix('.zip.tmp')
    items = sorted(records, key=lambda r: r['repo_path'])
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=5) as z:
        for r in items:
            p = ROOT / r['repo_path']
            assert sha(p) == r['sha256'], ('changed_during_pack', str(p))
            z.write(p, r['repo_path'])
        if include_manifest:
            z.write(MANIFEST, str(MANIFEST.relative_to(ROOT)))
    with tmp.open('rb') as f:
        os.fsync(f.fileno())
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        assert len(set(z.namelist())) == len(items) + int(include_manifest)
        for r in items:
            h = hashlib.sha256()
            with z.open(r['repo_path']) as f:
                for b in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(b)
            assert h.hexdigest() == r['sha256'], ('archive_byte_mismatch', r['repo_path'])
    os.replace(tmp, target)
    return dict(path=str(target.relative_to(ROOT)), files=len(items) + int(include_manifest),
                bytes=target.stat().st_size, sha256=sha(target), crc_and_file_sha_verified=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inventory-only', action='store_true')
    args = ap.parse_args()
    selected, external = collect()
    records = [selected[k] for k in sorted(selected)] + [external[k] for k in sorted(external) if k not in selected]
    buf = io.StringIO(newline='')
    fields = ['repo_path', 'archive', 'delivery_mode', 'role', 'bytes', 'sha256', 'hash_source', 'required_for', 'source_identity']
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(records)
    atomic(MANIFEST, buf.getvalue().encode('utf-8-sig'))
    summary = {a: dict(files=sum(r['archive'] == a for r in selected.values()),
                       source_bytes=sum(r['bytes'] for r in selected.values() if r['archive'] == a))
               for a in [CORE, SMALL]}
    if args.inventory_only:
        print(json.dumps(dict(status='inventory_saved', summary=summary, external_files=len(external)), ensure_ascii=False))
        return
    packages = [build_archive(a, [r for r in selected.values() if r['archive'] == a], a == CORE) for a in [CORE, SMALL]]
    # No included source may change unnoticed between its manifest and archive.
    for r in selected.values():
        assert sha(ROOT / r['repo_path']) == r['sha256'], ('source_changed_after_pack', r['repo_path'])
    receipt = dict(status='complete', purpose='packaging_only', underlying_data='real v2',
                   source_main='324dba44d0a82d9d64a62965f2e549ee05165417',
                   native_input_commit='82c6164b0d4630de5316199c92aa405930973168',
                   packages=packages, summary=summary, external_dependencies=len(external),
                   manifest=dict(path=str(MANIFEST.relative_to(ROOT)), rows=len(records), sha256=sha(MANIFEST)),
                   python_files=sum(p.endswith('.py') for p in selected),
                   portable_panel_summaries=253, portable_cell_completions=253,
                   exact_expanded_request_parts=253, full_event_shards_external=25,
                   external_full_expanded_event_rows=390208,
                   root_main_report='independently delivered; never included',
                   recommendation_tables='independently delivered; not read while being finalized',
                   new_fusion_calls=0, new_scoring_calls=0, new_model_fits=0,
                   excluded='runtime; working/partial files; nested ZIPs; duplicate full events and endpoints; raw original images; virtual environments',
                   note='The manifest is included in CORE without a self-hash row. Its SHA is recorded here. External delivery indices and receipts remain authoritative for independently delivered large tables.')
    atomic(RECEIPT, json.dumps(receipt, ensure_ascii=False, indent=2).encode())
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
