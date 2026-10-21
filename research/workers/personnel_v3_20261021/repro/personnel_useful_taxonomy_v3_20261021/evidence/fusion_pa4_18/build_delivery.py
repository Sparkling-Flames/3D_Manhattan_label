#!/usr/bin/env python3
"""Validate and package the two Manual mechanism cases, excluding large caches."""
import hashlib, json, zipfile
import pandas as pd
import export_cases as e

HERE = e.HERE

def main():
    receipt = e.gs.read(HERE/'CASE_EXPORT_RECEIPT.json')
    assert receipt['full_state_replays'] == 6 and receipt['score_calls'] == 0 and receipt['new_teams'] == 0
    event_table = pd.read_csv(HERE/'EXACT_EVENTS.csv',keep_default_na=False)
    assert event_table.shape == (2,796)
    checks, designs, teams = [], [], set()
    for path in sorted((HERE/'cases').glob('*.json.gz')):
        c = e.gs.read(path);a,b,d = c['teams'];ev = c['event']
        background = set(ev['common_background'].split('|'))
        assert set(a['member_workers'])&set(b['member_workers']) == background
        assert set(a['member_workers'])&set(d['member_workers']) == background
        assert a['counts'] == b['counts'] and a['counts'] != d['counts']
        for t in c['teams']:
            assert t['k'] == c['n'] and t['minimum_support'] == c['n']//2
            assert e.gs.digest(t['geometry']) == e.gs.digest(t['full_state']['candidate'])
            assert sum(t['counts'].values()) == c['n'];teams.add(t['team_key'])
            designs.append(dict(case_id=c['case_id'],event_id=ev['event_id'],arm=t['label'],n=t['k'],
                method_id=c['method_id'],archived_tier=c['tier'],coarse_and_fine_identical_partition=True,
                exact_counts=ev[t['label']+'_counts'],team_key=t['team_key'],
                members='|'.join(t['member_workers']),common_background=ev['common_background'],
                common_background_n=len(background),outgoing_block_X=ev['outgoing_block_X'],
                same_count_block_Y=ev['same_count_block_Y'],changed_count_block_Z=ev['changed_count_block_Z'],
                m_AB=ev['m_AB'],m_AC=ev['m_AC'],m_BC=ev['m_BC'],native_geometry_sha256=e.gs.digest(t['geometry'])))
        assert ev['m_AB'] == ev['m_AC'] == c['n']-len(background)
        assert ev['m_BC'] == len(set(b['member_workers'])-set(d['member_workers']))
        checks.append(dict(case_id=c['case_id'],n=c['n'],matched_m=ev['m_AB'],background_people=len(background),
            BC_net_m=ev['m_BC'],all_native_geometry_exact=True,
            coarse_fine_same_partition=True,complete_native_events=True))
    assert len(teams) == 6
    e.savecsv('EXPERIMENT_DESIGN.csv',pd.DataFrame(designs))
    e.gs.save(HERE/'FINAL_CASE_CHECKS.json',dict(cases=checks,unique_teams=len(teams),full_state_replays=6,
        no_quality_score_calls=True,new_teams=0,event_fields=796,rendered_images=len(list((HERE/'figures').rglob('*.png')))))
    sourcepaths = [e.OLD/'composition/global_study.py',e.OLD/'evidence/render_evidence.py',
        e.OLD/'evidence/analyze_vote_transitions.py',e.ROOT/'tools/thesis_main/analysis/ring_correspondence_20261007.py',
        e.ROOT/'tools/thesis_main/analysis/consensus_delivery_20261008.py',
        e.ROOT/'tools/thesis_main/analysis/wall_consensus_quality_20261015.py',
        e.ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py',
        e.ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py',
        e.ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv',e.V3/'taxonomy/LABELS_LOBO.csv.gz']
    e.savecsv('REUSED_INPUT_CODE_HASHES.csv',pd.DataFrame([dict(path=str(p.relative_to(e.ROOT)),bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sourcepaths]))
    photo = e.V3/'evidence/originals/pa4otMbVnkk_64ba4f267872432abdcb00af002649d5.png'
    excluded = {'DELIVERY_MANIFEST.csv','DELIVERY_RECEIPT.json','EXPORT_PROGRESS.json'}
    files = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and
        p.suffix not in ['.zip','.tmp','.log','.partial'] and p.name not in excluded]+[photo]
    e.savecsv('DELIVERY_MANIFEST.csv',pd.DataFrame([dict(path=str(p.relative_to(e.V3)),bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)]))
    files.append(HERE/'DELIVERY_MANIFEST.csv')
    archive = HERE/'HOHONET_v3_pa4_18_Manual结构补票与同构成反例_20261021.zip'
    tmp = archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(files):z.write(p,p.relative_to(e.V3))
    tmp.replace(archive)
    with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    result = dict(archive=archive.name,bytes=archive.stat().st_size,files=len(files),
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),case_ids=[c['case_id'] for c in checks],
        full_state_replays=6,score_calls=0,new_teams=0,report='evidence/fusion_pa4_18/REPORT_ZH.md')
    e.gs.save(HERE/'DELIVERY_RECEIPT.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
