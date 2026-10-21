"""Descriptive independent reanalysis of committed same-room structural predictions.

No refitting, new labels, fusion, or production changes. Run from repository root.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / 'research/same_room/same_room_multiview_20261020/structure_transfer/transfer_predictions.csv.gz'
OUT = ROOT / 'research/same_room/same_room_independent_followup_20261021/structure'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(INPUT)
    key = ['metric', 'building', 'image', 'worker']
    assert not data.duplicated(key).any(), 'Repeated target evidence needs explicit resolution'
    assert data[['actual', 'predicted', 'baseline', 'other_source']].notna().all().all()
    for err, prediction in [('error', 'predicted'), ('baseline_error', 'baseline'), ('other_source_error', 'other_source')]:
        np.testing.assert_allclose(data[err], abs(data.actual-data[prediction]), rtol=1e-10, atol=1e-10)
    images = data.groupby(['metric', 'building', 'image'])[['error','baseline_error','other_source_error']].mean().reset_index()
    buildings = images.groupby(['metric','building'])[['error','baseline_error','other_source_error']].mean().reset_index()
    buildings['own_gain_vs_source_peers'] = buildings.other_source_error-buildings.error
    buildings['own_gain_vs_outside_history'] = buildings.baseline_error-buildings.error
    buildings.to_csv(OUT/'building_errors.csv', index=False)
    images.to_csv(OUT/'image_errors.csv', index=False)
    rng = np.random.default_rng(20261021)
    rows = []
    for metric, b in buildings.groupby('metric'):
        gain = b.own_gain_vs_source_peers.to_numpy()
        n = len(gain)
        assert n > 1
        boot = gain[rng.integers(n, size=(20000,n))].mean(axis=1)
        loo = (gain.sum()-gain)/(n-1)
        original = data[data.metric.eq(metric)]
        rows.append(dict(metric=metric, target_records=len(original), images=original.image.nunique(), buildings=n,
                         workers=original.worker.nunique(), history_n_min=int(original.history_n.min()),
                         history_n_max=int(original.history_n.max()), own_source_mae=b.error.mean(),
                         source_peers_mae=b.other_source_error.mean(), outside_history_mae=b.baseline_error.mean(),
                         own_gain_vs_source_peers=gain.mean(), positive_buildings=int((gain>1e-12).sum()),
                         tied_buildings=int((abs(gain)<=1e-12).sum()), negative_buildings=int((gain < -1e-12).sum()),
                         leave_one_building_gain_min=loo.min(),leave_one_building_gain_max=loo.max(),
                         descriptive_bootstrap_lower=float(np.quantile(boot,.025)), descriptive_bootstrap_upper=float(np.quantile(boot,.975))))
    pd.DataFrame(rows).to_csv(OUT/'summary.csv', index=False)
    receipt = dict(input=str(INPUT.relative_to(ROOT)), input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                   input_rows=len(data), duplicate_metric_building_image_worker=0,
                   source_commit='3391bc6ba241172e06fa114728b4c58d40558b3f',
                   estimand='Worker-average within target image, image-average within building, equal building mean paired absolute-error difference.',
                   bootstrap='20,000 bootstrap resamples of 7 building means; seed 20261021; descriptive only, not independent held-out confirmation.',
                   scope='Existing all available source histories. No re-enumeration of strict-majority information budgets; does not verify the inaccessible new Pro package.')
    (OUT/'provenance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()

