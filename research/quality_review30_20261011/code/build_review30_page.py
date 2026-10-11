"""Anonymous 30-primary + independent optional-pair offline review page."""
import csv,hashlib,html,io,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='quality_review30_receipt_v1'
FIELDS=['case_id','case_type','absolute_quality','space_compatibility','reference_question','difference_to_reference','reason','confidence','notes']
PAIR_FIELDS=['pair_id','left_case_id','right_case_id','preference','gap','reason','confidence','notes']
OPTIONS={'absolute_quality':['可接受','有轻微问题','明显问题','严重不可接受','无法判断'],'space_compatibility':['仅 A 可匹配','仅 B 可匹配','两者均可匹配','两者均不匹配','无法判断'],'reference_question':['参考/目标可判断','参考/目标有疑问','无法判断'],'difference_to_reference':['很小','中等','很大','无法判断'],'confidence':['低','中','高'],'preference':['T23 更好','T24 更好','相近','无法判断'],'gap':['小','中','大','无法判断']}
LABELS={'absolute_quality':'这一份作答的绝对质量','space_compatibility':'这份作答与两个空间的底面匹配','reference_question':'参考/目标是否可判断','difference_to_reference':'作答与参考的差距','reason':'主要原因（也可说明参考、目标、遮挡或看图困难）','confidence':'信心','notes':'备注','preference':'同图同参考的两份作答比较','gap':'两份作答的差距'}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def control(cid,kind,field):
 attr=f'data-row-id="{cid}" data-kind="{kind}" data-field="{field}"';label=LABELS[field]
 if field in OPTIONS:c=f'<select {attr}><option value="">请选择（留空不计回答）</option>'+''.join('<option>'+html.escape(v)+'</option>' for v in OPTIONS[field])+'</select>'
 else:c=f'<textarea {attr} maxlength="2000" aria-label="{html.escape(label)}"></textarea>'
 return f'<label>{html.escape(label)}：{c}</label>'
