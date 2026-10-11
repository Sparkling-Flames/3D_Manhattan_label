"""Check algebra numerically. This is not a test of human quality validity."""
import json
import math
import random
from pathlib import Path


def check(n=100000, seed=20261011):
    rng = random.Random(seed)
    for _ in range(n):
        i, r = rng.random(), rng.random()
        s, h, q = rng.random() * 12, rng.random() * 2, rng.uniform(.001, 100)
        score = 100 * i * r / (1 + (s / 4) ** 2 + (h / .5) ** 2)
        assert (score >= q) == ((s / 4) ** 2 + (h / .5) ** 2 <= 100 * i * r / q - 1)
        if score >= q:
            assert i >= q / 100 - 1e-12
            assert s <= 4 * math.sqrt(100 / q - 1) + 1e-12
            assert h <= .5 * math.sqrt(100 / q - 1) + 1e-12
        i0, r0 = i * rng.random(), r * rng.random()
        s0, h0 = s + rng.random(), h + rng.random()
        assert score >= 100 * i0 * r0 / (1 + (s0 / 4) ** 2 + (h0 / .5) ** 2) - 1e-12
    return dict(seed=seed, random_trials=n, budget_equivalence=True,
                necessary_bounds=True, joint_tolerance_sufficient_lower_bound=True,
                human_threshold_validation=False)


if __name__ == '__main__':
    result = check()
    expected = json.loads(Path(__file__).with_name('math_identity_checks.json').read_text())
    assert result == expected
    print(json.dumps(result, ensure_ascii=False, indent=2))
