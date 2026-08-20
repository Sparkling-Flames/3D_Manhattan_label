from __future__ import annotations

import hashlib, json, math, subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
SEED = 20260820
RNG = np.random.default_rng(SEED)
C1_ROOT = ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
PACKAGE = ROOT / "analysis_results" / "paper_a_data_mining_package_20260820_v1"
DEFAULT_OUT = ROOT / "analysis_results" / "annotation_uncertainty_mining_20260820_v1"

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def git_head() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except Exception:
        return 'not_identifiable'

def truth(value: Any) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y', 'passed', 'valid', 'eligible', 'matched'}

def num(value: Any) -> float | None:
    try:
        result = float(str(value).strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def norm_worker(value: Any) -> str:
    text = str(value or '').strip().upper()
    if text.startswith('W'):
        text = text[1:]
    return str(int(text)) if text.isdigit() else text

def clean_condition(value: Any) -> str:
    text = str(value or '').strip().lower().replace('-', '_')
    if 'semi' in text or 'assist' in text:
        return 'semi'
    if 'manual' in text:
        return 'manual'
    return text

def read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    return pd.read_csv(path, encoding='utf-8-sig', low_memory=False, **kwargs)

def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding='utf-8', lineterminator='\n')

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + '\n', encoding='utf-8')

def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(type(value).__name__)

def entropy_from_counts(counts: Sequence[int], *, normalized: bool=False) -> float:
    values = np.asarray([int(v) for v in counts if int(v) > 0], dtype=float)
    if not len(values):
        return float('nan')
    p = values / values.sum()
    h = float(-(p * np.log(p)).sum())
    if normalized:
        denominator = math.log(len(values))
        return h / denominator if denominator > 0 else 0.0
    return h

def miller_madow_entropy(counts: Sequence[int]) -> float:
    values = [int(v) for v in counts if int(v) > 0]
    n = sum(values)
    if not n:
        return float('nan')
    return entropy_from_counts(values) + (len(values) - 1) / (2 * n)

def gini_simpson(counts: Sequence[int]) -> float:
    values = np.asarray([int(v) for v in counts if int(v) > 0], dtype=float)
    if not len(values):
        return float('nan')
    p = values / values.sum()
    return float(1.0 - np.square(p).sum())

def bh_adjust(p_values: Sequence[float | None]) -> list[float | None]:
    valid = [(i, float(p)) for i, p in enumerate(p_values) if p is not None and math.isfinite(float(p))]
    output: list[float | None] = [None] * len(p_values)
    if not valid:
        return output
    ordered = sorted(valid, key=lambda item: item[1])
    running = 1.0
    for rank in range(len(ordered), 0, -1):
        index, p = ordered[rank - 1]
        running = min(running, p * len(ordered) / rank)
        output[index] = running
    return output

def paired_sign_flip(values: Sequence[float], *, replicates: int=20000, seed: int=SEED) -> float | None:
    x = np.asarray([v for v in values if math.isfinite(float(v))], dtype=float)
    if len(x) < 3:
        return None
    observed = abs(float(x.mean()))
    rng = np.random.default_rng(seed + len(x))
    if len(x) <= 18:
        extreme = total = 0
        for mask in range(1 << len(x)):
            signs = np.where([mask >> i & 1 for i in range(len(x))], 1.0, -1.0)
            extreme += abs(float(np.mean(x * signs))) >= observed - 1e-15
            total += 1
        return extreme / total
    signs = rng.choice([-1.0, 1.0], size=(replicates, len(x)))
    permuted = np.abs(np.mean(signs * x[None, :], axis=1))
    return float((np.count_nonzero(permuted >= observed - 1e-15) + 1) / (replicates + 1))

def bootstrap_interval(values: Sequence[float], *, replicates: int=10000, seed: int=SEED) -> tuple[float | None, float | None]:
    x = np.asarray([v for v in values if math.isfinite(float(v))], dtype=float)
    if len(x) < 3:
        return (None, None)
    rng = np.random.default_rng(seed + 13 * len(x))
    indices = rng.integers(0, len(x), size=(replicates, len(x)))
    draws = np.mean(x[indices], axis=1)
    return (float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)))

