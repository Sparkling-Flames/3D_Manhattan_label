#!/usr/bin/env python3
"""Re-export merged decimal seeds from exact per-pool originals; no resampling."""
from pathlib import Path
import argparse, csv, gzip, hashlib, io, json
import pandas as pd
from precision_core import read_csv_exact_seeds, save_csv, save_json, seed_for


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args(); root = args.root.resolve(); changes = []
    for stage in [0, 1, 2]:
        out = root / 'analysis_precision26' / ('results_stage' + str(stage))
        target = out / 'NATURAL_PATH_STRATA.csv.gz'
        if not target.exists():
            changes.append(dict(stage=stage, status='no merged seed table yet; formal compiler patched'))
            continue
        old_raw = target.read_bytes(); old = read_csv_exact_seeds(target)
        # Preserve exactly this existing merged support, not the later subset
        # that happened to finish before the correction was run.
        pids = list(dict.fromkeys(old.pool_id))
        paths = [out / 'pool_checkpoints' / (pid + '__path_strata.csv.gz') for pid in pids]
        current = pd.concat([read_csv_exact_seeds(p) for p in paths], ignore_index=True)
        key = ['pool_id', 'path_id']; a = old.set_index(key); b = current.set_index(key)
        assert set(a.index) == set(b.index) and len(a) == len(b)
        assert current.bootstrap_stratum_seed.map(lambda x: str(x).isdigit()).all()
        for (pid, stratum), g in current.groupby(['pool_id', 'stratum']):
            done = json.loads((out / 'pool_checkpoints' / (pid + '__DONE.json')).read_text())
            expected = str(seed_for(done['bootstrap_master_seed'], pid, stratum, 'whole_paths'))
            assert g.bootstrap_stratum_seed.eq(expected).all(), (pid, stratum)
        changed_rows = int((a.bootstrap_stratum_seed.astype(str) != b.loc[a.index].bootstrap_stratum_seed.astype(str)).sum())
        record = save_csv(current, target)
        # Check the actual serialized decimal tokens, not a float reload.
        rr = csv.DictReader(io.StringIO(gzip.decompress(target.read_bytes()).decode()))
        assert all(row['bootstrap_stratum_seed'].isdigit() for row in rr)
        receipt = out / 'ANALYSIS_RECEIPT.json'
        if receipt.exists():
            meta = json.loads(receipt.read_text())
            meta['outputs'] = [record if Path(x['file']).name == target.name else x for x in meta.get('outputs', [])]
            meta['seed_export_corrected_from_exact_per_pool_checkpoints'] = True
            save_json(meta, receipt)
        changes.append(dict(stage=stage, status='corrected merged export',
                            old_sha256=hashlib.sha256(old_raw).hexdigest(),
                            paths_with_changed_serialized_seed=changed_rows, exact_pool_support=len(pids),
                            bootstrap_resampled=False, statistics_recomputed=False, output=record))
    save_json(dict(source='exact per-pool path_strata checkpoints and existing bootstrap master seed',
                   cause='int64/uint64 cross-pool concatenation can coerce to float64',
                   locked_S02_modified=False, changes=changes),
              root / 'analysis_precision26/SEED_EXPORT_CORRECTION.json')
    print(json.dumps(changes, ensure_ascii=False))


if __name__ == '__main__':
    main()
