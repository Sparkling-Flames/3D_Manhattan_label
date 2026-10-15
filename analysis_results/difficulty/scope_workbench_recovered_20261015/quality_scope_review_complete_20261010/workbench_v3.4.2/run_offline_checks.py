#!/usr/bin/env python3
"""Run the unmodified v3.4.2 offline regression suites, without a browser."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parent
SCRIPTS=['qa-geometry-v2.cjs','qa-state.cjs','qa-confirmed-receipt.cjs','qa-gt-snap.cjs','qa-space-regions.cjs','qa-missing-room-queue.cjs','qa-edge-drag.cjs','qa-outside-gt.cjs']
checks=[]
for script in SCRIPTS:
    result=subprocess.run(['node',script],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(result.stdout,end='')
    checks.append({'script':script,'exit_code':result.returncode})
    if result.returncode: raise SystemExit(result.returncode)
print(json.dumps({'passed':True,'suites':checks,'browser_visual_or_real_interaction_tested':False},ensure_ascii=False,indent=2))
