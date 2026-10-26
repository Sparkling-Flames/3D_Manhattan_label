"""Index real deliveries; default preserves the stage entry, --final is explicit.

No uploads, downloads, fusion or statistics are performed. All final gates are
checked before either existing user-facing index file is replaced.
"""
from pathlib import Path
import argparse,csv,io,json,re

COMMIT='b9bcec809fbaec8ab055931a1abb7baa5db44dac'
EXPECTED_ENDPOINTS=1356657


def require(ok,message):
    if not ok:raise ValueError(message)


def good_readback(r):
    return (isinstance(r,dict) and r.get('every_member_read_to_EOF') is True
        and r.get('inner_gzip_read_to_EOF') is True
        and isinstance(r.get('zip_bytes'),int) and r['zip_bytes']>0
        and re.fullmatch(r'[0-9a-fA-F]{64}',str(r.get('zip_sha256',''))) is not None)


def final_deliveries(d,rows,saved,verified,packages):
    """Read real independent attachments and gate final adoption without writing."""
    path=d/'FINAL_INDIVIDUAL_DELIVERIES.json'
    require(path.is_file(),'Final mode requires '+str(path))
    manifest=json.loads(path.read_text())
    require(manifest.get('schema_version')==1,'Unsupported final manifest schema')
    require(manifest.get('source_commit')==COMMIT,'Final manifest source_commit differs')
    require(manifest.get('ready_for_final') is True,'Final manifest is not ready_for_final')
    by_name={r['filename']:r for r in rows};chosen={}
    choices=manifest.get('final_packages',{})
    require(isinstance(choices,dict),'final_packages must be an object')
    for stage in ['S10','S11']:
        names=[n for n in by_name if '_'+stage+'_' in n]
        selected=choices.get(stage)
        if selected is None:
            require(len(names)==1,'Need one saved '+stage+' ZIP; if multiple exist specify final_packages.'+stage)
            selected=names[0]
        require(selected in names,'Selected '+stage+' has no saved identity: '+str(selected))
        require(saved[selected].get('_is_save_receipt') is True,selected+': no successful UPLOAD/SAVE receipt')
        require(good_readback(verified.get(selected)),selected+': actual DOWNLOADED_ZIP_READBACK with both EOF flags is required')
        chosen[stage]=by_name[selected]
    data=[r for r in rows if '_DATA_' in r['filename']]
    indexed={r['filename'] for r in data};closed={n for n in packages if '_DATA_' in n}
    require(indexed==closed,'All closed DATA packages need saved identities: '+str(sorted(indexed^closed)))
    for row in data:
        name=row['filename'];p=packages[name];check=verified.get(name)
        require(saved[name].get('_is_save_receipt') is True,name+': no successful UPLOAD/SAVE receipt')
        require(good_readback(check),name+': actual downloaded ZIP readback is incomplete')
        require(isinstance(row['unique_new_endpoint_records'],int) and row['unique_new_endpoint_records']>0,name+': missing endpoint count')
        require(check['zip_bytes']==p.get('zip_bytes') and check['zip_sha256'].lower()==str(p.get('zip_sha256','')).lower(),name+': downloaded ZIP differs from PACKAGE_COMPLETE')
    total=sum(r['unique_new_endpoint_records'] for r in data)
    require(total==EXPECTED_ENDPOINTS,f'Final mode needs {EXPECTED_ENDPOINTS:,} verified saved DATA records; found {total:,}')
    entries=manifest.get('deliveries')
    require(isinstance(entries,list) and entries,'No final independent deliveries')
    individuals=[];roles={'primary_report','report','key_table','table','figure','code','other'}
    for i,item in enumerate(entries):
        label='Final independent delivery '+str(i+1)
        require(isinstance(item,dict),label+': object required')
        name=item.get('filename');fid=item.get('library_file_id');version=item.get('delivered_version')
        require(isinstance(name,str) and name and Path(name).name==name,label+': actual basename required')
        require(isinstance(fid,str) and re.fullmatch(r'libfile_[A-Za-z0-9_-]+',fid),label+': actual library_file_id required')
        require(item.get('save_status')=='succeeded',label+': successful save not recorded')
        require(item.get('download_verified') is True,label+': actual download not verified')
        require(isinstance(item.get('bytes'),int) and not isinstance(item['bytes'],bool) and item['bytes']>0,label+': actual byte count required')
        require(re.fullmatch(r'[0-9a-fA-F]{64}',str(item.get('sha256',''))),label+': actual SHA256 required')
        require(isinstance(version,int) and not isinstance(version,bool) and version>=0,label+': actual delivered_version required')
        require(item.get('role') in roles,label+': unsupported role')
        require(isinstance(item.get('purpose_zh'),str) and item['purpose_zh'].strip(),label+': purpose_zh required')
        url='https://chatgpt.com/library?file_id='+fid+'&account_id=personal'
        require(item.get('download_url') in (None,url),label+': URL and identity disagree')
        individuals.append(dict(filename=name,library_file_id=fid,download_url=url,bytes=item['bytes'],
            sha256=item['sha256'].lower(),purpose_zh=item['purpose_zh'],unique_new_endpoint_records=0,
            downloaded_inner_tables_verified='',delivered_version=version,artifact_kind='individual',
            role=item['role'],download_verified=True))
    require(sum(r['role']=='primary_report' for r in individuals)==1,'Exactly one primary_report is required; companion reports use role=report')
    require(any(r['role']=='key_table' for r in individuals),'At least one verified key_table is required')
    combined=rows+individuals
    require(len({r['filename'] for r in combined})==len(combined),'Duplicate delivered filename')
    require(len({r['library_file_id'] for r in combined})==len(combined),'One saved identity assigned to multiple files')
    individuals.sort(key=lambda r:(r['role']!='primary_report',r['role']!='key_table',r['filename']))
    return individuals,chosen


