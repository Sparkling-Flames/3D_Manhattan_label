#!/usr/bin/env python3
"""Verify frozen project sources; optionally fetch missing files, never overwrite data."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import urllib.parse
import urllib.request

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
HEAD='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
PREFIX='https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/'+HEAD+'/'
UPDATED_DOCS={
    'research/data/releases/v2.1/CURRENT_RESEARCH_BASIS.md',
    'research/data/releases/v2.1/README.md',
    'research/data/releases/v2.1/final_classification_downstream/README.md',
    'research/statistics/research_explorer_v1_r2_20261017/index.html',
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--download-missing',action='store_true');args=ap.parse_args()
    rows=list(csv.DictReader((BASE/'SOURCE_INDEX.csv').open(encoding='utf-8-sig')))
    result={'matching':0,'downloaded':0,'current_documentation':[],'missing':[],'mismatch':[],'errors':[]}
    for row in rows:
        if row.get('source_kind')!='frozen_GitHub_file':continue
        rel=row['path'];p=(ROOT/rel).resolve()
        if not p.is_relative_to(ROOT.resolve()):raise ValueError('Source path outside repository')
        if p.exists():
            if hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']:result['matching']+=1
            elif rel in UPDATED_DOCS:result['current_documentation'].append(rel)
            else:result['mismatch'].append(rel)
            continue
        if not args.download_missing:
            result['missing'].append(rel);continue
        url=PREFIX+urllib.parse.quote(rel,safe='/')
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'HOHONET-current-class-frozen-sources'})
            with urllib.request.urlopen(req,timeout=45) as response:b=response.read()
            if hashlib.sha256(b).hexdigest()!=row['sha256']:raise ValueError('SHA-256 mismatch')
            if len(b)!=int(row['bytes']):raise ValueError('Byte count mismatch')
            p.parent.mkdir(parents=True,exist_ok=True)
            tmp=p.with_name(p.name+'.download-partial');tmp.write_bytes(b);tmp.replace(p)
            result['downloaded']+=1
        except Exception as exc:result['errors'].append({'path':rel,'error':str(exc)})
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['missing'] or result['mismatch'] or result['errors']:raise SystemExit(1)

if __name__=='__main__':main()
