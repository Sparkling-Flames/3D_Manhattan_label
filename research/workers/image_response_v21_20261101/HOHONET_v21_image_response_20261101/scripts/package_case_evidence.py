#!/usr/bin/env python3
"""Package verified cases without changing sources; inspect all archive layers."""
from pathlib import Path
from io import BytesIO,StringIO
import csv,gzip,hashlib,json,os,tempfile,zipfile

ROOT=Path(__file__).resolve().parents[1]
PREFIX=ROOT.name+'/'
DELIVERY=ROOT/'delivery';META=ROOT/'stage09_delivery'
DEST=DELIVERY/'05_Cases_and_Evidence.zip'
SCRIPTS=[
 'build_doorway_case_viewer.py','build_manual_cases.py',
 'fetch_doorway_replay_dependencies.py','integrate_manual_full35.py',
 'prepare_doorway_cases.py','render_doorway_cases.py','replay_doorway_cases.py',
 'replay_manual_full35.py','validate_manual_cases.py','write_manual_case_notes.py',
 'normalize_manual.py','normalize_doorway.py','package_case_evidence.py',
]
EXCLUDED_DIRS={'__pycache__','tmp','temp','qa','qa_render','render_checks',
 'rendered_pages','pdf_readback','manual_case_pdf_readback','thumbnails','thumbs'}
ROOTS=['stage05_cases/manual','stage04_doorway_cases']

def exclude(path):
    rel=path.relative_to(ROOT)
    if any(x in EXCLUDED_DIRS for x in rel.parts):return 'runtime cache or temporary rendering/QA directory'
    if path.suffix.lower() in {'.pyc','.pyo'}:return 'compiled Python cache'
    if path.name.endswith(('.writing','.tmp','.part')):return 'temporary unfinished file'
    return None

def category(rel):
    if rel.startswith('stage04_doorway_cases/replay_engine/'):return 'pinned_frozen_engine'
    if rel.startswith('stage04_doorway_cases/'):return 'doorway_cases_and_evidence'
    if rel.startswith('stage05_cases/manual/'):return 'ordinary_manual_cases_and_evidence'
    if rel.startswith('scripts/'):return 'same_version_case_source_script'
    return 'delivery_dependency_note'

def inspect_compressed(name,data,nested):
    """Check archive bytes, not a second copy of the source file."""
    info=dict(gzip_eof_verified=False,inner_zip_crc_verified=False,
              table_readable=False,table_rows=None,json_readable=False)
    if name.lower().endswith('.gz'):
        with gzip.GzipFile(fileobj=BytesIO(data),mode='rb') as gz:raw=gz.read()
        info['gzip_eof_verified']=True
        n={'member':name,'kind':'gzip','compressed_bytes':len(data),'uncompressed_bytes':len(raw),'EOF_and_CRC_valid':True}
        if name.lower().endswith('.csv.gz'):
            rows=list(csv.reader(StringIO(raw.decode('utf-8-sig'))));n['table_rows']=max(0,len(rows)-1)
            info.update(table_readable=True,table_rows=n['table_rows'])
        elif name.lower().endswith('.json.gz'):
            json.loads(raw);info['json_readable']=True;n['json_readable']=True
        elif name.lower().endswith('.jsonl.gz'):
            n['jsonl_rows']=sum(1 for line in raw.decode('utf8').splitlines() if line.strip() and json.loads(line) is not None)
            info['json_readable']=True
        nested.append(n)
    elif name.lower().endswith('.zip'):
        with zipfile.ZipFile(BytesIO(data)) as z:
            assert z.testzip() is None,'Inner ZIP CRC failed: '+name
            names=z.namelist();assert len(names)==len(set(names)),'Duplicate inner ZIP names: '+name
            checked=0
            for zi in z.infolist():
                if zi.is_dir():continue
                contents=z.read(zi.filename);checked+=1
                if zi.filename.lower().endswith(('.zip','.gz')):inspect_compressed(name+'!'+zi.filename,contents,nested)
        info['inner_zip_crc_verified']=True
        nested.append(dict(member=name,kind='zip',members=len(names),file_members_fully_read=checked,all_CRC_valid=True))
    elif name.lower().endswith('.csv'):
        rows=list(csv.reader(StringIO(data.decode('utf-8-sig'))));info.update(table_readable=True,table_rows=max(0,len(rows)-1))
    elif name.lower().endswith('.json'):
        json.loads(data);info['json_readable']=True
    return info

