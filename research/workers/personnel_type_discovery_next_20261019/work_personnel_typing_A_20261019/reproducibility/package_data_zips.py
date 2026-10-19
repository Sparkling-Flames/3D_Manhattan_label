#!/usr/bin/env python3
"""Package frozen Part A data without modifying scientific inputs or outputs.

All ZIP entries preserve the work_personnel_typing_A_20261019/ prefix. The
scientific byte hashes are checked before and after ZIP creation. The manifest
is external to these two ZIPs, so its archive hashes do not create a cycle.
"""
from __future__ import annotations
import argparse,base64,collections,datetime,gzip,hashlib,json,os,re,shutil,stat,time,zipfile
from pathlib import Path,PurePosixPath

HERE=Path(__file__).resolve().parent
LEAF='work_personnel_typing_A_20261019'
FIXED_ZIP_TIME=(2026,10,19,0,0,0)
LIMIT=450*2**20

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.writing')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,path)

def manifest_rows(path):
    d=load(path)
    return d['files'] if isinstance(d,dict) else d

def safe_entry(name):
    p=PurePosixPath(name)
    if '\\' in name or '\x00' in name or p.is_absolute() or '..' in p.parts or ':' in name or not name.startswith(LEAF+'/'):
        raise ValueError('unsafe ZIP entry '+repr(name))
    return name

def inventory(root):
    records=[]
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('symlink not allowed in data snapshot '+str(p))
        if not p.is_file():continue
        if not p.resolve().is_relative_to(root.resolve()):raise ValueError('path escaped data root '+str(p))
        records.append(p)
    return records

def frozen_expectations(work):
    directory=work/'reproducibility/pro_archive_manifests'
    result={};source=manifest_rows(directory/'SOURCE_FILES.json');core=manifest_rows(directory/'PORTABLE_MANIFEST.json')
    assert len(source)==824 and len(core)==519
    for role,prefix,rows in [('frozen_source','repo_main_20261019/',source),('retained_core','',core)]:
        for row in rows:
            if not row.get('materialize',True):continue
            relative='recovered/'+prefix+row['path'];p=work/relative
            assert p.is_file(),relative
            assert sha(p)==row['sha256'],('frozen SHA mismatch',relative)
            if 'bytes' in row:assert p.stat().st_size==row['bytes'],('frozen size mismatch',relative)
            result[relative]={'role':role,'sha256':row['sha256'],'bytes':p.stat().st_size}
    assert len(result)==1343
    receipt=load(work/'recovered/BOOTSTRAP_RECEIPT.json')
    assert receipt['source_files_verified']==824 and receipt['retained_files_verified']==519
    return result,{'frozen_source_files_verified':824,'retained_core_files_verified':519,
        'all_frozen_hashes_match':True,'source_files_manifest_sha256':sha(directory/'SOURCE_FILES.json'),
        'portable_manifest_sha256':sha(directory/'PORTABLE_MANIFEST.json'),
        'bootstrap_receipt':receipt,'no_full_collection_or_original_archive_reproduction_claim':True}

def record(work,p,reason=None,rebuild=None,role=None):
    relative=p.relative_to(work).as_posix();name=safe_entry(LEAF+'/'+relative)
    row={'path':name,'bytes':p.stat().st_size,'sha256':sha(p)}
    if role:row['role']=role
    if reason:row.update(reason=reason,rebuild=rebuild)
    return row

