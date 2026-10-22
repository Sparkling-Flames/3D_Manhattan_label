"""Build the research core package, readable report export and real file index.

The source report stays in its established repository location. The standalone
copy only resolves links for direct reading. No remote upload/publication here.
"""
from pathlib import Path
import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import shutil
import zipfile
from urllib.parse import quote

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
COMMIT='ef148c82df18582228b2d23837faa2659e79eba7'
REPORT=REPO/'docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'
CORE_NAME='HOHONET_人员分类构成_主报告标签机制与代码_20261022.zip'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def put(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('wb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def js(path,data):
    put(path,json.dumps(data,ensure_ascii=False,indent=2).encode('utf8'))


def valid(path):
    return path.is_file() and not any(x in ('__pycache__','.git') for x in path.parts) and not path.name.endswith(('.tmp','.partial','.pyc'))


def make_csv(path,rows):
    import io
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    put(path,s.getvalue().encode('utf-8-sig'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--destination',type=Path,required=True);ap.add_argument('--recovery-root',type=Path)
    args=ap.parse_args();dest=args.destination.resolve();dest.mkdir(parents=True,exist_ok=True)
    # Historical origins recorded without repackaging the large old archives.
    recovered=[]
    if args.recovery_root:
        for name in ['v3_finite','n20']:
            p=args.recovery_root/name/'RECOVERED_SOURCE_MANIFEST.json'
            if p.exists():
                data=json.loads(p.read_text())
                for row in data:
                    row=dict(row)
                    for key in ['recovered_to','destination']:
                        if key in row:
                            row[key]=str(Path(row[key]).relative_to(args.recovery_root.resolve()))
                    recovered.append(dict(source_family=name,**row))
        js(HERE/'SOURCE_RECOVERY_INDEX.json',{'source_main':COMMIT,'archives':recovered,
             'note':'Original filenames and hashes retained. Output results included in new packages; historical archives are not duplicated.'})
    # Reviewable document change relative to the exact read main.
    before=(HERE/'inputs/MAIN_REPORT_BEFORE.md').read_text()
    current=REPORT.read_text()
    patch=''.join(difflib.unified_diff(before.splitlines(True),current.splitlines(True),
            fromfile='a/'+str(REPORT.relative_to(REPO)),tofile='b/'+str(REPORT.relative_to(REPO))))
    put(HERE/'integration/MAIN_REPORT_CHANGE.patch',patch.encode('utf8'))
    # Main report links: verify current artifacts; historical repository references
    # can be sparse locally but must exist in the frozen git tree if supplied.
    treefile=REPO.parent/'repo_tree_paths.txt'
    tree=set(treefile.read_text().splitlines()) if treefile.exists() else set()
    refs=[];broken=[];exports={}
    known={
      'configurations/CONFIGURATION_OVERVIEW_manual.csv.gz':'HOHONET_Manual全部10094配比格_20261022.csv.gz',
      'configurations/CONFIGURATION_OVERVIEW_semi.csv.gz':'HOHONET_Semi全部3312配比格_20261022.csv.gz',
      'configurations/EXAMPLE_manual_structure_DISTRIBUTIONS.png':'HOHONET_Manual结构_完整配比与成员分布.png',
      'configurations/EXAMPLE_semi_joint_DISTRIBUTIONS.png':'HOHONET_Semi联合_完整配比与成员分布.png',
      'exchanges/ALL_CONDITIONS.csv':'HOHONET_严格ABC全部85条件_20261022.csv',
      'exchanges/COMMON_QT_CONDITIONS.csv':'HOHONET_严格ABC共同QT分母_20261022.csv',
      'exchanges/legacy_n20/PARENT_FIXED_M_RESPONSE.csv':'HOHONET_旧n20父内全部76规模条件_20261022.csv',
      'direct_ac/CONDITION_COMPARISON.csv':'HOHONET_直接换类全部461条件.csv',
      'integration/有效换类条件表.csv':'HOHONET_有效换类18条件_20261022.csv',
      'integration/METHOD_SELECTION_AND_COVERAGE.csv':'HOHONET_11家族分类采用与覆盖_20261022.csv',
      'integration/RECOMMENDED_CONDITION_MEMBERS_BY_FOLD.csv':'HOHONET_重点条件逐折实际成员_20261022.csv',
      'difficulty/exchange_difficulty_core.csv':'HOHONET_全部201换类难度条件_20261022.csv',
      'difficulty/case_7y13_background/ERP_BEV_three_paths.png':'HOHONET_7y13真实ERP与背景正反机制_20261022.png',
      'difficulty/case_qdown_pa4/RAW_BLOCKS_AND_ABC_BEV.png':'HOHONET_pa4原答块与定位换类机制_20261022.png',
    }
    for rel,out in known.items():
        src=HERE/rel;target=dest/out
        assert src.exists(),src
        if not target.exists() or sha(src)!=sha(target):shutil.copyfile(src,target)
        exports[src.resolve()]=target
    # These are useful independently even when the main report cites a parent entry.
    extra={
      'inputs/four_main/ALL_CLASS_MEMBERS_EXPLAINED.csv':'HOHONET_四分类ALL完整成员与解释_20261022.csv',
      'inputs/four_main/ALL_METHOD_LABELS_LOBO.csv.gz':'HOHONET_实际楼外人员标签5456行_20261022.csv.gz',
      'integration/RECOMMENDED_STRICT_CONDITIONS.csv':'HOHONET_推荐条件全部分项与分母_20261022.csv',
      'exchanges/finite_pair_comparison/FINITE_PAIR_SELECTED_ZH.csv':'HOHONET_同背景同规模配比比较精选_20261022.csv',
      'difficulty/case_qdown_pa4/DIFFICULTY_SUPPORT_AND_RISK.csv':'HOHONET_困难快类方向真实失败与损失_20261022.csv',
      'difficulty/case_7y13_background/ALL_924_quality_change.png':'HOHONET_7y13全部924背景路径_20261022.png',
      'REPRODUCE.md':'HOHONET_复现与恢复说明_20261022.md',
    }
    for rel,out in extra.items():
        src=HERE/rel;target=dest/out;assert src.exists(),src
        if not target.exists() or sha(src)!=sha(target):shutil.copyfile(src,target)
        exports[src.resolve()]=target
    def replacement(match):
        link=match.group(2)
        if re.match(r'^(?:https?://|sandbox:|#|mailto:)',link): return match.group(0)
        base,sep,fragment=link.partition('#')
        path=(REPORT.parent/base).resolve()
        try: relative=path.relative_to(REPO).as_posix()
        except ValueError: broken.append(link);return match.group(0)
        isnew=path.is_relative_to(HERE)
        exists=path.is_file() or relative in tree
        refs.append(dict(link=link,repository_path=relative,current_round=isnew,exists_or_in_frozen_tree=exists))
        if not exists: broken.append(link);return match.group(0)
        if isnew:
            if path not in exports:
                target=dest/('HOHONET_evidence_'+path.relative_to(HERE).as_posix().replace('/','__'))
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target);exports[path]=target
            out='sandbox:'+str(exports[path])
        else:
            out='https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/'+COMMIT+'/'+quote(relative,safe='/')
        if sep:out+='#'+fragment
        return match.group(1)+'('+out+')'
    rendered=re.sub(r'(!?\[[^\]]*\])\(([^)]+)\)',replacement,current)
    assert not broken,broken
    report_export=dest/REPORT.name
    put(report_export,rendered.encode('utf8'))
    js(HERE/'integration/REPORT_LINK_CHECK.json',{'source_commit':COMMIT,'report':str(REPORT.relative_to(REPO)),
         'references':refs,'broken_links':broken,'standalone_link_rewriting_only':True})
    # Index the actual complete research tree, omitting self-referential manifests.
    skip={'COMPLETE_FILE_INDEX.csv','FINAL_RECEIPT.json','DELIVERY_CORE_MANIFEST.json'}
    files=sorted(p for p in HERE.rglob('*') if valid(p) and p.name not in skip)
    rows=[dict(path=p.relative_to(REPO).as_posix(),bytes=p.stat().st_size,sha256=sha(p),
         module=p.relative_to(HERE).parts[0]) for p in files]
    make_csv(HERE/'COMPLETE_FILE_INDEX.csv',rows)
    js(HERE/'FINAL_RECEIPT.json',dict(status='completed_scope_with_actual_outputs',source_commit=COMMIT,
        required_commit='ef148c82d',data_version='real_v2',main_report=str(REPORT.relative_to(REPO)),
        new_native_fusion=0,new_quality_scores=0,new_classification_fits=0,
        configuration_cells=13406,unique_panel_endpoints=310458,finite_panel_pair_opportunities=143279136,
        strict_registered_events=146031,strict_physical_ABC=138244,strict_conditions=85,
        legacy_n20_events=271331,legacy_parent_scale_conditions=76,direct_AC_events=2056,direct_AC_conditions=461,
        difficulty_conditions=201,recommended_conditions=18,recommended_fold_image_member_rows=523,
        current_artifact_files=len(rows),current_artifact_bytes=sum(x['bytes'] for x in rows),
        main_report_links_valid=True,scope_not_done=['whole_image_pool_all_member_sets_and_all_backgrounds',
          'all_random_entry_orders','new_semi_difficult_image_collection','new_same_room_prediction'],
        saved_data_not_index_only=True))
    # Core excludes large already-delivered modules. Their hashes remain indexed.
    core=sorted(p for p in HERE.rglob('*') if valid(p) and p.relative_to(HERE).parts[0] not in ('configurations','direct_ac','exchanges')
                and p.name!='DELIVERY_CORE_MANIFEST.json')+[REPORT]
    core_manifest=[dict(path=p.relative_to(REPO).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in core]
    js(HERE/'DELIVERY_CORE_MANIFEST.json',{'source_commit':COMMIT,'files':core_manifest,
         'other_modules_delivered_in':['stage02','stage03A','stage03B'],'no_full_original_image_archive':True})
    core.append(HERE/'DELIVERY_CORE_MANIFEST.json')
    target=dest/CORE_NAME;temp=target.with_name(target.name+'.tmp')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in core:z.write(p,p.relative_to(REPO).as_posix())
    with zipfile.ZipFile(temp) as z: assert z.testzip() is None
    os.replace(temp,target)
    # Package index lists only real files, with correct extraction roots.
    package_names=[
       ('HOHONET_四分类完整混合配比与大块AC_阶段02_20261022.zip','research/workers/','Full finite configurations/endpoints and direct AC'),
       ('HOHONET_personnel_stage03A_exchanges_v2data_20261022.zip','.','Complete strict ABC and legacy n20'),
       ('HOHONET_personnel_stage03B_finite_pairs_v2data_20261022.zip','.','All finite matched-pair background statistics'),
       (CORE_NAME,'.','Updated existing main report, labels, recommendations, difficulty, cases and source/code index')]
    packages=[]
    for name,extract,use in package_names:
        p=dest/name;assert p.exists(),p
        packages.append(dict(file=name,bytes=p.stat().st_size,sha256=sha(p),extract_under_repository=extract,purpose=use))
    standalone=[dict(file=str(p.relative_to(dest)),bytes=p.stat().st_size,sha256=sha(p),source=str(s.relative_to(REPO)))
                for s,p in sorted(exports.items(),key=lambda x:str(x[1]))]
    standalone.append(dict(file=report_export.name,bytes=report_export.stat().st_size,sha256=sha(report_export),
                       source=str(REPORT.relative_to(REPO))+' (links resolved only)'))
    manifest=dest/'HOHONET_最终下载与实际文件索引_20261022.json'
    js(manifest,dict(source_commit=COMMIT,data_version='real_v2',packages=packages,standalone_files=standalone,
         previous_stage01='Retained historical checkpoint; superseded by the four complete packages, no need to download for current full results.',
         note='No public repository push or external publication. Exact archive files exist; stage manifests contain per-file checksums.'))
    index=dest/'HOHONET_下载入口与成果定位_20261022.md'
    body=['# HOHONET 人员分类与混合构成：下载入口','',f'实际读取提交：`{COMMIT}`。真人v2。主报告沿用既有文件，本轮已完成当前支持范围内的比较与采用。',
      '',f'- [中文主报告]({report_export.name})',
      '- [18个有效/风险换类条件](HOHONET_有效换类18条件_20261022.csv)',
      '- [11家族分类采用与覆盖](HOHONET_11家族分类采用与覆盖_20261022.csv)',
      '- [四分类完整ALL成员](HOHONET_四分类ALL完整成员与解释_20261022.csv)',
      '- [重点条件逐折实际成员](HOHONET_重点条件逐折实际成员_20261022.csv)',
      '- [全部201个难度条件](HOHONET_全部201换类难度条件_20261022.csv)',
      '- [同背景同规模比较精选](HOHONET_同背景同规模配比比较精选_20261022.csv)',
      '', '## 完整包','', '|文件|字节|解压位置|内容|','|---|---:|---|---|']
    for row in packages:body.append(f"|[{row['file']}]({row['file']})|{row['bytes']:,}|`{row['extract_under_repository']}`|{row['purpose']}|")
    body += ['', '主报告和关键表可单独取得，完整逐事件、成员关联、端点与背景分片在上述实际文件包。阶段01保留为先前检查点，完整接续无需再次下载。',
      '', '## 复用与新增','',
      '复用：原标签、真实原答、现有确定性端点、质量分项、既有共同域QT与背景/规模控制。',
      '本轮新增分析：13,406完整配比分布、143,279,136有限配对机会的同背景同m比较、全方向85条件与旧n20/直接AC整理、201难度格、实际原答条件解释和机制呈现。',
      '新增融合/评分/拟合标签均为0。有限面板完整不等于所有图片全人员池或所有进入顺序。',
      '', '## 精确查找','',
      '主报告第4.5—4.10节对应本轮。完整源码及表路径见研究目录的 COMPLETE_FILE_INDEX.csv；源包、数据版本和标签身份见 SOURCE_RECOVERY_INDEX.json、inputs/SOURCE_MANIFEST.csv。每ZIP内另有逐文件SHA256清单。',
      '', '- [完整下载文件及哈希](HOHONET_最终下载与实际文件索引_20261022.json)',
      '- [复现与恢复说明](HOHONET_复现与恢复说明_20261022.md)',
      '', '本轮未新开展全部随机前缀、Semi困难图采集或同房预测；原图全集、虚拟环境与重复旧大缓存不随包交付。']
    index_text='\n'.join(body)
    index_text=re.sub(r'(\[[^\]]*\])\(([^)]+)\)',lambda m:m.group(1)+'(sandbox:'+str(dest/m.group(2))+')',index_text)
    put(index,index_text.encode('utf8'))
    new_uploads=set(exports.values())|{report_export,target,manifest,index}
    # Large already-saved stages are excluded, while selected standalone copies
    # may be uploaded or replaced by the caller using official Library tools.
    js(dest/'FINAL_SAVE_CANDIDATES.json',{'paths':[str(p) for p in sorted(new_uploads)]})
    print(json.dumps({'core_bytes':target.stat().st_size,'core_files':len(core),'standalone_files':len(standalone),
        'indexed_research_files':len(rows),'main_report_bytes':report_export.stat().st_size,'broken_report_links':len(broken)},ensure_ascii=False))


if __name__=='__main__':main()
