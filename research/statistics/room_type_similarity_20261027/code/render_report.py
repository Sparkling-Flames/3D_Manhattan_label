#!/usr/bin/env python3
"""Render one self-contained HTML reading copy from REPORT_ZH.md and saved figures."""
from pathlib import Path
import argparse,base64,html,mimetypes,re
import markdown

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);a=ap.parse_args();b=a.base.resolve()
    raw=(b/'REPORT_ZH.md').read_text()
    def embed(m):
        label,path=m.group(1),m.group(2);p=(b/path).resolve();assert p.is_file(),p
        mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        return f'![{label}](data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()})'
    raw=re.sub(r'!\[([^]]*)\]\(([^)]+)\)',embed,raw)
    body=markdown.markdown(raw,extensions=['tables','fenced_code','toc'],extension_configs={'toc':{'toc_depth':'2-3'}})
    content='''<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET 同用途的不同房间：质量与个人表现</title><style>
    :root{color-scheme:light;--ink:#182a3a;--muted:#526579;--line:#d9e2e9;--accent:#196c83}*{box-sizing:border-box}body{margin:0;background:#edf2f5;color:var(--ink);font:17px/1.8 system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}main{max-width:1180px;margin:36px auto;background:white;padding:46px 58px;box-shadow:0 5px 25px #1a384412;border-radius:8px}h1{font-size:31px;line-height:1.4;margin:0 0 25px;border-bottom:4px solid var(--accent);padding-bottom:22px}h2{font-size:25px;margin-top:2.6em;border-bottom:1px solid var(--line);padding-bottom:9px}h3{font-size:21px;margin-top:1.8em}p{margin:1em 0}a{color:#126d9b;text-decoration:none}a:hover{text-decoration:underline}table{border-collapse:collapse;font-size:14px;line-height:1.6;width:100%;margin:22px 0}th,td{border:1px solid var(--line);padding:9px 10px;vertical-align:top}th{background:#e9f2f5;font-weight:650;text-align:left}tr:nth-child(even) td{background:#f8fafb}code{font:0.88em/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-word;background:#eef3f6;padding:2px 4px;border-radius:3px}pre{overflow:auto;padding:18px;background:#eef3f6}pre code{padding:0;background:none}img{display:block;width:100%;height:auto;margin:22px auto;border:1px solid #e1e7eb}blockquote{border-left:4px solid var(--accent);padding:8px 18px;margin:22px 0;background:#f1f7f9}.note{color:var(--muted);font-size:14px;border:1px solid var(--line);padding:12px 16px;border-radius:5px}li{padding:3px 0}@media(max-width:750px){body{font-size:16px}main{margin:0;padding:24px 18px;border-radius:0}h1{font-size:25px}h2{font-size:22px}table{display:block;overflow-x:auto;font-size:13px}}@media print{body{background:white}main{max-width:none;margin:0;padding:0;box-shadow:none}h2,h3{break-after:avoid}img,table{break-inside:avoid}a{color:inherit}}
    </style></head><body><main><div class="note">完整阅读版 · 2026-10-27 · 采用main b2b0898b90bd631df37f1f2e75e8380800a43cf8。图像已嵌入，可离线阅读；表与脚本链接对应解压后的同一研究目录。</div>'''+body+'</main></body></html>'
    (b/'REPORT_ZH.html').write_text(content)
    print({'html_bytes':len(content.encode()),'embedded_images':content.count('data:image/'),'title':'REPORT_ZH.html'})

if __name__=='__main__':main()
