"""Create an immutable stage ZIP and read every member back, including gzip CRC.

This utility only packages saved work; it never fits, samples, fuses or scores.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--include', nargs='+', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    root, out = Path(a.root).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    target = out / (a.name + '.zip')
    if target.exists():
        raise FileExistsError('Stage archives are immutable: ' + str(target))
    files = sorted(set(f for item in a.include for f in
        ((root / item).rglob('*') if (root / item).is_dir() else [root / item])
        if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'))
    manifest = []
    with zipfile.ZipFile(target, 'w', allowZip64=True) as z:
        for f in files:
            data = f.read_bytes()
            rel = str(f.relative_to(root))
            manifest.append({'path': rel, 'bytes': len(data), 'sha256': sha(data)})
            z.writestr(rel, data, compress_type=zipfile.ZIP_STORED if f.suffix in
                       {'.gz', '.zip', '.jpg', '.png', '.pdf'} else zipfile.ZIP_DEFLATED)
        z.writestr('ARCHIVE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    checks = []
    with zipfile.ZipFile(target) as z:
        assert len(z.namelist()) == len(manifest) + 1
        for m in manifest:
            data = z.read(m['path'])
            assert sha(data) == m['sha256'] and len(data) == m['bytes']
            name = m['path']
            decoded = gzip.decompress(data) if name.endswith('.gz') else data
            plain = name[:-3] if name.endswith('.gz') else name
            check = {'path': name, 'sha256_match': True, 'all_bytes_read': True}
            if plain.endswith('.json'):
                json.loads(decoded); check['json_parsed'] = True
            elif plain.endswith('.jsonl'):
                count = sum(1 for line in decoded.decode('utf-8-sig').splitlines()
                            if line.strip() and json.loads(line) is not None)
                check['jsonl_rows'] = count
            elif plain.endswith('.csv'):
                rows = csv.reader(io.StringIO(decoded.decode('utf-8-sig')))
                header = next(rows, [])
                count = 0
                for row in rows:
                    assert len(row) == len(header), (name, count, len(row), len(header))
                    count += 1
                check['csv_rows'] = count
            checks.append(check)
    receipt = {'archive': str(target), 'archive_sha256': sha(target.read_bytes()),
               'archive_bytes': target.stat().st_size, 'files': len(manifest),
               'passed': True, 'gzip_crc_and_end_verified': True, 'checks': checks}
    (out / (a.name + '_READABILITY.json')).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'checks'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
