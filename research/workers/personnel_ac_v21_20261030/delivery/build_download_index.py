"""Build the final download directory from successful uploads and full-read receipts.

This packages no scientific data and makes no network calls.
"""
from pathlib import Path
import csv, hashlib, html, json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'delivery'
ARCHIVES = [
    ('容量与来源', 'HOHONET_v21_AC_stage01_capacity_and_sources.zip'),
    ('最终冻结设计与精确成员', 'HOHONET_v21_AC_stage02_frozen_design_clean.zip'),
    ('原生完整端点 1/4', 'HOHONET_v21_AC_stage03_native_part01.zip'),
    ('原生完整端点 2/4', 'HOHONET_v21_AC_stage03_native_part02.zip'),
    ('原生完整端点 3/4', 'HOHONET_v21_AC_stage03_native_part03.zip'),
    ('原生完整端点 4/4', 'HOHONET_v21_AC_stage03_native_part04.zip'),
    ('逐事件指标 1/2', 'HOHONET_v21_AC_stage04_metrics_part01.zip'),
    ('逐事件指标 2/2', 'HOHONET_v21_AC_stage04_metrics_part02.zip'),
    ('图楼汇总、难度、严格ABC对照', 'HOHONET_v21_AC_stage05_main_context_strict_bridge.zip'),
    ('成员、背景、人数、整类与联盟敏感性', 'HOHONET_v21_AC_stage05_member_background_sensitivity.zip'),
    ('原图、完整原答、几何与票账案例', 'HOHONET_v21_AC_stage06_mechanism_cases.zip'),
    ('全部研究代码、配置、最小复现输入', 'HOHONET_v21_AC_stage07_code_and_reproduction.zip'),
    ('中文综合报告、名单、数值账本及验收', 'HOHONET_v21_AC_stage08_report_and_evidence.zip'),
]
EXTRAS = [
    ('先读：28页中文报告PDF', 'HOHONET_v21_AC_population_report_ZH.pdf'),
    ('中文报告HTML，自包含', 'HOHONET_v21_AC_population_report_ZH.html'),
    ('人工重点：pa4-11七联盟与35份原答', 'PA4_11_ALLIANCE_VIEWER_ZH.html'),
    ('正、负、小变化与互斥表达案例', 'REPRESENTATIVE_AC_VIEWER_ZH.html'),
    ('固定九人块、只换背景的四端点', 'BACKGROUND_WC2_53_VIEWER_ZH.html'),
    ('pa4-06七联盟、位置与劳动', 'PA4_06_ALLIANCE_VIEWER_ZH.html'),
]


def link(r):
    return 'https://chatgpt.com/library?file_id=' + r['library_file_id'] + '&account_id=personal'


def make_rows(items, lookup):
    result=[]
    for i,(purpose,name) in enumerate(items,1):
        r=dict(lookup[name]);r.update(order=i,purpose=purpose,url=link(r),size_MiB=round(r['bytes']/2**20,3))
        result.append(r)
    return result