def image(cid,kind,label):return f'<figure><a href="{cid}_{kind}.{"jpg" if kind in ["original","overlay"] else "png"}" target="_blank" rel="noopener"><img loading="lazy" src="{cid}_{kind}.{"jpg" if kind in ["original","overlay"] else "png"}" alt="{cid} {label}"></a><figcaption>{label} · 点击放大</figcaption></figure>'
def main():
 s=read(ROOT/'results/selection_private.json');order=read(ROOT/'results/display_order.json');byid={r['case_id']:r for r in s['records']};user=ROOT/'user';user.mkdir(exist_ok=True)
 rows=[{f:r['case_id'] if f=='case_id' else ('quality' if r['case_type']=='single_absolute_quality' else 'space') if f=='case_type' else '' for f in FIELDS} for r in s['records']]
 active={r['case_id']:(['absolute_quality','reference_question','difference_to_reference','reason','confidence','notes'] if r['case_type']=='quality' else ['space_compatibility','reference_question','reason','confidence','notes']) for r in rows};pairs=[{f:'P01' if f=='pair_id' else 'T23' if f=='left_case_id' else 'T24' if f=='right_case_id' else '' for f in PAIR_FIELDS}]
 dataset='quality_review30_selection_v1:'+sha(ROOT/'results/selection_private.json')+':seed'+str(order['seed']);schema={'dataset_id':dataset,'display_order':order['primary_display_order'],'fields':FIELDS,'rows':rows,'active_fields':active,'pair_fields':PAIR_FIELDS,'pair_rows':pairs,'pair_active_fields':{'P01':['preference','gap','reason','confidence','notes']},'options':OPTIONS}
 receipt={'format_version':VERSION,'dataset_id':dataset,'case_ids':[r['case_id'] for r in rows],'display_order':schema['display_order'],'fields':FIELDS,'answers':rows,'pair_ids':['P01'],'pair_fields':PAIR_FIELDS,'pair_answers':pairs}
 parts=['''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>30份几何审核</title><style>
body{font:17px system-ui,sans-serif;max-width:1400px;margin:auto;padding:0 14px;line-height:1.6;color:#20252b}button,select,input,textarea{font:inherit}button{cursor:pointer;margin:3px;padding:5px 9px}select{max-width:100%;padding:5px}textarea{display:block;width:96%;min-height:72px}label{display:block;margin:12px 0}figure{margin:0;padding:6px}img{width:100%;height:auto;display:block}figcaption{color:#49535f} .images,.pair-images{display:grid;grid-template-columns:1fr 1fr;gap:8px}.navigation{position:sticky;top:0;background:#fff9e4;border:1px solid #d5bb64;padding:8px;z-index:2}#case-nav{display:flex;flex-wrap:wrap;margin:15px 0}#case-nav button{font-size:14px}button[aria-current="true"]{outline:3px solid #2d6eaf}button[data-state="已回答"]{background:#dcefdc}button[data-state="部分填写"]{background:#fff0c7}[hidden]{display:none!important}#draft-status[data-state="invalid"],#draft-status[data-state="unavailable"]{color:#a30d00;font-weight:bold}#receipt-status{min-height:1.4em}.notice{border-left:4px solid #6888a9;padding:10px;background:#f1f5f8}.small{font-size:14px}.orange{color:#ba5000}.green{color:#137535}.blue{color:#176cbb}@media(max-width:700px){.images,.pair-images{grid-template-columns:1fr}body{font-size:16px}}section{margin:18px 0 40px}
</style></head><body><h1>30份几何审核</h1><p>每份独立回答，不需要把不同房间排序。全部来自历史材料；部分图片已在之前小样出现。默认回答为空，不代表接受。若存在匹配草稿，页面会明确提示恢复。</p>
<div class="notice">请结合原图、叠线和几何视图判断。现有参考可能有边界语义、简化模型、遮挡或坐标局限；看图并不表示每段墙已认证为严格曼哈顿。可以选择“参考/目标有疑问”或“无法判断”，并说明原因。空间A/B的底面合理性已认可；本页询问几何匹配，不推断标注者真实意图。</div>
<div><h2>保存与续填</h2><p id="draft-status" role="status" aria-live="polite">请下载回执备份。</p><button id="download-json" type="button">下载 JSON 回执</button><button id="download-csv" type="button">下载 CSV 回执</button><label>导入本页回执继续填写：<input id="import-receipt" type="file" accept=".json,.csv"></label><p class="small">成功导入会替换当前回答，请先下载备份。旧8例或不匹配回执会被拒绝，不清除当前输入。导入后定位第一份未回答题；全部已答时定位最后一题。每字段最多2000字，导入上限1 MiB。</p><p id="receipt-status" role="status" aria-live="polite"></p></div>
<div class="navigation"><strong id="current-position"></strong><button id="prev-case" type="button">上一份</button><button id="next-case" type="button">下一份</button><div id="primary-progress" aria-live="polite"></div><div id="pair-progress" class="small"></div></div><nav id="case-nav" aria-label="30份展示顺序">''']
 for cid in schema['display_order']:parts.append(f'<button type="button" data-go-case="{cid}">{cid} · 未填写</button>')
 parts.append('</nav><button id="go-pair" type="button">最后：可选同图成对题 P01（不计入30份）</button>')
 for cid in schema['display_order']:
  r=byid[cid];space=r['case_type']=='single_floor_space_compatibility';parts.append(f'<section data-panel-id="{cid}" hidden><h2>题号 {cid} · '+('底面空间匹配' if space else '单份质量判断')+'</h2>')
  if r['old8_image_exposure']:parts.append('<p class="small">此图片曾在之前小样展示；仍请独立填写本题。</p>')
  parts.append('<p><span class="orange">橙色：这一份作答</span>；<span class="green">绿色：空间A底面</span>；<span class="blue">蓝色：空间B底面</span>。全部几何视图只画底面，B顶界尚未确认，不提供完整B质量。</p>' if space else '<p><span class="orange">橙色：这一份作答</span>；<span class="green">绿色：现有参考</span>。几何视图与参考共用尺度，未作旋转、平移或尺度对齐。</p>')
  parts.append('<div class="images">'+image(cid,'original','原图像素')+image(cid,'overlay','全景叠线')+image(cid,'bev','同尺度BEV')+image(cid,'3d','3D仅底面（B顶界待定）' if space else '同尺度3D')+'</div>')
  for field in active[cid]:parts.append(control(cid,'case',field))
  parts.append('</section>')
 parts.append('<section data-panel-id="P01" hidden><h2>可选同图成对题 P01</h2><p>这里复用T23和T24；同一图片、同一现有参考，BEV和3D坐标范围相同。此题不增加作答记录数，不计入30份进度。先完成两份单份判断；参考有疑问时可选无法判断并说明。</p><div class="pair-images">')
 for cid in ['T23','T24']:parts.append('<div><h3>'+cid+'</h3>'+image(cid,'original','原图')+image(cid,'overlay','叠线')+image(cid,'bev','BEV')+image(cid,'3d','3D')+'</div>')
 parts.append('</div>')
 for field in schema['pair_active_fields']['P01']:parts.append(control('P01','pair',field))
 parts.append('</section><p>浏览器草稿可能被禁用或清理。关闭/刷新前请下载回执；下载后的JSON/CSV是可携带的续填文件。空白、仅查看和仅填写原因均不算完成；“无法判断”是有效回答。</p><noscript>JavaScript未启用：导航与保存不能工作。请用随包responses.csv填写，或在启用JavaScript的浏览器打开。</noscript>')
 parts.append('<script type="application/json" id="receipt-schema">'+json.dumps(schema,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+'</script><script src="review30_receipt.js"></script></body></html>')
 (user/'index.html').write_text('\n'.join(parts)+'\n',encoding='utf-8');shutil.copyfile(Path(__file__).with_name('review30_receipt.js'),user/'review30_receipt.js');(user/'responses.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 output=io.StringIO(newline='');w=csv.writer(output);w.writerows([['#format_version',VERSION],['#dataset_id',dataset],['#display_order',*schema['display_order']],['#case_fields',*FIELDS],*[[r[f] for f in FIELDS] for r in rows],['#pair_fields',*PAIR_FIELDS],*[[r[f] for f in PAIR_FIELDS] for r in pairs]]);(user/'responses.csv').write_text(output.getvalue(),encoding='utf-8-sig',newline='')
 (user/'使用说明.md').write_text('''解压整个文件夹后，在浏览器打开index.html。每份原图、叠线、BEV与3D均可点击放大。

30份展示顺序已固定。题号不会因翻页改变。每份独立判断，可选同图成对题在最后，单独保存、不增加作答数。

橙色是作答，绿色是现有参考/空间A，蓝色是空间B。空间题只显示底面；B顶界待确认。参考/目标有疑问或无法判断时，请保留该判断并说明原因；不要把候选当作人员意图。

首次打开所有回答为空；匹配本浏览器草稿时会提示恢复。空白/仅查看/仅原因不算完成，“无法判断”是有效回答。JSON/CSV都可导入续填；旧8例回执与本页隔离。

浏览器可能禁止或清除本地草稿，不能保证自动持久保存。关闭或刷新前请下载回执并确认文件已保存。导入会替换现有回答，建议先下载备份；不匹配导入不会清除当前输入。导入后定位第一份未回答题。

若浏览器不支持页面脚本，可使用responses.csv填写，保持格式标记、清单、字段和固定身份列不变。每个回答字段最多2000字；导入上限1 MiB。
''',encoding='utf-8')
 (ROOT/'results/receipt_schema_anonymous.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Page built:30 unique primary answers +1 independent optional pair; all blank; order frozen')
if __name__=='__main__':main()