def candidates(work,expected):
    included={2:[],3:[]};omitted=[]
    for p in inventory(work/'recovered'):
        relative=p.relative_to(work).as_posix()
        if relative in expected:
            included[2].append(record(work,p,role=expected[relative]['role']))
        elif relative=='recovered/BOOTSTRAP_RECEIPT.json':
            included[2].append(record(work,p,role='bootstrap_receipt'))
        elif '__pycache__' in p.parts or p.suffix=='.pyc':
            omitted.append(record(work,p,'generated Python bytecode; not part of frozen manifest',
                {'required_for_science':False,'action':'Python recreates bytecode when importing the retained .py source; interpreter-specific byte identity is not required.'}))
        else:
            # No unnamed extra file can silently be called a scientific cache.
            assert relative=='recovered/work_v2_20261019/clusters/fusion_analysis/.composition_statistics.csv.v9tLBR',relative
            omitted.append(record(work,p,'uncommitted temporary write file outside both frozen manifests; canonical composition_statistics.csv retained',
                {'required_for_science':False,'retained_canonical_path':LEAF+'/recovered/work_v2_20261019/clusters/fusion_analysis/composition_statistics.csv','action':'Do not reconstruct an incomplete temporary write; read the SHA-verified canonical file.'}))
    assert len(included[2])==1344
    for p in inventory(work/'events'):
        relative=p.relative_to(work).as_posix()
        if '__pycache__' in p.parts or p.suffix=='.pyc':
            omitted.append(record(work,p,'generated Python bytecode',{'required_for_science':False,'action':'Recreated by Python imports from retained event code.'}))
        elif p.suffix=='.lock':
            omitted.append(record(work,p,'runtime writer lock, not scientific data',{'required_for_science':False,'action':'events/run_events.py creates its own lock on execution.'}))
        elif 'native_preview' in p.relative_to(work/'events').parts:
            twin=work/'recovered/work_v2_20261019/fusion'/p.name
            same=twin.is_file() and sha(twin)==sha(p)
            omitted.append(record(work,p,'pre-bootstrap download copy superseded by the complete SHA-verified recovered layout',
                {'required_for_science':False,'identical_retained_copy':LEAF+'/'+twin.relative_to(work).as_posix() if same else None,
                 'action':'Use the retained recovered fusion files. The superseded download receipt is operational provenance, not a scientific input.'}))
        elif p.name.endswith(('.writing','.tmp','.partial')) or p.name.startswith('.'):
            omitted.append(record(work,p,'temporary runtime file',{'required_for_science':False,'action':'Not needed or reproduced for science; completed outputs and receipts retained.'}))
        else:included[3].append(record(work,p,role='exact_event_data_or_completed_run_evidence'))
    for key in included:included[key].sort(key=lambda x:x['path'])
    omitted.sort(key=lambda x:x['path'])
    return included,omitted

def required_event_check(rows):
    names={r['path'] for r in rows};prefix=LEAF+'/events/'
    for name in ['run_events.py','register_events.py','DESIGN.json','REGISTRATION_RECEIPT.json','REQUESTS.json.gz','event_design.csv.gz','common_events.csv.gz',
                 'nested_chains.csv.gz','nested_coverage.csv.gz','pool_members.csv.gz','FULL_RUN_RECEIPT.json','EVENT_VERIFICATION_RECEIPT.json','native_runs/team_results.csv']:
        assert prefix+name in names,'required event entry missing '+name
    counts={name:sum(r['path'].startswith(prefix+'native_runs/pools/') and r['path'].endswith('/'+name) for r in rows)
            for name in ['states.json.gz','requests.json.gz','request_results.json.gz','scores.json.gz','context.json','LAST_RUN.json']}
    assert set(counts.values())=={175},counts
    return {'pools_with_all_required_native_state_parts':175,'parts':counts,'global_team_results_retained':True,
            'all_58882_exact_requests_and_286666_events_retained':True}

def write_zip(work,path,rows,log_label):
    started=time.monotonic();temp=path.with_name(path.name+'.writing')
    if path.exists():raise FileExistsError('Do not overwrite existing completed data ZIP: '+str(path))
    if temp.exists():raise FileExistsError('Existing incomplete archive must be handled explicitly: '+str(temp))
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True,strict_timestamps=True) as z:
        for i,row in enumerate(rows,1):
            name=safe_entry(row['path']);source=work.parent/name
            assert source.stat().st_size==row['bytes'],('source size changed during packaging',name)
            zi=zipfile.ZipInfo(name,FIXED_ZIP_TIME);zi.compress_type=zipfile.ZIP_DEFLATED;zi.create_system=3
            zi.external_attr=(stat.S_IFREG|0o644)<<16;zi._compresslevel=9
            h=hashlib.sha256()
            with source.open('rb') as src,z.open(zi,'w',force_zip64=True) as dst:
                for b in iter(lambda:src.read(2**20),b''):h.update(b);dst.write(b)
            assert h.hexdigest()==row['sha256'],('source content changed during packaging',name)
            if i%200==0 or i==len(rows):print(json.dumps({'zip':log_label,'written_entries':i,'total':len(rows),'elapsed_seconds':round(time.monotonic()-started,1)},ensure_ascii=False),flush=True)
    return temp,{'archive_bytes':temp.stat().st_size,'archive_sha256':sha(temp),'build_seconds':time.monotonic()-started}

