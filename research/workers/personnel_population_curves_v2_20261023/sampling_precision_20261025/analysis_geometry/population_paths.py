"""Resolve the pinned old population inputs without assuming scratch layout.

This helper only locates existing inputs. It does not download, copy, alter or
select data, and it never falls back silently after an explicit invalid path.
"""
from __future__ import annotations
import os
from pathlib import Path


def add_population_root_argument(parser):
    parser.add_argument('--population-root',type=Path,
        help='Old personnel_population_curves_v2_20261023 directory; otherwise HOHONET_POPULATION_ROOT, the final repository parent, or legacy scratch layout.')


def resolve_population_root(study,explicit=None):
    study=Path(study).expanduser().resolve()
    sentinel=Path('design/ACTUAL_POOLS.csv')
    def checked(value,source):
        p=Path(value).expanduser().resolve()
        if not (p/sentinel).is_file():
            raise FileNotFoundError(f'{source} does not contain {sentinel}: {p}')
        return p
    if explicit is not None:return checked(explicit,'--population-root')
    env=os.environ.get('HOHONET_POPULATION_ROOT')
    if env:return checked(env,'HOHONET_POPULATION_ROOT')
    candidates=[study.parent,study/'repo/research/workers/personnel_population_curves_v2_20261023']
    for p in candidates:
        if (p/sentinel).is_file():return p.resolve()
    raise FileNotFoundError('Cannot locate the old population inputs. Pass --population-root or set HOHONET_POPULATION_ROOT. Checked: '+', '.join(str(p) for p in candidates))
