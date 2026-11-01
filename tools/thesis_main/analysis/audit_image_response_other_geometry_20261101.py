"""Independent all-cell checks of saved geometry denominators and four distances."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

BASE = Path(__file__).resolve().parents[3] / 'research/workers/image_response_v21_20261101'
R = BASE / 'HOHONET_v21_image_response_20261101'
O = BASE / 'audit_geometry'
weights = pd.read_csv(R / 'stage04_geometry/doorway_exact_U/PATH_STATE_MULTIPLICITIES.csv.gz')
curves = pd.read_csv(R / 'stage04_geometry/doorway_exact_U/GEOMETRY_U_CURVES.csv.gz')
saved = curves.set_index(['pool_id', 'k', 'metric'])
rows = []
for image, iw in weights.groupby('image'):
    cat = pd.read_csv(R / f'stage02_normalized/doorway_enriched/geometry/{image}.csv.gz', low_memory=False)
    cat = cat[cat.k.ge(3)].reset_index(drop=True)
    validity = {}
    for ix in iw.catalog_index.unique():
        row = cat.loc[ix]
        allowed = str(row.geometry_eligible).lower() in ['true', '1', '1.0']
        if allowed and isinstance(row.footprint_json, str):
            polygon = Polygon(json.loads(row.footprint_json))
            validity[ix] = bool(polygon.is_valid and not polygon.is_empty and polygon.area > 0)
        else:
            validity[ix] = False
    assert np.array_equal(iw.catalog_index.map(validity).to_numpy(), iw.floor_valid_for_pair.to_numpy())
    ids = iw.loc[iw.floor_valid_for_pair, 'catalog_index'].unique()
    centers = {i: np.array(Polygon(json.loads(cat.loc[i, 'footprint_json'])).centroid.coords)[0] for i in ids}
    for (pool, k), group in iw.groupby(['pool_id', 'k']):
        good = group[group.floor_valid_for_pair]
        expanded = np.repeat(good.catalog_index.to_numpy(int), good.path_multiplicity.to_numpy(int))
        for metric, source in [('centroid_distance_h', None), ('height_distance_h', 'height_mean_h'),
                               ('node_count_distance', 'nodes'), ('turn_count_distance', 'turns')]:
            if source is None:
                val = np.array([centers[i] for i in expanded]).reshape(-1, 2)
            else:
                val = pd.to_numeric(cat.loc[expanded, source], errors='coerce').to_numpy(float)
                val = val[np.isfinite(val)]
            count = len(val)
            a, b = np.triu_indices(count, 1)
            d = np.linalg.norm(val[a] - val[b], axis=1) if source is None else np.abs(val[a] - val[b])
            avg = float(d.mean()) if len(d) else np.nan
            s = saved.loc[(pool, k, metric)]
            assert int(s.valid_paths) == count and int(s.valid_path_pairs) == len(d)
            # Tolerances are stated numerically; actual maximum errors are saved.
            assert np.isclose(avg, s['mean'], atol=1e-6, rtol=1e-5, equal_nan=True), (pool, k, metric, avg, s['mean'])
            rows.append(dict(pool_id=pool, k=k, metric=metric, pairs=len(d), recomputed=avg, saved=s['mean']))
    print(image, len(rows), flush=True)
out = pd.DataFrame(rows)
out.to_csv(O / 'OTHER_GEOMETRY_DIRECT_CHECKS.csv', index=False)
out['abs_error'] = (out.recomputed - out.saved).abs()
summary = out.groupby('metric').agg(cells=('k', 'size'), max_abs_error=('abs_error', 'max'), path_pairs=('pairs', 'sum')).reset_index()
summary.to_csv(O / 'OTHER_GEOMETRY_SUMMARY.csv', index=False)
print(summary.to_string(index=False))
