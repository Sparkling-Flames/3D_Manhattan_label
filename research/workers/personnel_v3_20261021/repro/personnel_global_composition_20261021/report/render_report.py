"""Render this study's controlled Markdown to an offline HTML and a PDF.

No external assets or browser JavaScript are needed. Scientific figures are
embedded unchanged; the source Markdown and exact data tables remain separate.
The parser deliberately supports only the blocks used in this report.
"""
from __future__ import annotations
import argparse
import base64
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FONT = HERE / 'assets/HOHONET_Report_Regular.ttf'


def blocks(text):
    lines = text.splitlines(); result = []; i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1; continue
        if s.startswith('```'):
            code = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i]); i += 1
            result.append(('code', '\n'.join(code))); i += 1; continue
        m = re.match(r'^(#{1,4})\s+(.+)$', s)
        if m:
            result.append(('h' + str(len(m[1])), m[2])); i += 1; continue
        m = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', s)
        if m:
            result.append(('image', (m[1], m[2]))); i += 1; continue
        if s.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [v.strip() for v in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{2,}:?', v) for v in row):
                    rows.append(row)
                i += 1
            if rows:
                assert all(len(v) == len(rows[0]) for v in rows), 'table column mismatch'
                result.append(('table', rows))
            continue
        if re.match(r'^(-|\d+[.])\s+', s):
            result.append(('li', re.sub(r'^(-|\d+[.])\s+', '', s))); i += 1; continue
        if s == '---':
            result.append(('rule', '')); i += 1; continue
        p = [s]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#|\||!\[|```|- |\d+\. )', lines[i].strip()):
            p.append(lines[i].strip()); i += 1
        result.append(('p', ' '.join(p)))
    return result


def inline(s, pdf=False):
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', lambda m: '<font color="#41556d">' + m[1] + '</font>' if pdf else '<code>' + m[1] + '</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>' if pdf else r'<strong>\1</strong>', s)
    if pdf:
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: m[1] if not m[2].startswith('http') else '<link href="'+html.escape(m[2],quote=True)+'" color="#146b85">'+m[1]+'</link>', s)
    else:
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: '<a href="'+html.escape(m[2],quote=True)+'">'+m[1]+'</a>', s)
    return s


