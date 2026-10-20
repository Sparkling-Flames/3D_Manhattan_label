"""Self-contained Chinese research report in HTML and PDF.

No browser or external fonts/assets are required to read the HTML. PDF uses a
caller-supplied Chinese static TTF. The input Markdown and all numeric tables
remain in the compact reproducibility package.
"""
from __future__ import annotations
import argparse,base64,html,json,re,shutil
from pathlib import Path
import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether

HERE=Path(__file__).resolve().parents[1]
NAME='HOHONET_personnel_classification_20261021'
INK='#162c42';BLUE='#106a7e';PALE='#edf4f7'

def table_md(headers,rows):
    return '\n'.join(['|'+ '|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(str(x) for x in row)+'|' for row in rows])

def members_appendix():
    frames=[pd.read_csv(HERE/'labels'/f'{c}_labels.csv') for c in ['manual','semi']]
    out=[]
    for c,d in zip(['Manual','Semi'],frames):
        out+=['### '+c+' A2几何关系分区','']
        rows=[]
        for cl,g in d[d.geometry_relation_class.ne('unassigned')].groupby('geometry_relation_class'):
            rows.append([cl,len(g),'、'.join(g.worker_id)])
        out += [table_md(['类','人数','全数据描述成员'],rows),'']
    d=frames[1]
    out+=['### Semi SP_T完整比较组成员','']
    out+=['、'.join(d.loc[d.position_scale_class.eq('SP_T'),'worker_id'])+'。','']
    out+=['### 冻结Semi结构探索细类（不作推荐主类）','']
    rows=[]
    for cl,g in d[d.structure_fine_class.ne('unassigned')].groupby('structure_fine_class'):
        rows.append([cl,len(g),'、'.join(g.worker_id)])
    out += [table_md(['探索细类','人数','实际成员'],rows),'']
    return '\n'.join(out)

def blocks(text):
    lines=text.splitlines();out=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line or line.startswith('<!--'):
            i+=1;continue
        m=re.match(r'^(#{1,6})\s+(.+)$',line)
        if m:out.append(('heading',(len(m[1]),m[2])));i+=1;continue
        m=re.match(r'^!\[([^]]*)\]\(([^)]+)\)$',line)
        if m:out.append(('image',(m[1],m[2])));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{2,}:?',c) for c in cells):rows.append(cells)
                i+=1
            out.append(('table',rows));continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].strip().startswith('```'):code.append(lines[i]);i+=1
            i+=1;out.append(('code','\n'.join(code)));continue
        if line.startswith('- '):out.append(('bullet',line[2:]));i+=1;continue
        p=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||!\[|```|<!--|- )',lines[i].strip()):p.append(lines[i].strip());i+=1
        out.append(('paragraph',' '.join(p)))
    return out

def inline(s,pdf=False):
    s=html.escape(str(s),quote=False)
    if pdf:
        s=s.replace('−','-').replace('—','-').replace('–','-').replace('\u2011','-')
    s=re.sub(r'`([^`]+)`',lambda m:f'<font color="{BLUE}">{m[1]}</font>' if pdf else '<code>'+m[1]+'</code>',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>' if pdf else r'<strong>\1</strong>',s)
    # All links are explicit, retained primary references; no remote content is loaded.
    s=re.sub(r'\[([^]]+)\]\((https?://[^)]+)\)',lambda m:('<link href="'+html.escape(m[2],quote=True)+'" color="'+BLUE+'">'+m[1]+'</link>') if pdf else '<a href="'+html.escape(m[2],quote=True)+'">'+m[1]+'</a>',s)
    s=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<i>\1</i>',s)
    return s

def build_html(bs,path):
    parts=[];nav=[];sid=0
    for kind,b in bs:
        if kind=='heading':
            level,title=b
            if level==2:sid+=1;nav.append((sid,title))
            parts.append(f'<h{level}'+(f' id="s{sid}"' if level==2 else '')+'>'+inline(title)+f'</h{level}>')
        elif kind in ['paragraph','bullet']:parts.append(('<p class="bullet">• ' if kind=='bullet' else '<p>')+inline(b)+'</p>')
        elif kind=='table':
            rows=b;parts.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>')
            parts += ['<tr>'+''.join('<td>'+inline(x)+'</td>' for x in row)+'</tr>' for row in rows[1:]]
            parts.append('</tbody></table></div>')
        elif kind=='image':
            title,rel=b;src=HERE/rel
            data=base64.b64encode(src.read_bytes()).decode()
            parts.append('<figure><img loading="lazy" src="data:image/png;base64,'+data+'" alt="'+html.escape(title,quote=True)+'"><figcaption>'+inline(title)+'</figcaption></figure>')
        elif kind=='code':parts.append('<pre><code>'+html.escape(b)+'</code></pre>')
    style='''
    :root{--ink:#162c42;--blue:#106a7e;--line:#d8e3ea;--pale:#edf4f7}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f6f8;color:var(--ink);font-family:system-ui,-apple-system,"Microsoft YaHei","Noto Sans SC",sans-serif;line-height:1.78}
    header{padding:27px 36px;background:var(--ink);color:white;border-bottom:5px solid #26a5b6}header .eyebrow{font-size:13px;letter-spacing:2px;color:#9ddae2}header .title{font-size:25px;font-weight:650;margin-top:5px}header .meta{font-size:13px;color:#d9e6ed;margin-top:7px}
    .layout{display:grid;grid-template-columns:225px minmax(0,1120px);gap:28px;max-width:1430px;margin:0 auto;padding:25px 25px 65px}nav{position:sticky;top:20px;align-self:start;font-size:13px;line-height:1.7}nav a{display:block;padding:7px 9px;color:#395669;text-decoration:none;border-bottom:1px solid #dbe5eb}nav a:hover{background:#dfeef2;color:#064a5d}nav .label{font-weight:700;font-size:14px;margin:9px}
    main{background:white;border:1px solid var(--line);padding:34px 42px;min-width:0;box-shadow:0 2px 9px #162c4208}h1{font-size:30px;line-height:1.3;margin:0 0 20px;color:var(--ink)}h2{font-size:24px;line-height:1.4;border-top:3px solid #d8edf1;padding-top:23px;margin:47px 0 20px;scroll-margin-top:20px}h3{font-size:19px;color:var(--blue);margin:27px 0 13px}p{font-size:15px;margin:14px 0;overflow-wrap:anywhere}strong,b{font-weight:700}code{font-size:.89em;color:#125e74;background:#f0f5f7;padding:1px 4px;border-radius:3px;overflow-wrap:anywhere}a{color:#086a87;text-underline-offset:3px}
    .table-wrap{overflow-x:auto;margin:22px 0;border:1px solid var(--line);border-radius:4px}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.65}th{background:var(--pale);font-weight:650;color:#153e55}th,td{padding:9px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}tr:nth-child(even) td{background:#fafcfd}tr:last-child td{border-bottom:none}figure{margin:29px 0 36px;border:1px solid var(--line);padding:12px;background:white}figure img{display:block;width:100%;height:auto}figcaption{font-size:13px;color:#536b7d;border-top:1px solid #e7edf1;padding-top:10px;margin-top:10px}pre{white-space:pre-wrap;padding:15px;background:#edf3f6}footer{padding:20px;text-align:center;font-size:12px;color:#577286}
    @media(max-width:900px){.layout{display:block;padding:13px}nav{position:relative;display:flex;flex-wrap:wrap;gap:3px;margin-bottom:18px}nav .label{width:100%}nav a{padding:4px 7px;border:1px solid #dbe5eb;background:white}main{padding:23px 19px}h1{font-size:25px}h2{font-size:21px}header{padding:22px}}
    @media print{body{background:white}header,nav,footer{display:none}.layout{display:block;padding:0}main{border:0;box-shadow:none;padding:0}h2{break-before:page}figure,tr{break-inside:avoid}a{color:inherit}}
    '''
    toc='<div class="label">阅读导航</div>'+''.join(f'<a href="#s{i}">{html.escape(t)}</a>' for i,t in nav)
    page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET人员标法分类研究</title><style>'+style+'</style></head><body><header><div class="eyebrow">HOHONET / PERSONNEL TAXONOMY</div><div class="title">人员类别、局部结构与团队贡献</div><div class="meta">Manual / Semi 独立研究 · 20261021 v1 · 全文、成员与16幅图均可离线阅读</div></header><div class="layout"><nav>'+toc+'</nav><main>'+''.join(parts)+'</main></div><footer>完整代码、逐人标签、楼外标签、精确团队与证据见配套复现包。</footer></body></html>'
    path.write_text(page,encoding='utf8')

class ResearchDoc(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='H2':
            key='outline-'+str(getattr(self,'_outline_n',0));self._outline_n=getattr(self,'_outline_n',0)+1
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(flowable.getPlainText(),key,level=0)

def build_pdf(bs,path,font,bold_font=None):
    pdfmetrics.registerFont(TTFont('ResearchCJK',str(font)))
    pdfmetrics.registerFont(TTFont('ResearchCJKBold',str(bold_font or font)))
    pdfmetrics.registerFontFamily('ResearchCJK',normal='ResearchCJK',bold='ResearchCJKBold',italic='ResearchCJK',boldItalic='ResearchCJKBold')
    W,H=A4;avail=W-90
    doc=ResearchDoc(str(path),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=48,bottomMargin=44,
         title='HOHONET 人员标法分类与换人、换类研究',author='HOHONET personnel taxonomy study',pageCompression=1)
    base=dict(fontName='ResearchCJK',textColor=colors.HexColor(INK),wordWrap='CJK',splitLongWords=True,alignment=TA_LEFT)
    styles={
      'body':ParagraphStyle('Body',fontSize=9.6,leading=15.5,spaceAfter=9,**base),
      'H1':ParagraphStyle('H1',fontSize=23,leading=31,spaceAfter=18,fontName='ResearchCJKBold',textColor=colors.HexColor(INK),wordWrap='CJK',keepWithNext=True),
      'H2':ParagraphStyle('H2',fontSize=15,leading=22,spaceBefore=15,spaceAfter=11,fontName='ResearchCJKBold',textColor=colors.HexColor(BLUE),wordWrap='CJK',keepWithNext=True),
      'H3':ParagraphStyle('H3',fontSize=11.7,leading=18,spaceBefore=11,spaceAfter=7,fontName='ResearchCJKBold',textColor=colors.HexColor(INK),wordWrap='CJK',keepWithNext=True),
      'cell':ParagraphStyle('Cell',fontSize=8.1,leading=12.8,spaceAfter=0,**base),
      'caption':ParagraphStyle('Caption',fontSize=9,leading=14,spaceBefore=7,spaceAfter=11,**base),
      'code':ParagraphStyle('Code',fontSize=8.1,leading=12.4,spaceAfter=10,backColor=colors.HexColor(PALE),borderPadding=6,**base)}
    story=[]
    def length(x):return sum(1 if ord(c)>127 else .54 for c in re.sub(r'[`*]','',str(x)))
    for kind,b in bs:
        if kind=='heading':
            level,title=b
            if level==2 and title.startswith('二、'):story.append(PageBreak())
            story.append(Paragraph(inline(title,True),styles['H1' if level==1 else 'H2' if level==2 else 'H3']))
        elif kind in ['paragraph','bullet']:
            p=Paragraph(('• ' if kind=='bullet' else '')+inline(b,True),styles['body'])
            story.append(KeepTogether([p]) if re.match(r'^\[R\d+\]',b) else p)
        elif kind=='table':
            rows=b;n=len(rows[0]);weights=[]
            for j in range(n):
                vals=[length(r[j]) for r in rows if len(r)>j]
                weights.append(max(7,min(60,max(vals))))
            ws=[avail*x/sum(weights) for x in weights]
            minimum=32
            ws=[max(minimum,x) for x in ws];ws=[x*avail/sum(ws) for x in ws]
            cellrows=[[Paragraph(('<b>'+inline(x,True)+'</b>') if i==0 else inline(x,True),styles['cell']) for x in row] for i,row in enumerate(rows)]
            t=Table(cellrows,colWidths=ws,repeatRows=1,hAlign='LEFT')
            cmds=[('BACKGROUND',(0,0),(-1,0),colors.HexColor(PALE)),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.65,colors.HexColor('#91aebe')),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d1dfe7'))]
            for i in range(2,len(rows),2):cmds.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#f8fafb')))
            t.setStyle(TableStyle(cmds));t.spaceBefore=4;story.extend([t,Spacer(1,12)])
        elif kind=='image':
            title,rel=b;p=HERE/rel
            with PILImage.open(p) as im:iw,ih=im.size
            draw_w=avail;draw_h=draw_w*ih/iw
            if draw_h>H-152:draw_h=H-152;draw_w=draw_h*iw/ih
            story.append(KeepTogether([Image(str(p),width=draw_w,height=draw_h),Paragraph(inline(title,True),styles['caption'])]))
        elif kind=='code':story.append(Paragraph(inline(b,True).replace('\n','<br/>'),styles['code']))
    def page(c,d):
        c.saveState();c.setStrokeColor(colors.HexColor('#c8dbe6'));c.line(45,H-32,W-45,H-32)
        c.setFont('ResearchCJK',7.6);c.setFillColor(colors.HexColor('#577286'));c.drawString(45,H-23,'HOHONET 人员标法分类 / 20261021 v1')
        c.drawRightString(W-45,H-23,'B8L2 主线 · D10 敏感性')
        c.setFont('ResearchCJK',8);c.drawString(45,25,'正文、成员、楼外检查与实际替换证据');c.drawRightString(W-45,25,str(d.page));c.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--font',type=Path,required=True);ap.add_argument('--bold-font',type=Path);ap.add_argument('--html-only',action='store_true')
    args=ap.parse_args();args.out.mkdir(exist_ok=True,parents=True)
    source=HERE/'REPORT_ZH.md';s=source.read_text()
    block='<!-- AUTO_MEMBERS_BEGIN -->\n'+members_appendix()+'\n<!-- AUTO_MEMBERS_END -->'
    if '<!-- AUTO_MEMBERS -->' in s:s=s.replace('<!-- AUTO_MEMBERS -->',block)
    else:s=re.sub(r'<!-- AUTO_MEMBERS_BEGIN -->.*?<!-- AUTO_MEMBERS_END -->',lambda _:block,s,flags=re.S)
    source.write_text(s,encoding='utf8');bs=blocks(s)
    hp=args.out/(NAME+'.html');build_html(bs,hp)
    if not args.html_only:build_pdf(bs,args.out/(NAME+'.pdf'),args.font,args.bold_font)
    for cond in ['manual','semi']:shutil.copy2(HERE/'labels'/f'{cond}_labels.csv',args.out/f'HOHONET_{cond}_labels_20261021.csv')
    print(json.dumps({'report_characters':len(s),'blocks':len(bs),'figures':sum(k=='image' for k,_ in bs),'tables':sum(k=='table' for k,_ in bs),'html_bytes':hp.stat().st_size,'pdf_bytes':(args.out/(NAME+'.pdf')).stat().st_size if not args.html_only else None},ensure_ascii=False))

if __name__=='__main__':main()
