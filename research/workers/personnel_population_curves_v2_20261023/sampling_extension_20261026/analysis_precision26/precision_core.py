#!/usr/bin/env python3
"""Frozen estimands and whole-path precision calculations; no fusion code.

Multinomial path weights are an exact computational representation of the
ordinary nonparametric bootstrap, not new paths or unequal design weights.
"""
from pathlib import Path
import csv, gzip, hashlib, io, json, math, os, warnings, importlib.util
for _env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_env] = "1"
import numpy as np
import pandas as pd
from scipy.stats import beta, binom, norm, t

warnings.filterwarnings("ignore", category=RuntimeWarning)
META = ["pool_id", "image", "image_id", "building", "condition", "layer",
        "difficulty", "pool_n", "reference_id", "reference_version"]
COMP = ["B8_floor_block", "B8_direction_block", "B8_height_block",
        "B8_global_height_block", "B8_local_height_block", "iou_2d",
        "S_bottom_deg", "dir", "height_mean_h", "Hmean", "Hcenter",
        "omission", "extension", "D10_direction_block"]
RAW = ["B8L2", "D10", "floor_turn5_n", "floor_redundant5_n", "nodes",
       "score_failure_nonpolicy", "incomplete_nonpolicy", "policy_deferred",
       "consensus_unformed_nonpolicy", "output_unscoreable_nonpolicy",
       "reference_unavailable_nonpolicy", "not_executed_nonpolicy"]
BOOL = ["score_available", "complete_evaluable", "connection_available", "below_four",
        "score_failure_nonpolicy", "incomplete_nonpolicy", "policy_deferred"]
STATUS = ["score_status", "geometry_status"]
METRICS = ["Q_mean", "Q_p10", "Q_sd_ddof1", "D10_mean", "floor_turn5_mean",
           "floor_redundant5_mean", "nodes_mean", "failure_rate", "incomplete_rate",
           "Q_p10_inverse_cdf", "actual_consensus_failure_rate", "output_unscoreable_rate",
           "reference_unavailable_rate", "not_executed_rate"]
IMETRICS = ["marginal_Q_delta", "Q_p10_delta", "Q_sd_delta", "paired_Q_delta",
            "paired_D10_delta", "paired_Q_loss_gt5_rate", "paired_Q_gain_gt5_rate",
            "failure_delta", "incomplete_delta", "floor_turn5_delta", "nodes_delta",
            "actual_consensus_failure_delta", "output_unscoreable_delta"]
COHORTS = {"old48": ["old24", "prior_new24"],
           "stage1_104": ["new104A"], "stage2_104": ["new104B"],
           "new208": ["new104A", "new104B"],
           "pooled152": ["old24", "prior_new24", "new104A"],
           "pooled256": ["old24", "prior_new24", "new104A", "new104B"],
           "prior96": ["old24", "prior_new24", "prior_focus48"],
           "all_history304": ["old24", "prior_new24", "prior_focus48", "new104A", "new104B"]}
STRATUM_COUNTS = {"old24": 24, "prior_new24": 24, "prior_focus48": 48,
                  "new104A": 104, "new104B": 104}
TOL = 1e-9
_FROZEN_BLOCKS = None


def add_frozen_blocks(frame, root):
    """Projection of named explanation terms; never recompute saved Q/status."""
    global _FROZEN_BLOCKS
    if _FROZEN_BLOCKS is None:
        path = Path(root) / "engine26/derive_frozen_blocks.py"
        if not path.exists():
            raise FileNotFoundError("Required frozen component projection: " + str(path))
        spec = importlib.util.spec_from_file_location("hohonet_frozen_named_blocks26", path)
        _FROZEN_BLOCKS = importlib.util.module_from_spec(spec); spec.loader.exec_module(_FROZEN_BLOCKS)
    return _FROZEN_BLOCKS.add_blocks_frame(frame, check_existing=True)


def seed_for(*values):
    return int.from_bytes(hashlib.sha256("|".join(map(str, values)).encode()).digest()[:8], "little")


def write_bytes(path, payload):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".writing")
    with open(tmp, "wb") as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    assert tmp.read_bytes() == payload
    os.replace(tmp, path)
    assert path.read_bytes() == payload


def save_csv(frame, path):
    path = Path(path)
    body = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    payload = gzip.compress(body, compresslevel=6, mtime=0) if path.suffix == ".gz" else body
    write_bytes(path, payload)
    actual = path.read_bytes(); decoded = gzip.decompress(actual) if path.suffix == ".gz" else actual
    rows = csv.reader(io.StringIO(decoded.decode("utf-8"))); header = next(rows)
    assert header == list(frame.columns), (path, "header")
    count = 0
    for row in rows:
        count += 1
        assert len(row) == len(header), (path, count, "fields")
    assert count == len(frame), (path, count, len(frame))
    return dict(file=str(path), rows=count, fields=len(header), bytes=len(actual),
                sha256=hashlib.sha256(actual).hexdigest(), readback="CSV/gzip complete to EOF")