def spearman_with_group_permutation(frame: pd.DataFrame, x: str, y: str, group: str, *, replicates: int=9999, seed: int=SEED) -> dict[str, Any]:
    data = frame[[x, y, group]].dropna().copy()
    if len(data) < 6 or data[x].nunique() < 2 or data[y].nunique() < 2:
        return {'n': len(data), 'groups': data[group].nunique(), 'rho': None, 'p': None}
    aggregate = data.groupby(group, as_index=False)[[x, y]].mean()
    if len(aggregate) < 4:
        return {'n': len(data), 'groups': len(aggregate), 'rho': None, 'p': None}
    observed = float(stats.spearmanr(aggregate[x], aggregate[y]).statistic)
    rng = np.random.default_rng(seed + len(aggregate))
    y_values = aggregate[y].to_numpy().copy()
    extreme = 0
    for _ in range(replicates):
        rng.shuffle(y_values)
        value = stats.spearmanr(aggregate[x], y_values).statistic
        if abs(float(value)) >= abs(observed) - 1e-15:
            extreme += 1
    return {'n': len(data), 'groups': len(aggregate), 'rho': observed, 'p': (extreme + 1) / (replicates + 1)}

def flatten_json(value: Any, prefix: str='') -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value and prefix:
            yield (prefix, value)
        for key, child in value.items():
            yield from flatten_json(child, f'{prefix}.{key}' if prefix else str(key))
    elif isinstance(value, list):
        path = f'{prefix}[]'
        if not value:
            yield (path, value)
        for child in value:
            yield from flatten_json(child, path)
    elif prefix:
        yield (prefix, value)

def raw_inventory(out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_root = PACKAGE / 'raw'
    rows: list[dict[str, Any]] = []
    fields: Counter[tuple[str, str]] = Counter()
    for path in sorted((p for p in raw_root.rglob('*') if p.is_file())):
        rel = path.relative_to(ROOT).as_posix()
        suffix = path.suffix.lower()
        record_count: int | None = None
        parse_status = 'inventory_only'
        root_type = ''
        try:
            if suffix == '.json':
                value = json.loads(path.read_text(encoding='utf-8-sig'))
                root_type = type(value).__name__
                record_count = len(value) if isinstance(value, list) else 1
                for field, _ in flatten_json(value):
                    fields[rel, field] += 1
                parse_status = 'parsed'
            elif suffix == '.jsonl':
                count = 0
                with path.open(encoding='utf-8-sig') as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        value = json.loads(line)
                        count += 1
                        for field, _ in flatten_json(value):
                            fields[rel, field] += 1
                root_type = 'jsonl'
                record_count = count
                parse_status = 'parsed'
            elif suffix == '.csv':
                frame = read_csv(path)
                root_type = 'csv'
                record_count = len(frame)
                for field in frame.columns:
                    fields[rel, str(field)] += int(frame[field].notna().sum())
                parse_status = 'parsed'
        except Exception as exc:
            parse_status = f'parse_error:{type(exc).__name__}'
        category = 'other'
        name = rel.lower()
        if 'active' in name and suffix in {'.json', '.jsonl'}:
            category = 'active_log_or_audit'
        elif 'ground' in name or 'gt' in Path(name).name or 'groudtruth' in name:
            category = 'ground_truth_export'
        elif suffix == '.json':
            category = 'label_studio_or_json'
        rows.append({'source_path': rel, 'suffix': suffix, 'size_bytes': path.stat().st_size, 'sha256': sha256(path), 'category_heuristic': category, 'root_type': root_type, 'record_count': record_count, 'parse_status': parse_status, 'new_server_excluded': 'new_server' in name})
    inventory = pd.DataFrame(rows)
    field_rows = pd.DataFrame([{'source_path': source, 'field_path': field, 'observed_count': count} for (source, field), count in sorted(fields.items())])
    write_csv(out / 'raw_file_inventory_complete.csv', inventory)
    write_csv(out / 'raw_field_inventory_complete.csv', field_rows)
    return (inventory, field_rows)
