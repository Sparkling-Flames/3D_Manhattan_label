"""Generate offline report and an 18-pair inspection atlas. No external assets or fonts."""
from pathlib import Path
import base64,json,math,html
import pandas as pd
import mistune
R=Path(__file__).resolve().parents[1]
CSS='''body{font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:#152334;background:#f4f6f9;margin:0;line-height:1.7}main{max-width:1050px;margin:36px auto;padding:42px;background:white;border-radius:10px}h1{font-size:28px;line-height:1.35}h2{font-size:22px;margin-top:38px;border-top:1px solid #dce3e9;padding-top:24px}h3{font-size:18px}p{margin:12px 0}table{border-collapse:collapse;font-size:14px;display:block;overflow:auto;margin:18px 0}th,td{border:1px solid #d8e0e8;padding:9px 12px;text-align:left;vertical-align:top}th{background:#edf2f7}code{background:#f1f4f7;padding:2px 4px;overflow-wrap:anywhere}pre{white-space:pre-wrap}a{color:#225787}img{max-width:100%;height:auto}figcaption,.sub{font-size:14px;color:#526477}figure{margin:24px 0;padding:16px;border:1px solid #dce3e9}nav{background:#132d46;color:white;padding:14px 28px}nav a{color:white;margin-right:24px}blockquote{border-left:4px solid #587693;margin:20px 0;padding:2px 22px;background:#f4f7fa}select,button{padding:10px;max-width:100%;font:inherit;margin:7px 12px 7px 0}details{margin:14px 0;padding:10px;border:1px solid #d8e0e8}footer{font-size:13px;color:#667;margin-top:32px} @media(max-width:700px){main{margin:0;padding:20px}h1{font-size:24px}table{font-size:12px}}'''
def b64(p):return 'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode()
def page(title,body,extra=''):
 return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+CSS+'</style><nav><a href="00_START_HERE.html">入口</a><a href="REPORT_ZH.html">报告</a><a href="ATLAS_18.html">原图与点集</a></nav><main>'+body+'</main>'+extra+'</html>'
def safe(o):
 if isinstance(o,dict):return {str(k):safe(v)for k,v in o.items()}
 if isinstance(o,list):return [safe(x)for x in o]
 if isinstance(o,float)and not math.isfinite(o):return None
 return o

