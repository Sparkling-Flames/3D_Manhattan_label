"""Build a self-contained HTML report from the delivered Markdown."""
from pathlib import Path
import base64,re
import mistune
ROOT=Path(__file__).resolve().parent
md=mistune.create_markdown(escape=False,plugins=['table','url'])
text=(ROOT/'REPORT_ZH.md').read_text()
body=md(text)
for name in ['real24_complete_boundary.png','thin_feature_sampling.png']:
    data=base64.b64encode((ROOT/'figures'/name).read_bytes()).decode()
    body=body.replace('figures/'+name,'data:image/png;base64,'+data)
sources=md((ROOT/'SOURCES_ZH.md').read_text())
css='''body{font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif;color:#24323a;background:#f3f5f5;margin:0}main{max-width:1120px;margin:32px auto;padding:40px 48px;background:white;border:1px solid #e0e5e7}h1{font-size:32px;line-height:1.35}h2{margin-top:42px;padding-bottom:8px;border-bottom:2px solid #dbe3e7;font-size:25px}h3{font-size:20px;margin-top:28px}p{margin:14px 0}a{color:#194f79}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.65;margin:20px 0}th,td{border:1px solid #dce2e5;padding:9px;vertical-align:top}th{background:#edf2f4;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f7;padding:16px;font-size:13px}code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;overflow-wrap:anywhere}img{width:100%;height:auto}strong{color:#132d40}li{margin:5px 0}summary{cursor:pointer;font-weight:bold}details{padding:16px;background:#f8f9fa;margin:30px 0}@media(max-width:800px){main{padding:20px;margin:0}table{font-size:12px}}'''
html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全景布局连线、质量与全员共识 · 独立研究</title><style>'+css+'</style><main>'+body+'<details><summary>仓库来源与可访问性账本</summary>'+sources+'</details></main></html>'
(ROOT/'REPORT_ZH.html').write_text(html)
print('report chars',len(text),'html bytes',len(html.encode()))