def verify_zip(path,rows):
    expected={r['path']:r for r in rows};bad=None;count=0;total=0;compressed=0
    with zipfile.ZipFile(path,'r') as z:
        infos=z.infolist();assert len(infos)==len(expected)
        assert len({i.filename for i in infos})==len(infos),'duplicate ZIP entry'
        assert {i.filename for i in infos}==set(expected),'archive entry list mismatch'
        for info in infos:
            safe_entry(info.filename);assert not info.is_dir();assert not info.flag_bits&1,'encrypted entry'
            assert stat.S_IFMT(info.external_attr>>16)!=stat.S_IFLNK,'symlink entry'
            row=expected[info.filename];assert info.file_size==row['bytes']
            h=hashlib.sha256()
            with z.open(info) as f:
                for b in iter(lambda:f.read(2**20),b''):h.update(b)
            assert h.hexdigest()==row['sha256'],('ZIP payload SHA mismatch',info.filename)
            count+=1;total+=info.file_size;compressed+=info.compress_size
        # Explicit ZIP CRC pass in addition to per-entry byte SHA checks.
        bad=z.testzip();assert bad is None,('ZIP CRC failure',bad)
    return {'entry_count':count,'total_uncompressed_bytes':total,'total_compressed_payload_bytes':compressed,
            'entry_paths_safe':True,'duplicate_entries':0,'all_payload_sha256_match_sources':True,
            'zip_testzip_crc_pass':True,'zip_testzip_bad_entry':bad}

