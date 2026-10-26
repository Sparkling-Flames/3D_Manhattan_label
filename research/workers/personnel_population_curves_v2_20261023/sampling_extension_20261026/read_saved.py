"""Read archived results only; strings preserve NA, booleans and 64-bit seeds."""
import csv
import gzip
import json
from itertools import islice
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
ACCESS = json.loads((BASE / 'DATA_ACCESS.json').read_text(encoding='utf-8'))


def resolve(path, root=ROOT):
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Path leaves declared source root: ' + str(path))
    return target


def table_path(alias):
    return resolve(ACCESS['tables'][alias]['path'])


def csv_rows(path, required=(), filters=None):
    filters = filters or {}
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        missing = (set(required) | set(filters)) - set(fields)
        if missing or len(fields) != len(set(fields)):
            raise ValueError(f'{path}: missing/duplicate fields: {sorted(missing)}')
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{path}:{reader.line_num}: CSV row width mismatch')
            if all(row[key] == str(value) for key, value in filters.items()):
                yield row


def rows(alias, defaults=True, **filters):
    spec = ACCESS['tables'][alias]
    selected = {**(spec['default_filters'] if defaults else {}), **filters}
    yield from csv_rows(table_path(alias), spec['required_columns'], selected)


def endpoints(pool_id, stage=None):
    selected = dict(pool_id=pool_id)
    if stage is not None:
        selected['stage'] = stage
    for shard in rows('endpoint_shards', **selected):
        yield from csv_rows(resolve(shard['scalar_file'], BASE),
                            ('team_key', 'pool_id', 'reference_id', 'geometry_state_pointer'))


def geometry(scalar):
    filename, marker, line = scalar['geometry_state_pointer'].partition('#L')
    if not marker or not line.isdecimal() or int(line) < 1:
        raise ValueError('Invalid 1-based geometry pointer')
    with gzip.open(resolve(filename, BASE), 'rt', encoding='utf-8-sig') as stream:
        payload = next(islice(stream, int(line)-1, int(line)), None)
    if payload is None:
        raise ValueError('Geometry pointer exceeds saved file')
    record = json.loads(payload)
    if any(record[key] != scalar[key] for key in ('team_key', 'pool_id', 'reference_id')):
        raise ValueError('Geometry/scalar identity mismatch')
    return record


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('table', choices=ACCESS['tables'])
    parser.add_argument('--limit', type=int, default=3)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error('--limit must be nonnegative')
    print(json.dumps(list(islice(rows(args.table), args.limit)), ensure_ascii=False, indent=2))
