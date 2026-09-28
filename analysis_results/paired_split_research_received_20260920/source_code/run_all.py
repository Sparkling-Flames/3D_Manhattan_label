"""Offline reproduction. Numeric inputs do not require GitHub or network.
Run: python code/run_all.py --root .
Optional --render requires the packaged visual/*.png|jpg images and Pillow.
All numeric outputs are regenerated in separate main and association-control folders.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import study, diagnostics, tests

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args();root=args.root.resolve()
    study.run(root,'min_horizontal',root/'sensitivity_min_horizontal_results')
    study.run(root,'legacy_guarded')
    diagnostics.run(root)
    tests.run(root)
    if args.render:
        import visuals
        visuals.run(root)

if __name__=='__main__':main()
