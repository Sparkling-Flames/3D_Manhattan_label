#!/usr/bin/env python3
"""Render this repository's plain Markdown report into a standalone HTML file.

Only the intentionally small report syntax is supported: headings, paragraphs,
tables, unordered lists, fenced code, links, inline code, bold and images.
Research figures are embedded unchanged; no generative images or JavaScript.
"""
from pathlib import Path
import argparse,base64,html,re
from html.parser import HTMLParser

def render(source:Path):
    text=source.read_text(encoding='utf-8');base=source.parent
    assert '{{' not in text,'Unfilled report section'
    def target(x):
        if re.match(r'^(https?://|sandbox:|#)',x):return x
        return 'sandbox:'+str((base/x).resolve())
    def inline(s):
        out=[];last=0
        pattern=re.compile(r'`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)')
        for m in pattern.finditer(s):
            out.append(html.escape(s[last:m.start()]))
            if m.group(1) is not None:out.append('<code>'+html.escape(m.group(1))+'</code>')
            elif m.group(2) is not None:out.append('<strong>'+inline(m.group(2))+'</strong>')
            else:out.append('<a href="'+html.escape(target(m.group(4)),quote=True)+'">'+inline(m.group(3))+'</a>')
            last=m.end()
        out.append(html.escape(s[last:]));return ''.join(out)
    lines=text.splitlines();blocks=[];toc=[];i=0;heading_count=0
    while i<len(lines):
        s=lines[i].strip()
        if not s:i+=1;continue
        if s.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].strip().startswith('```'):code.append(lines[i]);i+=1
            blocks.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');i+=1;continue
        h=re.match(r'^(#{1,6})\s+(.+)$',s)
        if h:
            level=len(h.group(1));heading_count+=1;anchor='section-'+str(heading_count)
            if level==2:toc.append((anchor,h.group(2)))
            blocks.append(f'<h{level} id="{anchor}">'+inline(h.group(2))+f'</h{level}>');i+=1;continue
        img=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',s)
        if img:
            p=(base/img.group(2)).resolve();assert p.is_file(),p
            mime='image/png' if p.suffix.lower()=='.png' else 'image/jpeg'
            data=base64.b64encode(p.read_bytes()).decode()
            blocks.append('<figure><img src="data:'+mime+';base64,'+data+'" alt="'+html.escape(img.group(1),quote=True)+'"><figcaption>'+html.escape(img.group(1))+'</figcaption></figure>');i+=1;continue
        if s.startswith('|') and i+1<len(lines) and re.fullmatch(r'[\s|:\-]+',lines[i+1].strip()):
            header=[x.strip() for x in s.strip('|').split('|')];i+=2;rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                assert len(row)==len(header),(i,row,header)
                rows.append(row);i+=1
            blocks.append('<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in header)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>');continue
        if s.startswith('- '):
            items=[]
            while i<len(lines) and lines[i].strip().startswith('- '):items.append(lines[i].strip()[2:]);i+=1
            blocks.append('<ul>'+''.join('<li>'+inline(x)+'</li>' for x in items)+'</ul>');continue
        para=[s];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#','|','![','- ','```')):
            para.append(lines[i].strip());i+=1
        blocks.append('<p>'+inline(' '.join(para))+'</p>')
    css='''body{font-family:"Noto Sans CJK SC","Microsoft YaHei",system-ui,sans-serif;color:#192b3c;background:#eef2f5;margin:0;line-height:1.8;font-size:16px}main{max-width:1200px;margin:28px auto;padding:48px 60px;background:white;box-shadow:0 4px 24px #17324614}h1{font-size:31px;line-height:1.45;border-bottom:4px solid #237766;padding-bottom:20px}h2{font-size:24px;margin-top:45px;padding-top:8px;color:#164f55}h3{font-size:20px;margin-top:28px}p{margin:16px 0}a{color:#176c9a;text-decoration:underline;text-underline-offset:3px}code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;background:#f0f3f5;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}pre{padding:18px;background:#f3f5f7;overflow:auto}pre code{background:transparent;padding:0}.table-scroll{overflow-x:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}th{background:#e9f2f1;text-align:left;color:#174c50}th,td{padding:10px 12px;border:1px solid #dbe2e7;vertical-align:top}tbody tr:nth-child(even){background:#f7f9fa}figure{margin:28px 0;padding:12px;border:1px solid #e0e5e9;background:white}img{width:100%;height:auto;display:block}figcaption{font-size:14px;color:#526473;padding:10px 4px 0}nav{padding:18px 24px;background:#f2f6f8;margin:22px 0}nav ol{columns:2;padding-left:22px}nav a{font-size:14px}footer{margin-top:40px;padding-top:16px;border-top:1px solid #dce3e8;color:#627382;font-size:13px}@media(max-width:700px){main{padding:24px 16px;margin:0}h1{font-size:26px}nav ol{columns:1}table{font-size:13px}}@media print{body{background:white;font-size:10.5pt}main{box-shadow:none;margin:0;padding:0;max-width:none}h2,h3{break-after:avoid}tr,figure{break-inside:avoid}nav{display:none}a{color:inherit}}'''
    title=next(x[2:].strip() for x in lines if x.startswith('# '))
    navigation='<nav><strong>报告目录</strong><ol>'+''.join('<li><a href="#'+a+'">'+html.escape(t)+'</a></li>' for a,t in toc)+'</ol></nav>'
    body=blocks[0]+navigation+''.join(blocks[1:])
    result='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+css+'</style></head><body><main>'+body+'<footer>HOHONET人员分类与有效换类条件研究 · 真实v2数据 · 图像已嵌入，完整标签、事件与端点另有独立文件。</footer></main></body></html>'
    parser=HTMLParser();parser.feed(result);parser.close()
    dest=source.with_suffix('.html');dest.write_text(result,encoding='utf-8')
    print(str(dest),len(result.encode('utf-8')),'bytes',len(toc),'sections',result.count('<figure>'),'figures')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args();render(a.source)
