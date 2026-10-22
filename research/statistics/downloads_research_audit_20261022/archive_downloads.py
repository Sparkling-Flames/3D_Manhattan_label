"""Downloads研究材料选择性归档：不执行外部分析、不重跑评分、不计算SHA。"""
from pathlib import Path, PurePosixPath
import argparse, ast, collections, csv, gzip, io, json, os, re, shutil, subprocess, tokenize, zipfile

PREFIX = 'research/workers/personnel_effective_exchange_conditions_20261022/'
PATTERN = re.compile(r'hohonet|personnel|same.?room|quality|difficulty|fusion|consensus|layout|research|evidence|CORE_RESEARCH|SMALL_ANALYSIS|n20|native|cross|研究|质量|审查|候选|109核验', re.I)
CORE = {'CORE_RESEARCH_CODE_AND_SMALL_EVIDENCE.zip', 'SMALL_ANALYSIS_INPUTS.zip'}
TEXT = {'.py','.md','.txt','.json','.csv','.gz'}
REPORT = re.compile(r'readme|report|findings|methods|provenance|reproduc|field|contract',re.I)

def safe_member(name):
    p = PurePosixPath(name.replace('\\','/'))
    if p.is_absolute() or '..' in p.parts or ':' in name:
        raise ValueError('unsafe ZIP member: '+name)
    return p

def privacy_flags(data, suffix):
    if suffix == '.gz':
        stream = gzip.open(io.BytesIO(data),'rt',encoding='utf-8-sig')
    else:
        text=data.decode('utf-8-sig')
        if suffix=='.py':
            text='\n'.join(t.string for t in tokenize.generate_tokens(io.StringIO(text).readline)
                           if t.type in (tokenize.STRING,tokenize.COMMENT))
        stream = io.StringIO(text)
    flags=set()
    with stream:
        for line in stream:
            if re.search(r'C:[/\\]Users[/\\]|wxid_',line):
                flags.add('private_path_or_wxid')
            if re.search(r'"(?:source_account_id|real_name|phone|email|username)"\s*:',line):
                flags.add('direct_identity_field')
            if '@' in line and re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',line):
                flags.add('email')
    return sorted(flags)

def historical_candidate(name,size):
    p=PurePosixPath(name)
    if any(part.startswith(('repo_main_','__pycache__')) for part in p.parts):
        return False
    if p.suffix=='.py':
        return True
    if p.suffix=='.md' and REPORT.search(p.name):
        return True
    if p.name.lower().startswith(('requirements','license')) and p.suffix=='.txt':
        return True
    return p.suffix=='.json' and size<131072 and re.search(r'model|parameter|config|schema|contract',p.name,re.I) is not None

def save_csv(path,rows):
    if not rows:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows)

