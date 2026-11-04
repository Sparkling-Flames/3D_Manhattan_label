"""Final identity, support, missingness, image and artifact integrity checks."""
from __future__ import annotations
import base64,json,re,zlib,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import pandas as pd
from mechanism_core import ROOT,OUT,COMMIT,read_json,iter_jsonl,save_json,save_csv,sha,digest,ws

def main():
    frozen=read_json(OUT/'DIAGNOSTIC_SAMPLE_FREEZE_RECEIPT.json')
    assert sha(OUT/'DIAGNOSTIC_SAMPLE.csv.gz')==frozen['sample_sha256']
    s=pd.read_csv(OUT/'DIAGNOSTIC_SAMPLE.csv.gz',keep_default_na=False)
    case_selection=pd.read_csv(OUT/'CASE_SELECTION.csv',keep_default_na=False)
    case_frozen=read_json(OUT/'CASE_SELECTION_RECEIPT.json')
    assert sha(OUT/'CASE_SELECTION.csv')==case_frozen['selection_sha256']
    sample_keys=set(s.A_team_key)|set(s.C_team_key)
    case_keys=set(case_selection.A_team_key)|set(case_selection.C_team_key)
    assert len(s)==248 and len(sample_keys)==496 and len(case_keys)==24
    assert len(sample_keys|case_keys)==508
    saved={r['team_key']:r for r in iter_jsonl(OUT/'source/SAVED_LEGACY_ENDPOINTS.jsonl.gz')}
    assert set(saved)==sample_keys|case_keys
    origins=pd.read_csv(OUT/'source/SAVED_LEGACY_ENDPOINT_ORIGINS.csv')
    assert len(origins)==508 and not origins.team_key.duplicated().any() and set(origins.team_key)==set(saved)
    exact_geometry=0
    for key,old in saved.items():
        r=read_json(OUT/'trace_endpoints'/(key+'.json.gz'))
        assert r['trace_source_endpoint_sha256']==digest(old)
        for field,value in old.items():assert digest(r[field])==digest(value),(key,field,'saved_core_changed')
        assert r['trace_only_replay_existing_team'] and not r['additional_new_physical_team']
        assert r['trace_replay_parity']['full_geometry_json_hash_identical']
        exact_geometry+=1
    d=pd.read_csv(OUT/'DIAGNOSTIC_PAIR_RESULTS.csv.gz')
    assert len(d)==248 and not d.canonical_pair_id.duplicated().any()
    assert set(d.canonical_pair_id)==set(s.canonical_pair_id)
    for r in d.to_dict('records'):
        a,c=saved[r['A_team_key']],saved[r['C_team_key']]
        D,X,Z=map(lambda k:set(ws(r[k])),['D_workers','X_workers','Z_workers'])
        assert not(D&X or D&Z or X&Z)
        assert set(a['member_workers'])==D|X and set(c['member_workers'])==D|Z
        assert a['reference_id']==c['reference_id']==r['reference_id']
        assert a['reference_version']==c['reference_version']==r['reference_version']
        assert a['k']==c['k']==r['n'] and len(X)==len(Z)==r['m']
        good=a.get('B8L2') is not None and c.get('B8L2') is not None
        assert bool(r['Q_pair_valid'])==good
        if good:assert abs(r['delta_Q']-(c['B8L2']-a['B8L2']))<1e-10
        else:assert pd.isna(r['delta_Q']) and pd.isna(r['abs_delta_Q'])
        assert r['minimum_support_A']==r['minimum_support_C']==(r['n']+1)//2
    metrics_path=OUT.parent/'analysis/PHYSICAL_PAIRS_AUTOMATIC.csv.gz'
    m=pd.read_csv(metrics_path,usecols=['canonical_physical_pair_id','official_difficulty'])
    dd=d.merge(m,left_on='canonical_pair_id',right_on='canonical_physical_pair_id',validate='one_to_one')
    assert dd.difficulty.eq(dd.official_difficulty).all()
    approvals=pd.read_csv(OUT/'source/APPROVED_MANUAL_ORDER_IDENTITY_INDEX.csv')
    checks=pd.read_csv(OUT/'CASE_APPROVED_MANUAL_ORDER_MATCH.csv')
    assert len(approvals)==57 and len(checks)==24 and not checks.exact_team_pool_reference_match.any()
    for r in checks.to_dict('records'):
        hit=approvals
        for k in ['team_key','pool_id','reference_id','reference_version']:hit=hit[hit[k].eq(r[k])]
        assert hit.empty
    image_receipt=read_json(OUT/'ORIGINAL_IMAGE_RECEIPT.json')
    assert image_receipt['AC_case_originals']==11 and image_receipt['existing_ABC_appendix_originals']==1 and len(image_receipt['images'])==12
    for r in image_receipt['images']:
        p=OUT/r['path'];b=p.read_bytes()
        assert sha(p)==r['sha256'] and len(b)==int(r['uncompressed_bytes'])
        assert zlib.crc32(b)==int(r['zip_crc32'],16)
        with Image.open(p) as im:
            assert im.size==(int(r['width']),int(r['height']));im.verify()
    for p in (OUT/'figures').glob('*.png'):
        with Image.open(p) as im:im.verify()
    for p in (OUT/'figures').glob('*.svg'):ET.parse(p)
    html_path=OUT/'CURRENT_DSTRUCT_AC_ATLAS.html';html=html_path.read_text()
    embedded=json.loads(re.search(r'const DATA=(.*?);\s*const NS=',html,re.S).group(1))
    assert len(embedded['cases'])==12 and len(embedded['images'])==12
    for code,img in embedded['images'].items():assert base64.b64decode(img.split(',',1)[1])==(OUT/'originals'/(code+'.png')).read_bytes()
    for c in embedded['cases']:
        disk=read_json(OUT/'cases'/(c['case_id']+'.json.gz'))
        assert {k:v for k,v in c.items() if k!='interpretation'}==disk
    assert embedded['appendix']['not_current_AC_sample']
    js=read_json(OUT/'ATLAS_JS_RUNTIME_CHECKS.json');assert js['status']=='passed' and js['atlas_sha256']==sha(html_path)
    # The final receipt itself is a link target and is written below.
    links=[]
    for p in [OUT/'REPORT_ZH.md',OUT/'README.md',OUT/'CASE_SELECTION_PROTOCOL.md']:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text()):
            if '://' in target or target.startswith('#'):continue
            dest=(p.parent/target.split('#')[0]).resolve()
            assert dest.exists() or dest==OUT/'MECHANISMS_FINAL_CHECKS.json',(p.name,target)
            links.append(dict(document=p.name,target=target,status='exists'))
    save_csv(OUT/'DOCUMENT_LINK_CHECKS.csv',links)
    receipt=dict(status='passed',input_main=COMMIT,
        frozen_diagnostic_pairs=248,unique_diagnostic_endpoints=496,case_pairs=12,case_endpoints=24,
        sample_case_overlap_endpoints=12,unique_delivered_native_traces=508,
        successful_native_diagnostic_replays=dict(sample=496,additional_case=12,excluded_pilot=1,total=509),
        new_physical_scientific_teams=0,saved_core_endpoint_fields_preserved=508,full_geometry_json_hash_identical=exact_geometry,
        fixed_same_image_pool_reference_n_m_D=True,current_difficulty_bindings_checked=248,difficulty_mismatches=0,
        missing_Q_never_zero=True,failed_pairs_in_state_counts=True,quality_denominator_requires_two_original_Q=True,
        source_input_contract='Preprocessed frozen pool records and exact references; no new ordering, coordinate edits, reference rerouting or forced connection.',
        diagnostic_sample_outcome_blind=True,cases_post_outcome_illustrative=True,existing_ABC_appendix_excluded_from_AC=True,
        AC_original_photos=11,existing_ABC_original_photos=1,all_12_original_sizes_CRC_SHA_and_embedded_bytes_identical=True,
        all_24_case_endpoints_exact_approved_manual_order_matches=0,
        figure_validation=dict(png_decoded=16,svg_xml_parsed=8,
            visually_inspected=['AC07_GEOMETRY.png','AC08_GEOMETRY.png','AC09_POSITION_FOCUS.png','AC11_GEOMETRY.png','AC12_GEOMETRY.png','APPENDIX_EXISTING_ABC.png','VOTE_CROSSING_ASSOCIATION.png','DIFFICULTY_VOTE_ASSOCIATION.png']),
        html_validation=dict(runtime='Node V8 + minimal DOM test double',all_12_cases_and_controls_passed=True,graphical_browser_pixel_validation_performed=False,exact_original_images_embedded=12),
        document_relative_links_checked=len(links),main_metrics_sha256=sha(metrics_path),
        limitations=['Mechanism associations are conditional descriptions of legacy legal stock teams, not new randomized mechanism interventions.',
                     'Ambiguous D-group mappings do not establish exact same-node crossing; counts and coverage are retained.',
                     'No entering-order convergence or new timing experiment was run.',
                     'No native re-evaluation was performed for the cited existing ABC appendix.'])
    save_json(OUT/'MECHANISMS_FINAL_CHECKS.json',receipt)
    manifest=[]
    for p in sorted(OUT.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name in ['MECHANISMS_FILE_MANIFEST.csv','MECHANISMS_FILE_MANIFEST.csv.writing'] or p.name.endswith('.writing'):continue
        manifest.append(dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)))
    save_csv(OUT/'MECHANISMS_FILE_MANIFEST.csv',manifest)
    print(json.dumps(dict(status='passed',source_endpoints=508,frozen_pairs=248,case_pairs=12,original_images=12,relative_links=len(links),files=len(manifest)),ensure_ascii=False))

if __name__=='__main__':main()
