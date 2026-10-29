"""Merge independently registered, outcome-blind studies by exact identity.

No native endpoint or outcome is read. Design links retain their provenance;
events and teams are deduplicated. All gzip files are read to EOF before return.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, os
from collections import defaultdict
from pathlib import Path


def read(path):
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sources', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    sources = [Path(p).resolve() for p in a.sources]
    out = Path(a.out).resolve(); out.mkdir(exist_ok=False)
    counts, identities, family = {}, {}, defaultdict(set)
    manifests = []
    for filename, key in [('DESIGN_LINKS.csv.gz', 'link_id'), ('AC_EVENTS.csv.gz', 'event_id'),
                          ('TEAM_REQUESTS.csv.gz', 'team_key')]:
        fields = set()
        for source in sources:
            path = source / filename
            first = next(read(path), {})
            fields.update(first)
            manifests.append({'source': str(source), 'file': filename, 'sha256': sha(path), 'bytes': path.stat().st_size})
        fields.update(['registration_source'])
        fields = sorted(fields)
        seen, n, duplicates = {}, 0, 0
        tmp = out / (filename + '.partial')
        with gzip.open(tmp, 'wt', encoding='utf-8-sig', newline='', compresslevel=5) as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
            for si, source in enumerate(sources):
                for row in read(source / filename):
                    original_key = row[key]
                    if filename == 'DESIGN_LINKS.csv.gz':
                        row[key] = str(si) + ':' + original_key
                        family[row['event_id']].add(row['design_family'])
                    elif filename == 'AC_EVENTS.csv.gz':
                        row['design_family'] = '|'.join(sorted(family[row['event_id']]))
                        identity = digest({k: row.get(k, '') for k in [
                            'event_id', 'pool_id', 'method', 'A_team_key', 'C_team_key',
                            'A_workers', 'C_workers', 'D_workers', 'X_workers', 'Z_workers',
                            'source_class', 'target_class', 'n_A', 'n_C', 'reference_id', 'reference_version']})
                        if original_key in seen:
                            assert seen[original_key] == identity, ('event identity disagreement', original_key)
                            duplicates += 1; continue
                        seen[original_key] = identity
                    else:
                        identity = digest({k: row.get(k, '') for k in [
                            'team_key', 'pool_id', 'member_workers', 'n', 'member_object_ids',
                            'reference_id', 'reference_version']})
                        if original_key in seen:
                            assert seen[original_key] == identity, ('team identity disagreement', original_key)
                            duplicates += 1; continue
                        seen[original_key] = identity
                    row['registration_source'] = source.name
                    w.writerow(row); n += 1
        # Reopen from disk to flush the complete stream before atomically publishing.
        with tmp.open('rb') as f:
            os.fsync(f.fileno())
        tmp.replace(out / filename)
        count = 0
        for row in read(out / filename):
            assert None not in row and all(v is not None for v in row.values())
            count += 1
        assert count == n
        counts[filename] = {'rows': n, 'duplicates_removed': duplicates,
                            'sha256': sha(out / filename), 'gzip_EOF_and_CRC_verified': True}
    receipt = {'sources': manifests, 'outputs': counts,
               'outcome_reads': 0, 'fusion_calls': 0, 'design_frozen_before_new_results': True,
               'reverse_views_not_replicates': True,
               'events_unique_with_design_links_preserved': True}
    (out / 'FROZEN_MERGED_DESIGN.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == '__main__':
    main()
