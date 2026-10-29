"""Independent final report evidence validation; no fusion or scoring.

Checks immutable source bytes, every exact ledger selection and complete
unrounded saved row, table structure/citations, and all DOCX ZIP/XML members.
Only creates validation artifacts. It never edits report or scientific inputs.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import posixpath
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def jread(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.writing')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    temp.replace(path)


def cwrite(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def normalize(value):
    if pd.isna(value):return None
    return value.item() if hasattr(value,'item') else value


def exact_equal(a,b):
    if a is None or b is None:return a is None and b is None
    if isinstance(a,bool) or isinstance(b,bool):return type(a) is type(b) and a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return math.isfinite(a) and math.isfinite(b) and a==b
    return type(a) is type(b) and a==b


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--report-dir',type=Path)
    ap.add_argument('--docx',type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args();root=args.root.resolve()
    report=args.report_dir or root/'stage08_report';out=args.output or report/'verification'
    out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    blocks_path=report/'REPORT_BLOCKS.json';index_path=report/'REPORT_EVIDENCE_INDEX.json'
    ledger_path=report/'REPORT_NUMBER_LEDGER.csv'
    docx=args.docx or report/'HOHONET_v21_AC_population_report_ZH.docx'
    snapshot={str(p.relative_to(root)):sha(p) for p in [blocks_path,index_path,ledger_path,docx]}
    blocks=jread(blocks_path);sources=jread(index_path)
    with ledger_path.open(encoding='utf-8-sig',newline='') as f:ledger=list(csv.DictReader(f))
    errors=[];warnings=[];source_checks=[];ledger_checks=[];table_checks=[];spot_checks=[]
    cache={};path_hashes={};field_counts=collections.Counter();numeric_max=0.0

    def error(kind,**details):errors.append({'kind':kind,**details})

    def csv_data(path):
        path=Path(path).resolve()
        if path not in cache:
            # Independently re-read the immutable CSV rather than a build-time
            # object or a prior ledger. The CSV parser is recorded explicitly.
            cache[path]=pd.read_csv(path,low_memory=False)
        return cache[path]

    for source,info in sources.items():
        p=(root/info['relative_path']).resolve()
        row={'source':source,'relative_path':info['relative_path'],'expected_sha256':info.get('sha256'),
             'expected_bytes':info.get('bytes'),'exists':p.is_file()}
        if not p.is_file():
            error('source_missing',source=source,path=str(p));source_checks.append(row);continue
        actual=path_hashes.setdefault(p,sha(p))
        row.update(actual_sha256=actual,actual_bytes=p.stat().st_size,
                   sha256_match=actual==info.get('sha256'),bytes_match=p.stat().st_size==info.get('bytes'))
        if not row['sha256_match'] or not row['bytes_match']:error('source_hash_or_size_mismatch',**row)
        if p.suffix=='.json':jread(p)
        elif p.suffix in ['.md','.txt']:p.read_text(encoding='utf-8-sig')
        source_checks.append(row)

    for i,row in enumerate(ledger,2):
        source=row['source'];filters=json.loads(row['filters']);saved=json.loads(row['values'])
        result={'ledger_csv_row':i,'source':source,'filters':row['filters']}
        if source not in sources:
            error('ledger_unknown_source',row=i,source=source);ledger_checks.append(result);continue
        p=(root/sources[source]['relative_path']).resolve()
        try:
            full=csv_data(p);selected=full
            for col,value in filters.items():
                if col not in full.columns:raise KeyError(col)
                selected=selected[selected[col].astype(str).eq(str(value))]
            result['matching_source_rows']=len(selected)
            if len(selected)!=1:
                error('ledger_selection_not_unique',row=i,source=source,filters=filters,matches=len(selected))
                ledger_checks.append(result);continue
            actual={str(k):normalize(v) for k,v in selected.iloc[0].items()}
            result['source_dataframe_row_index']=int(selected.index[0]);result['source_columns']=len(actual)
            missing=sorted(set(actual)-set(saved));extra=sorted(set(saved)-set(actual))
            if missing or extra:error('ledger_column_set_mismatch',row=i,missing=missing,extra=extra)
            differences=[]
            for col in set(actual)&set(saved):
                a,b=actual[col],saved[col]
                if not exact_equal(a,b):differences.append({'column':col,'source_value':a,'ledger_value':b})
                if a is None:field_counts['null']+=1
                elif isinstance(a,bool):field_counts['boolean']+=1
                elif isinstance(a,(int,float)):
                    field_counts['numeric']+=1
                    if isinstance(b,(int,float)) and not isinstance(b,bool):numeric_max=max(numeric_max,abs(a-b))
                else:field_counts['string']+=1
            if differences:error('ledger_saved_value_mismatch',row=i,source=source,differences=differences)
            result.update(saved_columns=len(saved),all_saved_values_exact=not differences and not missing and not extra,
                          source_sha256=path_hashes[p])
        except Exception as exc:
            error('ledger_read_or_filter_exception',row=i,source=source,exception=repr(exc))
        ledger_checks.append(result)

    table_blocks=[];reference_occurrences=0;image_checks=[]
    for i,b in enumerate(blocks):
        source=b.get('source')
        if source:
            refs=source.split('/')
            for ref in refs:
                reference_occurrences+=1
                if ref not in sources:error('unknown_block_source_reference',block=i,reference=ref)
        if b['kind']=='table':
            table_blocks.append((i,b));n=len(b['headers']);rows=b['rows']
            good=all(len(row)==n for row in rows)
            widths=b.get('widths');widths_good=widths is None or (len(widths)==n and all(float(x)>0 for x in widths))
            table_checks.append({'block_index':i,'title':b.get('title'),'columns':n,'data_rows':len(rows),
                                 'all_rows_width_correct':good,'column_widths_valid':widths_good,'source':source})
            if not good:error('report_table_row_width',block=i)
            if not widths_good:error('report_table_width_settings',block=i)
            if not source:error('report_table_without_source',block=i,title=b.get('title'))
        if b['kind']=='image':
            p=root/b['path'];exists=p.is_file();image_checks.append({'block_index':i,'path':b['path'],'exists':exists,
                'sha256':sha(p) if exists else None})
            if not exists:error('report_image_missing',block=i,path=b['path'])

    def spot(name,report_value,expected,source_path,source_key):
        p=root/source_path
        record={'name':name,'report_value':report_value,'source_value':expected,'source_path':source_path,
                'source_key':source_key,'source_sha256':sha(p),'passed':exact_equal(report_value,expected)}
        spot_checks.append(record)
        if not record['passed']:error('hardcoded_number_mismatch',**record)

    def paragraph(prefix):
        matches=[b['text'] for b in blocks if b['kind']=='p' and b['text'].startswith(prefix)]
        if len(matches)!=1:raise ValueError((prefix,'paragraph_matches',len(matches)))
        return matches[0]

    def numbers(pattern,text):
        m=re.search(pattern,text)
        if not m:raise ValueError(('hardcoded_pattern_not_found',pattern))
        return [int(x.replace(',','')) for x in m.groups()]

    try:
        apath='stage02_engine/EXECUTION_ACCOUNTING_CLARIFICATION.json';account=jread(root/apath)
        mpath='stage01_registered/FROZEN_MERGED_DESIGN.json';merged=jread(root/mpath)
        qpath='stage04_metrics/MEASUREMENT_RECEIPT.json';measured=jread(root/qpath)
        text=paragraph('最终登记')
        values=numbers(r'最终登记([\d,]+)支不同团队、([\d,]+)条方法事件、([\d,]+)个无向物理端点对、([\d,]+)条设计关联',text)
        for label,value,expected,path,key in [
            ('registered_teams',values[0],account['frozen_requested_unique_teams'],apath,'frozen_requested_unique_teams'),
            ('registered_method_events',values[1],merged['outputs']['AC_EVENTS.csv.gz']['rows'],mpath,'outputs.AC_EVENTS.csv.gz.rows'),
            ('physical_endpoint_pairs',values[2],measured['unique_physical_pairs'],qpath,'unique_physical_pairs'),
            ('design_links',values[3],merged['outputs']['DESIGN_LINKS.csv.gz']['rows'],mpath,'outputs.DESIGN_LINKS.csv.gz.rows')]:
            spot(label,value,expected,path,key)
        values=numbers(r'核心运行([\d,]+)支是真正新增实体，([\d,]+)支为已有标量而缺完整几何的必要回放，([\d,]+)支直接复用',text)
        for v,key in zip(values,['new_physical_teams','old_physical_entities_replayed_for_geometry','full_existing_endpoint_reuse']):spot(key,v,account[key],apath,key)
        text=paragraph('核心原生评价')
        values=numbers(r'核心原生评价([\d,]+)次，分为首波([\d,]+)次与续算([\d,]+)次',text)
        for v,key in zip(values,['native_endpoint_evaluations_in_core_endpoint_run','native_endpoint_evaluations_in_first_timed_wave','native_endpoint_evaluations_in_continued_full_pass']):spot(key,v,account[key],apath,key)
        text=paragraph('所有设计合并的')
        for label,pattern in [('complete_conditional',r'([\d,]+)支产出complete_conditional'),('no_connection',r'([\d,]+)支为legacy no_connection'),('below_four',r'([\d,]+)支below_four'),('invalid_floor',r'([\d,]+)支invalid_floor')]:
            spot('endpoint_state_'+label,numbers(pattern,text)[0],account['score_status_counts'][label],apath,'score_status_counts.'+label)
        spot('Q_missing',numbers(r'合计([\d,]+)支缺Q',text)[0],account['Q_missing_rows'],apath,'Q_missing_rows')
        cap_path=sources['E02']['relative_path'];cap=csv_data(root/cap_path)
        capacity_table=next(b for _,b in table_blocks if b['title'].startswith('主目标逐图类别容量'))
        methods={'TARGET K3':'TARGET_DSTRUCT_K3','RAW3 K3':'V21_DSTRUCT_RAW3_K3','OPPJOINT K3':'OPPJOINT_K3','OPPJOINT K4':'OPPJOINT_K4','OPPSTRUCT K3':'OPPSTRUCT_K3'}
        for row in capacity_table['rows']:
            method=methods[row[0]]
            for col,(m,field) in enumerate([(7,'any_n_pools'),(8,'any_n_pools'),(9,'any_n_pools'),(10,'any_n_pools'),(12,'any_n_pools'),(10,'n20_pools'),(12,'n20_pools')],1):
                rr=cap[(cap.method==method)&(cap.m==m)];assert len(rr)==1
                spot('capacity_'+method+'_'+str(m)+'_'+field,int(row[col]),int(rr.iloc[0][field]),cap_path,f'method={method},m={m};{field}')
        old_path=sources['R00']['relative_path'];old=(root/old_path).read_text();text=paragraph('已独立核验的TARGET主方向严格ABC')
        patterns={14:r'14/7登记(\d+)图、三队共同可评(\d+)图，平均同类\|ΔQ\|([\d.]+)、跨类\|ΔQ\|([\d.]+)，GA=([+\d.]+)，(\d+/\d+)图GA>0',
                  20:r'20/7登记(\d+)图、三队共同可评(\d+)图，同类([\d.]+)、跨类([\d.]+)，GA=([+\d.]+)，(\d+/\d+)图GA>0'}
        for n,pattern in patterns.items():
            line=next(x for x in old.splitlines() if x.startswith(f'|TARGET K3，{n}人换7人|'))
            cells=line.strip('|').split('|');parsed=re.fullmatch(r'(\d+)（登记(\d+)）',cells[1])
            expected=[int(parsed[2]),int(parsed[1]),float(cells[2]),float(cells[3]),float(cells[4]),cells[5]]
            match=re.search(pattern,text);assert match is not None
            actual=[int(match[1]),int(match[2]),float(match[3]),float(match[4]),float(match[5]),match[6]]
            for label,a,e in zip(['registered_images','joint_scored_images','within_absQ','cross_absQ','GA','positive_GA_images'],actual,expected):
                spot(f'old_ABC_{n}_7_'+label,a,e,old_path,f'TARGET K3，{n}人换7人;{label}')
        s=re.search(r'对称GS的多数比例分别(\d+/\d+)、(\d+/\d+)',text);assert s is not None
        for i,n in enumerate([14,20],1):
            line=next(x for x in old.splitlines() if x.startswith(f'|TARGET K3，{n}人换7人|'))
            spot(f'old_ABC_{n}_7_positive_GS',s[i],line.strip('|').split('|')[7],old_path,f'TARGET K3，{n}人换7人;GS_positive')
        spath='stage05_funnel_bridge/STRICT_PREPARATION_RECEIPT.json';strict=jread(root/spath)
        fpath='stage05_funnel_bridge/FUNNEL_AND_STRICT_BRIDGE_RECEIPT.json';funnel=jread(root/fpath)
        text=paragraph('本轮接入')
        matches=[('normalized_strict_events',r'本轮接入([\d,]+)个旧严格事件'),('selected_prior_m7_m8_rows',r'm7/m8为([\d,]+)'),('selected_latest_m9_m10_rows',r'm9/m10为([\d,]+)'),('completed_stage03_already_in_integrated',r'此前([\d,]+)条'),('strict_unique_physical_AC_BC_pairs',r'AC/BC去重([\d,]+)个物理对'),('new_registered_physical_pairs_matching_strict_pair',r'交集为([\d,]+)')]
        for key,pattern in matches:spot('strict_'+key,numbers(pattern,text)[0],strict[key],spath,key)
        spot('strict_compatible_directed_conditions',numbers(r'([\d,]+)个旧有向条件',text)[0],funnel['strict_directed_conditions_with_new_same_condition'],fpath,'strict_directed_conditions_with_new_same_condition')
    except Exception as exc:error('hardcoded_spot_check_exception',exception=repr(exc))

    xml_entries=[];zip_entries=[];docx_table_rows=[]
    try:
        with zipfile.ZipFile(docx) as z:
            names=z.namelist();assert len(names)==len(set(names))
            bad=z.testzip();assert bad is None,bad
            xml_roots={}
            for info in z.infolist():
                data=z.read(info.filename);zip_entries.append({'path':info.filename,'uncompressed_bytes':len(data),'crc32':f'{info.CRC:08x}'})
                if info.filename.endswith(('.xml','.rels')):
                    element=ET.fromstring(data);xml_roots[info.filename]=element
                    xml_entries.append({'path':info.filename,'root_tag':element.tag,'bytes':len(data)})
            for filename,element in xml_roots.items():
                if filename.endswith('.rels'):
                    base=filename.rsplit('/_rels/',1)[0] if '/_rels/' in filename else ''
                    for relation in element:
                        if relation.get('TargetMode')=='External':continue
                        target=relation.get('Target','')
                        resolved=posixpath.normpath(posixpath.join(base,target)).lstrip('/')
                        if resolved not in names:error('docx_missing_relationship_target',part=filename,target=target,resolved=resolved)
            w={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            tables=xml_roots['word/document.xml'].findall('.//w:tbl',w)
            if len(tables)!=len(table_blocks):error('docx_table_count_mismatch',actual=len(tables),expected=len(table_blocks))
            canonical=lambda x:re.sub(r'\s+','',str(x))
            for ti,((bi,b),table) in enumerate(zip(table_blocks,tables)):
                expected=[b['headers']]+b['rows']
                actual=[[''.join(cell.itertext()) for cell in row.findall('w:tc',w)] for row in []]
                actual=[]
                for row in table.findall('w:tr',w):
                    actual.append([''.join(t.text or '' for t in cell.findall('.//w:t',w)) for cell in row.findall('w:tc',w)])
                good=len(actual)==len(expected) and all(len(x)==len(y) and all(canonical(a)==canonical(e) for a,e in zip(x,y)) for x,y in zip(actual,expected))
                docx_table_rows.append({'report_block':bi,'docx_table_index':ti,'expected_rows':len(expected),'actual_rows':len(actual),'cell_text_matches_ignoring_layout_whitespace':good})
                if not good:error('docx_table_content_mismatch',block=bi,table=ti,expected=expected,actual=actual)
        docx_result={'complete_zip_crc_passed':True,'all_xml_parts_parsed':True,'zip_members':zip_entries,'xml_parts':xml_entries,'table_comparisons':docx_table_rows,'docx_sha256':sha(docx),'visual_pdf_review_outside_this_validator':True}
    except Exception as exc:
        error('docx_zip_xml_exception',exception=repr(exc));docx_result={'complete_zip_crc_passed':False,'exception':repr(exc)}

    for p,initial in snapshot.items():
        final=sha(root/p)
        if final!=initial:error('input_changed_during_validation',path=p,before=initial,after=final)
    for p,initial in path_hashes.items():
        final=sha(p)
        if final!=initial:error('source_changed_during_validation',path=str(p),before=initial,after=final)
    cwrite(out/'REPORT_SOURCE_SHA_VALIDATION.csv',source_checks)
    cwrite(out/'REPORT_LEDGER_ROW_VALIDATION.csv',ledger_checks)
    cwrite(out/'REPORT_TABLE_STRUCTURE_VALIDATION.csv',table_checks)
    dump(out/'REPORT_HARDCODED_NUMBER_SPOT_CHECKS.json',spot_checks)
    dump(out/'DOCX_ZIP_XML_VALIDATION.json',docx_result)
    receipt={'status':'passed' if not errors else 'failed','passed':not errors,'complete':not errors,
      'blocks':len(blocks),'tables':len(table_blocks),'declared_sources':len(sources),'unique_source_files':len(path_hashes),
      'source_hashes_and_bytes_passed':sum(r.get('sha256_match',False) and r.get('bytes_match',False) for r in source_checks),
      'ledger_rows':len(ledger),'ledger_rows_unique_and_full_values_exact':sum(r.get('all_saved_values_exact',False) for r in ledger_checks),
      'ledger_compared_fields':dict(field_counts),'maximum_numeric_ledger_source_difference':numeric_max,
      'numeric_comparison':'Exact numeric equality after fresh CSV parsing with pandas; no rounding or numeric tolerance. Nulls and strings checked separately.',
      'csv_parser_version':pd.__version__,'source_reference_occurrences':reference_occurrences,
      'report_images_checked':image_checks,'hardcoded_number_spot_checks':len(spot_checks),
      'hardcoded_spot_checks_passed':sum(x['passed'] for x in spot_checks),
      'hardcoded_scope':'Selected registration, reuse, native-evaluation, status, capacity and old strict ABC statements; not a claim to verify every prose sentence.',
      'docx_zip_members':len(zip_entries),'docx_xml_parts':len(xml_entries),
      'docx_tables_matching_report_blocks':sum(x['cell_text_matches_ignoring_layout_whitespace'] for x in docx_table_rows),
      'input_hashes':snapshot,'source_inputs_unchanged_during_check':not any(x['kind'].endswith('changed_during_validation') for x in errors),
      'verification_code_sha256':sha(Path(__file__)),
      'exceptions':errors,'warnings':warnings,'seconds':time.monotonic()-started,
      'new_fusions':0,'new_scores':0,'report_body_or_scientific_sources_modified':False,
      'pdf_visual_review':'Handled independently by the parent; not claimed here.'}
    dump(out/'REPORT_EVIDENCE_VALIDATION.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['input_hashes','report_images_checked','exceptions']},ensure_ascii=False))
    if errors:
        print(json.dumps({'exceptions':errors},ensure_ascii=False)[:18000]);sys.exit(1)


if __name__=='__main__':main()
