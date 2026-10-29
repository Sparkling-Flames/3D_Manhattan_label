"""Create an immutable stage ZIP and read every member back, including gzip CRC.

This utility only packages saved work; it never fits, samples, fuses or scores.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--include', nargs='+', required=True)
    p.add_argument('--exclude', action='append', default=[], help='Relative path prefix or glob to omit explicitly')
    p.add_argument('--out', required=True)
    p.add_argument('--verify-existing', action='store_true', help='Read an existing immutable archive and verify it without rewriting')
    a = p.parse_args()
    root, out = Path(a.root).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    target = out / (a.name + '.zip')
    if target.exists() and not a.verify_existing:
        raise FileExistsError('Stage archives are immutable: ' + str(target))
    files = sorted(set(f for item in a.include for f in
        ((root / item).rglob('*') if (root / item).is_dir() else [root / item])
        if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'
        and not any(str(f.relative_to(root)).startswith(x.rstrip('/') + '/') or
                    str(f.relative_to(root)) == x.rstrip('/') or
                    f.relative_to(root).match(x) for x in a.exclude)))
    if a.verify_existing:
        with zipfile.ZipFile(target) as z:
            manifest=json.loads(z.read('ARCHIVE_MANIFEST.json'))
        current=[{'path':str(f.relative_to(root)),'bytes':f.stat().st_size,'sha256':file_sha(f)} for f in files]
        assert manifest==current, 'Existing archive is not an exact match to selected frozen files'
    else:
        manifest = []
        with zipfile.ZipFile(target, 'w', allowZip64=True) as z:
            for f in files:
                rel = str(f.relative_to(root))
                manifest.append({'path': rel, 'bytes': f.stat().st_size, 'sha256': file_sha(f)})
                z.write(f, rel, compress_type=zipfile.ZIP_STORED if f.suffix in
                        {'.gz', '.zip', '.jpg', '.png', '.pdf'} else zipfile.ZIP_DEFLATED)
            z.writestr('ARCHIVE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    checks = []
    with zipfile.ZipFile(target) as z:
        assert len(z.namelist()) == len(manifest) + 1
        assert json.loads(z.read('ARCHIVE_MANIFEST.json')) == manifest
        for m in manifest:
            name = m['path']
            h=hashlib.sha256(); n=0
            with z.open(name) as src:
                for chunk in iter(lambda:src.read(1<<20),b''):h.update(chunk);n+=len(chunk)
            assert h.hexdigest() == m['sha256'] and n == m['bytes']
            plain = name[:-3] if name.endswith('.gz') else name
            check = {'path': name, 'sha256_match': True, 'all_bytes_read': True}
            with z.open(name) as raw:
                binary = gzip.GzipFile(fileobj=raw) if name.endswith('.gz') else raw
                if plain.endswith(('.json','.jsonl','.csv')):
                    with io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as src:
                        if plain.endswith('.json'):
                            json.load(src); check['json_parsed'] = True
                        elif plain.endswith('.jsonl'):
                            count = sum(1 for line in src if line.strip() and json.loads(line) is not None)
                            check['jsonl_rows'] = count
                        else:
                            rows=csv.reader(src);header=next(rows,[]);count=0;empty=0
                            for row in rows:
                                if not row:
                                    empty+=1
                                    continue
                                assert len(row)==len(header),(name,count,len(row),len(header))
                                count+=1
                            check['csv_rows']=count
                            check['csv_empty_records_preserved']=empty
                elif name.endswith('.gz'):
                    for chunk in iter(lambda:binary.read(1<<20),b''):pass
                    binary.close()
            checks.append(check)
    receipt = {'archive': str(target), 'archive_sha256': file_sha(target),
               'archive_bytes': target.stat().st_size, 'files': len(manifest),
               'passed': True, 'gzip_crc_and_end_verified': True, 'checks': checks}
    (out / (a.name + '_READABILITY.json')).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'checks'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
