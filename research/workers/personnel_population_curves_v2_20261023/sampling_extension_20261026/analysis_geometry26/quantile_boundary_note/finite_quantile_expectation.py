"""Verbatim existing function from analysis_precision26/exact_anchor_and_display.py.
No RNG, simulation or fusion calls.
"""
import numpy as np
from scipy.stats import binom

def finite_quantile_expectation(values, n, p=.1):
    """Exact expected sample quantiles from a known discrete finite law.

    Given n scoreable uniform-team draws, P(X_(r)<=v)=P(Bin(n,F(v))>=r).
    Linear interpolation uses the two adjacent expected order statistics.
    This is a deterministic calculation, not a new permutation or bootstrap.
    """
    q = np.asarray(values, float); q = q[np.isfinite(q)]
    if len(q) == 0 or n <= 0:
        return np.nan, np.nan
    value, count = np.unique(q, return_counts=True)
    F = np.cumsum(count) / len(q)
    def order_mean(rank):
        cd = binom.sf(rank - 1, n, F)
        mass = np.diff(np.r_[0., cd])
        return float(value @ mass)
    h = p * (n - 1); lower = int(np.floor(h)) + 1; upper = int(np.ceil(h)) + 1
    frac = h - np.floor(h)
    linear = (1 - frac) * order_mean(lower) + frac * order_mean(upper)
    inverse = order_mean(max(1, int(np.ceil(p * n))))
    return linear, inverse
