#!/usr/bin/env python3
"""Convenient package-root entry; copied as run_reproduction.py on assembly."""
from pathlib import Path
import argparse
import datetime as dt
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description='Reproduce the fixed top/structure quality study in a fresh external directory.')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--with-figures', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    runner = package / 'top_structure_20261012/delivery_tools/prepare_and_reproduce.py'
    if not runner.is_file():
        parser.error('Run the copy named run_reproduction.py at the delivered package root.')
    tag = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = args.output_root or package.parent / ('reproduction_top_structure_' + tag)
    command = [sys.executable, str(runner), 'reproduce', '--package-root', str(package),
               '--output-root', str(output.resolve()), '--workers', str(args.workers)]
    if args.with_figures:
        command.append('--with-figures')
    if args.prepare_only:
        command.append('--prepare-only')
    return subprocess.call(command, cwd=package)


if __name__ == '__main__':
    raise SystemExit(main())
