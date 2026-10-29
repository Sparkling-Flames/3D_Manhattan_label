"""Verify old frozen-design archive identity and exact current source hashes.

No design, fusion, scoring, or source file is modified. The optional cleanup
only removes the newly downloaded duplicate after its durable archive hash is
verified; the original uploaded archive and all scientific sources remain.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--remove-newly-downloaded-duplicate', action='store_true')
    a = p.parse_args()
    root = a.root.resolve()
    out = root / 'delivery/clean_design_source_verification'
    out.mkdir(exist_ok=True)
    old_name = 'HOHONET_v21_AC_stage02_frozen_design'
    old_zip = out / (old_name + '.zip')
    old_receipt = json.loads((root / 'delivery' / (old_name + '_READABILITY.json')).read_text())
    actual_old_sha = file_sha(old_zip)
    assert actual_old_sha == old_receipt['archive_sha256'], 'Old archive identity differs'
    assert old_zip.stat().st_size == old_receipt['archive_bytes']
    old_paths = [r['path'] for r in old_receipt['checks']]
    rows = []
    diffs = []
    with zipfile.ZipFile(old_zip) as z:
        raw_manifest = z.read('ARCHIVE_MANIFEST.json')
        manifest = json.loads(raw_manifest)
        assert set(x['path'] for x in manifest) == set(old_paths)
        assert len(manifest) == len(old_paths)
        (out / 'OLD_ARCHIVE_MANIFEST.json').write_bytes(raw_manifest)
        for m in manifest:
            rel = m['path']
            current = root / rel
            excluded = any(part == '__pycache__' or part.lower() == 'cache' for part in Path(rel).parts) or '.partial' in Path(rel).name or Path(rel).suffix == '.pyc'
            row = {'path': rel, 'included_in_clean_design': not excluded,
                   'old_bytes': m['bytes'], 'old_sha256': m['sha256'],
                   'current_exists': current.is_file()}
            if current.is_file():
                row.update(current_bytes=current.stat().st_size, current_sha256=file_sha(current))
                row['identical'] = row['current_sha256'] == m['sha256'] and row['current_bytes'] == m['bytes']
                if not row['identical'] and current.suffix in {'.py', '.md', '.json', '.csv'}:
                    old_bytes = z.read(rel)
                    assert hashlib.sha256(old_bytes).hexdigest() == m['sha256']
                    dest = out / 'old_changed_sources' / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(old_bytes)
                    diff = ''.join(difflib.unified_diff(old_bytes.decode('utf-8').splitlines(True), current.read_text().splitlines(True), fromfile='old/' + rel, tofile='current/' + rel))
                    diffs.append(diff)
            else:
                row['identical'] = False
            rows.append(row)
    includes = [r['path'] for r in rows if r['included_in_clean_design']]
    assert len(includes) == len(set(includes))
    assert all((root / rel).is_file() for rel in includes)
    (out / 'CURRENT_VS_OLD_SOURCE_DIFFS.patch').write_text('\n'.join(diffs))
    (out / 'CLEAN_DESIGN_INCLUDE_PATHS.json').write_text(json.dumps(includes, indent=2) + '\n')
    changes = [r for r in rows if not r['identical']]
    receipt = {
        'old_archive_name': old_name + '.zip',
        'old_archive_library_file_id': 'libfile_91c0ad2578ec8191a9f11ad9052e1949',
        'old_archive_file_id': 'file_000000003b6c81f585f9ab9265d8cf35',
        'old_archive_sha256_verified': actual_old_sha,
        'old_archive_bytes_verified': old_zip.stat().st_size,
        'original_manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(),
        'manifest_path_set_matches_original_readability': True,
        'original_payload_files': len(rows),
        'clean_payload_files': len(includes),
        'unchanged_files': sum(r['identical'] for r in rows),
        'changed_files': len(changes),
        'changed_paths': [r['path'] for r in changes],
        'excluded_paths': [r['path'] for r in rows if not r['included_in_clean_design']],
        'source_files_modified_by_this_check': 0,
        'new_fusions_or_scores': 0,
        'per_file': rows,
        'duplicate_cleanup_authorization': 'Parent explicitly authorized removal of only this newly downloaded duplicate after full archive SHA matched durable upload receipt; all source files and durable old archive retained.',
        'newly_downloaded_duplicate_removed': False,
    }
    if a.remove_newly_downloaded_duplicate:
        assert old_zip.parent == out
        old_zip.unlink()
        receipt['newly_downloaded_duplicate_removed'] = True
    receipt['free_bytes_after_check'] = shutil.disk_usage(root).free
    (out / 'OLD_ARCHIVE_SOURCE_COMPARISON.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'per_file'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