def images_check(work):
    p=work/'presentation';acquired=load(p/'CASE_IMAGE_RECEIPT.json');build=load(p/'VIEWER_BUILD_RECEIPT.json');qa=load(p/'qa/VIEWER_QA.json');visual=load(p/'VISUAL_REVIEW.json')
    assert acquired['requested_images']==7 and len(acquired['images'])==7
    for row in acquired['images']:
        assert row['local_path'] and sha(p/row['local_path'])==row['sha256'],row['image_id']
    html=(p/build['html']).read_text();packed=re.search(r'<script id="packed" type="application/octet-stream">([^<]+)</script>',html)
    assert packed is not None
    data=json.loads(gzip.decompress(base64.b64decode(packed.group(1).strip())))
    missing=sorted({pool['meta']['image'] for pool in data['pools'].values() if not data['images'][pool['meta']['image_id']]['original_available']})
    assert missing==['2t7WUuJeko7-02','2t7WUuJeko7-03']
    ims=list(data['images'].values());original=sum(bool(x['data']) and x['original_available'] for x in ims)
    previews=sum(bool(x['data']) and not x['original_available'] for x in ims);unembedded=sum(not x['data'] and x['original_available'] for x in ims)
    assert (original,previews,unembedded)==(7,2,168)
    assert all('仅仓库预览' in x['status'] for x in ims if not x['original_available'])
    assert all('未嵌入' in x['status'] for x in ims if not x['data'])
    assert build['html_sha256']==qa['html_sha256']==sha(p/build['html'])
    assert visual['original_images_acquired']==7 and visual['case_context_images_actually_opened']==5
    assert not visual['full_resolution_original_visual_review'] and not visual['browser_layout_screenshot_verified']
    browser_log=(work/'events/chromium_install.log').read_text(errors='replace').lower()
    assert 'failed to install browsers' in browser_log and ('site unavailable' in browser_log or 'end of central directory' in browser_log)
    return {'status':'PASS','originals_acquired_and_per_file_sha_verified':7,'embedded_case_original_previews':7,'repository_only_previews':2,
            'missing_original_image_codes':missing,'original_available_but_not_embedded':168,
            'assistant_viewed_case_context_images':5,'assistant_viewed_final_canvases':visual['final_canvas_files_actually_opened'],
            'retrieval_is_not_visual_review':True,'full_resolution_original_visual_review':False,'real_browser_layout_screenshot_verified':False,
            'viewer_sha256':build['html_sha256'],'image_retrieval_receipt_sha256':sha(p/'CASE_IMAGE_RECEIPT.json'),
            'visual_review_receipt_sha256':sha(p/'VISUAL_REVIEW.json'),'note':'This is a consistency check. Case original bytes and viewer are delivered by the separate report/code/viewer package, not duplicated into data ZIPs 02/03.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=HERE.parent)
    ap.add_argument('--output-dir',type=Path);args=ap.parse_args();work=args.source.resolve()
    assert work.name==LEAF
    out=(args.output_dir or work.parent/'deliverables_personnel_A_20261019').resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();expected,frozen=frozen_expectations(work);included,omitted=candidates(work,expected)
    images=images_check(work);requirements=required_event_check(included[3]);archives=[];attempts=[]
    for number,name in [(2,'PartA_02_Frozen_Inputs.zip'),(3,'PartA_03_Exact_Events.zip')]:
        rows=included[number];path=out/name
        temp,info=write_zip(work,path,rows,name)
        if temp.stat().st_size>=LIMIT:
            assert number==3,'frozen inputs cannot be trimmed'
            # Preserve all primary endpoint states and exact requests. The first
            # large candidate is only our own temporary ZIP, not a source file.
            attempts.append(dict(archive=name,attempt='all_completed_event_outputs',**info,accepted=False,reason='archive exceeds strict 450 MiB ceiling'))
            oversized=Path('/tmp')/('PartA_full_events_packaging_candidate_'+str(os.getpid())+'.zip')
            if oversized.exists():raise FileExistsError(oversized)
            shutil.move(temp,oversized)
            kept=[]
            for row in rows:
                relative=row['path'][len(LEAF)+1:]
                derive=relative.startswith('events/comparisons/') or (relative.startswith('events/native_runs/pools/') and relative.endswith('/team_results.csv'))
                if derive:
                    omitted.append(dict(row,reason='derived per-pool comparison or redundant per-pool CSV omitted to keep archive below 450 MiB; all exact native states/requests/results retained',
                        rebuild={'required_for_science':False,'scientific_data_preserved_in':['events/common_events.csv.gz','events/native_runs/pools/*/states.json.gz','events/native_runs/pools/*/requests.json.gz','events/native_runs/pools/*/request_results.json.gz','events/native_runs/team_results.csv'],
                                 'comparison_command':['python','events/run_events.py','--stage','compare','--jobs','6'],
                                 'per_pool_csv_command':['python','events/run_events.py','--stage','full','--jobs','6'],
                                 'working_directory':LEAF,'new_workspace_only':True,
                                 'instructions':'Unpack all packages and use reproducibility/reproduce.py to prepare a NEW workspace. The retained native request/state cache avoids new fusion for the derived regeneration; receipt timestamps may differ. New native execution is explicitly logged if a cache is missing.'}))
                else:kept.append(row)
            rows=kept;included[number]=rows;requirements=required_event_check(rows)
            temp,info=write_zip(work,path,rows,name+' primary plus receipts')
            assert temp.stat().st_size<LIMIT,'primary state archive still exceeds size ceiling'
            # Remove only the superseded ZIP made by this invocation, never a
            # scientific source or retained output. Its hash/size remains logged.
            oversized.unlink()
        assert temp.stat().st_size<LIMIT
        verification=verify_zip(temp,rows);os.replace(temp,path)
        archives.append({'file':name,'relative_prefix':LEAF+'/',**info,**verification,
            'below_450_MiB':True,'included_files':rows})
        print(json.dumps({'completed':name,'bytes':info['archive_bytes'],'MiB':round(info['archive_bytes']/2**20,3),'sha256':info['archive_sha256'],'entries':verification['entry_count'],'zip_crc':'PASS'},ensure_ascii=False),flush=True)
    manifest={'schema':'PartA_read_only_data_packaging_v1','status':'PASS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'archive_size_limit_bytes_strictly_less_than':LIMIT,'fixed_zip_entry_timestamp':list(FIXED_ZIP_TIME),'zip_compression':'DEFLATE level 9',
        'source_working_directory_name':LEAF,'no_scientific_file_modified':True,'no_source_or_scientific_output_deleted':True,'upload_performed':False,
        'packaging_script_sha256':sha(Path(__file__)),'frozen_input_verification':frozen,'native_event_required_parts':requirements,
        'case_original_image_consistency':images,'archives':archives,'oversize_attempts':attempts,
        'omitted_files':sorted(omitted,key=lambda x:x['path']),
        'omitted_file_count':len(omitted),'omitted_logical_bytes':sum(r['bytes'] for r in omitted),
        'all_events_successful_outputs_included_except_superseded_download_and_runtime_files':not attempts,
        'manifest_placement':'External to data ZIPs to avoid hash cycles; identical copy in work_personnel_typing_A_20261019/reproducibility/PACKAGING_DATA_MANIFEST.json for report/code package.',
        'elapsed_seconds':time.monotonic()-started}
    save(out/'PACKAGING_DATA_MANIFEST.json',manifest)
    save(work/'reproducibility/PACKAGING_DATA_MANIFEST.json',manifest)
    assert sha(out/'PACKAGING_DATA_MANIFEST.json')==sha(work/'reproducibility/PACKAGING_DATA_MANIFEST.json')
    print(json.dumps({'status':'PASS','manifest_sha256':sha(out/'PACKAGING_DATA_MANIFEST.json'),'archives':[{'file':a['file'],'bytes':a['archive_bytes'],'sha256':a['archive_sha256'],'entries':a['entry_count']} for a in archives],
        'omitted_files':len(omitted),'elapsed_seconds':round(manifest['elapsed_seconds'],2)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
