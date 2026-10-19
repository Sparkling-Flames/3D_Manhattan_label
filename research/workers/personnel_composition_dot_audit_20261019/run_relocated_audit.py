"""Run an unchanged audit script with only its original workspace prefix relocated."""
import argparse,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--script',type=Path,required=True);a,rest=ap.parse_known_args()
p=a.script.resolve();source=p.read_text().replace('/workspace/shared/composition_audit_20261019',str(a.root.resolve()))
sys.argv=[str(p)]+rest;sys.path.insert(0,str(p.parent));exec(compile(source,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
