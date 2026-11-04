#!/usr/bin/env python3
"""Final checks of the delivered joins, supports, identities and local references."""
from pathlib import Path
from html.parser import HTMLParser
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote,urlsplit
import numpy as np
import pandas as pd
from PIL import Image

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
HEAD='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
DOCS={
 'research/data/releases/v2.1/CURRENT_RESEARCH_BASIS.md',
 'research/data/releases/v2.1/README.md',
 'research/data/releases/v2.1/final_classification_downstream/README.md',
 'research/statistics/research_explorer_v1_r2_20261017/index.html',
}

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.refs=[];self.scripts=[];self.in_script=False;self.buf=[];self.script_type=''
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for k in ['href','src']:
            if k in a:self.refs.append(a[k])
        if tag=='script':
            self.in_script=True;self.buf=[];self.script_type=a.get('type','')
    def handle_endtag(self,tag):
        if tag=='script' and self.in_script:
            if self.script_type!='application/json':self.scripts.append(''.join(self.buf))
            self.in_script=False
    def handle_data(self,data):
        if self.in_script:self.buf.append(data)

def main():
    sources=pd.read_csv(BASE/'SOURCE_INDEX.csv').fillna('')
    stable=[];docs=[]
    for r in sources.itertuples(index=False):
        p=ROOT/r.path;assert p.is_file(),r.path
        got=hashlib.sha256(p.read_bytes()).hexdigest()
        if got==r.sha256:stable.append(r.path)
        else:
            assert r.path in DOCS,('Unexpected changed source',r.path)
            docs.append(dict(path=r.path,source_sha256=r.sha256,current_sha256=got,change='authorized current documentation/entry update'))
    joined=json.loads((BASE/'dstruct/VALIDATION.json').read_text())
    assert joined['ordinary_records']==7703
    assert [(x['records'],x['matched']) for x in joined['quality_component_joins']]==[(7472,7472),(231,231)]
    assert max(x['max_abs_Q_difference'] for x in joined['quality_component_joins'])<1e-10
    labs=pd.read_csv(BASE/'basis/WORKER_LABELS_ALL_LOBO.csv.gz')
    assert len(labs)==7130 and not labs.duplicated(['method','heldout_building','worker_id']).any()
    cp=pd.read_csv(BASE/'UNIFIED_COMMON_CLASS_PROFILES.csv')
    assert len(cp)==10162 and not cp.duplicated(['method','condition','scope','source_stratum','metric','class_id','difficulty']).any()
    expected={'TARGET_DSTRUCT_K3':201,'RFUSE_GEOM_K2':192,'OPPJOINT_K3':194,'OPPJOINT_K4':164}
    for method,n in expected.items():
        z=cp[(cp.method==method)&(cp.condition=='manual')&(cp.scope=='primary')&(cp.source_stratum=='all')&(cp.metric=='B8L2')&(cp.difficulty=='ALL')]
        assert len(z)==int(method[-1]) and z.n_images.eq(n).all()
    qt=pd.read_csv(BASE/'rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv')
    assert len(qt)==283 and not qt.duplicated(['method','condition','scope','source_stratum','class_A','class_B','difficulty']).any()
    panel=pd.read_csv(BASE/'team_effects/COMMON_COMPLETE_PANEL_METRICS.csv')
    pq=panel[(panel.metric=='B8L2') & panel.summary_axis.eq('all') & panel.summary_value.eq('all')]
    assert len(pq)==4 and pq.panels.eq(174).all() and pq.images.eq(32).all()
    assert pq.valid_team_links.eq(159655).all()
    err=float((panel.total_variance-panel.within_variance-panel.between_variance).abs().max())
    relative_err=float(((panel.total_variance-panel.within_variance-panel.between_variance).abs()/np.maximum(1,panel.total_variance.abs())).max())
    # Source tables serialize 12 significant digits; seconds-squared variances are large.
    assert np.allclose(panel.total_variance,panel.within_variance+panel.between_variance,rtol=1e-10,atol=1e-8)
    matrix=pd.read_csv(BASE/'basis/CLASS_ORIGINAL_TEAM_MATRIX.csv');assert len(matrix)==12
    ev=pd.read_csv(BASE/'team_effects/UNIFIED_EVIDENCE_MATRIX.csv');assert len(ev)==2084
    ledger=pd.read_csv(BASE/'CONCLUSION_LEDGER.csv');assert len(ledger)==13

    links=[];scripts=[];bad=[]
    for p in sorted(BASE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        if p.suffix=='.md':refs=re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig'))
        elif p.suffix=='.html':
            page=Page();page.feed(p.read_text(encoding='utf-8-sig'));refs=page.refs
            scripts.extend((p,i,s) for i,s in enumerate(page.scripts) if s.strip())
        else:continue
        for link in refs:
            if not link or link.startswith(('#','http:','https:','data:','mailto:','javascript:')):continue
            pathpart=unquote(urlsplit(link).path)
            if not pathpart:continue
            target=(p.parent/pathpart).resolve()
            links.append((str(p.relative_to(BASE)),link))
            if not target.exists():bad.append(dict(file=str(p.relative_to(BASE)),link=link))
    assert not bad,bad
    for p in BASE.rglob('*.py'):
        ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    node=os.environ.get('CODEX_PRIMARY_RUNTIME_NODE') or shutil.which('node')
    js_checked=[]
    if node:
        with tempfile.TemporaryDirectory(prefix='hohonet_script_check_') as td:
            for p,i,s in scripts:
                tmp=Path(td)/f'{len(js_checked)}.js';tmp.write_text(s,encoding='utf-8')
                proc=subprocess.run([node,'--check',str(tmp)],text=True,capture_output=True,timeout=30)
                assert proc.returncode==0,(str(p),proc.stderr[:1500])
                js_checked.append(str(p.relative_to(BASE)))
    else:raise RuntimeError('Node is needed for the advertised JavaScript syntax check')
    pngs=[]
    for p in BASE.rglob('*.png'):
        with Image.open(p) as im:
            im.verify()
        pngs.append(str(p.relative_to(BASE)))
    sample=json.loads((BASE/'examples/DISPLAY_VALIDATION.json').read_text())
    result=dict(status='passed',frozen_source_commit=HEAD,
        source_files_or_assets_unchanged=len(stable),current_documentation_updates=docs,
        original_quality_component_joins=joined['quality_component_joins'],
        current_label_rows=7130,unique_label_key=['method','heldout_building','worker_id'],
        unified_common_class_profile_rows=len(cp),all_class_primary_Q_images=expected,
        common_record_same_source_QT_conditions=len(qt),current_class_matrix_rows=len(matrix),
        team_evidence_conditions=len(ev),common_team_panels=174,Q_team_links=159655,
        maximum_variance_decomposition_residual=err,
        maximum_variance_decomposition_scaled_residual=relative_err,
        variance_check_note='CSV uses 12 significant digits; relative tolerance applies across Q, geometry and seconds-squared units. Pre-serialization identity check remains in team_effects/CHECKS.json.',
        root_conclusion_rows=len(ledger),local_reference_checks=len(links),broken_references=bad,
        python_syntax_files=len(list(BASE.rglob('*.py'))),javascript_syntax_documents=js_checked,
        PNG_files_verified=len(pngs),visual_review='21 derived scientific/example PNGs reviewed, including four added JOINT K4 plates; original PNG identities separately verified',
        current_display=dict(methods=4,images=4,typical_slots=sample['typical_slots'],feature_supplement_slots=sample['feature_supplement_slots'],
            unique_original_answers=sample['objects'],JOINT_K4_added_slots=28,JOINT_K4_plates=4,
            JOINT_K4_independent_review='examples/JOINT_K4_INDEPENDENT_REVIEW.json'),
        browser_interaction_tested=False,browser_note='No installed browser; checked local links, embedded-data construction, JavaScript syntax and static graphics.',
        independent_review='Team analyst checked main/DSTRUCT support, versions and Q/T; example analyst checked case descriptions and scientific figures. Corrections were rounding, signed background-step wording, and complete class list in the hard example.',
        new_classification_fit=0,new_scoring=0,new_fusion=0,new_teams=0,
        source_receipts=['dstruct/VALIDATION.json','basis/LABEL_VERSION_CHECKS.json','basis/CLASS_MATRIX_CHECKS.json','rfuse_joint/VERIFICATION.json','team_effects/CHECKS.json','examples/DISPLAY_VALIDATION.json'])
    (BASE/'DELIVERY_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['current_documentation_updates','source_receipts','independent_review']},ensure_ascii=False))

if __name__=='__main__':main()
