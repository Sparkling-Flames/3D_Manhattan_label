"""Collect finished scientific figures into the portable report tree.

Copies bytes only. No new sampling, endpoint evaluation, geometry or statistics.
Natural F01--F04 become N01--N04 to avoid the already delivered finite-case
F04--F07. Original source paths and hashes remain in a compact manifest.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    args = ap.parse_args()
    base = args.base.resolve()
    for relative in ['analysis_precision26/results_stage2/NATURAL_FINALIZATION_COMPLETE.json',
                     'analysis_geometry26/GEOMETRY_FINALIZATION_COMPLETE.json']:
        if not (base / relative).is_file():
            raise FileNotFoundError(relative)
    folders = [
        ('analysis_precision26/figures_stage2', 'N'),
        ('analysis_geometry26/figures', 'G'),
        ('analysis_geometry26/low_k_cases', 'L'),
        ('analysis_policy26/presentation', 'P'),
    ]
    out = base / 'report26/figures'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for directory, prefix in folders:
        folder = base / directory
        for file in sorted(folder.rglob('*')):
            if not file.is_file() or '__pycache__' in file.parts or '.matplotlib_cache' in file.parts:
                continue
            figure = file.suffix.lower() in {'.png', '.pdf', '.svg'}
            source = 'SOURCE' in file.name and file.name.endswith(('.csv', '.csv.gz', '.json'))
            caption = 'CAPTION' in file.name and file.suffix == '.md'
            if not (figure or source or caption):
                continue
            name = file.name
            if name.startswith('F') and len(name) > 2 and name[1:3].isdigit():
                name = prefix + name[1:]
            elif not name.startswith(prefix):
                name = prefix + '_' + name
            target = out / name
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Different source would overwrite ' + str(target))
            shutil.copyfile(file, target)
            rows.append(dict(source=str(file.relative_to(base)),
                report_file=str(target.relative_to(base)), bytes=target.stat().st_size,
                sha256=digest, operation='byte-identical copy; no analysis'))
    if not any('N05' in r['report_file'] and r['report_file'].endswith('.png') for r in rows):
        raise RuntimeError('Run plot_individual_full_curves.py before collecting final figures')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=['source','report_file','bytes','sha256','operation'])
    writer.writeheader(); writer.writerows(rows)
    (out / 'FINAL_FIGURE_SOURCE_MANIFEST.csv').write_text(stream.getvalue(), encoding='utf-8')
    receipt = dict(complete=True, files=len(rows), new_sampling=False, new_statistics=False,
        all_copies_identical=True, original_case_F04_to_F07_untouched=True)
    (out / 'FINAL_FIGURE_COLLECTION_RECEIPT.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