def file_link(row,label=None):
    return '['+(label or row['filename'])+']('+row['download_url']+')'


def final_top(rows,chosen):
    primary=next(r for r in rows if r['role']=='primary_report')
    tables=[r for r in rows if r['role']=='key_table']
    return ['## 当前采用：最新综合报告与最少下载','',
        '**最新独立综合报告：'+file_link(primary)+'**。附件已实际取回核验。','',
        '关键小表：'+'；'.join(file_link(r) for r in tables)+'。','',
        '**最少下载：'+file_link(chosen['S10'],'S10报告代码包')+' + '+file_link(chosen['S11'],'S11完整分析结果包')+'。** 用于完整阅读、汇总接入和重画已保存结果，无须先下载全部端点。','',
        '**完整路径复算：**在S10/S11之外，另加S01完整精确设计、全部DATA_S1与DATA_S2，以及指定main历史输入。各包解压到同一接收根目录，最后解压S10。','',
        'S10为当前采用报告和代码；S11保留全量分析及源表。S00/S04是历史检查点；S05是已完整保存的策略阶段，已接入最终报告，不能用早期代码覆盖S10。S02、FINITE_CASES及ORIGINAL_IMAGE_CASES分别保留六小池、近满员目录及原图机制的独立复算用途，不替代全量DATA。','']


def atomic_text(path,text):
    temporary=path.with_name(path.name+'.writing');temporary.write_text(text,encoding='utf-8');temporary.replace(path)


