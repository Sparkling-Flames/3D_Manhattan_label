from pathlib import Path
import base64,re,html
import mistune
ROOT=Path(__file__).resolve().parents[1]
def main():
 text=(ROOT/'REPORT_ZH.md').read_text()
 # Add numerical illustrations to HTML only; the source tables remain in Markdown.
 text=text.replace('### 6.3 压缩本身确实改变了方法判断','### 6.3 压缩本身确实改变了方法判断\n\n![压缩与参考比较](figures/compression_changes_comparison.png)')
 text=text.replace('### 5.3 0.5px下的实际损失','![锁定底边的编辑代价](figures/bottom_lock_cost.png)\n\n### 5.3 0.5px下的实际损失')
 body=mistune.create_markdown(plugins=['table'])(text)
 def embed(m):
  p=ROOT/m.group(1)
  if p.is_file():return 'src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"'
  return m.group(0)
 body=re.sub(r'src="(figures/[^"]+)"',embed,body)
 css='''body{font:16px/1.85 system-ui,"Noto Sans CJK SC",sans-serif;color:#22313e;background:#f3f6f8;margin:0}main{max-width:1080px;margin:30px auto;background:#fff;padding:40px 52px;border:1px solid #d9e1e8;border-radius:8px}h1{font-size:29px;line-height:1.4}h2{font-size:23px;border-top:1px solid #dce3e8;padding-top:22px;margin-top:32px}h3{font-size:19px}p{margin:12px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.7;margin:18px 0}th,td{padding:9px 11px;border:1px solid #dce3e8;text-align:left;vertical-align:top}th{background:#edf3f7}pre{white-space:pre-wrap;word-break:break-word;padding:18px;background:#f1f5f7;font-size:13px;line-height:1.75}code{font-size:.9em}img{max-width:100%;height:auto}a{color:#125f88}strong{font-weight:650}header{border-bottom:3px solid #375c77;padding-bottom:12px;color:#536a7b;font-size:13px}.banner{padding:15px 20px;background:#fff6e9;border-left:4px solid #af7b32;margin:20px 0}.nav{font-size:14px;margin:18px 0}@media(max-width:750px){main{margin:0;padding:22px}table{font-size:12px}}@media print{body{background:white}main{max-width:none;border:0;padding:0;margin:0}h2{break-after:avoid}tr{break-inside:avoid}a{color:inherit}}'''
 top='<header>INDEPENDENT RESEARCH · 2026-10-05 · FOUR-IMAGE MECHANISM PANEL</header><div class="nav"><a href="EVIDENCE_VIEWER_ZH.html">打开完整名单／上下配对／BEV／来源展示</a> · <a href="README_ZH.md">复算说明</a></div><div class="banner">本报告有条件式数学与数值证据，没有原图视觉裁决。精确投票、编辑近似和人员支持的含义分别保留。</div>'
 (ROOT/'REPORT_ZH.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>全员布局共识可靠性研究</title><style>'+css+'</style></head><body><main>'+top+body+'</main></body></html>',encoding='utf-8')
if __name__=='__main__':main()
