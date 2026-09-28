"""复用二审Studio与冻结分簇，生成独立定向补审入口。"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'analysis_results/review_reconciliation_20260925'
OUT=ROOT/'analysis_results/review_return_20260927'
INPUT=Path('C:/Users/ASUS/Downloads/全历史标注_二次复核_20260925(2).json')
HERE=Path(__file__).parent

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def build():
    audit=read(OUT/'audit.json')
    notes=read(HERE/'review_return_notes_20260927.json')
    baseline=read(INPUT)
    text=(OLD/'data.js').read_text(encoding='utf-8')
    data=json.loads(text.split('window.STUDIO_DATA=',1)[1].split(';\nwindow.STUDIO_IMAGES=',1)[0])
    data['return_review']={'baseline':baseline,'legacy_binding':data['binding'],'summary':audit['summary']}
    data['binding']={'id':'review_return_20260927_v1'}
    note_rows=notes['comments']
    questions=notes.get('questions',[])
    comment_pending=read(OUT/'comment_pending.json')['rows']
    trap_inventory=read(OUT/'trap_inventory.json')
    additional_issues=read(OUT/'coverage_semantics.json')['additional_issues']
    all_issues=set()
    variant_count=0
    for c in data['cases']:
        iid=c['image_id']; info=audit['images'].get(iid,{})
        background=[i for i in info.get('issues',[]) if i['kind']=='room_comparison']
        issues=[i for i in info.get('issues',[]) if i['kind']!='room_comparison']
        for item in additional_issues:
            if item['image_id']==iid:
                issues.append({'kind':item['kind'],'title':item['title'],'annotation_ids':item['annotation_ids'],'evidence':item['evidence']})
        for row in comment_pending:
            if row['image_id']==iid:
                issues.append({'kind':'undecided','title':'评论仍未定：'+row['reason'],'annotation_ids':[row['annotation_id']] if row.get('annotation_id') else [],'evidence':row})
        for n,q in enumerate(questions):
            if q.get('image_id')==iid or iid in q.get('image_ids',[]):
                item={'id':f"{q.get('id','semantic:'+str(n))}:{iid}",'kind':q.get('kind','consistency'),'title':q.get('title',q.get('question','评论含义需核对')),'annotation_ids':[a for a in q.get('annotation_ids',[]) if a in c['review']['annotation_ids']],'evidence':q}
                if q.get('id') in ['model_correction_consistency','doorframe_within_image','wall_change_within_image']:
                    item['kind']='contradiction';issues.append(item)
                elif q.get('id')=='conditional_cluster_repair':issues.append(item)
                else:background.append(item)
        if c['code']=='yqstnuAEVhm-04':
            issues.append({'kind':'semantic','title':'评论中“原始GT”和“MP3D原始标注”指同一版本吗？先确认所指参考，保留空间取舍。','annotation_ids':[],'evidence':baseline['image_decisions'][iid]})
        # 同一图同类问题合成一张卡；原子证据全部保留，不把对照成员算成额外待审任务。
        grouped={}
        for issue in issues:
            kind=issue['kind'] if issue['kind'] in ['contradiction','semantic'] else 'repair' if 'repair' in issue['kind'] else 'undecided'
            group=grouped.setdefault(kind,{'id':iid+':'+kind,'kind':kind,'title':{'undecided':'尚未决定／个人未决事项','repair':'补点、删点与修复核对','contradiction':'前后判断可能矛盾','semantic':'评论指代或含义需确认'}[kind],'annotation_ids':[],'evidence':[]})
            group['annotation_ids']=sorted(set(group['annotation_ids'])|set(issue.get('annotation_ids',[])))
            group['evidence'].append(issue)
        issues=list(grouped.values())
        for issue in issues:
            if issue['id'] in all_issues:raise ValueError('重复问题ID: '+issue['id'])
            all_issues.add(issue['id'])
            workers=[audit['annotations'][a]['worker']+' · '+audit['annotations'][a]['condition'] for a in issue.get('annotation_ids',[])]
            workers=list(dict.fromkeys(workers))
            if workers:issue['title']=' / '.join(workers[:3])+(f' 等{len(workers)}份' if len(workers)>3 else '')+'：'+issue['title']
        frozen=[r for r in audit.get('cluster_references',[]) if r.get('image_id')==iid]
        traps=[trap_inventory['annotations'][a] for a in c['review']['annotation_ids']]
        models={m['annotation_id']:m for m in audit.get('model_checks',[]) if m['image_id']==iid}
        models.update({t['annotation_id']:t['model_check'] for t in traps if t.get('model_check')})
        model_checks=list(models.values())
        traps=[{k:v for k,v in t.items() if k!='model_check'} for t in traps]
        c['return_review']={'issues':issues,'background':background,'notes':[n for n in note_rows if n.get('image_id')==iid],'cluster_references':frozen,'model_checks':model_checks,'trap_checks':traps}
        review=c['review']; flags=set(review['flags'])&{'doorway','oos','representation'}
        for issue in issues:
            kind=issue['kind']
            flags.add(kind)
        if model_checks or any(t['condition']=='semi' or t['trap_status']=='confirmed_trap' for t in traps):flags.add('model')
        if issues:flags.add('followup')
        if any(baseline['annotation_decisions'].get(a,{}).get('verdict')=='invalid' for a in review['annotation_ids']):flags.add('statistics')
        review['flags']=sorted(flags)
        review['followup_ids']=sorted({a for i in issues for a in i.get('annotation_ids',[]) if a in review['annotation_ids']})
        review['followup_reasons']=[{'kind':i['kind'],'title':i['title'],'annotation_ids':i.get('annotation_ids',[])} for i in issues]
        review['questions']=[]
        review['summary']='原二审已载入；场景背景共享，个人错误判断独立。保留误差与不同标法，仅处理下列具体问题。'
        src=(OLD/c['history_script']).read_text(encoding='utf-8')
        at=src.index('Object.assign(window.STUDIO_DATA.cases[')
        prefix=src[:at]; obj=json.loads(src[at:].split('],',1)[1].rsplit(');',1)[0])
        c['return_review']['image_src']=json.loads(prefix.split('=',1)[1].strip().removesuffix(';'))['original']
        obj['review']=review;obj['return_review']=c['return_review']
        for m in model_checks:
            if not m.get('initial_points_1024x512'):continue
            points=m['initial_points_1024x512'];labels=['初始p'+str(i+1) for i in range(len(points))]
            obj['variants'].append({'name':'实际初始化 · '+m['worker'],'geometry':None,'error':'初始化仅作点位对照，不重建','source':{'role':'initialization_reference','reference_name':'initial:'+m['annotation_id'],'worker_id':'','condition':'reference','raw_points':points,'effective_points':points,'shared_x_points':[],'raw_point_labels':labels,'effective_point_labels':labels,'shared_x_point_labels':[],'events':[],'audit':{'source':m.get('import_sources',[]),'repairs':[],'history':[],'pairing':{'status':'not_applicable'}},'clusters':{},'geometry_basis':'实际冻结初始化，不是GT、不参与分簇'}})
        # 同级输出目录：原图相对路径仍有效；不重算点位、分簇或几何。
        idx=data['cases'].index(c)
        (OUT/c['history_script']).parent.mkdir(parents=True,exist_ok=True)
        (OUT/c['history_script']).write_text(prefix+f'Object.assign(window.STUDIO_DATA.cases[{idx}],'+json.dumps(obj,ensure_ascii=False,separators=(',',':'))+');\n',encoding='utf-8')
        variant_count+=len(obj['variants'])
    data['counts']['variants']=variant_count
    for name in ['studio.js','studio.css','three.min.js','OrbitControls.js']:
        shutil.copyfile(OLD/name,OUT/name)
    for ext in ['js','css']:shutil.copyfile(HERE/f'review_reconciliation_panel_20260925.{ext}',OUT/f'review.{ext}')
    shutil.copyfile(HERE/'review_return_20260927.js',OUT/'return.js')
    (OUT/'data.js').write_text('window.STUDIO_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\nwindow.STUDIO_IMAGES={};\n',encoding='utf-8')
    html=(OLD/'index.html').read_text(encoding='utf-8').replace('<script defer src="review.js">','<script defer src="return.js"></script><script defer src="review.js">').replace('两人审核 · 二次复审','二审归并 · 定向补审')
    html=html.replace('</head>','<style>#return-panel{border:1px solid #abc1b5;padding:18px;margin:16px 0;background:#f5f8f4}#return-panel pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:360px;overflow:auto}#return-panel textarea{display:block;width:100%;box-sizing:border-box}#return-panel fieldset label{display:inline-block;margin:8px}#return-panel fieldset{margin:12px 0}#return-usage{padding:12px;background:#e7eee1;font-weight:600}</style></head>')
    (OUT/'index.html').write_text(html,encoding='utf-8')
    (OUT/'evidence').mkdir(exist_ok=True)
    shutil.copyfile(INPUT,OUT/'evidence/review_return_original.json')
    dump(OUT/'comments.json',notes)
    dump(OUT/'page_manifest.json',{'images':len(data['cases']),'followup_images':sum('followup' in c['review']['flags'] for c in data['cases']),'issues':len(all_issues),'baseline_images':len(baseline['image_decisions']),'baseline_annotations':len(baseline['annotation_decisions']),'raw_or_gt_changes':0,'schema':'review_return_decisions_v2'})
    manifest=read(OUT/'page_manifest.json')
    lines=['# 二审归并与定向补审','',
        '[打开补审页面](index.html) · [详细核验报告](回收核验报告.md) · [本轮SOP](../../docs/thesis_main/两人审核归并与二次复核SOP_20260925.md)','',
        f"本轮定向入口 {manifest['followup_images']} 图、{manifest['issues']} 张合并问题卡，只包含尚未决定、补点/删点、前后矛盾、语义不明四类。同房分类不同、已明确的GT细节差异、模型来源与分簇解释仅作背景，不自动要求重审。完整资料库239图，其他图可查阅，不要求全部重审。原二审197张图、625份作答已载入。新增补充独立保存，不回写原审核。",'',
        '## 是否已经审完','',
        '197张原定复核图都有整体记录，没有整图漏填。11张整体待定；625份个人记录为506份保留、81份排除、27份待定、11份待修复。原定复核作答有45份未单独填写：共享图片背景可以继承，但旧排除、具体个人问题和待落实修复不能被图级确认隐藏。','',
        '六份旧排除尚无新个人结论：e9zR4mvMWw7-32/W011、uNb9QFRL6hY-52/W034、uNb9QFRL6hY-60/W012、uNb9QFRL6hY-67/W037与W028、wc2JMjhGNzB-60/W037。','',
        '## 已确认的研究口径','',
        '保留误差和不同标法。普通图里“没标好但保留”不自动剔除；OOS/难标门洞的保留表示保留研究记录，不表示人员主质量资格。非正交但可稳定标注的共识单列。细节简化与大块空间取舍分别标记、允许共存，都保留在主研究，不先拆簇美化曲线。','',
        '参考细节省略不直接认定GT错误。明确实质错误陈述需核对原始/修订参考版本；如yqstnuAEVhm-04中不同来源称谓不合并。难度未写保持未记录。','',
        '## 人员与排除分布','',
        '| 人员 | 本轮逐份填写 | 保留 | 排除 | 待定/待修复 | 全库作答 |','|---|---:|---:|---:|---:|---:|']
    for worker in ['W034','W037']:
        w=audit['workers'][worker];v=w['verdicts'];lines.append(f"| {worker} | {w['reviewed']} | {v.get('usable',0)} | {v.get('invalid',0)} | {v.get('undetermined',0)+v.get('repair_needed',0)} | {w['total_annotations']} |")
    lines+=['','以上是定向审核记录，不能据此给出总体错误率。W034评论明确的圆柱案例为B6ByNegPMKs-11和-37；其余特点与具体证据见详细报告。排除数量最多为7y3sRwLe3Va-13（5份），其次UwV83HsGsw3-06与-10（各3份），报告同时列审核覆盖与全图作答数。','',
        '## Trap与预标注独立收集','',
        '独立筛选入口覆盖本页全部466份Semi及相关评论对象，不自动增加必审任务。正式导入与运行时字段核对：预设Trap288份（自然模型错误144、人工构造144）、明确对照72份、身份字段缺失106份。未保存字段不能推定非Trap；Manual/OOS缺失字段同样保留未确认。','',
        '466份Semi均对照冻结初始化与最终原始坐标：366份点集改变、100份未变。坐标按多重集比较、保留重复点、取1e-6像素精度；不据此推断是否检查。每份可叠加实际初始化。补充分类中单独选择Trap已确认/非Trap/待核实，与初始化改动标签分别保存，不能同时选择互斥Trap状态。来源见trap_inventory.json。','',
        '评论未决逐条核对见comment_pending.json：37条保留未决线索（36条原已待定，1条已选选项但文字仍犹豫），合并入四类队列，不按关键词重复生成图片。','',
        '## 来源与显示','',
        '406条非空评论逐条保留原话、释义和身份。31条簇评论均按旧affinity绑定具体worker、canonical作答、条件、有效点与shared-x点；切到complete只作展示对照，不能改变原评论指代。10组同房分类差异提供并排原图；同房不同机位可合理不同，不自动统一。','',
        '25份预标注评论对照冻结导入、运行时预览及原始导出：20份最终坐标多重集未变，5份改变；坐标未变不证明未检查，改动不证明改对。页面“此次二审原文”中可选择叠加实际初始化。自然模型错误被选为trap与人工构造trap分别记录。','',
        '当前239图中的2844份作答重新核验了原始身份、点序和坐标；全库3019份中另175份属于页面外20图，本轮不宣称重新核验。原始导出、GT、配对与分簇均未修改。','',
        '## 保存与文件格式','',
        '页面初始载入原二审；图级和个人工作副本允许补充，原件在evidence/review_return_original.json保持原字节。旧两位审核者原话独立展示。问题说明与补充分类独立导出为review_return_decisions_v2，兼容导入旧review_reconciliation_decisions_v1（导入替换须确认）。','',
        '新格式在原图级/作答级字段之外增加traits与issue_decisions。traits以image:图片ID或annotation:作答ID绑定，记录status、tags、difficulty、comment、updated_at；标签允许并存。issue_decisions按固定问题ID记录status、comment、updated_at。问题确认必须写处理说明；仍待定的个人判断不会因图级确认被隐藏。页面不把这些标签自动写成清洗结论。','',
        '复建：先运行 python -m tools.thesis_main.analysis.audit_review_return_20260927，再运行 python -m tools.thesis_main.analysis.build_review_return_20260927。评论释义由支撑文件review_return_notes_20260927.json提供，不自动生成裁决。','',
        '原JSON：evidence/review_return_original.json；全量核验：audit.json；评论释义：comments.json；页面清单：page_manifest.json。最终补审仍由用户确认，角点顺序及实验重算不属于本次。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return read(OUT/'page_manifest.json')

if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False))
