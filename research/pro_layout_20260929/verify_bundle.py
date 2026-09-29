"""Verify this directory as a standalone numerical handoff; no network needed."""
import json
from collections import Counter
from pathlib import Path
from tools.thesis_main.analysis.research_round_20260929 import validate_panel, coverage

root=Path(__file__).resolve().parent
panel=json.loads((root/'inputs/panel.json').read_text(encoding='utf-8'))
validate_panel(panel)
counts=Counter(r['version'] for i in panel['images'] for r in i['references'])
summary,_,_=coverage(panel)
assert summary['annotations']==3152 and summary['images']==259 and summary['reference_only_images']==2
assert counts=={'original':259,'manual_revision':30}
for i in panel['images']:
    for r in i['annotations']:
        assert r['worker'].startswith('P') and r['id'].startswith('R')
        assert 'source' not in r and 'review_evidence' not in r
print(json.dumps(dict(verified=True,**summary,references=dict(counts)),ensure_ascii=False,indent=2))