def main():
    DELIVERY.mkdir(parents=True,exist_ok=True);META.mkdir(parents=True,exist_ok=True)
    note=META/'CASE_PACKAGE_README_ZH.md'
    note.write_text('''# 05_Cases_and_Evidence.zip：案例、原始依据与冻结诊断代码

本包保持统一目录前缀 `HOHONET_v21_image_response_20261101/`，原样保存三个普通 Manual 案例及两个门洞后段案例。

## 阅读入口

- `stage05_cases/manual/README_ZH.md`：三个普通案例；每图 `VIEWER.html` 可脱网查看原图、完整个人标注、当前参考、精确团队、实际融合点对与支持票。
- `stage04_doorway_cases/DOORWAY_LATE_CASES_ZH.md` 与 `DOORWAY_LATE_RESPONSE_EVIDENCE.html`：两个门洞后段案例和离线可视证据。
- 原图、全部相关个人原答、正式参考、逐团队分数与状态、完整保存几何、实际票账和回放一致性证据均在各案例目录。正文使用的 PNG、PDF、SVG 与绘图数据保留。
- 原验证文件原样保留；本次只做封装、CRC、内层压缩读取与文件哈希核对，不重新做科学分析或视觉裁决。

## 复现依赖与边界

`stage04_doorway_cases/replay_engine/` 是固定仓库提交 e1873bfadc1d0e61499809c91fba9dc39c717f83 下恢复的冻结代码与测量引擎，不是本轮重新调参的版本。`scripts/` 中所收案例脚本及本地导入辅助脚本与主代码包采用同一当前文件字节，其 SHA256 记入外部清单。

本包不携带 vendor 二进制目录。执行代码前请依照 06 代码包的 requirements 安装依赖，其中 Shapely 固定为 `shapely==2.1.2`。脚本将不存在的 `ROOT/vendor` 加入搜索路径不妨碍使用已安装的对应依赖。

案例查看页和保存的证据可独立阅读；完整脚本复现还需要 04 输入包中的源快照、正常化输入所用数据和所引用缓存，以及相应规范化路径结果。三个普通案例的 `CURRENT_POOL_FULL_INPUT.json.gz`、`CURRENT_PATH_PREFIX_VALUES.csv.gz` 和保存端点均已包含，但现有复现脚本仍按项目标准目录读取源材料。本案例包不宣称独立包含全库数据或完整运行环境。

当前图表和统计结果没有被打包操作改变。已存在团队的诊断回放与新科学团队/新随机路径分别记账；原历史来源位于 `legacy_evidence/` 时保留其原日期、原口径与原说明。

## 验证清单

本包 SHA256、ZIP CRC、内层 gzip 完整 EOF/CRC、内层 ZIP CRC 与表格可读性记录位于统一交付清单 `stage09_delivery/CASE_PACKAGE_MANIFEST.csv` 和 `CASE_PACKAGE_VALIDATION.json`。这两份外部文件给出封装后的实际成员与哈希，不将临时渲染页、缩略图、Python 字节码缓存纳入交付。
''',encoding='utf8')
    files=[];excluded=[]
    for root in ROOTS:
        for p in sorted((ROOT/root).rglob('*')):
            if not p.is_file():continue
            why=exclude(p)
            if why:excluded.append(dict(path=str(p.relative_to(ROOT)),reason=why))
            else:files.append(p)
    files.extend(ROOT/'scripts'/s for s in SCRIPTS)
    files.append(note);files=sorted(set(files),key=lambda p:str(p.relative_to(ROOT)))
    assert all(p.is_file() for p in files)
    assert not any('vendor' in p.relative_to(ROOT).parts for p in files)
    pre={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
    fd,tmpname=tempfile.mkstemp(prefix='.05_Cases_and_Evidence.',suffix='.writing',dir=DELIVERY);os.close(fd)
    temp=Path(tmpname)
    try:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for p in files:
                rel=str(p.relative_to(ROOT));data=p.read_bytes()
                assert len(data)==pre[rel]['bytes'] and hashlib.sha256(data).hexdigest()==pre[rel]['sha256'],'Source changed during packaging: '+rel
                zi=zipfile.ZipInfo(PREFIX+rel,date_time=(2026,10,31,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o644<<16
                z.writestr(zi,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        os.replace(temp,DEST)
    finally:
        if temp.exists():temp.unlink()
    rows=[];nested=[]
    with zipfile.ZipFile(DEST) as z:
        names=z.namelist();assert len(names)==len(set(names))
        assert all(n.startswith(PREFIX) for n in names)
        assert z.testzip() is None,'Outer ZIP CRC failed'
        for zi in z.infolist():
            assert not zi.is_dir();rel=zi.filename[len(PREFIX):];data=z.read(zi)
            sha=hashlib.sha256(data).hexdigest();assert sha==pre[rel]['sha256']
            assert len(data)==pre[rel]['bytes']==zi.file_size
            check=inspect_compressed(zi.filename,data,nested)
            rows.append(dict(archive_member=zi.filename,source_relative_path=rel,category=category(rel),
                bytes=len(data),compressed_bytes=zi.compress_size,sha256=sha,zip_crc32=f'{zi.CRC:08x}',
                zip_crc_verified=True,source_bytes_unchanged=True,**check))
    # Check source files again after all archival reads; packaging is read-only.
    source_changed=[]
    for p in files:
        rel=str(p.relative_to(ROOT))
        if hashlib.sha256(p.read_bytes()).hexdigest()!=pre[rel]['sha256']:source_changed.append(rel)
    assert not source_changed,source_changed
    manifest=META/'CASE_PACKAGE_MANIFEST.csv'
    with manifest.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    receipt=dict(archive=str(DEST.relative_to(ROOT)),archive_prefix=PREFIX,
        archive_bytes=DEST.stat().st_size,archive_sha256=hashlib.sha256(DEST.read_bytes()).hexdigest(),
        archive_members=len(rows),uncompressed_payload_bytes=sum(x['bytes'] for x in rows),
        outer_zip_crc_all_members_passed=True,all_member_SHA256_match_sources=True,source_files_changed=source_changed,
        gz_members=sum(x['gzip_eof_verified'] for x in rows),all_inner_gzip_EOF_and_CRC_passed=True,
        inner_zip_members=sum(x['inner_zip_crc_verified'] for x in rows),all_inner_zip_CRC_passed=True,
        readable_CSV_tables=sum(x['table_readable'] for x in rows),readable_JSON_files=sum(x['json_readable'] for x in rows),
        nested_compressed_checks=nested,excluded_files=excluded,vendor_included=False,
        requirements='06 code package requirements, including shapely==2.1.2; required 04 inputs and normalized path tables',
        scientific_or_visual_checks_repeated=False,case_source_files_modified=False,
        manifest=str(manifest.relative_to(ROOT)),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        source_commit='e1873bfadc1d0e61499809c91fba9dc39c717f83',uploaded=False)
    (META/'CASE_PACKAGE_VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:receipt[k] for k in ['archive','archive_bytes','archive_sha256','archive_members',
        'uncompressed_payload_bytes','gz_members','inner_zip_members','readable_CSV_tables','readable_JSON_files',
        'manifest_sha256','source_files_changed','vendor_included','uploaded']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