def render_html(doc, target):
    content = []; toc = []; section = 0
    for kind, value in doc:
        if kind.startswith('h'):
            section += 1; ident = f'section-{section}'
            content.append(f'<{kind} id="{ident}">{inline(value)}</{kind}>')
            if kind == 'h2':toc.append(f'<a href="#{ident}">{html.escape(value)}</a>')
        elif kind == 'p':content.append('<p>'+inline(value)+'</p>')
        elif kind == 'li':content.append('<p class="bullet">• '+inline(value)+'</p>')
        elif kind == 'table':
            rows = ['<tr>' + ''.join('<'+tag+'>'+inline(v)+'</'+tag+'>' for v in row)+'</tr>' for tag,row in [('th',value[0])]+[('td',r) for r in value[1:]]]
            content.append('<div class="table-wrap"><table>'+''.join(rows)+'</table></div>')
        elif kind == 'code':content.append('<pre><code>'+html.escape(value)+'</code></pre>')
        elif kind == 'image':
            alt,path=value; p=(HERE/path).resolve(); assert p.is_file(), p
            mime='image/png' if p.suffix=='.png' else 'image/jpeg'
            src='data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode('ascii')
            content.append('<figure><img src="'+src+'" alt="'+html.escape(alt,quote=True)+'"><figcaption>'+inline(alt)+'</figcaption></figure>')
        elif kind == 'rule':content.append('<hr>')
    css='''
    :root{color-scheme:light;--ink:#203049;--muted:#58687a;--teal:#176e85;--line:#dce5ec;--pale:#eef5f8}
    *{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:var(--ink);font:17px/1.85 system-ui,-apple-system,"Noto Sans SC","Microsoft YaHei",sans-serif}
    .top{height:8px;background:linear-gradient(90deg,#176e85,#2d4565)}main{max-width:1160px;margin:0 auto;padding:48px 64px 72px;background:white;min-height:100vh}
    h1{font-size:34px;line-height:1.4;margin:0 0 24px;letter-spacing:.02em}h2{font-size:25px;border-top:2px solid var(--line);padding-top:30px;margin-top:52px;line-height:1.5}
    h3{font-size:21px;line-height:1.5;margin-top:32px;color:#16536d}h4{font-size:18px;margin-top:24px}p{margin:14px 0}.bullet{padding-left:18px;text-indent:-14px}
    strong{font-weight:700}a{color:var(--teal);text-underline-offset:3px}nav{display:flex;flex-wrap:wrap;gap:7px 18px;margin:30px 0;padding:18px 20px;background:var(--pale);font-size:14px;line-height:1.7}
    .table-wrap{overflow:auto;margin:24px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}th{text-align:left;background:#e8f0f5;font-weight:700;border-bottom:2px solid #bacdd9}td,th{padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--line)}tr:nth-child(even) td{background:#f8fafc}
    figure{margin:28px 0}img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:3px}figcaption{font-size:14px;color:var(--muted);margin-top:10px;line-height:1.7}
    code{font-size:.86em;color:#41556d;overflow-wrap:anywhere}pre{padding:18px;background:#f1f4f7;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.7}hr{border:0;border-top:1px solid var(--line);margin:32px 0}
    footer{font-size:13px;color:var(--muted);border-top:1px solid var(--line);margin-top:48px;padding-top:18px}
    @media(max-width:760px){main{padding:28px 20px}h1{font-size:27px}h2{font-size:23px}body{font-size:16px}td,th{padding:8px}table{font-size:13px}}
    @media print{main{max-width:none;padding:0}nav{display:none}body{font-size:11pt}h2{break-before:page}figure, tr{break-inside:avoid}a{color:inherit}}
    '''
    title='HOHONET 人员分类与整体构成研究 · 2026-10-21'
    body='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+css+'</style></head><body><div class="top"></div><main><nav aria-label="目录">'+''.join(toc)+'</nav>'+''.join(content)+'<footer>离线报告：正文、表格与图像均包含在本文件。精确标签、成员集合与事件小表可单独取得；源数据及旧成果保持其原阶段身份。</footer></main></body></html>'
    target.write_text(body,encoding='utf8')


