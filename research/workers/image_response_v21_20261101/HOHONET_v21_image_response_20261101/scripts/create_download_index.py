"""Create the public delivery index from successful, locally retained receipts.

This administrative script does not upload or modify any scientific result.
Raw transfer metadata is never copied into the public index.
"""
from pathlib import Path
import csv,hashlib,html,json

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage09_delivery'

def role(name):
    if name=='HOHONET_IMAGE_RESPONSE_REPORT_ZH.pdf':return ('先读','12页中文综合报告；规则、分母、主要结果、反例和正文回连。')
    if name=='HOHONET_IMAGE_RESPONSE_REPORT_ZH.html':return ('先读','同一综合报告的自包含HTML，图像嵌入，可离线阅读。')
    if name=='IMAGE_RESULTS_INDEX_ZH.html':return ('先读','可按图名/难度筛选的206图简明结果索引。')
    if name=='MANUAL_206_IMAGE_RESULTS.csv':return ('逐图结果','206图容量、k/N、质量、状态、几何、各类起点及无判定原因。')
    if name=='DOORWAY_85_POOL_RESULTS.csv':return ('逐图结果','17图×5池定义，包括13个空池；分空间、容量和有效分母分别保存。')
    if name=='Manual_206_Image_Atlas.pdf':return ('先读','206页普通Manual逐图曲线，每图一页。')
    if name=='Doorway_17_Image_Atlas.pdf':return ('先读','17页门洞逐图曲线，当前584/439及各合法空间单列。')
    if name.startswith('02_'):return ('完整结果','报告、全部统计/敏感性、逐图/逐人数表、PNG/PDF/SVG及绘图数据；包含两份图册。')
    if name.startswith('03_'):return ('完整逐路径结果','逐路径质量/结构变化事件的独立ZIP之一；四包合计337张gzip表。')
    if name.startswith('04_'):return ('冻结复现输入','必要的精确成员、路径端点投影、参考、几何目录、索引与现成精度带；三包合并使用。')
    if name.startswith('05_'):return ('机制证据','五个完整案例，原图、全部原答、精确团队、参考、几何、候选票、连接轨迹、离线查看页。')
    if name.startswith('06_'):return ('复现代码','全部本轮代码、requirements、中文复现说明、上游依赖、验证清单和报告字体。')
    if name.startswith('07_'):return ('完整逐路径结果','门洞几何相邻步、间隔步、到实际满员和初始匹配距离事件；精确U汇总在02包。')
    if name.startswith('01_'):return ('历史检查点','研究中途已保存的来源锁与几何检查点；最终结论以02包与综合报告为准。')
    return ('其它','研究交付文件')

