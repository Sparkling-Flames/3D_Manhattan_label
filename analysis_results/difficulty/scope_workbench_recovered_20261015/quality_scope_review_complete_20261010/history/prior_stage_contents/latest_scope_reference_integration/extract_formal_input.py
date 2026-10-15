#!/usr/bin/env python3
"""Read current loaders and freeze a small BEV replay input, with committed-byte provenance."""
import argparse
import hashlib
import importlib.util
import io
import re
import subprocess
import sys
from pathlib import Path

from recompute_bev import ROOT, digest, project_floor, read, save, sha


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo)


def verify_file(repo, commit, relative):
    committed = git(repo, 'show', commit + ':' + relative)
    materialized = (repo / relative).exists()
    if not materialized:
        assert not committed.startswith(b'version https://git-lfs.github.com/spec/v1\n'), 'missing_materialized_LFS:' + relative
    actual = (repo / relative).read_bytes() if materialized else committed
    if committed.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
        expected = re.search(rb'oid sha256:([a-f0-9]{64})', committed).group(1).decode()
        size = int(re.search(rb'size ([0-9]+)', committed).group(1))
        assert sha(repo / relative) == expected and len(actual) == size, relative
        kind = 'lfs_content_sha256_and_size'
    else:
        assert actual == committed, relative
        kind = 'exact_committed_blob'
    return {'path': relative, 'sha256': hashlib.sha256(actual).hexdigest(), 'bytes': len(actual),
            'verification': kind, 'read_from': 'checkout' if materialized else 'committed_blob_missing_in_sparse_checkout'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--inputs', type=Path, default=ROOT / 'inputs')
    p.add_argument('--provenance-out', type=Path, default=ROOT / 'results/source_provenance.json')
    args = p.parse_args()
    repo, inputs = args.repo.resolve(), args.inputs.resolve()
    output_path = inputs / 'current_formal_subset.json'
    commit = git(repo, 'rev-parse', 'HEAD').decode().strip()
    overlay, raw = read(inputs / 'normalized_confirmation_overlay.json'), read(inputs / 'raw_scope_return.json')
    assert raw['latest_scope_review_source_commit'] == commit
    raw_map = {r['image_code']: r for r in raw['records']}
    files = ['docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json']
    manifest_path = 'analysis_results/research_input_20260929/manifest.json'
    manifest = read(repo / manifest_path)
    files += [manifest_path] + [str(Path(manifest_path).parent / rel) for rel in manifest['entrypoints'].values()]
    files += ['tools/thesis_main/data_prep/' + n for n in [
        'consolidate_research_input.py', 'materialize_current_research_input.py',
        'apply_quality_review_20261010.py', 'apply_difficulty_orders_20261010.py',
        'project_public_research_20260929.py']]
    files += ['analysis_results/image_difficulty_full_review_20261010/build_scope_review.py',
              'analysis_results/objective_difficulty_20261009/structure_classification/images.csv']
    historic_confirmation_path = 'research/quality_scope_comparison_20261010/inputs/manual_scope_confirmation_20261010.json'
    files += [historic_confirmation_path, 'research/quality_scope_comparison_20261010/README_三图对照.md',
              'research/quality_scope_comparison_20261010/reproduce.py']
    verified = [verify_file(repo, commit, rel) for rel in sorted(set(files))]
    sys.path.insert(0, str(repo))
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle = load_current_bundle()
    assert bundle['data'] == load_current_input(), 'current_loader_disagreement'
    _, aliases = project_bundle(bundle)
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    images = {i['image_code']: i for i in bundle['data']['images']}
    protected = ['original_export_points', 'before_preprocessing_points', 'preprocessed_points',
                 'points_1024x512', 'ordered_source_pair_indices', 'point_labels', 'links_zero_based',
                 'worker_id', 'condition', 'cleaning_disposition', 'independent_vote_eligible',
                 'worker_quality_gate', 'main_quality_gate', 'main_consensus_gate', 'source', 'review']
    import csv
    classification_path = 'analysis_results/objective_difficulty_20261009/structure_classification/images.csv'
    classification_bytes = ((repo / classification_path).read_bytes() if (repo / classification_path).exists()
                            else git(repo, 'show', commit + ':' + classification_path))
    with io.StringIO(classification_bytes.decode('utf-8-sig'), newline='') as f:
        selections = {r['image_id']: r['gt_object_id'] for r in csv.DictReader(f)}
    fields = ['object_id', 'object_kind', 'image_id', 'image_code', 'points_1024x512',
              'worker_id', 'condition', 'cleaning_disposition', 'independent_vote_eligible',
              'worker_quality_gate', 'main_quality_gate', 'main_consensus_gate', 'ring_confirmed',
              'ordered_source_pair_indices', 'quality_review_provenance', 'order_record']

    def subset(o):
        return {k: o.get(k) for k in fields} | {'record_id': aliases['records'][o['object_id']],
                                             'formal_object_sha256': digest(o)}

    snapshot_images = []
    for r in sorted(overlay['records'], key=lambda r: r['image_code']):
        code = r['image_code']
        im, receipt = images[code], raw_map[code]
        selected, original = objects[r['reference_object_id']], objects[im['references']['gt_original']]
        assert r['image_id'] == im['image_id'] == selected['image_id'] == original['image_id']
        assert r['reference_object_id'] == selections[im['image_id']], 'editing_reference_not_current_selected_GT:' + code
        assert selected['points_1024x512'] == receipt['editing_reference_points_1024x512']
        assert original['object_id'] == receipt['historical_original_GT_object_id']
        assert original['points_1024x512'] == receipt['historical_original_GT_points_1024x512']
        snapshot_images.append({
            'image_code': code, 'image_id': im['image_id'], 'references': im['references'],
            'selected_gt': subset(selected), 'original_gt': subset(original),
            'annotations': [subset(o) for o in objects.values() if o['image_code'] == code and o['object_kind'] == 'annotation'],
        })
    # Compare independent stdlib trig projection to the existing repository's numpy implementation.
    oracle_path = repo / 'analysis_results/image_difficulty_full_review_20261010/build_scope_review.py'
    spec = importlib.util.spec_from_file_location('existing_scope_projection', oracle_path)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    projection_checks = []
    max_error = 0.0
    for im in snapshot_images:
        for obj in [im['selected_gt'], im['original_gt']] + im['annotations']:
            points = obj['points_1024x512']
            actual, status = project_floor(points)
            if points is None:
                # The existing numpy helper assumes an array. Unavailable source coordinates remain null.
                assert actual is None and status == 'invalid_pairs'
                expected_status = 'unavailable_coordinates'
                error = None
            else:
                expected, expected_status = oracle.polygon(points)
                assert status == expected_status, (obj['record_id'], status, expected_status)
                if actual is not None:
                    error = max(abs(a - b) for x, y in zip(actual.exterior.coords, expected.exterior.coords) for a, b in zip(x, y))
                    assert error < 1e-12, (obj['record_id'], error)
                    max_error = max(max_error, error)
                else:
                    error = None
            projection_checks.append({'record_id': obj['record_id'], 'status': status,
                                      'existing_helper_status': expected_status, 'max_coordinate_error_h': error})
    unchanged = all(sha(repo / item['path']) == item['sha256'] for item in verified if item['read_from'] == 'checkout')
    assert unchanged
    snapshot = {
        'schema': 'scope_formal_geometry_snapshot_v1', 'source_commit': commit,
        'raw_receipt_sha256': sha(inputs / 'raw_scope_return.json'),
        'overlay_sha256': sha(inputs / 'normalized_confirmation_overlay.json'),
        'both_current_loaders_identical': True, 'formal_bundle_validation': bundle['validation'],
        'quality_update_revision': bundle['data'].get('quality_update_revision'),
        'order_update_revision': bundle['data'].get('order_update_revision'),
        'source_files': verified, 'images': snapshot_images,
        'historical_three_floor_confirmations': read(repo / historic_confirmation_path),
        'historical_three_floor_confirmation_path': historic_confirmation_path,
        'all_formal_object_digests': {oid: digest(o) for oid, o in objects.items()},
        'all_protected_object_digests': {oid: digest({k: o.get(k) for k in protected}) for oid, o in objects.items()},
        'protected_fields': protected,
    }
    save(output_path, snapshot)
    save(inputs / 'input_manifest.json', {
        'schema': 'scope_bev_input_manifest_v1', 'source_commit': commit,
        'files': {name: sha(inputs / name) for name in
                  ('raw_scope_return.json', 'normalized_confirmation_overlay.json', 'current_formal_subset.json')},
    })
    save(args.provenance_out, {
        'passed': True, 'source_commit': commit, 'verified_files': verified,
        'formal_bundle_validation': bundle['validation'], 'both_current_loaders_identical': True,
        'source_files_unchanged_after_extraction': unchanged,
        'all_formal_objects_fingerprinted': len(objects),
        'selected_reference_matches_current_structure_classification': True,
        'projection_checks': projection_checks, 'max_coordinate_error_h': max_error,
        'extracted_images': len(snapshot_images),
        'extracted_annotations': sum(len(i['annotations']) for i in snapshot_images),
        'existing_scope_projection_path': str(oracle_path.relative_to(repo)),
        'snapshot_sha256': sha(output_path),
        'LFS_note': 'Materialized LFS files may appear modified to sparse Git status; exact committed LFS SHA256 and size are verified here.',
    })
    print('Extracted', len(snapshot_images), 'images;', sum(len(i['annotations']) for i in snapshot_images),
          'annotations;', len(verified), 'committed files verified; max projection error', max_error)


if __name__ == '__main__':
    main()