def purpose(name):
    if '_DATA_' in name:return '本轮新算端点标量、逐队最终几何及必要完整状态'
    if '_S00_' in name:return '计算前冻结设计和方法快照；非当前最终分析代码'
    if '_S01_' in name:return '完整精确顺序、前缀、请求、缓存关联及阶段代码'
    if '_S02_' in name:return '六小池完整目录、真实路径、结果和独立复算'
    if '_S04_' in name:return '计算中的分析代码检查点；最终采用S10最新代码'
    if '_S05_' in name:return '已完成四种历史策略16→32：报告、15张证据表、图和提取代码'
    if '_ORIGINAL_IMAGE_CASES' in name:return '两张Release原图、原答/融合/参考叠加与票账'
    if '_FINITE_CASES' in name:return '三个既定近满员有限目录案例及几何精度'
    if '_S10_' in name:return '当前综合报告、关键表、完整新代码与复现入口'
    if '_S11_' in name:return '完整逐图逐人数分析、策略、几何和精度结果'
    return '本轮成果；用途见包内README'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--final',action='store_true',help='Explicit final adoption after real save/download verification')
    args=ap.parse_args();base=args.base.resolve();d=base/'delivery26'
    saved={}
    for f in sorted(d.glob('*RECEIPT_PRIVATE.json'),key=lambda x:x.stat().st_mtime):
        try:r=json.loads(f.read_text())
        except ValueError:continue
        for item in r.get('results',[]):
            if item.get('status')=='succeeded' and str(item.get('local_path','')).endswith('.zip') and item.get('library_file_id'):
                name=Path(item['local_path']).name
                is_save='UPLOAD' in f.name.upper() or 'SAVE' in f.name.upper()
                if is_save or name not in saved or not saved[name].get('_is_save_receipt'):
                    saved[name]=dict(item,_is_save_receipt=is_save,_receipt_name=f.name)
    verified={}
    for f in sorted(d.glob('*DOWNLOADED_ZIP_READBACK.json'),key=lambda x:x.stat().st_mtime):
        r=json.loads(f.read_text());verified[r['zip_name']]=r
    packages={json.loads(f.read_text())['zip_name']:json.loads(f.read_text()) for f in (d/'endpoint_packages').glob('*/PACKAGE_COMPLETE.json')}
    rows=[]
    for name,item in sorted(saved.items()):
        candidate=verified.get(name);check=candidate if good_readback(candidate) else None;pkg=packages.get(name,{})
        size=(check or pkg).get('zip_bytes')
        if size is None:
            local=Path(item['local_path']);size=local.stat().st_size if local.exists() else 0
        row=dict(filename=name,library_file_id=item['library_file_id'],
            download_url='https://chatgpt.com/library?file_id='+item['library_file_id']+'&account_id=personal',
            bytes=size,
            sha256=(check or pkg).get('zip_sha256',''),purpose_zh=purpose(name),
            unique_new_endpoint_records=pkg.get('unique_new_endpoints',0),
            downloaded_inner_tables_verified=check is not None,
            delivered_version=item.get('current_version_number',0),artifact_kind='zip_package',
            role='package',download_verified=check is not None)
        rows.append(row)
    package_count=len(rows);chosen=None
    if args.final:
        individuals,chosen=final_deliveries(d,rows,saved,verified,packages);rows=individuals+rows
    fields=['filename','library_file_id','download_url','bytes','sha256','purpose_zh','unique_new_endpoint_records','downloaded_inner_tables_verified','delivered_version','artifact_kind','role','download_verified']
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    lines=['# HOHONET 人数曲线追加：当前交付入口','',
        '实际来源 main：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`；真人 v2。',
        '']
    if args.final:lines+=final_top(rows,chosen)
    lines += ['## 当前可取得文件','',
        '| 文件 | MiB | 用途 | 实际下载后的内部读回 |',
        '|---|---:|---|---|']
    for r in rows:
        status=('已实际取回，bytes与SHA256已核验' if r['artifact_kind']=='individual' else
            ('已完整读取CSV/gzip/JSON至EOF' if r['downloaded_inner_tables_verified'] else '已保存；实际取回核验待完成'))
        lines.append('| '+file_link(r)+' | '+format(r['bytes']/1048576,'.2f')+' | '+r['purpose_zh'].replace('|','／').replace('\n',' ')+' | '+status+' |')
    total=sum(r['unique_new_endpoint_records'] for r in rows)
    progress=('全部已保存且实际取回验证的DATA分片合计 **'+format(total,',')+'** 个新增端点结果记录；失败和延期状态保留，端点数不等于独立路径或图片数。' if args.final else
        '已保存的新算端点分片覆盖 **'+format(total,',')+'** 个结果记录；科学汇总使用完整固定支持，不能用完成先后的这些池代表总体。')
    stage_note=('S10是当前采用；S00/S04保留历史检查点，S05保留完整策略阶段身份。新增DATA按阶段和分片号完整合并读取；旧main大表按固定版本引用，不重复打包。' if args.final else
        'S00保留计算前身份；S01保存完整设计；S02及两个案例包是已经完成的有限子域。S04为历史代码检查点，S05为完整策略阶段。最终综合报告与代码包完成并实际取回验证后才以--final切换采用入口。新增DATA按阶段和分片号全部合并读取；旧main大表按固定版本引用，不重复打包。')
    lines += ['', progress,
        '', '## 完整计划与阶段关系','',
        '194个Manual池（177普通、17门洞）各新增208条独立完整自然顺序，主比较旧48与独立新208、合256。53个旧重点池的额外48只作为304条敏感性；四种旧V3角色策略另有16个新配对基础顺序，比较旧16与新16、合32。',
        '', '精确登记：50,400条新自然／策略路径、1,644,576次前缀出现、1,396,509个去重团队，其中39,852队复用，1,356,657队为本轮新增端点请求。请求量与实际完成量分别登记；两人延期不冒称实际共识失败。',
        '', stage_note,
        '', '仓库相对根路径：`research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/`。',
        '', '## 可单独阅读的已完成报告','',
        '- [第一批104条完整追加的固定157图精度表（阶段检查点）](https://chatgpt.com/library?file_id=libfile_c529199a8d8c8191a629903c16cd3c3b&account_id=personal)',
        '- [已完成四种历史策略16→32报告](https://chatgpt.com/library?file_id=libfile_2452307baac481919bd3aa72e37cbfe3&account_id=personal)',
        '- [六小池精确抽样对照](https://chatgpt.com/library?file_id=libfile_3de753684a688191b7a15f8c938b7db1&account_id=personal)',
        '- [三个近满员有限目录案例](https://chatgpt.com/library?file_id=libfile_8d048cb7eb1c8191b2d9df228c55140a&account_id=personal)',
        '- [Release原图机制解释](https://chatgpt.com/library?file_id=libfile_d892f38a8a148191a69815f2fe9b2acf&account_id=personal)',
        '', '完整文件名、SHA256和实际保存身份见同目录 `CURRENT_VALID_FILES.csv`。']
    # All final validation and rendering succeed before either current file is written.
    atomic_text(d/'CURRENT_VALID_FILES.csv',s.getvalue())
    atomic_text(d/'CURRENT_ENTRY_ZH.md','\n'.join(lines)+'\n')
    print(json.dumps(dict(final_mode=args.final,saved_packages=package_count,individual_deliveries=len(rows)-package_count,
        saved_new_endpoint_records=total,download_checked_packages=sum(bool(r['downloaded_inner_tables_verified']) for r in rows))))


if __name__=='__main__':main()
