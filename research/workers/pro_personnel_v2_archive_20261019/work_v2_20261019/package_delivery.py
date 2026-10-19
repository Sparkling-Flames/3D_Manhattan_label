#!/usr/bin/env python3
"""Package frozen scientific payloads. No fitting, fusion, or class mutation."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,json,os,tempfile,time,zipfile,zlib

WORK=Path(__file__).resolve().parent;ROOT=WORK.parent;DEL=WORK/'delivery'
PARTS={
 'methods_results_a':'personnel_v2_methods_results_a.zip',
 'methods_results_b':'personnel_v2_methods_results_b.zip',
 'geometry_a':'personnel_v2_geometry_a.zip',
 'geometry_b':'personnel_v2_geometry_b.zip',
}
def sha(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def js(p):return json.loads(p.read_text())
def eligible(p):return p.is_file()and not any(x in {'__pycache__','node_modules','mpl_cache','.git'}for x in p.parts)
def main():
    started=time.monotonic();payload={};known={};roles={}
    def add(p,part='methods_results_a',role='source_or_reproducible_result',expected=None):
        p=p.resolve();assert eligible(p),p
        rel=str(p.relative_to(ROOT));assert rel not in payload or payload[rel]==part,rel
        payload[rel]=part;roles[rel]=role
        if expected:known[rel]=expected
    # Frozen module manifests are authoritative for nonredundant payloads.
    fm=js(WORK/'fusion/FUSION_DELIVERY_MANIFEST.json');pools={}
    for row in fm['files']:
        if not row['recommended_include']:continue
        p=ROOT/row['path']
        if '/pools/'in row['path']:
            pid=p.parent.name;pools.setdefault(pid,[]).append(row)
        else:add(p,role=row['role'],expected=row['sha256'])
    # Balance complete pools between two geometry ZIPs; never split one pool.
    totals={'geometry_a':0,'geometry_b':0}
    for pid,rows in sorted(pools.items(),key=lambda x:(-sum(r['bytes']for r in x[1]),x[0])):
        part=min(totals,key=lambda k:(totals[k],k))
        for row in rows:add(ROOT/row['path'],part,row['role'],row['sha256'])
        totals[part]+=sum(r['bytes']for r in rows)
    add(WORK/'fusion/FUSION_DELIVERY_MANIFEST.json',role='frozen_module_manifest')
    cm=js(WORK/'clusters/PACKAGING_MANIFEST.json')
    for row in cm['files']:add(WORK/'clusters'/row['path'],role='reverse_results_code_or_evidence',expected=row['sha256'])
    for name in ['PACKAGING_MANIFEST.json','FINAL_VALIDATION.json']:add(WORK/'clusters'/name,role='frozen_module_manifest_or_validation')
    for p in sorted((ROOT/'repo_main_20261019').rglob('*')):
        if eligible(p):add(p,role='pinned_github_source')
    for folder in ['audit','profiles','input']:
        for p in sorted((WORK/folder).rglob('*')):
            if eligible(p):add(p,role=folder+'_result_source_or_evidence')
    for p in sorted((WORK/'presentation').rglob('*')):
        if eligible(p)and'pilot'not in p.name.lower():add(p,role='offline_presentation_code_result_or_visual_evidence')
    for p in sorted((WORK/'logs').glob('*')):
        if eligible(p)and not any(x in p.name.lower()for x in ['delivery_save','library','upload','prepare_failure','final_payload_verification','packaging']):add(p,role='actual_run_log')
    for p in sorted(DEL.glob('*')):
        if eligible(p)and p.name not in {'DELIVERY_MANIFEST.json','PACKAGING_RECEIPT_V2.json'}:add(p,role='human_readable_report_and_evidence')
    add(WORK/'original_images/ORIGINAL_IMAGE_AUDIT.json',role='original_release_download_and_missing_ledger')
    for p in sorted(WORK.glob('*.py')):add(p,role='root_reproduction_or_packaging_code')
    add(WORK/'requirements.txt',role='numeric_environment')
    rows=[];bad=[]
    for rel,part in sorted(payload.items()):
        p=ROOT/rel;actual=sha(p)
        if rel in known and actual!=known[rel]:bad.append({'path':rel,'expected':known[rel],'actual':actual})
        rows.append({'path':rel,'bytes':p.stat().st_size,'sha256':actual,'archive_part':part,'archive':PARTS[part],'role':roles[rel]})
    assert not bad,bad
    # The save service accepts at most 512 MiB per file. Balance actual deflated
    # byte sizes, keeping every source/result file whole, to create four normal
    # independently extractable ZIPs. This is packaging only, not new analysis.
    def estimate(row):
        p=ROOT/row['path']
        if p.suffix.lower()in {'.gz','.png','.jpg','.jpeg','.zip'}:return row['bytes']
        co=zlib.compressobj(4,zlib.DEFLATED,-15);total=0
        with p.open('rb')as f:
            for b in iter(lambda:f.read(1<<20),b''):total+=len(co.compress(b))
        return total+len(co.flush())
    method_rows=[r for r in rows if r['archive_part']=='methods_results_a']
    estimates={r['path']:estimate(r)for r in method_rows};method_totals={'methods_results_a':0,'methods_results_b':0}
    for row in sorted(method_rows,key=lambda r:(-estimates[r['path']],r['path'])):
        part=min(method_totals,key=lambda k:(method_totals[k],k));row['archive_part']=part;row['archive']=PARTS[part];method_totals[part]+=estimates[row['path']]
    manifest={'schema':'v2_research_delivery_payload_r1','frozen_github_commit':'82c6164b0d4630de5316199c92aa405930973168',
      'files':rows,'payload_file_count':len(rows),'payload_bytes':sum(r['bytes']for r in rows),'archive_names':PARTS,
      'required_extraction':'Extract all four ZIPs into the same new root; each ZIP preserves repo_main_20261019/ or work_v2_20261019/ paths.',
      'archive_split_reason':'512 MiB per-file delivery limit; method/result files balanced losslessly, whole geometry pools balanced separately. No scientific data omitted.',
      'excluded_redundancy':['per-pool scores (all fields preserved in request_results)','per-pool CSV and comparisons (rebuild from states)','INITIAL global copies (final replacements restore required alias)','long swap predictions (lossless full wide table included)','pilot viewer and checkpoints'],
      'excluded_external_bytes':['full Release archives and originals; verified download script/ledger and embedded offline previews included'],
      'not_in_self_manifest':['DELIVERY_MANIFEST.json itself','post-archive PACKAGING_RECEIPT_V2.json and final file-verification log'],
      'all_frozen_module_manifest_hashes_match':True,'main_original_collection_rebuilt':False}
    mp=DEL/'DELIVERY_MANIFEST.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({'event':'manifest_ready','files':len(rows),'bytes':manifest['payload_bytes'],'parts':{k:{'files':sum(r['archive_part']==k for r in rows),'bytes':sum(r['bytes']for r in rows if r['archive_part']==k)}for k in PARTS}},ensure_ascii=False),flush=True)
    def build(part):
        target=ROOT/PARTS[part];temp=target.with_name(target.name+'.partial.'+str(os.getpid()))
        items=[r for r in rows if r['archive_part']==part]
        if part=='methods_results_a':items.append({'path':str(mp.relative_to(ROOT)),'bytes':mp.stat().st_size,'sha256':sha(mp)})
        with zipfile.ZipFile(temp,'w',allowZip64=True)as z:
            for row in items:
                p=ROOT/row['path'];info=zipfile.ZipInfo(row['path'],date_time=(2026,10,18,17,38,54))
                info.compress_type=zipfile.ZIP_STORED if p.suffix.lower()in {'.gz','.png','.jpg','.jpeg','.zip'}else zipfile.ZIP_DEFLATED
                info.external_attr=(0o100644<<16);info._compresslevel=4
                with p.open('rb')as src,z.open(info,'w',force_zip64=p.stat().st_size>2**31)as dst:
                    for b in iter(lambda:src.read(1<<20),b''):dst.write(b)
        with zipfile.ZipFile(temp)as z:
            bad_member=z.testzip();assert bad_member is None,bad_member
            assert len(z.infolist())==len(items)
            assert set(z.namelist())=={r['path']for r in items}
        temp.replace(target)
        assert target.stat().st_size<=536870912,target
        result={'part':part,'file':target.name,'bytes':target.stat().st_size,'files':len(items),'sha256':sha(target),'zip_full_crc_pass':True,'member_set_pass':True}
        print(json.dumps({'event':'archive_validated',**result},ensure_ascii=False),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4)as ex:archives=list(ex.map(build,PARTS))
    receipt={'schema':'v2_archive_validation_r1','archives':archives,'payload_manifest_sha256':sha(mp),
      'all_frozen_module_manifest_hashes_match':True,'file_manifest_entries':len(rows),'all_archive_crc_and_member_sets_pass':True,
      'elapsed_seconds':time.monotonic()-started,'not_a_new_model_or_fusion_run':True,
      'exact_source_geometry_and_all_real_members_orders_failures_included':True}
    (DEL/'PACKAGING_RECEIPT_V2.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps({'event':'packaging_complete','elapsed_seconds':receipt['elapsed_seconds'],'total_archive_bytes':sum(x['bytes']for x in archives)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
