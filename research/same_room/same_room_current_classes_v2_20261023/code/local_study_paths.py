"""Paths for the compact delivery or a restored HOHONET working tree."""
from pathlib import Path
import os
CODE_ROOT=Path(__file__).resolve().parent
PACKAGE_ROOT=CODE_ROOT.parent
WORK=Path(os.environ.get('HOHONET_WORK_ROOT',PACKAGE_ROOT)).resolve()
def choose(*paths):
    return next((p for p in paths if p.exists()),paths[0])
NATIVE=choose(WORK/'native',WORK/'results/native')
TAXONOMY=choose(WORK/'taxonomy',WORK/'source_index')
MECHANISMS=choose(WORK/'mechanisms',WORK/'cases/mechanisms')
BUDGET=choose(WORK/'budget_effects',WORK/'results/budget')
BUDGET_CASES=choose(WORK/'budget_effects/cases',WORK/'cases/budget')
BUDGET_FINAL=choose(WORK/'budget_effects/final',WORK/'results/budget')
FIGURES=choose(WORK/'budget_effects/figures',WORK/'figures')
ENGINE=choose(WORK/'engine',CODE_ROOT/'engine')
REPO=Path(os.environ.get('HOHONET_REPO',WORK/'hohonet')).resolve()