def run():
 cases=json.loads((R/'results/visual_cases.json').read_text());cache=json.loads((R/'results/cache_with_exemplars.json').read_text());pairs=pd.read_csv(R/'results/pairwise.csv');pm={tuple(sorted([r.id_a,r.id_b])):r._asdict()for r in pairs.itertuples(index=False)}
 body=mistune.create_markdown(plugins=['table'])((R/'REPORT_ZH.md').read_text())
 body+='<h2>关键图证</h2><p>以下只绘制真实点，不补画推定墙连接。完整18项及逐点证据见图册。</p>'
 for i in [1,8,9,14]:
  c=cases[i-1];body+='<figure><img alt="'+html.escape(c['code'])+'" src="'+b64(R/'visual'/c['overlay'])+'"><figcaption>'+html.escape(c['analyst_note'])+'</figcaption></figure>'
 (R/'REPORT_ZH.html').write_text(page('局部点比较与不确定性',body))
 records=[]
 for c in cases:
  g=next(g for g in cache.values()if c['id_a']in g['ids']);d={**c,'image':b64(R/'visual'/c['overlay']),'crop_image':b64(R/'visual'/c['crop']),'group':g,'features':pm[tuple(sorted([c['id_a'],c['id_b']]))]};d['group']={k:v for k,v in g.items()if k!='Ds'};records.append(d)
 atlas='''<h1>18个作答对：局部覆盖与分区</h1><p>17张原始图、35份不同作答。知道已有评论后的开发性复看，不是独立语义金标准。</p><label>作答对 <select id="case"></select></label><label>全图分组配置 <select id="method"></select></label><p id="metrics"></p><p id="note"></p><details><summary>这张图在当前配置下的全部成员</summary><div id="groups"></div></details><img id="picture" alt="原图及两份真实点"><details><summary>原分辨率局部裁切</summary><p class="sub">每侧中心为该份作答最远的最近邻点；另一份点以黄色表示。图像边缘外的黑区为裁切留空，不代表原图新增内容。</p><img id="crop" alt="局部点对照"></details><details><summary>来源及边界</summary><pre id="source"></pre></details><footer>更改配置只读取已经完成的分区，不重拟合、不改点。相同组号不等于相同空间；近似关系与用户整图合簇决定分开。</footer>'''
 js='''<script>const data=PAYLOAD;const cs=document.getElementById('case'),ms=document.getElementById('method');data.forEach((c,i)=>cs.add(new Option(`${String(c.case_id).padStart(2,'0')} ${c.code} ${c.condition} ${c.worker_a}/${c.worker_b}`,i)));Object.keys(data[0].group.labels).forEach(x=>ms.add(new Option(x,x)));ms.value='OSPA1_6';function render(){const c=data[+cs.value],g=c.group,l=g.labels[ms.value],ia=g.ids.indexOf(c.id_a),ib=g.ids.indexOf(c.id_b),f=c.features;document.getElementById('picture').src=c.image;document.getElementById('crop').src=c.crop_image;document.getElementById('metrics').textContent=`点数 ${c.n_a}/${c.n_b}；OSPA1 ${c.ospa1.toFixed(3)}°；最大局部距离 ${c.hausdorff.toFixed(3)}°；9°内最多一一匹配 ${f.matched_9} 点；当前全图分区：${l[ia]===l[ib]?'同组':'异组'}`;document.getElementById('note').textContent=c.analyst_note;let groups={};l.forEach((x,i)=>(groups[x]??=[]).push(g.workers[i]));const el=document.getElementById('groups');el.replaceChildren();Object.entries(groups).forEach(([k,v])=>{let p=document.createElement('p');p.textContent=`组${k}（${v.length}人）：${v.join('、')}`;el.append(p)});document.getElementById('source').textContent=`canonical: ${c.id_a} / ${c.id_b}\n原图: ${c.source_path}\n原图 SHA256: ${c.source_sha256}\n证据性质: ${c.visual_review_status}\n方法: ${ms.value}`;}cs.onchange=render;ms.onchange=render;render();</script>'''.replace('PAYLOAD',json.dumps(safe(records),ensure_ascii=False,separators=(',',':')))
 (R/'ATLAS_18.html').write_text(page('原图与局部点检查',atlas,js))
 start='''<h1>局部点比较与不确定性｜研究交付</h1><p><strong>这轮的结果不是“换成Hausdorff就解决了”，而是明确测出了平均距离、局部覆盖、局部数量和整簇关系的不同。</strong></p><h2>先看什么</h2><p><a href="REPORT_ZH.html">完整中文报告</a>：结果、反例、方法取舍、有限池人数诊断及同一个人的耗时规律。</p><p><a href="ATLAS_18.html">18对原图交互图册</a>：切换作答对与全图分组配置，核对近似却分开、同点数局部不同、不同点数局部相近。</p><p><a href="REPORT_ZH.md">Markdown报告</a>；<a href="results/pairwise.csv">20672对完整距离与局部匹配明细</a>；<a href="results/memberships.csv">全部239单元×18配置成员表</a>；<a href="results/exemplar_memberships.csv">4种真实代表分组成员表</a>。</p><h2>复算</h2><pre>python -m pip install -r requirements.txt\npython code/run_all.py\n# 额外重画原图叠加：\npython code/run_all.py --render</pre><p>数值复算不需要联网、不需要模型权重。17张原图、全部数值输入及来源哈希已打包；未附字体文件。原始数据、排除人员及未确认修复未改。</p><h2>覆盖与限制</h2><p>2501原始记录，排除W019/W026后2388；2381份直接点集，214图、239图片×条件单元。17图18对视觉复看不等于全214图语义审查；开发数据不是独立验证。</p><p>时间问题按“同一个人在同房/相似场景的耗时规律”研究，未将时间距离混入几何分簇。</p><p><a href="results/TESTS.json">数学与实现测试</a>；<a href="results/REPRODUCED.json">独立进程复算记录</a>；<a href="INPUT_MANIFEST.json">数值输入清单</a>；<a href="ORIGINAL_IMAGE_MANIFEST.json">原图清单</a>。</p>'''
 (R/'00_START_HERE.html').write_text(page('研究交付入口',start))
 print('built HTML report and 18-case atlas')
if __name__=='__main__':run()
