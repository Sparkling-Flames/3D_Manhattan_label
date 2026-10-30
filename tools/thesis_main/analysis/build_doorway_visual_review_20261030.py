"""Render per-answer visual audit sheets; no quality or scope inference."""
import json,math,html
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030/first_review_audit'
OUT=BASE/'visual_review'
def publish(data):
 notes=json.loads((OUT/'VISUAL_NOTES.json').read_text(encoding='utf8'))
 queue=[];sections=[]
 for ci,c in enumerate(data['cases']):
  cards=[];seen=set()
  for indexes,reason in notes['groups'][str(ci)]:
   for ri in indexes:
    assert ri not in seen and 0<=ri<len(c['records']);seen.add(ri)
    r=c['records'][ri];pts=r['points'] or [];floor=[];lines=[]
    for x,y in pts[1::2]:
     v=(y/512-.5)*math.pi
     if abs(math.tan(v))>1e-8:
      radius=1/math.tan(v);u=(x/1024-.5)*math.tau;floor.append([radius*math.sin(u),-radius*math.cos(u)])
    for parity in [0,1]:
     ring=pts[parity::2]
     for a,b in zip(ring,ring[1:]+ring[:1]):
      if abs(a[0]-b[0])<512:lines.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="cyan" stroke-width="2"/>')
      lines.append(f'<circle cx="{a[0]}" cy="{a[1]}" r="3" fill="red"/>')
    allp=floor+c['floor']+[[0,0]];xs=[p[0] for p in allp];ys=[p[1] for p in allp]
    scale=min(980/(max(xs)-min(xs) or 1),300/(max(ys)-min(ys) or 1))
    def xy(p):return (20+(p[0]-min(xs))*scale,20+(p[1]-min(ys))*scale)
    bev=[]
    for poly,color in [(c['floor'],'#a050b0'),(floor,'#007c9c')]:
     if poly:bev.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in map(xy,poly))+f'" fill="none" stroke="{color}" stroke-width="3"/>')
    for cut,color in zip(c['cuts'] or [],['#087f8c','#b45309']):
     a,b=map(xy,cut['line']);bev.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" stroke-width="2" stroke-dasharray="8 6"/>')
    x,y=xy([0,0]);bev.append(f'<circle cx="{x}" cy="{y}" r="4" fill="red"/>')
    item=dict(image=c['image'],image_id=c['image_id'],record_id=r['id'],worker=r['worker'],record_number=ri+1,reason=reason,category='数据待查' if not pts else '空间范围待复核',first_review=c['first_review'][r['id']],status='待用户复核')
    queue.append(item)
    photo=html.escape('../'+c['photo'],quote=True)
    label=html.escape(f"第{ri+1}份 · {r['worker']} · {r['id']}")
    cards.append(f'<details id="c{ci}r{ri}"><summary>{label} — {reason}</summary><p>当前状态：待用户复核；不据此剔除。</p><svg viewBox="0 0 1024 512"><image href="{photo}" width="1024" height="512"/>'+''.join(lines)+'</svg><svg viewBox="0 0 1024 350">'+''.join(bev)+'</svg></details>')
  sections.append(f'<section id="image{ci}"><h2>{c["image"]} · {len(seen)}份待复核 / {len(c["records"])}份</h2><p><a href="{ci:02d}.png">查看本图全部作答联系表</a> · <a href="../index.html">打开空间调整工作台（按图名及第几份定位）</a></p>'+''.join(cards)+'</section>')
 assert len({(r['image_id'],r['record_id']) for r in queue})==len(queue)
 total=sum(len(c['records']) for c in data['cases']);assert total==708
 report=dict(schema='doorway_visual_queue_v1',screened_images=len(data['cases']),screened_records=total,flagged_records=len(queue),unavailable_records=sum(r['category']=='数据待查' for r in queue),method=notes['method'],queue=queue)
 (OUT/'REVIEW_QUEUE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 intro=f'<h1>门洞作答：视觉初筛复核清单</h1><p>已浏览20张图、708份作答的原图点位及底面联系表；筛出{len(queue)}份待复核，其中{report["unavailable_records"]}份预处理点对为空。</p><p>这是复核队列，不是剔除名单。未入队不代表质量合格或已通过空间归属审核。斜边、少角点与“全部空间”本身不是剔除理由。</p><p>点击条目展开原图叠线和俯视图。紫色：原参考；蓝色：作答；红点：相机；青/橙虚线：当前两条停止边。俯视图单位不是米。原图青线仅是点序诊断直连，不是精确球面墙线；跨全景接缝的连线省略。</p><p>图级重点：2t7WUuJeko7-07 的GT漏角点与旧边界判定；7y3sRwLe3Va-18 的初审修改切分；q9vSo1VnCiC-24 的门洞身份。其余预切也尚待人工采用，尤其以经验间距代替门框宽度的图。</p>'
 nav='<nav>'+' · '.join(f'<a href="#image{i}">{c["image"]}</a>' for i,c in enumerate(data['cases']))+'</nav>'
 (OUT/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>门洞视觉复核</title><style>body{max-width:1100px;margin:24px auto;padding:0 16px;font:16px/1.65 system-ui;color:#17212b;background:#f7f8fa}section,details{background:white;padding:12px;margin:12px 0;border:1px solid #ccd3da;border-radius:6px}summary{cursor:pointer}svg{display:block;width:100%;background:white}a{color:#075c9c}nav{line-height:2.2}</style>'+intro+nav+''.join(sections)+'</html>',encoding='utf8')
 (OUT/'README.md').write_text(f'# 门洞视觉初筛\n\n入口：[复核页](index.html)。覆盖20图、708份；{len(queue)}份进入复核，其中{report["unavailable_records"]}份为预处理点对为空。\n\n人工视觉观察记录在 VISUAL_NOTES.json；生成的 REVIEW_QUEUE.json 包含图片、人员、原答ID、定位序号及疑点。只做全量联系表初筛，不能当作逐份高分辨率精审；未入队不等于已合格。不修改初审、原答、切分、GT或评分。\n\n图级另查：2t7WUuJeko7-07 的GT漏点与旧边界；7y3sRwLe3Va-18 修改后的切分；q9vSo1VnCiC-24 门洞身份。预切宽度仍需人工确认。\n\n字段：record_number为工作台从1开始序号；category区分空间范围待复核/数据待查；status统一待用户复核，first_review仅保留旁证。\n',encoding='utf8')
 print('Visual queue:',len(queue),'missing:',report['unavailable_records'])
 # Reuse the complete split editor, with an isolated 102-answer draft store.
 subset=json.loads(json.dumps(data));by_id={(r['image_id'],r['record_id']):r for r in queue}
 for c in subset['cases']:
  c['records']=[r for r in c['records'] if (c['image_id'],r['id']) in by_id]
  for r in c['records']:r['visual_reason']=by_id[c['image_id'],r['id']]['reason']
 assert sum(len(c['records']) for c in subset['cases'])==102
 (BASE/'review102-data.js').write_text('window.DOORWAY_DATA='+json.dumps(subset,ensure_ascii=False)+';',encoding='utf8')
 page=(BASE/'index.html').read_text(encoding='utf8').replace('src="data.js"','src="review102-data.js"').replace('src="review.js"','src="review102.js"').replace('初审复查 · 重新判定空间归属','102份视觉复核 · 空间归属').replace('20图已逐图预切。','仅显示视觉初筛选出的102份，其中8份点对为空，不能据此认定乱标。20图已逐图预切。')
 (BASE/'review102.html').write_text(page,encoding='utf8')
 js=(BASE/'review.js').read_text(encoding='utf8').replace('doorway_first_review_recheck_v2','doorway_visual_102_recheck_v2').replace("$('initialVerdict').textContent='初审质量判定：'","$('initialVerdict').textContent='复核疑点：'+r.visual_reason+'；初审质量判定：'")
 js=js.replace("save();renderAnswer()","save();msg('已自动保存：'+label);renderAnswer()")
 js=js.replace("{points:r.points},{points:c.points},null,{layers:polygons(c,d.cuts).flatMap", "{points:r.points},null,null,{layers:[{id:'reference',label:'GT参考',points:c.points,visible:false},...polygons(c,d.cuts).flatMap").replace("visible:false}]:[])});", "visible:false}]:[])]});")
 js=js.replace("if(p)s+=poly(p,colors[k])", "if(p){s+=poly(p,colors[k]);const m=xy(p.reduce((a,v)=>[a[0]+v[0]/p.length,a[1]+v[1]/p.length],[0,0]));s+=`<text x=\"${m[0]}\" y=\"${m[1]}\" text-anchor=\"middle\" fill=\"${colors[k]}\" font-size=\"18\" font-weight=\"bold\">空间${k+1}</text>`}")
 js=js.replace("if(p)trace(p,colors[k],3,true);", "if(p){trace(p,colors[k],3,true);const center=p.reduce((a,v)=>[a[0]+v[0]/p.length,a[1]+v[1]/p.length],[0,0]),q=Geo.erp(center),x=((q[0]/1024*w+offset)%w+w)%w,y=q[1]/512*h;ctx.font='bold 18px sans-serif';ctx.textAlign='center';ctx.lineWidth=4;ctx.strokeStyle='white';ctx.strokeText('空间'+(k+1),x,y);ctx.fillStyle=colors[k];ctx.fillText('空间'+(k+1),x,y);}")
 (BASE/'review102.js').write_text(js,encoding='utf8')

def main():
 OUT.mkdir(exist_ok=True)
 data=json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])
 for ci,c in enumerate(data['cases']):
  photo=Image.open(BASE/c['photo']).convert('RGB').resize((320,160))
  result=Image.new('RGB',(1920,40+math.ceil(len(c['records'])/6)*310),'white');draw=ImageDraw.Draw(result);draw.text((10,10),f"{ci:02d} {c['image']} : purple=reference blue=answer red=camera",fill='black')
  for ri,r in enumerate(c['records']):
   ox=(ri%6)*320;oy=40+(ri//6)*310
   result.paste(photo,(ox,oy+22));draw.text((ox+4,oy+3),f"{ri:02d} {r['worker']} pairs={len(r['points'] or [])//2}",fill='black')
   pts=r['points'] or [];f=[]
   for x,y in pts[1::2]:
    v=(y/512-.5)*math.pi
    if abs(math.tan(v))<1e-8:continue
    radius=1/math.tan(v);u=(x/1024-.5)*math.tau;f.append([radius*math.sin(u),-radius*math.cos(u)])
   # ERP points and direct adjacent segments are diagnostics, not repaired rings.
   for parity in [0,1]:
    ring=pts[parity::2]
    for a,b in zip(ring,ring[1:]+ring[:1]):
     aa=(ox+a[0]/1024*320,oy+22+a[1]/512*160);bb=(ox+b[0]/1024*320,oy+22+b[1]/512*160)
     if abs(a[0]-b[0])<512:draw.line([aa,bb],fill='#00ffff',width=2)
     draw.ellipse((aa[0]-2,aa[1]-2,aa[0]+2,aa[1]+2),fill='red')
   allp=f+c['floor']+[[0,0]];xs=[v[0] for v in allp];ys=[v[1] for v in allp];sc=min(290/(max(xs)-min(xs) or 1),110/(max(ys)-min(ys) or 1));xy=lambda p:(ox+10+(p[0]-min(xs))*sc,oy+190+(p[1]-min(ys))*sc)
   for poly,color in [(c['floor'],'#a050b0'),(f,'#007c9c')]:
    if poly:draw.line([xy(p) for p in poly]+[xy(poly[0])],fill=color,width=2)
   x,y=xy([0,0]);draw.ellipse((x-2,y-2,x+2,y+2),fill='red')
   draw.rectangle((ox,oy,ox+319,oy+309),outline='#cccccc')
  result.save(OUT/f'{ci:02d}.png')
 publish(data)
 print('20 sheets,',sum(len(c['records']) for c in data['cases']),'records')
if __name__=='__main__':main()
