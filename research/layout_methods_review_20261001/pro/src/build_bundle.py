"""Build a self-contained HTML report and the research ZIP from computed outputs."""
from pathlib import Path
import json,re,base64,zipfile,hashlib
import mistune
BASE=Path(__file__).resolve().parents[1]
def main():
 md=(BASE/'REPORT_zh.md').read_text();body=mistune.create_markdown(plugins=['table'])(md)
 def inline(m):
  path=BASE/m.group(1)
  if path.is_file():return 'src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'"'
  return m.group(0)
 body=re.sub(r'src="(figures/[^\"]+\.png)"',inline,body)
 css='''body{margin:0;background:#f5f5f2;color:#202529;font:17px/1.85 system-ui,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}main{max-width:1050px;margin:auto;padding:48px 50px;background:white}h1{font-size:30px;line-height:1.5}h2{font-size:23px;margin-top:48px;padding-top:16px;border-top:1px solid #ddd}h3{font-size:19px;margin-top:30px}p{margin:16px 0}img{display:block;max-width:100%;height:auto;margin:28px auto}a{color:#155e73;overflow-wrap:anywhere}code{font-size:.9em;background:#f1f3f4;padding:3px 5px;overflow-wrap:anywhere}pre{overflow:auto;padding:18px;background:#f1f3f4}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #ddd;padding:10px}small{color:#59656a}@media(max-width:700px){main{padding:22px}body{font-size:16px}}'''
 html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全景 layout 局部路径与方法研究</title><style>'+css+'</style><main><small>独立研究报告 · 2026-10-01 · 数学分析 / 数值对照 / 方法建议</small>'+body+'</main></html>'
 (BASE/'REPORT_zh.html').write_text(html)
 inventory=[]
 for p in sorted(BASE.rglob('*')):
  if p.is_file() and p.name!='FILES.json' and not any(t in p.parts for t in ['__pycache__','matplotlib_cache']):
   inventory.append(dict(path=str(p.relative_to(BASE)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 (BASE/'FILES.json').write_text(json.dumps(inventory,indent=2))
 target=BASE.parent/'layout_methods_20261001.zip'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(BASE.rglob('*')):
   if p.is_file() and not any(t in p.parts for t in ['__pycache__','matplotlib_cache']):z.write(p,BASE.name+'/'+str(p.relative_to(BASE)))
 print('HTML', (BASE/'REPORT_zh.html').stat().st_size,'ZIP',target.stat().st_size,'files',len(inventory)+1)
if __name__=='__main__':main()
