"""Reproduce this bounded six-case study into a separate directory."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from analyze import main
from local_diagnostics import run
from figures import render,render_focus
from report_tables import write_tables
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'reproduced');a=p.parse_args()
    rd=a.out/'results';fd=a.out/'figures'
    main(ROOT/'inputs',rd)
    run(ROOT/'inputs',rd,ROOT/'evidence/local_spec.json')
    write_tables(ROOT/'inputs',rd)
    render(ROOT/'inputs',rd,fd)
    render_focus(ROOT/'inputs',rd,fd,ROOT/'evidence/local_spec.json')
    print('Saved:',a.out.resolve())