def save_json(obj, path):
    write_bytes(path, json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=True).encode())


def read_csv_exact_seeds(path, **kwargs):
    """Preserve 64-bit decimal seed text before cross-pool concatenation.

    A mixture of int64 and uint64 columns can become float64 in pandas.concat.
    Treat every exact seed column as text before that conversion can occur.
    This changes reproducibility records only, never generated random draws.
    """
    header = pd.read_csv(path, nrows=0).columns
    dtypes = dict(kwargs.pop("dtype", {}) or {})
    dtypes.update({c: str for c in header if c == "seed" or c.endswith("_seed")})
    kwargs.setdefault("low_memory", False)
    return pd.read_csv(path, dtype=dtypes, **kwargs)


def numeric(s):
    return pd.to_numeric(s.replace({"True": 1, "False": 0, "true": 1, "false": 0}),
                         errors="coerce").replace([np.inf, -np.inf], np.nan)


def ratio(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float)
    return np.divide(num, den, out=np.full(np.broadcast_shapes(num.shape, den.shape), np.nan),
                     where=den > 0)


def weighted_mean(x, w):
    good = np.isfinite(x)
    den = w @ good.astype(float)
    return ratio(w @ np.where(good, x, 0), den), den


def weighted_quantiles(q, w):
    """NumPy linear P10 and empirical inverse-CDF P10 of weighted resamples.

    w contains integer bootstrap frequencies. NaN scores do not enter either
    conditional distribution; resamples with no valid Q stay NaN.
    """
    b, r = w.shape; nk = q.shape[1]
    linear = np.full((b, nk), np.nan); icdf = linear.copy()
    for ki in range(nk):
        good = np.flatnonzero(np.isfinite(q[:, ki]))
        if len(good) == 0:
            continue
        order = good[np.argsort(q[good, ki], kind="stable")]
        vals = q[order, ki]
        if vals[0] == vals[-1]:
            n = w[:, order].sum(1); linear[n > 0, ki] = vals[0]; icdf[n > 0, ki] = vals[0]
            continue
        cw = np.cumsum(w[:, order], axis=1); n = cw[:, -1]
        h = .1 * (n - 1); a = np.floor(h).astype(int); frac = h - a
        il = np.argmax(cw > a[:, None], axis=1)
        iu = np.argmax(cw > (a + (frac > 0))[:, None], axis=1)
        iv = np.argmax(cw >= np.ceil(.1 * n)[:, None], axis=1)
        ok = n > 0
        linear[ok, ki] = vals[il[ok]] * (1 - frac[ok]) + vals[iu[ok]] * frac[ok]
        icdf[ok, ki] = vals[iv[ok]]
    return linear, icdf


def weighted_stats(a, w):
    """Result [replicate,k,metric]; w=ones(1,R) gives observed estimates."""
    q = a["B8L2"]
    mean, count = weighted_mean(q, w)
    # Center on the observed mean to avoid catastrophic cancellation at full N.
    center = np.nanmean(q, axis=0)
    dev = q - center[None]
    md, _ = weighted_mean(dev, w)
    sq, _ = weighted_mean(dev * dev, w)
    var = ratio(np.maximum(sq - md * md, 0) * count, count - 1)
    constant = np.nanmin(q, axis=0) == np.nanmax(q, axis=0)
    if constant.any():
        value = np.nanmin(q, axis=0)
        mean[:, constant] = np.where(count[:, constant] > 0, value[constant][None], np.nan)
        var[:, constant] = np.where(count[:, constant] > 1, 0.0, np.nan)
    p10, icdf = weighted_quantiles(q, w)
    ndefer = np.isfinite(a["policy_deferred"]) & (a["policy_deferred"] == 0)
    den = w @ ndefer.astype(float)
    failure = ratio(w @ np.where(ndefer, a["score_failure_nonpolicy"], 0), den)
    incomplete = ratio(w @ np.where(ndefer, a["incomplete_nonpolicy"], 0), den)
    attempted = ndefer & (a["not_executed_nonpolicy"] == 0)
    aden = w @ attempted.astype(float)
    consensus_failure = ratio(w @ np.where(attempted, a["consensus_unformed_nonpolicy"], 0), aden)
    output_unscoreable = ratio(w @ np.where(attempted, a["output_unscoreable_nonpolicy"], 0), aden)
    reference_unavailable = ratio(w @ np.where(ndefer, a["reference_unavailable_nonpolicy"], 0), den)
    not_executed = ratio(w @ np.where(ndefer, a["not_executed_nonpolicy"], 0), den)
    return np.stack([mean, p10, np.sqrt(var), weighted_mean(a["D10"], w)[0],
                     weighted_mean(a["floor_turn5_n"], w)[0],
                     weighted_mean(a["floor_redundant5_n"], w)[0],
                     weighted_mean(a["nodes"], w)[0], failure, incomplete, icdf,
                     consensus_failure, output_unscoreable, reference_unavailable, not_executed], axis=-1)


