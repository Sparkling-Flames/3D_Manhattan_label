#!/usr/bin/env python3
"""Package existing path events without changing any research result.

Each output is a standalone conventional ZIP containing only unchanged gzip
tables. At most two archives are built/validated concurrently. Source and
archive member hashes must agree, each inner gzip is read to EOF, and actual
CSV row counts must match the existing per-pool computation checkpoint.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import time
import zipfile
import gzip


CHUNK = 1024 * 1024
MAX_ARCHIVE_BYTES = 250 * 1024 * 1024


def atomic_json(path: Path, value: object) -> None:
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


class HashingReader(io.RawIOBase):
    def __init__(self, underlying):
        super().__init__()
        self.underlying = underlying
        self.hash = hashlib.sha256()
        self.bytes_read = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        data = self.underlying.read(len(buffer))
        if not data:
            return 0
        self.hash.update(data)
        self.bytes_read += len(data)
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        if not self.closed:
            self.underlying.close()
        super().close()


def inventory(root: Path) -> list[dict]:
    records = []
    for branch in ('manual', 'doorway'):
        pool_root = root / 'stage03_response' / branch / 'by_pool'
        paths = sorted(pool_root.glob('*/PATH_CHANGE_EVENTS.csv.gz'))
        for path in paths:
            assert path.is_file() and not any('.tmp' in p for p in path.parts)
            checkpoint_path = path.parent / 'COMPLETION.json'
            checkpoint = json.loads(checkpoint_path.read_text(encoding='utf-8'))
            stat = path.stat()
            relative = path.relative_to(root).as_posix()
            member = root.name + '/' + relative
            records.append({
                'branch': branch,
                'pool_id': path.parent.name,
                'domain': checkpoint.get('domain'),
                'image': checkpoint.get('image'),
                'condition': checkpoint.get('condition'),
                'source_relative_path': relative,
                'archive_member': member,
                'source_bytes': stat.st_size,
                'source_mtime_ns': stat.st_mtime_ns,
                'expected_data_rows': checkpoint['output_rows']['PATH_CHANGE_EVENTS.csv.gz'],
                'checkpoint_relative_path': checkpoint_path.relative_to(root).as_posix(),
                'checkpoint_sha256': sha256_file(checkpoint_path),
            })
    if not records:
        raise RuntimeError('No official path event files found.')
    assert len(records) == len({x['archive_member'] for x in records})
    return records


def partition(records: list[dict]) -> list[list[dict]]:
    # Stored entries have 76 bytes of fixed local/central directory overhead.
    # A deliberately larger 1 KiB allowance per file also covers extra fields.
    parts, current, estimated = [], [], 22
    for record in records:
        allowance = record['source_bytes'] + 1024 + 2 * len(record['archive_member'].encode('utf-8'))
        if allowance + 22 > MAX_ARCHIVE_BYTES:
            raise RuntimeError('One source cannot fit in the requested standalone ZIP size limit.')
        if current and estimated + allowance > MAX_ARCHIVE_BYTES:
            parts.append(current)
            current, estimated = [], 22
        current.append(record)
        estimated += allowance
    if current:
        parts.append(current)
    return parts


def package_part(root: Path, number: int, records: list[dict]):
    started = time.monotonic()
    name = f'03_Path_Events_Part{number:02d}.zip'
    output = root / 'delivery' / name
    temp = output.with_name(output.name + '.tmp')
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite completed deliverable: {output}')
    hashes = {}
    with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_STORED, allowZip64=False) as z:
        for record in records:
            source = root / record['source_relative_path']
            before = source.stat()
            assert (before.st_size, before.st_mtime_ns) == (record['source_bytes'], record['source_mtime_ns'])
            info = zipfile.ZipInfo(record['archive_member'], date_time=(2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.file_size = before.st_size
            info.create_system = 3
            info.external_attr = (0o100644 << 16)
            h = hashlib.sha256()
            with source.open('rb') as src, z.open(info, 'w', force_zip64=False) as dst:
                while block := src.read(CHUNK):
                    h.update(block)
                    dst.write(block)
            after = source.stat()
            assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
            hashes[record['archive_member']] = h.hexdigest()
    assert temp.stat().st_size <= MAX_ARCHIVE_BYTES
    entries = []
    with zipfile.ZipFile(temp, 'r') as z:
        expected = [r['archive_member'] for r in records]
        assert z.namelist() == expected
        bad = z.testzip()
        if bad is not None:
            raise RuntimeError(f'ZIP CRC validation failed: {bad}')
        for record in records:
            member = record['archive_member']
            compressed_reader = HashingReader(z.open(member, 'r'))
            compressed_buffer = io.BufferedReader(compressed_reader, buffer_size=CHUNK)
            gzip_reader = gzip.GzipFile(fileobj=compressed_buffer, mode='rb')
            uncompressed_reader = HashingReader(gzip_reader)
            uncompressed_buffer = io.BufferedReader(uncompressed_reader, buffer_size=CHUNK)
            header = None
            data_rows = 0
            with io.TextIOWrapper(uncompressed_buffer, encoding='utf-8-sig', newline='') as text:
                reader = csv.reader(text)
                header = next(reader, None)
                for row in reader:
                    if header is None or len(row) != len(header):
                        raise RuntimeError(f'CSV shape mismatch: {member} row {data_rows+2}')
                    data_rows += 1
            # GzipFile does not own an explicitly supplied fileobj.
            compressed_buffer.close()
            assert compressed_reader.bytes_read == record['source_bytes'], member
            assert compressed_reader.hash.hexdigest() == hashes[member], member
            assert data_rows == record['expected_data_rows'], (member, data_rows, record['expected_data_rows'])
            # Empty event tables can still contain the frozen table schema.
            assert header is not None, member
            entries.append({
                **record,
                'package_name': name,
                'source_sha256': hashes[member],
                'archive_member_sha256': compressed_reader.hash.hexdigest(),
                'uncompressed_sha256': uncompressed_reader.hash.hexdigest(),
                'uncompressed_bytes': uncompressed_reader.bytes_read,
                'csv_data_rows': data_rows,
                'csv_columns': len(header),
                'gzip_read_to_eof': True,
                'source_equals_archive_member': True,
                'checkpoint_rows_match': True,
            })
    package_hash = sha256_file(temp)
    os.replace(temp, output)
    summary = {
        'package_name': name,
        'relative_path': output.relative_to(root).as_posix(),
        'bytes': output.stat().st_size,
        'MiB': output.stat().st_size / (1024 * 1024),
        'sha256': package_hash,
        'file_count': len(entries),
        'source_bytes': sum(e['source_bytes'] for e in entries),
        'uncompressed_bytes': sum(e['uncompressed_bytes'] for e in entries),
        'csv_data_rows': sum(e['csv_data_rows'] for e in entries),
        'zip_crc_test': 'passed',
        'all_inner_gzip_eof': True,
        'all_csv_checkpoint_rows_match': True,
        'all_source_member_hashes_match': True,
        'independent_standard_zip': True,
        'multi_volume_archive': False,
        'compression': 'ZIP_STORED; original gzip bytes preserved',
        'within_250_MiB': True,
        'elapsed_seconds': round(time.monotonic() - started, 3),
    }
    for entry in entries:
        entry['package_bytes'] = summary['bytes']
        entry['package_sha256'] = package_hash
    atomic_json(root / 'stage09_delivery' / f'PATH_EVENT_PART{number:02d}_VALIDATION.json', {
        'summary': summary, 'files': entries,
    })
    print(json.dumps(summary), flush=True)
    return summary, entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workers', type=int, default=2, choices=(1, 2))
    args = parser.parse_args()
    root = args.root.resolve()
    (root / 'delivery').mkdir(exist_ok=True)
    validation_dir = root / 'stage09_delivery'
    validation_dir.mkdir(exist_ok=True)
    records = inventory(root)
    parts = partition(records)
    atomic_json(validation_dir / 'PATH_EVENT_PACKAGING_PLAN.json', {
        'maximum_archive_bytes': MAX_ARCHIVE_BYTES,
        'file_count': len(records),
        'source_bytes': sum(r['source_bytes'] for r in records),
        'package_count': len(parts),
        'parts': [{'part': i, 'files': p} for i, p in enumerate(parts, 1)],
    })
    print(json.dumps({'packages': len(parts), 'files': len(records), 'source_bytes': sum(r['source_bytes'] for r in records)}), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(package_part, root, number, part) for number, part in enumerate(parts, 1)]
        results = [f.result() for f in futures]
    summaries = [r[0] for r in results]
    entries = [entry for _, group in results for entry in group]
    assert len(entries) == len(records)
    names = [r['archive_member'] for r in entries]
    assert len(names) == len(set(names))
    assert set(names) == {r['archive_member'] for r in records}
    # Verify no source appeared/disappeared or changed during packaging.
    final = inventory(root)
    assert final == records
    manifest = validation_dir / 'PATH_EVENT_PACKAGE_MANIFEST.csv'
    temp = manifest.with_name(manifest.name + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)
    os.replace(temp, manifest)
    receipt = {
        'scope': 'Only stage03_response/{manual,doorway}/by_pool/*/PATH_CHANGE_EVENTS.csv.gz',
        'archive_prefix': root.name + '/',
        'maximum_archive_bytes': MAX_ARCHIVE_BYTES,
        'files': len(entries),
        'branches': {branch: sum(e['branch'] == branch for e in entries) for branch in ('manual', 'doorway')},
        'source_bytes': sum(e['source_bytes'] for e in entries),
        'package_bytes': sum(s['bytes'] for s in summaries),
        'uncompressed_bytes': sum(e['uncompressed_bytes'] for e in entries),
        'csv_data_rows': sum(e['csv_data_rows'] for e in entries),
        'zero_row_tables': sum(e['csv_data_rows'] == 0 for e in entries),
        'package_count': len(summaries),
        'packages': summaries,
        'zip_testzip_all_passed': True,
        'inner_gzip_all_completely_decompressed': True,
        'csv_rows_all_match_original_checkpoints': True,
        'source_and_member_hashes_all_match': True,
        'no_overlapping_archive_members': True,
        'all_official_event_files_included_exactly_once': True,
        'no_tmp_files_included': True,
        'all_archives_standalone_non_split_zip': True,
        'all_archives_at_most_250_MiB': True,
        'research_source_files_modified': False,
        'manifest': manifest.relative_to(root).as_posix(),
        'manifest_sha256': sha256_file(manifest),
        'code': Path(__file__).resolve().relative_to(root).as_posix(),
        'code_sha256': sha256_file(Path(__file__).resolve()),
        'status': 'passed',
    }
    atomic_json(validation_dir / 'PATH_EVENT_PACKAGE_VALIDATION.json', receipt)
    atomic_json(validation_dir / 'VALIDATION.json', receipt)
    print(json.dumps({'status': 'passed', 'files': len(entries), 'packages': len(summaries), 'csv_data_rows': receipt['csv_data_rows'], 'package_bytes': receipt['package_bytes']}), flush=True)


if __name__ == '__main__':
    main()
