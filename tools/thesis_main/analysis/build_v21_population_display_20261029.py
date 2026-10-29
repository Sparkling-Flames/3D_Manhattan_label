"""Prepare per-method offline fragments from the accepted population summaries."""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/data/releases/v2.1/simulated_population_evidence'
OUT = ROOT / 'research/statistics/research_explorer_v1_r2_20261017/v21-population-data'
DIST_FIELDS = ['dataset', 'method', 'panel_id', 'pool_id', 'image', 'building', 'condition', 'n',
               'scope', 'support', 'class_counts', 'metric', 'time_source', 'teams', 'valid_teams',
               'missing_teams', 'mean', 'p05', 'p25', 'median', 'p75', 'p95', 'minimum', 'maximum',
               'sd', 'iqr', 'range', 'member_variation_estimable']


def safe_part(value):
    text = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_]+', text):
        raise ValueError(f'Unexpected dataset or method identifier: {text!r}')
    return text


def plain(frame):
    return frame.astype(object).where(pd.notna(frame), None).to_dict('records')


def build():
    summary = pd.read_csv(SOURCE/'composition/ALL_METHOD_SUMMARY.csv', low_memory=False)
    source_index = pd.read_csv(SOURCE/'composition/SOURCE_INDEX.csv', low_memory=False)
    coverage_path = SOURCE/'exchange/METHOD_DIMENSION_COVERAGE.csv'
    chain_path = SOURCE/'exchange/CHAIN_SUMMARY.csv'
    cases_path = SOURCE/'exchange/METHOD_ORIGINAL_CASES.csv'
    chain_cases_path = SOURCE/'exchange/CHAIN_CASES.csv'
    coverage = pd.read_csv(coverage_path, low_memory=False) if coverage_path.exists() else None
    chain = pd.read_csv(chain_path, low_memory=False) if chain_path.exists() else None
    cases = pd.read_csv(cases_path, low_memory=False) if cases_path.exists() else None
    chain_cases = pd.read_csv(chain_cases_path, low_memory=False) if chain_cases_path.exists() else None
    for frame, required in [(summary, ['dataset','method','condition','support','metric','time_source']),
                            (source_index, ['dataset','method']),
                            (coverage, ['method','dimension','status','valid_events','valid_images','valid_buildings','missing_events','source_table','fields','note']),
                            (chain, ['method','condition','scope','role_direction','stage','registered_images','net_CB_valid_images','delta_net_CB_valid_images','source_table']),
                            (cases, ['method','condition','scope','case_kind','event_id','original_snapshot','source_event_table']),
                            (chain_cases, ['method','condition','scope','stage','sign','metric','value','source_table','original_snapshot'])]:
        if frame is None:
            continue
        if missing := set(required)-set(frame.columns):
            raise ValueError(f'missing required fields: {sorted(missing)}')
    distribution = SOURCE/'composition/KEY_DISTRIBUTIONS.csv.gz'
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {'summary': plain(summary), 'source_index': plain(source_index),
                'coverage': plain(coverage) if coverage is not None else [],
                'chain': plain(chain) if chain is not None else [], 'cases': plain(cases) if cases is not None else [],
                'chain_cases': plain(chain_cases) if chain_cases is not None else [], 'parts': {},
                'availability': {'distributions': distribution.exists(), 'coverage': coverage is not None, 'chain': chain is not None}}
    dimension_files = {'all': 'ALL_DIMENSION_N_M_RESULTS.csv', 'difficulty': 'FORMAL_DIFFICULTY_RESULTS.csv',
                       'structure': 'STRUCTURAL_CONDITION_RESULTS.csv'}
    dimension_paths = [SOURCE/'exchange'/name for name in dimension_files.values()]
    manifest['dimension_parts'] = {}
    if all(path.exists() for path in dimension_paths):
        by_method = {}
        for kind, name in dimension_files.items():
            frame = pd.read_csv(SOURCE/'exchange'/name, low_memory=False)
            required = {'method', 'condition', 'scope', 'role_direction', 'n', 'm', 'B8L2_CB_mean_image', 'B8L2_CB_valid_images', 'source_table'}
            if missing := required-set(frame.columns):
                raise ValueError(f'missing dimension fields in {name}: {sorted(missing)}')
            for method, group in frame.groupby('method', sort=False):
                by_method.setdefault(safe_part(method), {})[kind] = plain(group)
        for method, groups in by_method.items():
            filename = 'dimension__'+method+'.js'
            (OUT/filename).write_text('window.V21_DIM_PARTS=window.V21_DIM_PARTS||{};window.V21_DIM_PARTS['+json.dumps(method)+']='+json.dumps(groups, ensure_ascii=False, allow_nan=False, separators=(',',':'))+';\n', encoding='utf8')
            manifest['dimension_parts'][method] = 'v21-population-data/'+filename
    paths = {}
    for chunk in pd.read_csv(distribution, chunksize=100000, low_memory=False) if distribution.exists() else []:
        if missing := set(DIST_FIELDS)-set(chunk.columns):
            raise ValueError(f'missing distribution fields: {sorted(missing)}')
        for (dataset, method), group in chunk.groupby(['dataset','method'], sort=False, dropna=False):
            dataset, method = safe_part(dataset), safe_part(method)
            key = dataset+'__'+method
            target = OUT/(key+'.js')
            mode = 'a' if key in paths else 'w'
            with target.open(mode, encoding='utf8') as f:
                if mode == 'w':
                    f.write('window.V21_POP_PARTS=window.V21_POP_PARTS||{};window.V21_POP_PARTS['+json.dumps(key)+']=[];\n')
                f.write('window.V21_POP_PARTS['+json.dumps(key)+']=window.V21_POP_PARTS['+json.dumps(key)+'].concat('+json.dumps(plain(group[DIST_FIELDS]), ensure_ascii=False, allow_nan=False, separators=(',',':'))+');\n')
            paths[key] = paths.get(key, 0)+len(group)
            manifest['parts'][key] = {'path': 'v21-population-data/'+key+'.js', 'rows': paths[key]}
    if distribution.exists() and not paths:
        raise ValueError('No distribution rows found')
    (OUT/'manifest.js').write_text('window.V21_POP_MANIFEST='+json.dumps(manifest, ensure_ascii=False, allow_nan=False, separators=(',',':'))+';\n', encoding='utf8')
    print(f'{len(paths)} method fragments, {sum(paths.values())} distribution rows')


if __name__ == '__main__':
    build()