def interval_definitions(n):
    candidates = [("1_to_3", 1, 3), ("3_to_6", 3, 6), ("6_to_10", 6, 10),
                  ("10_to_20", 10, 20), ("20_to_30", 20, 30), ("30_to_35", 30, 35),
                  ("3_to_20", 3, 20), ("3_to_full", 3, n), ("10_to_full", 10, n),
                  ("20_to_full", 20, n), ("30_to_full", 30, n),
                  ("leave_one_out_to_full", n - 1, n)]
    return [(name, ka, kb) for name, ka, kb in candidates
            if 1 <= ka <= kb <= n and (ka < kb or name.endswith("_to_full"))]


def weighted_intervals(a, w, stats, idefs):
    out = []
    for name, ka, kb in idefs:
        dq = (a["B8L2"][:, kb - 1] - a["B8L2"][:, ka - 1])[:, None]
        dd = (a["D10"][:, kb - 1] - a["D10"][:, ka - 1])[:, None]
        both = np.isfinite(dq)
        # Endpoint differences are marginal conditional distributions; paired
        # deltas use the same observed permutation with both Q values finite.
        out.append(np.stack([stats[:, kb - 1, 0] - stats[:, ka - 1, 0],
                             stats[:, kb - 1, 1] - stats[:, ka - 1, 1],
                             stats[:, kb - 1, 2] - stats[:, ka - 1, 2],
                             weighted_mean(dq, w)[0][:, 0], weighted_mean(dd, w)[0][:, 0],
                             weighted_mean(np.where(both, dq < -5, np.nan), w)[0][:, 0],
                             weighted_mean(np.where(both, dq > 5, np.nan), w)[0][:, 0],
                             stats[:, kb - 1, 7] - stats[:, ka - 1, 7],
                             stats[:, kb - 1, 8] - stats[:, ka - 1, 8],
                             stats[:, kb - 1, 4] - stats[:, ka - 1, 4],
                             stats[:, kb - 1, 6] - stats[:, ka - 1, 6],
                             stats[:, kb - 1, 10] - stats[:, ka - 1, 10],
                             stats[:, kb - 1, 11] - stats[:, ka - 1, 11]], axis=-1))
    return np.stack(out, axis=1)


def bootstrap_weights(pool_id, stratum, n, B, master):
    rng = np.random.default_rng(seed_for(master, pool_id, stratum, "whole_paths"))
    return rng.multinomial(n, np.repeat(1.0 / n, n), size=B).astype(float)


def boot_summary(values):
    valid = np.isfinite(values); n = int(valid.sum())
    if n == 0:
        return dict(low=np.nan, high=np.nan, MCSE=np.nan, valid=0)
    x = values[valid]
    lo, hi = np.quantile(x, [.025, .975])
    return dict(low=float(lo), high=float(hi), MCSE=float(np.std(x, ddof=1)) if n > 1 else np.nan,
                valid=n)


def binomial_precision(x, n, alpha=.05):
    if n <= 0:
        return dict(CP_low=np.nan, CP_high=np.nan, Wilson_low=np.nan, Wilson_high=np.nan,
                    one_sided_CP_high=np.nan)
    x, n = int(x), int(n); p = x / n; z = norm.ppf(1 - alpha / 2)
    cp_lo = 0.0 if x == 0 else beta.ppf(alpha / 2, x, n - x + 1)
    cp_hi = 1.0 if x == n else beta.ppf(1 - alpha / 2, x + 1, n - x)
    cp_one = 1.0 if x == n else beta.ppf(1 - alpha, x + 1, n - x)
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return dict(CP_low=float(cp_lo), CP_high=float(cp_hi), Wilson_low=float(c - h),
                Wilson_high=float(c + h), one_sided_CP_high=float(cp_one))


def quantile_order_interval(q, alpha=.05, p=.1):
    x = np.sort(np.asarray(q)[np.isfinite(q)]); n = len(x)
    if n == 0:
        return dict(low=np.nan, high=np.nan, lower_rank=np.nan, upper_rank=np.nan, n=0)
    lower = int(binom.ppf(alpha / 2, n, p))
    upper = int(binom.ppf(1 - alpha / 2, n, p)) + 1
    return dict(low=0.0 if lower == 0 else float(x[lower - 1]),
                high=100.0 if upper > n else float(x[upper - 1]),
                lower_rank=lower, upper_rank=upper, n=n)


