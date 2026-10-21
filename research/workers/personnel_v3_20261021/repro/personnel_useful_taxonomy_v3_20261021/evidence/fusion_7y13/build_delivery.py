#!/usr/bin/env python3
"""Package the complete two-case mechanism evidence and one original image."""
import csv,hashlib,json,zipfile
from pathlib import Path
import pandas as pd
import export_cases as e

HERE=e.HERE

def main():
    receipt=e.gs.read(HERE/'CASE_EXPORT_RECEIPT.json')
    assert receipt['full_state_replays']==6 and receipt['score_calls']==0 and receipt['new_teams']==0
    idx=pd.read_csv(e.V3/'composition/matched/PANEL_RESULT_SHARDS.csv')
    row=idx[idx.panel_id.eq('7y3sRwLe3Va-13__semi__5b6c87b5f3__v1__n12')]
    assert len(row)==1;e.savecsv('SOURCE_SHARD_ROW.csv',row)
    checks=[]
    for p in sorted((HERE/'cases').glob('*.json.gz')):
        c=e.gs.read(p);aa,bb,cc=c['teams']
        assert set(aa['member_workers'])&set(bb['member_workers'])==set(c['event']['common_background'].split('|'))
        assert set(aa['member_workers'])&set(cc['member_workers'])==set(c['event']['common_background'].split('|'))
        for t in c['teams']:
            assert t['k']==12 and t['nodes']==4 and t['minimum_support']==6
            assert e.gs.digest(t['geometry'])==e.gs.digest(t['full_state']['candidate'])
            assert sum(t['counts'].values())==12
        checks.append(dict(case_id=c['case_id'],n=12,matched_m=4,background_people=8,
            BC_net_m=len(set(bb['member_workers'])-set(cc['member_workers'])),all_native_geometry_exact=True))
    e.gs.save(HERE/'FINAL_CASE_CHECKS.json',dict(cases=checks,score_calls=0,rendered_images=9))
    sourcepaths=[e.OLD/'continuation_20261021/evidence/export_n20_cases.py',e.OLD/'evidence/render_evidence.py',
        e.OLD/'evidence/analyze_vote_transitions.py',e.ROOT/'tools/thesis_main/analysis/ring_correspondence_20261007.py',
        e.ROOT/'tools/thesis_main/analysis/wall_consensus_quality_20261015.py',
        e.ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py',
        e.V3/'taxonomy/LABELS_LOBO.csv.gz']
    e.savecsv('REUSED_INPUT_CODE_HASHES.csv',pd.DataFrame([dict(path=str(p.relative_to(e.ROOT)),bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sourcepaths]))
    photo=e.V3/'evidence/originals_7y13/7y3sRwLe3Va_92fb09a83f8949619b9dc5bda2855456.png'
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.zip','.tmp','.log','.partial']
        and p.name not in ['DELIVERY_MANIFEST.csv','DELIVERY_RECEIPT.json']]+[photo]
    manifest=[dict(path=str(p.relative_to(e.V3)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)]
    e.savecsv('DELIVERY_MANIFEST.csv',pd.DataFrame(manifest));files.append(HERE/'DELIVERY_MANIFEST.csv')
    archive=HERE/'HOHONET_v3_7y13_正反替换机制案例_20261021.zip'
    tmp=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(files):z.write(p,p.relative_to(e.V3))
    tmp.replace(archive)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    result=dict(archive=archive.name,bytes=archive.stat().st_size,files=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        case_ids=[c['case_id'] for c in checks],full_state_replays=6,score_calls=0,new_teams=0,
        report='evidence/fusion_7y13/REPORT_ZH.md')
    e.gs.save(HERE/'DELIVERY_RECEIPT.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
