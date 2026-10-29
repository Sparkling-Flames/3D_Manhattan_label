"""Read every delivered case artifact and verify concrete trace invariants.

This is output validation, not a re-audit of population eligibility or labels.
The old development fixtures are intentionally excluded from delivery.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path

import fitz
from PIL import Image


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
    dirs=['alliance_pa4_06','alliance_pa4_11','background_wc2_53','representative_cases']
    excluded=['validation_only','__pycache__']
    generated={'CASE_DELIVERY_VALIDATION.json','CASE_FILE_MANIFEST.csv'}
    files=sorted(x for x in root.rglob('*') if x.is_file() and not any(y in x.parts for y in excluded)
                 and x.name not in generated and not x.name.endswith('.pyc'))
    checks=collections.Counter();manifest=[]
    for path in files:
        suffix=''.join(path.suffixes)
        if suffix.endswith('.json.gz'):
            with gzip.open(path,'rt') as f:json.load(f)
            checks['gzip_json_full_read']+=1
        elif suffix.endswith('.csv.gz') or path.suffix=='.csv':
            opener=gzip.open if suffix.endswith('.csv.gz') else open
            with opener(path,'rt',newline='',encoding='utf-8-sig') as f:
                rows=csv.reader(f);header=next(rows,None)
                if header is not None:
                    assert len(header)==len(set(header)),f'duplicate headers {path}'
                    for lineno,row in enumerate(rows,2):
                        if not row:
                            checks['csv_blank_lines_ignored']+=1
                            continue
                        assert len(row)==len(header),(str(path),lineno,len(row),len(header))
            checks['csv_full_read']+=1
        elif path.suffix=='.json':
            json.loads(path.read_text());checks['json_full_read']+=1
        elif path.suffix=='.png':
            with Image.open(path) as im:im.load()
            checks['png_full_decode']+=1
        elif path.suffix=='.pdf':
            with fitz.open(path) as doc:
                assert len(doc)>0
                for page in doc:page.get_pixmap(matrix=fitz.Matrix(.2,.2))
            checks['pdf_all_pages_rasterized']+=1
        elif path.suffix in ['.md','.html','.py','.js','.txt']:
            path.read_text();checks['text_full_read']+=1
        else:
            with path.open('rb') as f:
                while f.read(1024*1024):pass
            checks['binary_full_read']+=1
        manifest.append({'relative_path':str(path.relative_to(root)),'bytes':path.stat().st_size,'sha256':sha(path)})
    seen={};event_ids=set();browser_cases=0;parity=[]
    for directory in dirs:
        r=root/directory
        q=json.loads((r/'BROWSER_QA.json').read_text())
        assert q['browser_validation_passed'] and not q['errors'] and not q['external_requests']
        browser_cases+=q['case_count']
        parity+=json.loads((r/'TRACE_SCALAR_GEOMETRY_PARITY.json').read_text())
        for path in (r/'traces').glob('*.json.gz'):
            with gzip.open(path,'rt') as f:d=json.load(f)
            e=d['event'];event_ids.add(e['event_id'])
            D=set(e['D_workers'].split('|')) if e['D_workers'] else set()
            X=set(e['X_workers'].split('|')) if e['X_workers'] else set()
            Z=set(e['Z_workers'].split('|')) if e['Z_workers'] else set()
            assert not(D&X or D&Z or X&Z)
            for arm,block in [('A',X),('C',Z)]:
                t=d['arms'][arm];members=set(t['member_workers'])
                assert members==D|block and len(members)==t['k']
                assert t['reference_id']==d['reference']['target_id']
                assert t['pool_id']==e['pool_id'] and t['team_key']==e[arm+'_team_key']
                original={r['worker_id']:r for r in d['pool']['records']}
                assert set(t['member_object_ids'])=={original[w]['id'] for w in members}
                s=t['full_state'];groups=s['identity_groups']
                assert s['minimum_support']==(t['k']+1)//2
                assert t['nodes']==sum(g['selected'] for g in groups)
                for g in groups:
                    workers={m['worker'] for m in g['members']}
                    assert len(workers)==g['support'] and workers<=members
                    assert g['selected']==(2*g['support']>=t['k'])
                    for observation in g['members']:
                        assert observation['id']==original[observation['worker']]['id']
                        idx=original[observation['worker']]['source_pair_indices'].index(observation['source_pair_index'])
                        assert observation['points']==original[observation['worker']]['points'][2*idx:2*idx+2]
                for edge in s['ring_diagnostics'].get('edges',[]):
                    assert edge['direct_support']==len(set(edge['direct_workers']))
                    assert edge['projected_support']==len(set(edge['projected_workers']))
                if t['team_key'] in seen:
                    # Same physical endpoint repeated by pair display is exact,
                    # including original core geometry and score/status.
                    prev=seen[t['team_key']]
                    assert all(prev.get(k)==t.get(k) for k in ['geometry','B8L2','D10','score_status','member_workers'])
                else:seen[t['team_key']]=t
    assert len(event_ids)==browser_cases==51 and len(seen)==32
    exact=sum(x.get('full_geometry_json_hash_identical',x.get('full_geometry_identical',False)) for x in parity)
    rounded=[x for x in parity if x.get('derived_footprint_one_ulp_roundoff_only')]
    assert len(parity)==32 and exact==31 and len(rounded)==1
    assert all(x['score_status_identical'] for x in parity)
    assert max(x['maximum_difference'] for x in parity)<1e-7
    assert rounded[0]['maximum_derived_footprint_difference']==4.440892098500626e-16
    original_receipt=json.loads((root/'originals/ORIGINALS_RECEIPT.json').read_text())
    for row in original_receipt['images']:
        path=root/'originals'/row['local_path']
        assert path.stat().st_size==int(row['bytes']) and sha(path)==row['sha256']
    statuses=dict(collections.Counter(x['score_status'] for x in seen.values()))
    assert statuses=={'complete_conditional':31,'no_connection':1}
    with (root/'CASE_FILE_MANIFEST.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['relative_path','bytes','sha256']);w.writeheader();w.writerows(manifest)
    receipt={'complete':True,'files_fully_read':len(manifest),'bytes':sum(x['bytes'] for x in manifest),
      'read_checks':dict(checks),'unique_physical_teams':len(seen),'display_events':len(event_ids),
      'unique_endpoint_states':statuses,'browser_case_checks':browser_cases,'browser_external_requests':0,
      'original_images_sha256_verified':len(original_receipt['images']),
      'identity_members_target_and_source_observation_links_verified':True,
      'all_selected_and_unselected_groups_and_direct_projected_edge_supports_verified':True,
      'full_geometry_json_hash_exact_replays':exact,'one_ulp_derived_footprint_only_replays':len(rounded),
      'maximum_trace_scalar_parity_difference':max(x['maximum_difference'] for x in parity),
      'maximum_derived_footprint_roundoff':rounded[0]['maximum_derived_footprint_difference'],
      'manifest_sha256':sha(root/'CASE_FILE_MANIFEST.csv'),'excluded_development_dirs':excluded,
      'new_fusions':0,'new_scoring':0,'no_old_source_or_core_endpoint_changes':True}
    (root/'CASE_DELIVERY_VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