def main(repo, downloads):
    missing=[n for n in CORE if not (downloads/n).is_file()]
    if missing:
        raise FileNotFoundError('Source ZIP unavailable; existing archive ledgers preserved: '+', '.join(sorted(missing)))
    # Windows原生长路径前缀仅用于本地IO，不改交付相对路径。
    if os.name=='nt' and not str(repo).startswith('\\\\?\\'):
        repo=Path('\\\\?\\'+str(repo))
    audit=repo/'research/statistics/downloads_research_audit_20261022'
    current=repo/PREFIX/'source_archive_20261022'
    quality=repo/'research/quality/download_source_archive_20261022'
    workers=repo/'research/workers/download_source_archive_20261022'
    audit.mkdir(parents=True,exist_ok=True)
    tracked=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0') if p]
    idx=collections.defaultdict(list)
    zipidx=collections.defaultdict(list)
    for rel in tracked:
        p=repo/rel
        if p.is_file():
            idx[(p.name.casefold(),p.stat().st_size)].append(rel)
        if rel.endswith('.zip') and p.is_file():
            try:
                with zipfile.ZipFile(p) as z:
                    for m in z.infolist():
                        if not m.is_dir():
                            zipidx[(PurePosixPath(m.filename).name.casefold(),m.file_size,m.CRC)].append((rel,m.filename))
            except zipfile.BadZipFile:
                pass
    packages=sorted({p for p in downloads.glob('*.zip') if PATTERN.search(p.name) or p.name in {'mp3d.zip','preprocess.zip'}})
    roots=[p for p in downloads.iterdir() if p.is_dir() and PATTERN.search(p.name)]
    for root in roots:
        packages.extend(root.rglob('*.zip'))
    packages=sorted(set(packages),key=lambda p:(p.name not in CORE,p.name.casefold()))
    inventory=[];members=[];local=[];extracted=[];newfiles=[];privacy=[];events=[]
    for package in packages:
        package_id=package.relative_to(downloads).as_posix()
        local.append(dict(source_id=package_id,source_path=str(package),kind='zip'))
        counts=collections.Counter()
        with zipfile.ZipFile(package) as z:
            infos=[m for m in z.infolist() if not m.is_dir()]
            for m in infos:
                name=safe_member(m.filename)
                public_name = '[source_export_path_omitted]' if any(x in name.parts for x in ('export_label','active_logs','raw_accounts')) else m.filename
                row=dict(source_id=package_id,member_path=public_name,bytes=m.file_size,
                         adopted_path='',baseline_path='',status='',reason='')
                if package.name in CORE:
                    if not m.filename.startswith(PREFIX):
                        raise ValueError('unexpected current topic namespace: '+m.filename)
                    rel=PurePosixPath(m.filename[len(PREFIX):])
                    if rel.suffix in ('.ttf','.pdf') or 'LOG' in rel.name:
                        row.update(status='not_copied',reason='duplicate_font_plot_pdf_or_transient_log')
                        members.append(row);counts[row['status']]+=1;continue
                    target=current/rel
                elif historical_candidate(m.filename,m.file_size):
                    data=z.read(m)
                    exact=next((n for n in idx.get((name.name.casefold(),len(data)),[]) if (repo/n).read_bytes()==data),None)
                    if not exact:
                        for zp,zn in zipidx.get((name.name.casefold(),m.file_size,m.CRC),[]):
                            with zipfile.ZipFile(repo/zp) as prior:
                                if prior.read(zn)==data:
                                    exact=zp+'!/'+zn;break
                    if exact:
                        row.update(status='already_archived_identical',baseline_path=exact,reason='byte_comparison_not_SHA')
                        members.append(row);counts[row['status']]+=1;continue
                    parent=workers if 'personnel' in package.name.lower() else quality
                    target=parent/package.stem/name
                else:
                    row.update(status='not_selected',reason='outside_necessary_code_report_small_config_or_existing_asset')
                    members.append(row);counts[row['status']]+=1;continue
                data=z.read(m)
                flags=privacy_flags(data,name.suffix) if name.suffix in TEXT else []
                if flags:
                    row.update(status='local_source_only_privacy_review',reason='|'.join(flags))
                    privacy.append(dict(source_id=package_id,member_path=m.filename,flags='|'.join(flags)))
                else:
                    target.resolve().relative_to(repo.resolve())
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(data)
                    assert target.read_bytes()==data
                    row.update(status='archived_source_not_recomputed',adopted_path=target.relative_to(repo).as_posix(),
                               reason='selected_current_evidence' if package.name in CORE else 'unique_historical_code_report_config_not_current_adoption')
                    idx[(target.name.casefold(),len(data))].append(target.relative_to(repo).as_posix())
                    newfiles.append(target)
                members.append(row);counts[row['status']]+=1
            docs=sorted([m for m in infos if m.filename.endswith('.md') and REPORT.search(PurePosixPath(m.filename).name)],key=lambda m:(len(PurePosixPath(m.filename).parts),'readme' not in m.filename.lower()))
            content_file=docs[0].filename if docs else ''
            content_heading=next((s.strip()[:200] for s in z.read(docs[0]).decode('utf-8-sig',errors='replace').splitlines() if s.strip()),'') if docs else ''
            firstparts=sorted({PurePosixPath(m.filename).parts[0] for m in infos})
            inventory.append(dict(source_id=package_id,kind='zip',bytes=package.stat().st_size,
                member_count=len(infos),uncompressed_bytes=sum(m.file_size for m in infos),
                content_roots='|'.join(firstparts),content_evidence_file=content_file,content_heading=content_heading,python_files=sum(m.filename.endswith('.py') for m in infos),
                scientific_identity='real_v2_effective_exchange_20261022' if package.name in CORE else 'historical_or_source_asset_not_promoted',
                member_status_counts=json.dumps(dict(counts),ensure_ascii=False)))
        print('inventoried',package_id,dict(counts),flush=True)
    attachments=list(downloads.glob('*EVENTS_COMPLETE.csv.gz'))+[downloads/'ENDPOINT_KEY_INDEX.csv.gz']
    attachments += [downloads/n for n in ('PURE_MANUAL_COMPLETE_EVENTS.csv.gz','PURE_SEMI_COMPLETE_EVENTS.csv.gz','ABC_EVENT_RESULTS_COMPLETE.csv.gz')]
    attachments += list(downloads.glob('人员分类与有效换类条件_整合报告_20261022.md'))
    csv.field_size_limit(10000000)
    for src in attachments:
        if not src.is_file():continue
        historical_event=src.name.startswith(('PURE_','ABC_EVENT'))
        target=workers/'v3_event_inputs_20261021'/src.name if historical_event else current/('joint_exchange' if 'EVENTS_COMPLETE' in src.name else 'external_inputs' if src.name.endswith('.gz') else 'report')/src.name
        data=src.read_bytes();flags=privacy_flags(data,src.suffix)
        if flags:raise ValueError((src.name,flags))
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        assert target.read_bytes()==data
        newfiles.append(target);idx[(target.name.casefold(),len(data))].append(target.relative_to(repo).as_posix())
        local.append(dict(source_id=src.name,source_path=str(src),kind='attachment'))
        inventory.append(dict(source_id=src.name,kind='attachment',bytes=len(data),
            adopted_path=target.relative_to(repo).as_posix(),scientific_identity='historical_v3_stage_real_v2_data' if historical_event else 'real_v2_current_events_or_report_not_recomputed'))
        if 'EVENTS_COMPLETE' in src.name or historical_event:
            total=0;ids=set();images=set();buildings=set();conditions=set()
            with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as stream:
                reader=csv.DictReader(stream);cols=reader.fieldnames
                for row in reader:
                    total+=1;ids.add(row['event_id']);images.add(row['image']);buildings.add(row['building']);conditions.add(row['condition'])
            events.append(dict(source_id=src.name,rows=total,event_ids=len(ids),images=len(images),
                buildings=len(buildings),condition='|'.join(sorted(conditions)),columns=len(cols),archive_path=target.relative_to(repo).as_posix()))
    for d in roots:
        n=sum(1 for p in d.rglob('*') if p.is_file())
        extracted.append(dict(source_id=d.name,kind='extracted_directory',files=n,
            status='indexed_only_no_duplicate_directory_copy',zip_candidates='|'.join(p.name for p in packages if p.stem==d.name)))
        local.append(dict(source_id=d.name,source_path=str(d),kind='extracted_directory'))
    source_catalog=downloads/'HOHONET_完整文件下载目录.csv'
    catalog=[]
    if source_catalog.is_file():
        with source_catalog.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                clean={k:v for k,v in row.items() if k not in ('local_path','download_link')}
                p=PurePosixPath(row['topic_relative_path'])
                paths=idx.get((p.name.casefold(),int(row['bytes'])),[])
                clean.update(archive_candidates='|'.join(paths[:8]),availability='candidate_by_name_size_only' if paths else 'not_found_in_selected_sources')
                catalog.append(clean)
        local.append(dict(source_id=source_catalog.name,source_path=str(source_catalog),kind='delivery_catalog'))
    manifest=current/'delivery/CORE_PACKAGE_INPUTS.csv'
    dependencies=[]
    with manifest.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            if row['delivery_mode']!='external':continue
            req=row['repo_path'];norm=req.removeprefix('HOHONET/')
            primary=current/norm[len(PREFIX):] if norm.startswith(PREFIX) else repo/norm
            candidates=([primary.relative_to(repo).as_posix()] if primary.is_file() and primary.stat().st_size==int(row['bytes']) else [])+idx.get((PurePosixPath(norm).name.casefold(),int(row['bytes'])),[])
            candidates=list(dict.fromkeys(candidates))
            other_versions=[p for (name,size),paths in idx.items() if name==PurePosixPath(norm).name.casefold() and size!=int(row['bytes']) for p in paths]
            dependencies.append(dict(requested_path=req,declared_bytes=row['bytes'],required_for=row['required_for'],
                resolved_candidates='|'.join(candidates[:8]),other_version_candidates='|'.join(other_versions[:8]),
                status='mapped_declared_size_not_SHA_verified' if candidates else 'other_version_only' if other_versions else 'missing_in_checked_sources'))
    save_csv(audit/'PACKAGE_INVENTORY.csv',inventory)
    save_csv(audit/'MEMBER_LEDGER.csv',members)
    save_csv(audit/'EXTRACTED_DIRECTORIES.csv',extracted)
    save_csv(audit/'DELIVERY_CATALOG.csv',catalog)
    save_csv(audit/'DEPENDENCY_MAP.csv',dependencies)
    save_csv(audit/'EVENT_STREAM_INVENTORY.csv',events)
    save_csv(audit/'PRIVACY_EXCLUSIONS.csv',privacy)
    save_csv(audit/'LOCAL_SOURCES.csv',local)
    (audit/'.gitignore').write_text('LOCAL_SOURCES.csv\n__pycache__/\n.pytest_cache/\n',encoding='utf-8')
    for p in newfiles:
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    summary=dict(schema='downloads_source_archive_audit_v1',source_packages=len(inventory),
        zip_packages=len(packages),zip_members=len(members),extracted_directories=len(extracted),
        archived_files=len(newfiles),archived_bytes=sum(p.stat().st_size for p in newfiles),
        new_python_files=sum(p.suffix=='.py' for p in newfiles),privacy_exclusions=len(privacy),
        external_dependency_rows=len(dependencies),missing_external_rows=sum(r['status']=='missing_in_checked_sources' for r in dependencies),
        catalog_rows=len(catalog),events=events,source_files_untouched=True,sha_computed=False,
        fusion_scoring_recomputed=False,baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        publication_status='prepared_for_task_PR_not_merged_or_release_uploaded')
    (audit/'CHECKS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--downloads',type=Path,required=True)
    args=parser.parse_args();main(args.repo.resolve(),args.downloads.resolve())
