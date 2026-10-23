#!/usr/bin/env python3
"""Restore original wide events from compact links without recomputing changes.

Uses only the Python standard library. Endpoint values are indexed on temporary
disk and events are written in bounded chunks. The output has strictly the
original columns, in input_position order; the six delivery-only link fields
remain available in the original LINKED file and are not appended here.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import sqlite3
import tempfile
from pathlib import Path


FILES = {
    'natural_adjacent': 'NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz',
    'natural_intervals': 'NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz',
    'policy_paired': 'POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz',
    'policy_direct': 'POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz',
}


def read_text(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    return opener(path, 'rt', encoding='utf-8-sig', newline='')


def load_plan(root, dataset):
    path = root / 'events/COLUMN_RETENTION_AND_ENDPOINT_MAP.csv'
    with read_text(path) as stream:
        plan = [r for r in csv.DictReader(stream) if r['dataset'] == dataset]
    plan.sort(key=lambda r: int(r['input_position']))
    if not plan:
        raise ValueError(f'No column mapping for {dataset}: {path}')
    if [int(r['input_position']) for r in plan] != list(range(1, len(plan) + 1)):
        raise ValueError('input_position must be unique and consecutive from 1')
    columns = [r['event_column'] for r in plan]
    if len(set(columns)) != len(columns):
        raise ValueError('Duplicate original event column in mapping')
    if set(r['action'] for r in plan) - {'keep', 'link_endpoint'}:
        raise ValueError('Unsupported mapping action; no expressions are evaluated')
    return plan


def required_sample_keys(path, key_columns, limit):
    if limit is None:
        return None
    with read_text(path) as stream:
        reader = csv.DictReader(stream)
        return {row[col] for row in itertools.islice(reader, limit) for col in key_columns}


def index_endpoints(connection, path, columns, required):
    connection.execute('CREATE TABLE endpoint (team_key TEXT PRIMARY KEY, vals TEXT NOT NULL)')
    scanned = indexed = 0
    remaining = None if required is None else set(required)
    with read_text(path) as stream:
        reader = csv.reader(stream)
        fields = next(reader)
        absent = ({'team_key'} | set(columns)) - set(fields)
        if absent:
            raise ValueError(f'Endpoint table lacks columns: {sorted(absent)}')
        key_idx = fields.index('team_key')
        indices = [fields.index(col) for col in columns]
        pending = []
        if remaining == set():
            return scanned, indexed
        for row in reader:
            scanned += 1
            key = row[key_idx]
            if required is not None and key not in required:
                continue
            pending.append((key, json.dumps([row[i] for i in indices], ensure_ascii=False,
                                            separators=(',', ':'))))
            indexed += 1
            if remaining is not None:
                remaining.discard(key)
            if len(pending) >= 2000:
                connection.executemany('INSERT INTO endpoint VALUES (?, ?)', pending)
                pending.clear()
            if remaining == set():
                break
        if pending:
            connection.executemany('INSERT INTO endpoint VALUES (?, ?)', pending)
    connection.commit()
    if remaining:
        raise KeyError(f'{len(remaining)} requested endpoint keys are absent; '
                       f'examples: {sorted(remaining)[:3]}')
    return scanned, indexed


def lookup_chunk(connection, keys):
    keys = list(keys)
    found = {}
    # 800 parameters also works with SQLite builds with the older 999 limit.
    for start in range(0, len(keys), 800):
        group = keys[start:start + 800]
        query = 'SELECT team_key, vals FROM endpoint WHERE team_key IN ('
        query += ','.join('?' for _ in group) + ')'
        for key, values in connection.execute(query, group):
            found[key] = json.loads(values)
    missing = set(keys) - found.keys()
    if missing:
        raise KeyError(f'{len(missing)} endpoint keys missing in chunk; '
                       f'examples: {sorted(missing)[:3]}')
    return found


def restore(root, dataset, out, limit=None, chunk_rows=5000):
    root = Path(root).resolve()
    out = Path(out).resolve()
    plan = load_plan(root, dataset)
    linked = root / 'events' / FILES[dataset]
    endpoint_path = root / 'results/ENDPOINT_SCALARS.csv.gz'
    if out in {linked.resolve(), endpoint_path.resolve()}:
        raise ValueError('Output must not overwrite a source table')
    endpoint_columns = sorted({r['endpoint_column'] for r in plan if r['action'] == 'link_endpoint'})
    key_columns = sorted({r['endpoint_key_column'] for r in plan if r['action'] == 'link_endpoint'})
    if not all(endpoint_columns) or not all(key_columns):
        raise ValueError('An endpoint link is missing its key or value column')
    required = required_sample_keys(linked, key_columns, limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = out.with_name(out.name + '.partial')
    restored = 0
    excluded = []
    try:
        with tempfile.TemporaryDirectory(prefix='hohonet_restore_', dir=out.parent) as temp:
            with sqlite3.connect(str(Path(temp) / 'endpoint_index.sqlite')) as connection:
                connection.execute('PRAGMA journal_mode=OFF')
                connection.execute('PRAGMA synchronous=OFF')
                scanned, indexed = index_endpoints(connection, endpoint_path, endpoint_columns, required)
                with read_text(linked) as source:
                    reader = csv.reader(source)
                    fields = next(reader)
                    field_index = {name: i for i, name in enumerate(fields)}
                    needed = {r['event_column'] for r in plan if r['action'] == 'keep'} | set(key_columns)
                    absent = needed - field_index.keys()
                    if absent:
                        raise ValueError(f'LINKED table lacks columns: {sorted(absent)}')
                    original_columns = [r['event_column'] for r in plan]
                    excluded = [name for name in fields if name not in set(original_columns)]
                    instructions = []
                    for item in plan:
                        if item['action'] == 'keep':
                            instructions.append(('keep', field_index[item['event_column']], None))
                        else:
                            instructions.append(('link', field_index[item['endpoint_key_column']],
                                                 endpoint_columns.index(item['endpoint_column'])))
                    key_indices = [field_index[col] for col in key_columns]
                    opener = gzip.open if out.name.endswith('.gz') else open
                    with opener(temporary_output, 'wt', encoding='utf-8', newline='') as destination:
                        writer = csv.writer(destination)
                        writer.writerow(original_columns)
                        while limit is None or restored < limit:
                            take = chunk_rows if limit is None else min(chunk_rows, limit - restored)
                            block = list(itertools.islice(reader, take))
                            if not block:
                                break
                            keys = {row[i] for row in block for i in key_indices}
                            endpoint = lookup_chunk(connection, keys)
                            for row in block:
                                result = [row[i] if action == 'keep' else endpoint[row[i]][j]
                                          for action, i, j in instructions]
                                writer.writerow(result)
                            restored += len(block)
        temporary_output.replace(out)
    except Exception:
        temporary_output.unlink(missing_ok=True)
        raise
    receipt = dict(dataset=dataset, root=str(root), source=str(linked), output=str(out),
                   rows_restored=restored, requested_limit=limit,
                   strict_original_columns=True, original_column_count=len(plan),
                   kept_columns=sum(r['action'] == 'keep' for r in plan),
                   linked_columns=sum(r['action'] == 'link_endpoint' for r in plan),
                   delivery_only_columns_excluded=excluded,
                   endpoint_rows_scanned=scanned, endpoint_rows_indexed=indexed,
                   missing_endpoint_keys=0, chunk_rows=chunk_rows,
                   keep_values='Copied unchanged as CSV cell strings from LINKED',
                   endpoint_values='Raw endpoint CSV cell strings, joined by mapped key and column',
                   event_changes_recomputed=False, source_row_order_preserved=True)
    receipt_path = out.with_name(out.name + '.receipt.json')
    temp_receipt = receipt_path.with_name(receipt_path.name + '.tmp')
    temp_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp_receipt.replace(receipt_path)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='Canonical research directory containing events/ and results/')
    parser.add_argument('--dataset', choices=sorted(FILES), required=True)
    parser.add_argument('--out', required=True, help='Restored .csv or .csv.gz; use a new output location')
    parser.add_argument('--limit', type=int, help='Restore only the first N event rows; omit for all rows')
    parser.add_argument('--chunk-rows', type=int, default=5000)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 0:
        parser.error('--limit must be nonnegative')
    if args.chunk_rows < 1:
        parser.error('--chunk-rows must be positive')
    csv.field_size_limit(16 * 1024 * 1024)
    print(json.dumps(restore(args.root, args.dataset, args.out, args.limit, args.chunk_rows),
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
