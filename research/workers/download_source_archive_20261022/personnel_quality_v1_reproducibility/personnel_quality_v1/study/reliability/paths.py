"""Portable paths: set PANORAMA_REPO and PANORAMA_STUDY if relocated."""
import os,sys
from pathlib import Path
STUDY=Path(os.environ.get('PANORAMA_STUDY',str(Path(__file__).resolve().parents[1]))).resolve()
ROOT=STUDY.parent
REPO=Path(os.environ.get('PANORAMA_REPO',str(ROOT/'repo'))).resolve()
OUT=Path(os.environ.get('PANORAMA_RELIABILITY_OUT',str(STUDY/'reliability'))).resolve()
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(REPO))
