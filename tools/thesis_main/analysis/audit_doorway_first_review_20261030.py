"""Audit supplied first review without converting quality verdicts into scope labels."""
import csv,io,json,zipfile
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/doorway_review_20261030/first_review_audit'
def main():
 OUT.mkdir(exist_ok=True)
 local=json.loads((OUT.parent/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1]);lookup={c['image_id']:c for c in local['cases']}
 with zipfile.ZipFile(Path.home()/'Downloads/门洞审核.zip') as z:
  def raw(suffix):return z.read(next(n for n in z.namelist() if n.endswith('/'+suffix)))
  for name in ['review_result_v2.json','verdicts_all.csv','summary_per_image.csv','classification.csv']:(OUT/name).write_bytes(raw(name))
  (OUT/'SOURCE_README.md').write_bytes(raw('README.md'))
  packed=json.loads(raw('data.js').decode('utf8').split('=',1)[1][:-1])
  assert packed==local,'Pack input differs from local source'
 reviewed=json.loads((OUT/'review_result_v2.json').read_text(encoding='utf8'))
 machine=list(csv.DictReader(io.StringIO((OUT/'classification.csv').read_text(encoding='utf-8-sig'))));mm={r['record_id']:r for r in machine}
 assert len(mm)==708
 counts=Counter();matrix=Counter();stale=[];changed=[];queue=[];seen=set()
 for c in reviewed['cases']:
  base=lookup[c['image_id']];assert base['image']==c['image'] and base['reference_id']==c['reference_id']
  records={r['id']:r for r in base['records']};assert len(c['verdicts'])==len(records)
  if c['cuts']!=base['cuts']:changed.append(c['image'])
  signature=[[x['line'],x['side']] for x in c['cuts']]
  for v in c['verdicts']:
   rid=v['record_id'];assert rid in records and rid not in seen;seen.add(rid)
   assert mm[rid]['image_id']==c['image_id'] and mm[rid]['worker']==records[rid]['worker']
   is_stale=json.loads(v['cuts_hash'])!=signature
   if is_stale:stale.append(dict(image=c['image'],record_id=rid,worker=records[rid]['worker']))
   counts[v['value']]+=1;matrix[v['value'],mm[rid]['space_verdict']]+=1
   queue.append(dict(image=c['image'],record_id=rid,worker=records[rid]['worker'],first_verdict=v['value'],machine_scope=mm[rid]['space_verdict'],stale=is_stale,scope_decision=None,review_action='requires_scope_review_not_quality_filter'))
  base['photo']='../'+base['photo'];base['cuts']=c['cuts'];base['first_review']={v['record_id']:dict(value=v['value'],machine_scope=mm[v['record_id']]['space_verdict']) for v in c['verdicts']}
 assert len(seen)==708 and len(reviewed['cases'])==20
 result=dict(records=len(seen),images=20,verdict_counts=dict(counts),changed_images=changed,stale=stale,cross_table=[dict(verdict=v,scope=s,n=n) for (v,s),n in sorted(matrix.items())],input_identity='all source data equal; all IDs matched',scope_labels_reviewed=0)
 (OUT/'CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 (OUT/'REVIEW_QUEUE.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf8')
 (OUT/'data.js').write_text('window.DOORWAY_DATA='+json.dumps(local,ensure_ascii=False)+';',encoding='utf8')
 html=(OUT.parent/'index.html').read_text(encoding='utf8').replace('src="../../','src="../../../').replace('href="../../','href="../../../')
 html=html.replace('<h1>门洞交界 · 空间审核</h1>','<h1>初审复查 · 重新判定空间归属</h1><p>初审的可用／需修正／无法判断仅作旁证，不能对应本页四项空间分类。新选择另存，不覆盖初审。</p>').replace('<div id="choices"></div>','<p id="initialVerdict"></p><div id="choices"></div>')
 (OUT/'index.html').write_text(html,encoding='utf8')
 js=(OUT.parent/'review.js').read_text(encoding='utf8').replace("localStorage.getItem(D.schema)||localStorage.getItem('doorway_review_v1')","localStorage.getItem('doorway_first_review_recheck_v2')").replace('localStorage.setItem(D.schema,',"localStorage.setItem('doorway_first_review_recheck_v2',")
 js=js.replace("const c=cur(),d=draft(),r=c.records[j];", "const c=cur(),d=draft(),r=c.records[j];const v=c.first_review[r.id];$('initialVerdict').textContent='初审质量判定：'+({pass:'可用',fix:'需修正',unsure:'无法判断'}[v.value])+'；附带程序空间初判：'+v.machine_scope+'（不是人工空间结论）';")
 (OUT/'review.js').write_text(js,encoding='utf8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
