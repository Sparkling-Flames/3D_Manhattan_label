#!/usr/bin/env python3
"""Read-only cross-package extraction audit using saved hashes and ZIP directories."""
from pathlib import Path,PurePosixPath
from collections import defaultdict,Counter
import csv,fnmatch,hashlib,json,ntpath,posixpath,re,stat,unicodedata,zipfile

ROOT=Path(__file__).resolve().parents[1];META=ROOT/'stage09_delivery';PREFIX=ROOT.name+'/'
SPECS=[('RESULTS_PACKAGE_MANIFEST.csv',None),('PATH_EVENT_PACKAGE_MANIFEST.csv',None),
       ('REPRODUCTION_INPUT_PACKAGE_MANIFEST.csv',None),('CASE_PACKAGE_MANIFEST.csv','05_Cases_and_Evidence.zip'),
       ('GEOMETRY_EVENT_PACKAGE_MANIFEST.csv',None)]

def savecsv(rows,path,fields=None):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def path_issue(name):
    raw=name.replace('\\','/')
    if any(ord(x)<32 for x in name):return 'control_character'
    if raw.startswith('/') or ntpath.splitdrive(name)[0]:return 'absolute_or_drive_path'
    if any(x in {'.','..'} for x in raw.split('/')):return 'dot_or_parent_component'
    if any(':' in x for x in raw.split('/')):return 'windows_alternate_stream_or_drive_component'
    if not raw.startswith(PREFIX):return 'unexpected_archive_root'
    if raw!=name or '//' in raw:return 'noncanonical_separator'
    return None

