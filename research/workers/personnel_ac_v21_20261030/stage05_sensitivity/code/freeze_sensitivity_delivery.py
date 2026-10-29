"""Freeze final deliverable inventory without copying regenerable checkpoints."""
from pathlib import Path
import argparse,ast,csv,gzip,hashlib,json,xml.etree.ElementTree as ET
from PIL import Image

EXCLUDED={'pool_shards','pool_summaries','__pycache__','core_members','three_leg_common_support'}
SELF={'SENSITIVITY_DELIVERY_MANIFEST.json','SENSITIVITY_DELIVERY_CHECKS.json'}


def hashfile(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(2**20):h.update(chunk)
    return h.hexdigest()


def walk_records(obj,records):
    if isinstance(obj,dict):
        if obj.get('full_gzip_eof') is True and obj.get('sha256'):
            records[obj['sha256']]={k:obj[k] for k in ['rows','columns','full_gzip_eof','csv_widths_valid'] if k in obj}
        for v in obj.values():walk_records(v,records)
    elif isinstance(obj,list):
        for v in obj:walk_records(v,records)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);a=ap.parse_args();b=Path(a.base)
    main_receipt=json.loads((b/'results_v1/SENSITIVITY_RECEIPT.json').read_text())
    amplitude=json.loads((b/'results_v1/AMPLITUDE_ENRICHMENT_RECEIPT.json').read_text())
    assert main_receipt['completed_pools']==258 and main_receipt['all_available_metric_pools_processed']
    assert amplitude['same_conditions_and_signed_effects_as_v1'] and amplitude['full_gzip_eof']
    assert json.loads((b/'member_variability_v2/INDEPENDENT_VARIABILITY_REVIEW.json').read_text()).get('status')=='passed'
    selected=sorted(p for p in b.rglob('*') if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(b).parts)
                    and not p.name.endswith('.partial') and p.name not in SELF)
    known={}
    for p in selected:
        if p.suffix=='.json':walk_records(json.loads(p.read_text(encoding='utf-8-sig')),known)
    files=[];new_reads=0;reused=0
    for p in selected:
        rel=str(p.relative_to(b));sha=hashfile(p);r={'path':rel,'bytes':p.stat().st_size,'sha256':sha}
        if p.name.endswith('.csv.gz') or p.suffix=='.csv':
            if p.name.endswith('.csv.gz') and sha in known:
                r.update(known[sha]);r['verification']='content hash matches prior complete gzip/CSV verification';reused+=1
            else:
                opener=gzip.open if p.name.endswith('.gz') else open
                with opener(p,'rt',encoding='utf-8-sig',newline='') as stream:
                    reader=csv.reader(stream);header=next(reader);assert len(header)==len(set(header)),(rel,'duplicate_columns');n=0
                    for row in reader:assert len(row)==len(header),(rel,n);n+=1
                r.update(rows=n,columns=len(header),full_gzip_eof=p.name.endswith('.gz'),csv_widths_valid=True,
                    verification='read complete CSV and compressed EOF now');new_reads+=1
        elif p.suffix=='.json':json.loads(p.read_text(encoding='utf-8-sig'));r['verification']='complete JSON parsed'
        elif p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'));r['verification']='complete Python AST parsed'
        elif p.suffix=='.png':
            with Image.open(p) as img:img.verify()
            r['verification']='complete PNG verified'
        elif p.suffix=='.svg':ET.parse(p);r['verification']='complete SVG parsed'
        else:p.read_text(encoding='utf-8-sig');r['verification']='complete UTF-8 text read'
        files.append(r)
    manifest={'complete':True,'root':str(b.resolve()),'files':files,'file_count':len(files),
        'total_bytes':sum(x['bytes'] for x in files),'excluded_checkpoint_or_intermediate_directories':sorted(EXCLUDED),
        'excluded_temporary_files':[str(p.relative_to(b)) for p in sorted(b.rglob('*.partial'))],
        'authoritative_member_variability':'member_variability_v2/MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz',
        'authoritative_effect_and_amplitude':'results_v1/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz; member variability superseded by the dedicated valid>=2 table',
        'authoritative_three_leg_support':'three_leg_common_support_v2',
        'upstream_dependencies':['stage01_registered','stage01_capacity','stage01b_semi','stage04_metrics/metric_shards','stage05_funnel_bridge','stage06_cases'],
        'main_pools':258,'same_signed_summaries_verified':True,'new_fusions_in_sensitivity_stage':0}
    (b/'SENSITIVITY_DELIVERY_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    checks={'complete':True,'file_count':len(files),'bytes':manifest['total_bytes'],
        'CSV_tables_reusing_complete_read_verification_after_hash_match':reused,'CSV_tables_read_in_full_now':new_reads,
        'main_receipt_sha256':hashfile(b/'results_v1/SENSITIVITY_RECEIPT.json'),
        'amplitude_receipt_sha256':hashfile(b/'results_v1/AMPLITUDE_ENRICHMENT_RECEIPT.json'),
        'manifest_sha256':hashfile(b/'SENSITIVITY_DELIVERY_MANIFEST.json'),
        'note':'Archive can use manifest paths and add these two inventory/receipt files; preserve upstream packages for full geometry and originals.'}
    (b/'SENSITIVITY_DELIVERY_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