def main():
    saved=json.loads((OUT/'UPLOAD_RECEIPTS.json').read_text())
    lookup={r['name']:r for r in saved}
    assert len(lookup)==len(saved),'Ambiguous duplicate uploaded filenames'
    archives=make_rows(ARCHIVES,lookup);extras=make_rows(EXTRAS,lookup)
    readability=[];paths=set();teams=0;events=0;native_pools=set();metric_pools=set()
    for r in archives:
        receipt=json.loads((OUT/(Path(r['name']).stem+'_READABILITY.json')).read_text())
        assert receipt['passed'] and receipt['archive_sha256']==r['sha256'] and receipt['archive_bytes']==r['bytes']
        assert receipt['files']==r['files']
        for item in receipt['checks']:
            assert item['all_bytes_read'] and item['sha256_match']
            path=item['path'];paths.add(path)
            if path.startswith('stage03_endpoints/pools/') and path.endswith('.jsonl.gz'):
                teams+=item['jsonl_rows'];native_pools.add(path.split('/')[2])
            if path.startswith('stage04_metrics/metric_shards/') and path.endswith('.csv.gz'):
                events+=item['csv_rows'];metric_pools.add(Path(path).name.removesuffix('.csv.gz'))
            assert not path.endswith('.partial'),('Recommended archive includes temporary partial',path)
        readability.append(receipt)
    assert teams==478012 and events==471758 and len(native_pools)==258 and len(metric_pools)==258
    refs=json.loads((ROOT/'stage08_report/REPORT_EVIDENCE_INDEX.json').read_text())
    missing_sources=[x['relative_path'] for x in refs.values() if x['relative_path'] not in paths]
    assert not missing_sources,missing_sources
    required=json.loads((OUT/'DELIVERY_REQUIRED_INCLUDE.json').read_text())['required_include']
    assert set(required)<=paths
    ev=json.loads((ROOT/'stage08_report/verification/REPORT_EVIDENCE_VALIDATION.json').read_text());assert ev['passed']
    pv=json.loads((ROOT/'stage08_report/verification/PDF_TEXT_COMPLETENESS_VALIDATION.json').read_text());assert pv['passed']
    vv=json.loads((ROOT/'stage08_report/verification/REPORT_RENDER_VISUAL_QA.json').read_text());assert vv['passed']
    pdf=ROOT/'stage08_report/HOHONET_v21_AC_population_report_ZH.pdf'
    assert hashlib.sha256(pdf.read_bytes()).hexdigest()==lookup[pdf.name]['sha256']==vv['pdf_sha256']
    historical=dict(lookup['HOHONET_v21_AC_stage02_frozen_design.zip']);historical['url']=link(historical)
    payload={'title':'HOHONET v2.1 直接AC与整类人群模拟：完整下载目录','source_commit':'ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff','recommended_archives':archives,'direct_report_and_viewers':extras,'historical_not_recommended':[historical],'recommended_archive_count':len(archives),'recommended_archive_bytes':sum(x['bytes'] for x in archives),'scientific_completion':{'complete':True,'unique_teams':teams,'method_events':events,'native_pools':len(native_pools),'metric_pools':len(metric_pools),'report_sources_covered':len(refs),'required_addendum_files_covered':len(required),'report_evidence_passed':True,'pdf_text_complete':True,'pdf_visual_qa_passed':True,'recommended_archives_have_no_partial_files':True},'extraction':'全部推荐ZIP解压到同一空目录，保留内部相对路径；四原生端点包及两指标包都是独立ZIP，不是分卷，需全部取得才是全域数据。','old_design_notice':'旧设计ZIP仅作历史保留；推荐clean版本不含暂存partial，正式设计数据不变。','verification_files':'所有推荐包均有逐文件SHA/完整读取回执；完整回执集中在DELIVERY_COMPLETION_RECEIPT.json。'}
    (OUT/'DOWNLOAD_INDEX_ZH.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    full={'complete':True,'recommended_archive_names':[x['name'] for x in archives],'completion':payload['scientific_completion'],'total_archive_bytes':payload['recommended_archive_bytes'],'readability_receipts':readability,'report_validation_files':['stage08_report/verification/REPORT_EVIDENCE_VALIDATION.json','stage08_report/verification/PDF_TEXT_COMPLETENESS_VALIDATION.json','stage08_report/verification/REPORT_RENDER_VISUAL_QA.json'],'old_design_is_historical_only':True}
    (OUT/'DELIVERY_COMPLETION_RECEIPT.json').write_text(json.dumps(full,ensure_ascii=False,indent=2)+'\n')
    cols=['order','purpose','name','bytes','size_MiB','sha256','library_file_id','url','files']
    with (OUT/'DOWNLOAD_INDEX.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(archives+extras)
    text=['# '+payload['title'],'','全部研究计算已完成。先读PDF/HTML报告，再按需要下载完整科研包。所有推荐包保存成功且完整读取通过。','',f'推荐科研包共 **{len(archives)} 包，{sum(x["bytes"] for x in archives)/2**30:.3f} GiB**；下列直接报告/查看器是方便阅读的重复入口，不必再次纳入统计。','','## 直接阅读','']
    for r in extras:text.append('- ['+r['purpose']+']('+r['url']+') · '+str(r['size_MiB'])+' MiB')
    text+=['','## 完整科研包','','|序号|内容与下载文件|MiB|包内文件数|','|---|---|---:|---:|']
    for r in archives:text.append(f'|{r["order"]}|{r["purpose"]}：[{r["name"]}]({r["url"]})|{r["size_MiB"]:.3f}|{r["files"]}|')
    text+=['','包内文件数不含每包另附的ARCHIVE_MANIFEST.json。', '',payload['extraction'],'','## 内容完整性','',f'四个原生端点包：258池、{teams:,}支团队；两个逐事件指标包：258池、{events:,}条事件。57项报告来源与11个补充溯源文件均已纳入。报告28页、36表233行、1,432单元格已验证完整。','','正式CSV/gzip/JSON/JSONL全部完整解析，缺Q保留缺失。各包SHA-256与最终文件ID如下；详细逐文件回执见DELIVERY_COMPLETION_RECEIPT.json。','','## SHA-256','']
    for r in archives+extras:text.extend(['### '+r['name'],'','`'+r['sha256']+'`',''])
    text+=['## 历史保留与最小复现','','旧设计包已由clean推荐包接续，旧版仍保留：['+historical['name']+']('+historical['url']+')。它含一个非分析暂存partial，不列入推荐科研包；不能追加到正式设计。旧新逐文件比对表保存在最终报告包。','','最小复现说明、依赖、冻结输入与142项当前提交源码在第12包；实际最小复现已通过23个数值字段、状态及完整几何一致核验。全部分类、参考、空间归属、排除及融合规则保持当前冻结版本。','']
    (OUT/'DOWNLOAD_INDEX_ZH.md').write_text('\n'.join(text))
    esc=html.escape
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(payload['title'])+'</title><style>body{font-family:system-ui,sans-serif;max-width:1120px;margin:36px auto;padding:0 22px;color:#17212c;line-height:1.75}h1{font-size:28px}h2{margin-top:32px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d4dde4;padding:9px;text-align:left;vertical-align:top}th{background:#edf2f6}a{color:#145b91;overflow-wrap:anywhere}code{font-size:12px;overflow-wrap:anywhere}.box{background:#f3f6f8;padding:14px 18px}ul{padding-left:24px}</style><body><h1>'+esc(payload['title'])+'</h1><p>全部研究计算、报告回连和包内读取验证已完成。</p><div class="box">推荐科研包13包，'+f'{payload["recommended_archive_bytes"]/2**30:.3f}'+' GiB。'+esc(payload['extraction'])+'</div><h2>先读报告与具体案例</h2><ul>']
    for r in extras:parts.append('<li><a href="'+esc(r['url'],quote=True)+'">'+esc(r['purpose'])+'</a> · '+str(r['size_MiB'])+' MiB</li>')
    parts+=['</ul><h2>完整科研下载</h2><table><thead><tr><th>#</th><th>内容</th><th>准确文件名与下载</th><th>MiB / 文件数</th></tr></thead><tbody>']
    for r in archives:parts.append('<tr><td>'+str(r['order'])+'</td><td>'+esc(r['purpose'])+'</td><td><a href="'+esc(r['url'],quote=True)+'">'+esc(r['name'])+'</a><br><code>SHA-256 '+r['sha256']+'</code></td><td>'+str(r['size_MiB'])+' / '+str(r['files'])+'</td></tr>')
    parts+=['</tbody></table><p>包内文件数不含每包另附的 ARCHIVE_MANIFEST.json。</p><h2>已验证覆盖</h2><p>258池、478,012支完整团队；同258池、471,758逐事件结果；57项报告来源与11个补充来源全部覆盖。28页报告、36表233行的表内顺序和完整内容通过验证。每个推荐包无partial暂存，均完整读取、SHA核对，并完整解析正式gzip/CSV/JSON/JSONL。</p><h2>历史与解释边界</h2><p>'+esc(payload['old_design_notice'])+' 历史版仍可取：<a href="'+esc(historical['url'],quote=True)+'">'+esc(historical['name'])+'</a>；无需下载或追加。</p><p>直接AC无同类B，不据此估计跨类超过同类；整类不等人数路径不当作与身份无关的纯人数作用；记录劳动不等于墙钟速度；缺Q不填0，完整输出不保证语义正确。详细研究判断见报告。</p><h2>精确校验与复现</h2><p>机器目录为DOWNLOAD_INDEX_ZH.json / DOWNLOAD_INDEX.csv；全包读取回执为DELIVERY_COMPLETION_RECEIPT.json。最小复现、依赖与142项当前提交源码在代码复现包中；正式来源提交 '+payload['source_commit']+'。</p></body></html>']
    (OUT/'DOWNLOAD_INDEX_ZH.html').write_text(''.join(parts),encoding='utf-8')
    print(json.dumps({'complete':True,'archives':len(archives),'archive_bytes':payload['recommended_archive_bytes'],'native_teams':teams,'method_events':events,'report_sources':len(refs),'direct_reading_files':len(extras)},ensure_ascii=False))


if __name__=='__main__':main()