def render_pdf(doc,target):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, CondPageBreak
    from reportlab.lib.utils import ImageReader
    pdfmetrics.registerFont(TTFont('NotoSC',str(FONT)))
    pdfmetrics.registerFontFamily('NotoSC',normal='NotoSC',bold='NotoSC',italic='NotoSC',boldItalic='NotoSC')
    ink=colors.HexColor('#203049');teal=colors.HexColor('#16536d');muted=colors.HexColor('#58687a')
    base=dict(fontName='NotoSC',wordWrap='CJK',textColor=ink,alignment=TA_LEFT,allowWidows=0,allowOrphans=0)
    styles={
        'h1':ParagraphStyle('Title',fontSize=22,leading=33,spaceAfter=20,**base),
        'h2':ParagraphStyle('H2',fontSize=16,leading=25,spaceBefore=12,spaceAfter=14,keepWithNext=True,**base),
        'h3':ParagraphStyle('H3',fontSize=12.5,leading=20,spaceBefore=14,spaceAfter=9,keepWithNext=True,**{**base,'textColor':teal}),
        'h4':ParagraphStyle('H4',fontSize=11,leading=18,spaceBefore=12,spaceAfter=7,keepWithNext=True,**base),
        'p':ParagraphStyle('Body',fontSize=10,leading=17.5,spaceAfter=9,**base),
        'li':ParagraphStyle('Bullet',fontSize=10,leading=17.5,leftIndent=12,firstLineIndent=-10,spaceAfter=7,**base),
        'table':ParagraphStyle('Cell',fontSize=8.3,leading=13.3,spaceAfter=0,**base),
        'thead':ParagraphStyle('HeaderCell',fontSize=8.5,leading=13.5,spaceAfter=0,**base),
        'caption':ParagraphStyle('Caption',fontSize=8.8,leading=14,spaceBefore=7,spaceAfter=12,**{**base,'textColor':muted}),
        'code':ParagraphStyle('Code',fontSize=7.7,leading=11.5,spaceAfter=10,backColor=colors.HexColor('#f1f4f7'),borderPadding=9,**base)
    }
    page_w,page_h=595.28,841.89;left=43;right=43;top=48;bottom=43;width=page_w-left-right
    story=[];seen_h2=False;pending_image_heading=None
    for bi,(kind,value) in enumerate(doc):
        if kind.startswith('h'):
            if kind=='h2':
                # Reserve a meaningful heading opening without imposing one
                # section per page when a short section can fit naturally.
                story.append(CondPageBreak(150));seen_h2=True
            heading=Paragraph(inline(value,True),styles[kind])
            if kind=='h3' and bi+1<len(doc) and doc[bi+1][0]=='image':
                pending_image_heading=heading
            else:story.append(heading)
        elif kind in ('p','li'):
            story.append(Paragraph(('• ' if kind=='li' else '')+inline(value,True),styles[kind]))
        elif kind=='table':
            cols=len(value[0]);widths=[width/cols]*cols
            # Explicitly privilege the text-heavy final column in small
            # definition/mapping tables; larger numeric tables stay even.
            if cols==2:widths=[width*.31,width*.69]
            elif cols==3:widths=[width*.23,width*.23,width*.54]
            elif cols==4:widths=[width*.20,width*.18,width*.27,width*.35]
            cells=[[Paragraph(inline(v,True),styles['thead' if i==0 else 'table']) for v in row] for i,row in enumerate(value)]
            table=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f0f5')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7fafc')]),
                ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#bacdd9')),
                ('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#dce5ec')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
                ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)
            ]));story.extend([Spacer(1,5),table,Spacer(1,13)])
        elif kind=='image':
            alt,path=value;p=(HERE/path).resolve();iw,ih=ImageReader(str(p)).getSize()
            scale=min(width/iw,470/ih);im=Image(str(p),width=iw*scale,height=ih*scale)
            caption=Paragraph(inline(alt,True),styles['caption'])
            opening=[pending_image_heading] if pending_image_heading is not None else []
            story.append(KeepTogether(opening+[Spacer(1,8),im,caption]))
            pending_image_heading=None
        elif kind=='code':
            story.append(Paragraph(html.escape(value).replace('\n','<br/>'),styles['code']))
        elif kind=='rule':story.append(Spacer(1,10))
    def page(c,document):
        c.saveState();c.setFont('NotoSC',8);c.setFillColor(muted)
        c.drawString(left,page_h-28,'HOHONET · 人员分类与整体构成研究')
        c.drawRightString(page_w-right,page_h-28,'2026-10-21')
        c.setStrokeColor(colors.HexColor('#dce5ec'));c.line(left,34,page_w-right,34)
        c.drawString(left,22,'冻结 main 51b519f · B8L2 主 / D10 敏感性')
        c.drawRightString(page_w-right,22,str(document.page));c.restoreState()
    pdf=SimpleDocTemplate(str(target),pagesize=(page_w,page_h),leftMargin=left,rightMargin=right,topMargin=top,bottomMargin=bottom,title='HOHONET 人员分类与整体构成研究',author='HOHONET 人员研究')
    pdf.build(story,onFirstPage=page,onLaterPages=page)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=HERE/'REPORT_ZH.md');ap.add_argument('--html-only',action='store_true');args=ap.parse_args()
    doc=blocks(args.source.read_text(encoding='utf8'));render_html(doc,HERE/'HOHONET_personnel_global_composition_20261021.html')
    if not args.html_only:render_pdf(doc,HERE/'HOHONET_personnel_global_composition_20261021.pdf')
    (HERE/'RENDER_RECEIPT.json').write_text(json.dumps({'source':args.source.name,'blocks':len(doc),'images':sum(k=='image' for k,v in doc),'tables':sum(k=='table' for k,v in doc),'self_contained_html':True,'figures_generated_from_actual_data':True},indent=2),encoding='utf8')


if __name__=='__main__':main()