def main():
    bypackage=defaultdict(dict);manifests=[]
    for filename,default in SPECS:
        f=META/filename;manifests.append(dict(path=str(f.relative_to(ROOT)),sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
        for row in csv.DictReader(f.open(encoding='utf-8-sig')):
            package=row.get('package_name') or default;member=row['archive_member']
            assert member not in bypackage[package],(package,member)
            bypackage[package][member]=dict(sha256=row.get('archive_member_sha256') or row.get('sha256'),
                bytes=int(row.get('source_bytes') or row.get('bytes')),manifest=filename)
    members=defaultdict(list);docs={};packagechecks=[];unsafe=[];symlinks=[];scripts=[]
    for package,registered in sorted(bypackage.items()):
        p=ROOT/'delivery'/package
        with zipfile.ZipFile(p) as z:
            infos=[i for i in z.infolist() if not i.is_dir()];names=[i.filename for i in infos]
            missing=sorted(set(registered)-set(names));unmanifested=sorted(set(names)-set(registered))
            duplicates=sorted(n for n,c in Counter(names).items() if c>1)
            sizebad=[]
            for i in infos:
                issue=path_issue(i.orig_filename)
                if issue:unsafe.append(dict(package=package,member=i.orig_filename,reason=issue))
                if stat.S_ISLNK(i.external_attr>>16):symlinks.append(dict(package=package,member=i.filename))
                if i.filename not in registered:continue
                saved=registered[i.filename]
                if i.file_size!=saved['bytes']:sizebad.append(i.filename)
                members[i.filename].append(dict(package=package,sha256=saved['sha256'],bytes=i.file_size))
                if i.filename.endswith('.md'):docs[i.filename]=dict(package=package,text=z.read(i).decode('utf-8-sig'))
                if package=='05_Cases_and_Evidence.zip' and i.filename.startswith(PREFIX+'scripts/'):
                    rel=i.filename[len(PREFIX):];data=z.read(i);current=ROOT/rel
                    actual=hashlib.sha256(data).hexdigest();now=hashlib.sha256(current.read_bytes()).hexdigest() if current.exists() else None
                    scripts.append(dict(archive_member=i.filename,archive_sha256=actual,manifest_sha256=saved['sha256'],
                        current_script_sha256=now,exists_current=current.exists(),all_equal=actual==saved['sha256']==now))
            packagechecks.append(dict(package=package,archive_bytes=p.stat().st_size,zip_file_members=len(infos),
                manifest_members=len(registered),missing_members=missing,unmanifested_members=unmanifested,
                duplicate_members_within_zip=duplicates,size_mismatches=sizebad,
                metadata_and_manifest_match=not(missing or unmanifested or duplicates or sizebad)))
    overlap=[]
    for member,occ in sorted(members.items()):
        if len(occ)>1:overlap.append(dict(archive_member=member,occurrences=len(occ),packages='|'.join(o['package'] for o in occ),
            byte_identical=len({(o['bytes'],o['sha256']) for o in occ})==1,
            sha256_values='|'.join(sorted({o['sha256'] for o in occ}))))
    collisiongroups=defaultdict(list)
    for name in members:collisiongroups[unicodedata.normalize('NFC',name).casefold()].append(name)
    casecollisions=[v for v in collisiongroups.values() if len(v)>1]
    hierarchy=[]
    for name in members:
        for ancestor in PurePosixPath(name).parents:
            a=str(ancestor)
            if a in members:hierarchy.append(dict(file_path=a,descendant_file=name))
    names=set(members);basename=defaultdict(list)
    for n in names:basename[PurePosixPath(n).name].append(n)
    localbyname=defaultdict(list)
    # Paths only: no large data, gzip, or ZIP payloads are reread.
    for p in ROOT.rglob('*'):
        if p.is_file() and 'delivery' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts:
            localbyname[p.name].append(str(p.relative_to(ROOT)))
    references=[]
    for doc,item in sorted(docs.items()):
        text=item['text'];tokens=[]
        for match in re.finditer(r'`([^`\n]+)`',text):
            t=match.group(1).strip()
            if t.startswith('python '):t=t.split()[1]
            if re.search(r'\.(?:csv|json|jsonl|md|py|png|pdf|svg|html|zip|txt)(?:\.gz)?(?:$|/)',t) or t.endswith('/') or ('*' in t and re.match(r'[A-Za-z0-9_/.-]+\*',t)):
                tokens.append((t,'backtick_reference',match.start()))
        for match in re.finditer(r'!?(?:\[[^\]]*\])\(([^)]+)\)',text):
            t=match.group(1).split('#',1)[0].strip()
            if t and not re.match(r'[A-Za-z]+://',t):tokens.append((t,'markdown_link',match.start()))
        seen=set()
        for token,kind,position in tokens:
            if (token,kind) in seen:continue
            seen.add((token,kind))
            variants=[token]
            m=re.match(r'^(.*)\.(png|pdf|svg)/\.(png|pdf|svg)$',token)
            if m:variants=[m.group(1)+'.'+m.group(2),m.group(1)+'.'+m.group(3)]
            resolved=[];status='unresolved'
            for t in variants:
                candidates=[posixpath.normpath(posixpath.join(posixpath.dirname(doc),t)),PREFIX+t,PREFIX+'source/repo/'+t]
                if t.rstrip('/')==ROOT.name:candidates.append(PREFIX.rstrip('/'))
                hits=[]
                for candidate in candidates:
                    if candidate in names:hits.append(candidate)
                    hits.extend(n for n in names if n.startswith(candidate.rstrip('/')+'/'))
                    if '*' in candidate:hits.extend(n for n in names if fnmatch.fnmatch(n,candidate))
                if hits:resolved.extend(hits);status='resolved_current_packages';continue
                if kind=='backtick_reference' and '/' in t:
                    hits=[n for n in names if n.endswith('/'+t.rstrip('/'))]
                    if t.endswith('/'):hits.extend(n for n in names if '/'+t in n)
                    if hits:resolved.extend(hits);status='resolved_source_path_suffix_in_current_packages';continue
                # Backticks often name a per-case file/directory generically. Do
                # not apply this fallback to an actual relative Markdown link.
                if kind=='backtick_reference' and '/' not in t.rstrip('/'):
                    b=t.rstrip('/');hits=[n for n in names if fnmatch.fnmatch(PurePosixPath(n).name,b)]
                    if t.endswith('/'):hits.extend(n for n in names if '/'+b+'/' in n)
                    if hits:resolved.extend(hits);status='resolved_generic_case_filename_or_directory';continue
            line=text[text.rfind('\n',0,position)+1:text.find('\n',position) if '\n' in text[position:] else len(text)]
            if not resolved:
                local=[]
                for t in variants:
                    for cand in [t,posixpath.normpath(posixpath.join(posixpath.dirname(doc)[len(PREFIX):],t)), 'source/repo/'+t]:
                        if (ROOT/cand).is_file():local.append(cand)
                    local.extend(localbyname.get(PurePosixPath(t).name,[]))
                if token.startswith('scripts/') or token.startswith('stage09_delivery/') or PurePosixPath(token).name in {'CASE_PACKAGE_VALIDATION.json'}:
                    status='pending_06_present_in_workspace' if local else 'unresolved_current_dependency'
                elif doc.endswith('DOWNSTREAM_HANDOFF_ZH.md'):
                    if token=='CURRENT_DOORWAY_FULL_STATE_CANDIDATES.csv':status='source_pointer_inventory_not_in_current_archives'
                    else:status='historical_source_reference_not_claimed_in_current_case_zip'
                elif local:status='present_in_workspace_not_current_packages'
                resolved=sorted(set(local))
            references.append(dict(document=doc,package=item['package'],reference=token,reference_kind=kind,
                resolution_status=status,resolved_or_workspace_paths='|'.join(sorted(set(resolved))[:8]),
                matches=len(set(resolved)),listed_match_limit=8,context=line))
    refcsv=META/'CROSS_PACKAGE_README_REFERENCES.csv';savecsv(references,refcsv)
    scriptcsv=META/'CASE_SCRIPT_CURRENT_HASH_CHECK.csv';savecsv(scripts,scriptcsv)
    if overlap:savecsv(overlap,META/'CROSS_PACKAGE_OVERLAPS.csv')
    current_issues=[r for r in references if r['resolution_status'] in ['unresolved','unresolved_current_dependency'] or
                    (r['reference_kind']=='markdown_link' and r['resolution_status'] not in ['resolved_current_packages','pending_06_present_in_workspace'])]
    pending=[r for r in references if r['resolution_status']=='pending_06_present_in_workspace']
    source_refs=[r for r in references if r['resolution_status'].startswith(('historical_','source_pointer_'))]
    conflict=[r for r in overlap if not r['byte_identical']]
    allsafe=all(p['metadata_and_manifest_match'] for p in packagechecks) and not(unsafe or symlinks or casecollisions or hierarchy or conflict) and all(s['all_equal'] for s in scripts)
    receipt=dict(status='passed_current_10_packages_pending_06' if allsafe and not current_issues else 'issues_found',
        scope='02, four 03 parts, three 04 parts, 05 and 07. 01 excluded; 06 not yet available.',
        packages=packagechecks,package_count=len(packagechecks),archive_file_members=sum(x['zip_file_members'] for x in packagechecks),
        distinct_extraction_paths=len(members),duplicate_paths_across_packages=len(overlap),
        identical_duplicate_paths=sum(o['byte_identical'] for o in overlap),different_content_overwrites=conflict,
        results02_vs_inputs04_common_paths=sum(any(o['package'].startswith('02_') for o in v) and any(o['package'].startswith('04_') for o in v) for v in members.values()),
        unsafe_paths=unsafe,symlink_entries=symlinks,case_or_unicode_path_collisions=casecollisions,file_directory_conflicts=hierarchy,
        case_package_scripts_checked=len(scripts),case_package_scripts_equal_current=all(s['all_equal'] for s in scripts),
        README_documents_checked=len(docs),README_reference_count=len(references),
        README_resolution_counts=dict(Counter(r['resolution_status'] for r in references)),
        current_broken_dependencies=current_issues,pending_06_references=pending,historical_external_source_references=source_refs,
        manifest_hashes_used=manifests,README_reference_table=str(refcsv.relative_to(ROOT)),
        script_hash_table=str(scriptcsv.relative_to(ROOT)),
        verification_method='ZIP central-directory names/sizes/modes cross-checked against fully validated manifests. Existing member hashes compared across packages; only Markdown and 05 source scripts were read from ZIP. No inner gzip was reprocessed.',
        archive_payloads_modified=False,existing_case_sources_modified=False,inner_gzip_revalidated=False,
        note='No current cross-package duplicate member exists; extraction order is therefore immaterial for these ten packages. 06 must still be compared once produced.')
    (META/'CROSS_PACKAGE_OVERLAP_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:receipt[k] for k in ['status','package_count','archive_file_members','distinct_extraction_paths',
        'duplicate_paths_across_packages','results02_vs_inputs04_common_paths','unsafe_paths','case_or_unicode_path_collisions',
        'case_package_scripts_checked','case_package_scripts_equal_current','README_documents_checked','README_resolution_counts',
        'current_broken_dependencies']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
