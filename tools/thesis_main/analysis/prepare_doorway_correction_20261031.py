"""Prepare a versioned correction overlay and the three unresolved ring reviews."""
import gzip
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030'
OUT=BASE/'pro_delivery_independent_audit_20261031'
P='HOHONET_doorway_v21_20261031/'

def main():
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_01_POOLS_REFERENCES_EVIDENCE.zip') as z:
        ledger=json.loads(z.read(P+'stage01_pools/FINAL_RECORD_LEDGER.json'))
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        records=json.loads(gzip.decompress(z.read(P+'stage04_computation/design/FROZEN_RECORDS.json.gz')))
    holds=json.loads((OUT/'INDEPENDENT_HOLDS_13.json').read_text(encoding='utf8'))
    ring={r['object_id'] for r in holds if 'input_geometry_unavailable' in r['reasons']}
    binding={r['object_id'] for r in holds}-ring
    receipt_path=OUT/'USER_RING_CONFIRMATION.json'
    confirmed={r['object_id']:r for r in json.loads(receipt_path.read_text(encoding='utf8'))['records']} if receipt_path.exists() else {}
    for oid,r in confirmed.items():
        assert oid in ring and r['points']==records[oid]['points'] and r['ring_confirmed'] is True
    suspect={'7y3sRwLe3Va-06','b8cTxDM8gDG-08','jtcxE69GiFV-12','q9vSo1VnCiC-13'}
    visual_path=OUT/'VISUAL_SCOPE_ADJUDICATION.json'
    visual={r['object_id']:r for r in json.loads(visual_path.read_text(encoding='utf8'))['records']} if visual_path.exists() else {}
    overlay=[]
    for r in ledger:
        if not r['base_candidate']:continue
        reasons=[]
        if r['object_id'] in ring and r['object_id'] not in confirmed:reasons.append('input_ring_confirmation_required')
        if r['object_id'] in binding:reasons.append('historical_target_binding_requires_resolution')
        if r['image'] in suspect and not r['protected_adjudication']:reasons.append('area_dominance_not_verified_scope_intent')
        adopted=visual.get(r['object_id'])
        if adopted:
            assert adopted['points']==records[r['object_id']]['points'] and adopted['before']==r['final_scope']
            assert adopted['scope'] in ['空间1','空间2','全部']
            assert not r['protected_adjudication'] or adopted['scope']==r['final_scope']
            reasons=[x for x in reasons if x not in ['area_dominance_not_verified_scope_intent','historical_target_binding_requires_resolution']]
        overlay.append(dict(object_id=r['object_id'],image=r['image'],worker=r['worker'],frozen_scope=r['final_scope'],
            correction_reasons=reasons,corrected_scope=adopted['scope'] if adopted else None if 'area_dominance_not_verified_scope_intent' in reasons else r['final_scope'],
            correction_status='pending' if reasons else 'agent_visual_reviewed' if adopted else 'unchanged',original_results_preserved=True,
            ring_confirmed_by_user=r['object_id'] in confirmed))
    assert len(overlay)==584 and len(ring)==3 and len(binding)==10
    (OUT/'CORRECTION_OVERLAY.json').write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    cases=json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']
    cases={c['image']:c for c in cases}
    items=[]
    for r in holds:
        if r['object_id'] not in ring:continue
        c=cases[r['image']];photo=(BASE/c['photo']).resolve();assert photo.exists()
        items.append(dict(**r,points=records[r['object_id']]['points'],photo=photo.as_uri()))
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>门洞环序专项复核</title>
<style>body{font:18px sans-serif;margin:24px;background:#f5f7fa}section{background:white;padding:16px;margin:20px 0}svg{width:100%;max-height:700px}button{font:inherit;padding:10px;margin:8px}button[aria-pressed=true]{background:#9de0d8}p{line-height:1.6}</style>
<h1>仅3份：点对连接顺序复核</h1><p>检查编号是否沿实际墙体依次连接，特别留意门洞遮挡处。黄色虚线是当前未确认的候选环序，并非已采用连线。此页不判断空间归属，不展示质量分。点击自动保存并停留；全部完成后导出回执。若顺序不对或看不清，保留待定，不强行采用。</p><button id="export">导出环序复核</button><span id="status"></span><main></main>
<script>const items=__DATA__;const key='doorway-ring-correction-20261031';let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){document.querySelector('#status').textContent='读取缓存失败，请重新选择并导出'}
const ns='http://www.w3.org/2000/svg';function el(t,a,parent){let n=document.createElementNS(ns,t);for(let k in a)n.setAttribute(k,a[k]);parent.append(n);return n}
for(const r of items){let s=document.createElement('section');document.querySelector('main').append(s);let h=document.createElement('h2');h.textContent=r.image+' · '+r.worker;s.append(h);let svg=el('svg',{viewBox:'0 0 1024 512',role:'img','aria-label':h.textContent+'候选连接'},s);el('image',{href:r.photo,width:1024,height:512},svg);
let points=r.points,xyz=[];for(let i=0;i<points.length;i+=2){let [u,v]=points[i+1],a=(u/1024-.5)*2*Math.PI,d=1/Math.tan((v/512-.5)*Math.PI);xyz.push([d*Math.sin(a),-d*Math.cos(a)])}
for(let i=0;i<xyz.length;i++){let a=xyz[i],b=xyz[(i+1)%xyz.length],last=null;for(let j=0;j<=80;j++){let t=j/80,x=a[0]*(1-t)+b[0]*t,z=a[1]*(1-t)+b[1]*t,u=(Math.atan2(x,-z)/(2*Math.PI)+.5)*1024,v=(Math.atan2(1,Math.hypot(x,z))/Math.PI+.5)*512;if(last&&Math.abs(last[0]-u)<512)el('line',{x1:last[0],y1:last[1],x2:u,y2:v,stroke:'#ffe000','stroke-width':2,'stroke-dasharray':'4 3'},svg);last=[u,v]}for(let q=0;q<2;q++){let [x,y]=points[2*i+q];el('circle',{cx:x,cy:y,r:4,fill:'#ff329f'},svg);el('text',{x:x+6,y:y-5,fill:'white',stroke:'black','stroke-width':.5,'font-size':15},svg).textContent=i+1}}
for(const label of ['环序正确','环序不正确','看不清／不能判断']){let b=document.createElement('button');b.textContent=label;b.setAttribute('aria-pressed',saved[r.object_id]?.decision===label);s.append(b);b.onclick=()=>{saved[r.object_id]={object_id:r.object_id,image:r.image,worker:r.worker,decision:label,points:r.points,updated_at:new Date().toISOString()};try{localStorage.setItem(key,JSON.stringify(saved));document.querySelector('#status').textContent='已保存'}catch(e){document.querySelector('#status').textContent='缓存保存失败，请立即导出'}for(let x of s.querySelectorAll('button'))x.setAttribute('aria-pressed',x===b)}}}
document.querySelector('#export').onclick=()=>{let a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify({version:key,decisions:saved},null,2)],{type:'application/json'}));a.href=u;a.download='门洞环序专项复核.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};</script></html>'''
    html=html.replace('__DATA__',json.dumps(items,ensure_ascii=False))
    if confirmed:
        html=html.replace('<h1>仅3份：点对连接顺序复核</h1>','<h1>已收到用户确认：三份环序均正确</h1><p><b>用户说明：本身标注奇怪，顺序没有问题。以下为历史复核显示，旧缓存或按钮不能覆盖已归档的对话裁决，无需再次提交。</b></p>')
        html=html.replace('</html>','<script>document.querySelectorAll("button").forEach(b=>b.disabled=true);</script></html>')
    (OUT/'RING_REVIEW.html').write_text(html,encoding='utf8')
    print(json.dumps(dict(base=len(overlay),pending=sum(bool(r['correction_reasons']) for r in overlay),ring_review=len(ring-set(confirmed)),scope_pending=sum('area_dominance_not_verified_scope_intent' in r['correction_reasons'] for r in overlay)),ensure_ascii=False))

if __name__=='__main__':main()
