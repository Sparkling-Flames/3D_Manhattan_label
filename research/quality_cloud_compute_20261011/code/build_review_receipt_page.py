"""Build receipt UI only; preserve all original images, case order, and CSV fields."""
import csv,html,json,shutil,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QUALITY='两份答案质量比较'
PREF='优劣（答案1更好/答案2更好/相近/无法判断）'
GAP='差距（小/中/大）'
ABS1='答案1（可接受/明显问题/严重不可接受/无法判断）'
ABS2='答案2（可接受/明显问题/严重不可接受/无法判断）'
SPACE='空间判断（仅 A 可匹配/仅 B 可匹配/两者均可匹配/两者均不匹配/无法判断）'
OPTIONS={PREF:['答案1更好','答案2更好','相近','无法判断'],GAP:['小','中','大'],ABS1:['可接受','明显问题','严重不可接受','无法判断'],ABS2:['可接受','明显问题','严重不可接受','无法判断'],SPACE:['仅 A 可匹配','仅 B 可匹配','两者均可匹配','两者均不匹配','无法判断']}
VERSION='quality_blind_sample_receipt_v1'
def write_review_page(user, blank_csv):
 with Path(blank_csv).open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);fields=list(reader.fieldnames);rows=list(reader)
 assert [r['case_id'] for r in rows]==['C01','C02','C03','C04','C05','C06','C07','X01']
 assert all(v=='' for r in rows for k,v in r.items() if k not in ['case_id','case_type'])
 active={r['case_id']:([ABS1,'答案1主要原因',ABS2,'答案2主要原因',PREF,GAP,'比较主要原因','信心','备注'] if r['case_type']==QUALITY else [SPACE,'主要原因','信心','备注']) for r in rows}
 schema={'fields':fields,'rows':rows,'active_fields':active,'options':OPTIONS}
 parts=['''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>几何比较小样</title><style>body{font:17px sans-serif;max-width:1450px;margin:15px auto;padding:0 12px;line-height:1.6}img{width:100%}section{margin:35px 0}textarea{width:96%;min-height:65px}label{display:block;margin:8px 0}select,button,input{font-size:17px}.receipt-bar{position:sticky;top:0;background:#fff8dc;border:1px solid #cba94a;padding:12px;z-index:2}.receipt-bar button{margin:3px 6px 3px 0}#draft-status[data-state="unavailable"],#draft-status[data-state="invalid"]{color:#a20d00;font-weight:bold}#receipt-status{min-height:1.4em}</style></head><body><h1>几何比较小样</h1>
<div class="receipt-bar"><strong>回执与本地草稿</strong><p id="draft-status" role="status" aria-live="polite">草稿状态尚未检查。请下载回执备份。</p><button id="download-json" type="button">下载 JSON 回执</button><button id="download-csv" type="button">下载 CSV 回执</button><label>导入回执继续填写：<input id="import-receipt" type="file" accept=".json,.csv"></label><p>导入本页下载的回执会替换当前回答。请先下载备份。导入不匹配文件时，当前输入不会被清除。</p><div id="receipt-status" role="status" aria-live="polite"></div></div>
<p>全部来自历史材料，无历史未见声明。默认回答全部留空；若本浏览器已有匹配草稿，会明确提示恢复。请先对每份答案作绝对评价，再比较优劣。绿色为认可参考，答案1为橙色，答案2为蓝色。参考可能有语义或模型局限；无法判断时请选择无法判断。</p><p>X01是同一份答案对空间A/B的比较；B只确认底面，顶界待定。这里单独判断空间匹配。</p>''']
 for row in rows:
  cid=row['case_id'];parts.append(f'<section><h2>{cid}</h2><a href="{cid}_original.jpg">查看原图像素</a><img src="{cid}.jpg" alt="{cid} 原图及同尺度比较">')
  for field in active[cid]:
   attr=f'data-case-id="{cid}" data-field="{html.escape(field,quote=True)}"'
   if field in OPTIONS:
    control=f'<select {attr}><option value="">请选择</option>'+''.join(f'<option>{html.escape(v)}</option>' for v in OPTIONS[field])+'</select>'
   else:control=f'<textarea {attr} maxlength="2000"></textarea>'
   parts.append('<label>'+html.escape(field)+'：'+control+'</label>')
  parts.append('</section>')
 config=json.dumps(schema,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
 parts.append('<p>填写时会尝试写入本浏览器草稿；文件浏览器可能禁止存储，不能保证自动保存。请在关闭或刷新前下载 JSON/CSV 回执，之后可导入继续填写。每个回答字段最多2000字，导入文件上限1 MiB。</p><noscript>浏览器未启用JavaScript：页面表单不能保存或导出，请使用随包CSV回执填写。</noscript><script type="application/json" id="receipt-schema">'+config+'</script><script src="review_receipt.js"></script></body></html>')
 user=Path(user);user.mkdir(exist_ok=True,parents=True);(user/'index.html').write_text('\n'.join(parts)+'\n',encoding='utf-8');shutil.copyfile(Path(__file__).with_name('review_receipt.js'),user/'review_receipt.js')
 # Versioned blank receipt keeps the existing header fields and case IDs.
 output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(['#format_version',VERSION]);writer.writerow(fields);writer.writerows([[r[f] for f in fields] for r in rows]);(user/'responses.csv').write_text(output.getvalue(),encoding='utf-8-sig',newline='')
 (user/'responses.json').write_text(json.dumps({'format_version':VERSION,'case_ids':[r['case_id'] for r in rows],'fields':fields,'answers':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return schema
if __name__=='__main__':
 schema=write_review_page(ROOT/'blind_sample/user',ROOT/'blind_sample/user_response_blank.csv');print('Receipt page updated:',len(schema['rows']),'cases;',len(schema['fields']),'stable fields; no image rendering.')