def main():
    receipt_paths=[ROOT/'stage01_intake/CHECKPOINT_UPLOAD_RECEIPT.json']+[OUT/n for n in [
        'PATH_EVENT_UPLOAD_RECEIPT.json','INPUT_UPLOAD_RECEIPT.json',
        'FINAL_RESULTS_UPLOAD_RECEIPT.json','CODE_UPLOAD_RECEIPT.json']]
    rows=[]
    for p in receipt_paths:
        d=json.loads(p.read_text());rr=d.get('results',[d])
        for x in rr:
            assert x.get('status')=='succeeded',x
            f=Path(x['local_path']);assert f.is_file(),f
            assert x.get('local_metadata_applied') is True
            nm=x['file_name'];cat,desc=role(nm)
            rows.append({'file_name':nm,'category':cat,'description_zh':desc,
                'relative_path':f.relative_to(ROOT).as_posix(),'bytes':f.stat().st_size,
                'MiB':round(f.stat().st_size/(1024**2),3),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
                'library_file_id':x['library_file_id'],
                'url':'https://chatgpt.com/library?file_id='+x['library_file_id']+'&account_id=personal',
                'library_saved':True,'local_identity_applied':True})
    assert len(rows)==len({r['library_file_id'] for r in rows})==len({r['file_name'] for r in rows})
    order=['先读','逐图结果','完整结果','机制证据','复现代码','完整逐路径结果','冻结复现输入','历史检查点','其它']
    rows.sort(key=lambda r:(order.index(r['category']),r['file_name']))
    with (OUT/'DELIVERY_FILE_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (OUT/'LIBRARY_FILES_PUBLIC.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    validations=[]
    for n in ['PATH_EVENT_PACKAGE_VALIDATION.json','REPRODUCTION_INPUT_PACKAGE_VALIDATION.json',
              'RESULTS_PACKAGE_VALIDATION.json','CASE_PACKAGE_VALIDATION.json',
              'GEOMETRY_EVENT_PACKAGE_VALIDATION.json','CODE_PACKAGE_VALIDATION.json',
              'CROSS_PACKAGE_FINAL_CHECK.json','REPORT_PRESENTATION_QA.json','MINIMUM_INPUT_REPRO_CHECK.json']:
        p=OUT/n;d=json.loads(p.read_text())
        validations.append({'file':n,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'result':d})
    summary={'analysis_id':ROOT.name,'commit':'e1873bfadc1d0e61499809c91fba9dc39c717f83',
        'status':'completed_and_saved','downloadable_research_files':len(rows),
        'new_research_team_count':0,'new_natural_path_count':0,
        'public_manifest_excludes_itself_and_this_index':True,'validations':validations}
    (OUT/'FINAL_DELIVERY_VALIDATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    parts=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>HOHONET v2.1研究下载清单</title><style>body{max-width:1180px;margin:36px auto;padding:0 24px;font-family:system-ui,sans-serif;line-height:1.8;color:#234}h1{font-size:30px}h2{margin-top:34px;border-bottom:2px solid #d9e7ee}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d7e1e7;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#eaf2f6}.sha{font-family:monospace;font-size:11px;color:#607180}a{color:#126799}pre{white-space:pre-wrap;background:#f3f7fa;padding:16px}</style><h1>HOHONET v2.1逐图人数响应与稳定性研究<br>完整下载清单</h1>',
      '<p>普通Manual 206图、22楼，每池256条随机进入路径；门洞17图，固定584份筛前／439份筛后。冻结仓库提交：<code>e1873bfadc1d0e61499809c91fba9dc39c717f83</code>。</p>',
      '<p>直接阅读：综合报告 → 逐图索引 → 两份图册。查机制：05案例包。查看完整研究结果：02结果包。重做统计：04三份输入包 + 06代码包。03四份与07保存完整新增逐路径结果，不是重做统计的前置输入。</p>',
      '<p>所有ZIP都是独立普通ZIP，不是分卷压缩。解压到同一上级目录，内部共同前缀为 <code>HOHONET_v21_image_response_20261101/</code>；重复路径已经逐项核对内容一致。若要保留原交付并重新执行，请复制工作目录。各包中未评分保持缺失，不填0。</p>',
      '<p>02已含报告、两份图册、全部PNG/PDF/SVG与绘图数据；独立PDF/CSV下载用于便捷阅读。04提供从冻结端点重做本轮下游的输入，05提供五个完整机制案例；全部206图的原始全景和全历史融合缓存仍依赖06登记的上游包，本交付不声称自包含整个仓库。</p>']
    for cat in order:
        rr=[r for r in rows if r['category']==cat]
        if not rr:continue
        parts.append('<h2>'+cat+'</h2><table><tr><th>文件</th><th>MiB</th><th>内容与SHA-256</th></tr>')
        for r in rr:
            parts.append('<tr><td><a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['file_name'])+'</a></td><td>'+str(r['MiB'])+'</td><td>'+html.escape(r['description_zh'])+'<br><span class="sha">'+r['sha256']+'</span></td></tr>')
        parts.append('</table>')
    parts.append('<h2>验证与边界</h2><p>外层ZIP CRC、每个内部gzip的完整EOF读取、表结构与原文件哈希均已验证。05中的内层ZIP也完整通过CRC。PDF共12页报告、206页普通图册和17页门洞图册；正文图表已检查可读性。逐文件清单记录精确字节、SHA-256和Library下载标识。路径次数不作为独立图片，跨人数汇总采用已登记的共同图片面板。</p><p>研究文件清单不含本清单自身，以避免递归哈希。阶段检查点保留其历史身份，不覆盖最终成果。</p></html>')
    (OUT/'DOWNLOAD_INDEX_ZH.html').write_text('\n'.join(parts),encoding='utf-8')
    print(json.dumps({'research_files':len(rows),'saved_files_all_succeeded':True,'index':'stage09_delivery/DOWNLOAD_INDEX_ZH.html'}))

if __name__=='__main__':main()
