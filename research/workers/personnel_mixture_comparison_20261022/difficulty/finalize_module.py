#!/usr/bin/env python3
"""Write an index of actual saved outputs and check complete file payloads."""
from __future__ import annotations
import gzip
import hashlib
import io
import json
import re
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
import pandas as pd
from PIL import Image
from analyze_difficulty import HERE,save,write_json

def main():
    rows=[];checked_links=0
    skip={'FILE_INDEX.csv','FINAL_RECEIPT.json'}
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name in skip:continue
        assert not p.name.endswith('.partial'),p
        b=p.read_bytes();rel=str(p.relative_to(HERE));nrow=ncol=None
        if rel.endswith('.csv') or rel.endswith('.csv.gz'):
            payload=gzip.decompress(b) if rel.endswith('.gz') else b
            df=pd.read_csv(io.BytesIO(payload),low_memory=False);nrow,ncol=df.shape
        elif rel.endswith('.json'):json.loads(b)
        elif rel.endswith('.png'):Image.open(io.BytesIO(b)).load()
        elif rel.endswith('.svg'):ET.fromstring(b)
        elif rel.endswith('.md'):
            for target in re.findall(r'\]\(([^\s)]+)\)',b.decode('utf-8')):
                if '://' in target or target.startswith('#'):continue
                assert (p.parent/target.split('#')[0]).exists(),(rel,target)
                checked_links+=1
        stage='final_documentation' if p.suffix=='.md' else 'reproducible_code' if p.suffix=='.py' else \
              'new_case_7y13' if 'case_7y13_background' in rel else 'new_case_qdown_pa4' if 'case_qdown_pa4' in rel else \
              'stage03_difficulty_of_fusion' if rel.startswith('exchange_') else \
              'historical_case_links' if rel.startswith('CASE_') or rel.startswith('profile_case_') else 'stage01_02_raw_answer'
        rows.append(dict(relative_path=rel,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),
                         rows=nrow,columns=ncol,stage=stage,parsed_complete=True))
    ix=pd.DataFrame(rows);save(ix,'FILE_INDEX.csv')
    counts={}
    for name in ['role_image_contrasts.csv.gz','same_class_nearQ_speed_pairs.csv.gz',
                 'exchange_difficulty_core.csv','exchange_difficulty_full.csv.gz']:
        counts[name]=int(ix[ix.relative_path.eq(name)].rows.iloc[0])
    write_json('FINAL_RECEIPT.json',dict(status='complete_and_frozen',
        saved_utc=datetime.now(timezone.utc).isoformat(),data_version='v2',
        input_commit='ef148c82df18582228b2d23837faa2659e79eba7',
        module='personnel_mixture_comparison_20261022/difficulty',
        files_indexed=len(ix),indexed_bytes=int(ix.bytes.sum()),checked_local_markdown_links=checked_links,
        complete_gzip_csv_read=True,png_full_decode=True,svg_xml_parse=True,
        counts=counts,new_fusion=0,new_scoring=0,new_classification=0,
        purpose='new raw-answer opportunity/difficulty and within-class speed analysis; new difficulty aggregation of cached strict exchange results; two exact mechanism exports',
        key_figures=['raw_answer_difficulty.png','case_7y13_background/ERP_BEV_three_paths.png',
                     'case_7y13_background/ALL_924_quality_change.png','case_qdown_pa4/RAW_BLOCKS_AND_ABC_BEV.png'],
        source_versions_preserved=True,
        limits=['v2 internally explored data; no new external blind set',
                '7y13 changes background and n together',
                'pa4 original RGB not newly fetched; exact raw/fusion BEV exported; existing original-image overlay linked separately'],
        index_sha256=hashlib.sha256((HERE/'FILE_INDEX.csv').read_bytes()).hexdigest()))
    print(json.dumps(dict(files=len(ix),bytes=int(ix.bytes.sum()),counts=counts,links=checked_links),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