def arrays(g, paths, ks):
    out = {}
    for c in RAW + COMP:
        if c not in g:
            out[c] = np.full((len(paths), len(ks)), np.nan)
        else:
            out[c] = g.pivot(index="path_id", columns="k", values=c).reindex(index=paths, columns=ks).to_numpy(float)
    return out


def concatenate_arrays(chunks):
    return {c: np.concatenate([a[c] for a in chunks], axis=0) for c in chunks[0]}


def curve_band(observed, boot, ks, min_valid, full_n, eligible_mask=None):
    """Fixed observed support; no bootstrap-dependent change of k or weights.

    An empirical maximum-deviation band is diagnostic, not a distribution-free
    proof about unseen score modes. Values at k=full_n have known zero MC error.
    """
    obs = np.asarray(observed); est = np.isfinite(obs) & (np.asarray(min_valid) >= 2) & (np.asarray(ks) != 2)
    full = np.asarray(ks) == full_n
    est |= full & np.isfinite(obs)
    if eligible_mask is not None:
        est &= np.asarray(eligible_mask, dtype=bool)
    result = dict(estimated_k_n=int(est.sum()), missing_k="|".join(map(str, np.asarray(ks)[~est])),
                  estimated_k="|".join(map(str, np.asarray(ks)[est])))
    bands = np.full((len(ks), 4), np.nan)
    if not est.any():
        return {**result, "complete_bootstrap_draws": 0, "max_abs_95": np.nan,
                "max_studentized_95": np.nan, "zero_empirical_se_nonfull_k": ""}, bands
    bb = boot[:, est]; oo = obs[est]
    complete = np.isfinite(bb).all(axis=1)
    result["complete_bootstrap_draws"] = int(complete.sum())
    se = np.nanstd(bb, axis=0, ddof=1)
    result["zero_empirical_se_nonfull_k"] = "|".join(map(str, np.asarray(ks)[est][(se <= 1e-12) & ~full[est]]))
    if not complete.any():
        return {**result, "max_abs_95": np.nan, "max_studentized_95": np.nan}, bands
    delta = bb[complete] - oo[None]
    critical = float(np.quantile(np.max(np.abs(delta), axis=1), .95))
    good_scale = np.isfinite(se) & (se > 1e-12)
    critical_t = float(np.quantile(np.max(np.abs(delta[:, good_scale] / se[good_scale]), axis=1), .95)) if good_scale.any() else 0.0
    bands[est, 0] = oo - critical; bands[est, 1] = oo + critical
    bands[est, 2] = oo - critical_t * se; bands[est, 3] = oo + critical_t * se
    if (full & est).any():
        bands[full & est] = obs[full & est, None]
    return {**result, "max_abs_95": critical, "max_studentized_95": critical_t}, bands


def verify_weighted_bootstrap():
    """Meaningful equivalence fixture: NaNs, unequal frequencies and ties."""
    q = np.array([[1., np.nan, 80.], [2., 7., 80.], [2., 9., 80.], [90., 10., 80.]])
    a = {c: q.copy() for c in RAW + COMP}
    a["policy_deferred"] = np.zeros_like(q)
    a["score_failure_nonpolicy"] = (~np.isfinite(q)).astype(float)
    a["incomplete_nonpolicy"] = a["score_failure_nonpolicy"]
    for c in ["consensus_unformed_nonpolicy", "output_unscoreable_nonpolicy", "reference_unavailable_nonpolicy", "not_executed_nonpolicy"]:
        a[c] = np.zeros_like(q)
    indices = np.array([[0, 0, 3, 3], [2, 1, 1, 1], [0, 0, 0, 0], [3, 2, 1, 0]])
    w = np.stack([np.bincount(v, minlength=4) for v in indices]).astype(float)
    actual = weighted_stats(a, w)
    for b, ix in enumerate(indices):
        qq = q[ix]
        expected = [np.nanmean(qq, axis=0), np.nanquantile(qq, .1, axis=0, method="linear"),
                    np.nanstd(qq, axis=0, ddof=1),
                    np.nanquantile(qq, .1, axis=0, method="inverted_cdf")]
        for out_index, ref in zip([0, 1, 2, 9], expected):
            np.testing.assert_allclose(actual[b, :, out_index], ref, atol=1e-12, equal_nan=True)
    return {"fixture": "whole-path multinomial weights equal explicit repeated indices; NaNs/ties included", "passed": True}


if __name__ == "__main__":
    print(json.dumps(verify_weighted_bootstrap(), indent=2))
