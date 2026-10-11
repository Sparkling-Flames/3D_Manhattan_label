from pathlib import Path
import json, re, shutil, hashlib, argparse
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--prior-user');a=p.parse_args()
 src=Path(a.prior_user) if a.prior_user else ROOT/'inputs/previous_review30_templates';dst=ROOT/'user/review30';dst.mkdir(parents=True,exist_ok=True)
 raw=(ROOT/'inputs/library/quality_review30_receipt.json').read_bytes();receipt=json.loads(raw)
 assert len(raw)==11986 and hashlib.sha256(raw).hexdigest()=='8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c'
 for f in src.iterdir():
  if f.suffix in ('.jpg','.png'):shutil.copy2(f,dst/f.name)
 if not a.prior_user:assert len(list(dst.glob('T??_original.jpg')))==30 and len(list(dst.glob('T??_bev.png')))==30
 h=(src/'index.html').read_text();m=re.search(r'(<script type="application/json" id="receipt-schema">)(.*?)(</script>)',h,re.S);s=json.loads(m[2])
 assert receipt['dataset_id']==s['dataset_id'] and receipt['display_order']==s['display_order'] and receipt['fields']==s['fields'] and receipt['pair_fields']==s['pair_fields']
 assert receipt['case_ids']==[r['case_id'] for r in s['rows']] and receipt['pair_ids']==[r['pair_id'] for r in s['pair_rows']]
 assert len(set(receipt['case_ids']))==30
 s['rows']=receipt['answers'];s['pair_rows']=receipt['pair_answers'];s['history_sha256']=hashlib.sha256(raw).hexdigest()
 h=h[:m.start(2)]+json.dumps(s,ensure_ascii=False,separators=(',',':'))+h[m.end(2):]
 h=h.replace('<h1>30份几何审核</h1>','<h1>收到的30份历史反馈（只读）</h1><p><a href="../editor/index.html">打开T30四空间补画与独立复核</a> · <a href="../historical_feedback/quality_review30_receipt.json" download>下载原回执</a></p><p>T30仍保留原判断“两者均不匹配 / 另一种空间”；新复核初始为“参考待补充”，两层分别导出。T29按用户指定A处理；T21/T22备注仅为研究警报。24份质量回答：2可接受、10有轻微问题、12明显问题、0严重；差距9很小、15中等。这是这批反馈，不是全体分布。P01原空白。</p>')
 h=h.replace('默认回答为空，不代表接受。若存在匹配草稿，页面会明确提示恢复。','本页保留已收到的原回答，不能覆盖。补充T30请进入四空间工作台。')
 (dst/'index.html').write_text(h)
 js=(src/'review30_receipt.js').read_text().replace("storageKey=VERSION+':'+schema.dataset_id", "storageKey=VERSION+':'+schema.dataset_id+':immutable-history:'+schema.history_sha256")
 js=js.replace('return {answers:validateRows(value.answers', "if(!equal(value.answers,schema.rows)||!equal(value.pair_answers,schema.pair_rows))throw Error('只读历史回执不得被覆盖；T30新复核请用独立工作台');\n      return {answers:validateRows(value.answers")
 js=js.replace('ctl.load();fill();locate(ctl.loadPosition(),false);', "ctl.load();fill();controls.forEach(el=>{el.disabled=true;el.setAttribute('aria-readonly','true')});locate(ctl.loadPosition(),false);")
 (dst/'review30_receipt.js').write_text(js)
 d=ROOT/'user/historical_feedback';d.mkdir(exist_ok=True);(d/'quality_review30_receipt.json').write_bytes(raw)
 (ROOT/'results/history_prefill_manifest.json').write_text(json.dumps({'dataset_id':receipt['dataset_id'],'case_ids':receipt['case_ids'],'display_order':receipt['display_order'],'original_sha256':s['history_sha256'],'rows':30,'read_only':True,'pair_original_blank':all(not receipt['pair_answers'][0][f] for f in ['preference','gap','reason','confidence','notes'])},ensure_ascii=False,indent=2)+'\n')
 print('Historical answers prefilled; original receipt verified; 120 prior images reused unchanged')
if __name__=='__main__':main()
