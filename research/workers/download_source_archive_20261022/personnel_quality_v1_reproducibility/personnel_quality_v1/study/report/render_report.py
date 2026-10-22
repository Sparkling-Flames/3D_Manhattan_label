#!/usr/bin/env python3
"""Render this study's Markdown report to a Chinese, embedded-font PDF.

This deliberately small renderer supports this report's headings, paragraphs,
lists, tables and local figures. It is not a general Markdown browser.
"""
from __future__ import annotations
import argparse, html, re, json
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT,TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,KeepTogether
from PIL import Image as PILImage

HERE=Path(__file__).resolve().parent
NAVY=colors.HexColor('#123C54')
TEAL=colors.HexColor('#087F8C')
GRAY=colors.HexColor('#57636D')
PAGE_W,PAGE_H=A4
MARGIN=43
WIDTH=PAGE_W-2*MARGIN

def inline(text):
    text=html.escape(text)
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:f'<a href="{m[2]}" color="#087F8C">{m[1]}</a>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
    return text

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,default=HERE/'REPORT_ZH.md')
    ap.add_argument('--out',type=Path,default=HERE/'personnel_quality_v1_report_zh.pdf')
    ap.add_argument('--font-dir',type=Path,default=HERE/'assets')
    a=ap.parse_args()
    pdfmetrics.registerFont(TTFont('NotoSC',str(a.font_dir/'NotoSansSC-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NotoSC-Bold',str(a.font_dir/'NotoSansSC-Bold.ttf')))
    pdfmetrics.registerFontFamily('NotoSC',normal='NotoSC',bold='NotoSC-Bold',italic='NotoSC',boldItalic='NotoSC-Bold')
    body=ParagraphStyle('body',fontName='NotoSC',fontSize=10.3,leading=16.4,textColor=colors.HexColor('#202830'),
                        spaceAfter=9,wordWrap='CJK',allowWidows=0,allowOrphans=0)
    title=ParagraphStyle('title',parent=body,fontName='NotoSC-Bold',fontSize=23,leading=32,textColor=NAVY,spaceBefore=4,spaceAfter=13)
    h2=ParagraphStyle('h2',parent=body,fontName='NotoSC-Bold',fontSize=15.5,leading=23,textColor=NAVY,spaceBefore=17,spaceAfter=10,keepWithNext=True)
    h3=ParagraphStyle('h3',parent=h2,fontSize=12.2,leading=19,spaceBefore=11,spaceAfter=8)
    cell=ParagraphStyle('cell',parent=body,fontSize=8.5,leading=12.4,spaceAfter=0,allowWidows=1,allowOrphans=1)
    head=ParagraphStyle('head',parent=cell,fontName='NotoSC-Bold',textColor=colors.white,fontSize=8.5,leading=12.5)
    caption=ParagraphStyle('caption',parent=body,fontSize=8.5,leading=13,textColor=GRAY,spaceAfter=10)
    bullet=ParagraphStyle('bullet',parent=body,leftIndent=10,firstLineIndent=0,bulletIndent=0,spaceAfter=7)
    story=[]; lines=a.source.read_text(encoding='utf-8').splitlines(); i=0; table_count=0; figure_count=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1;continue
        if line.startswith('# '):
            story.append(Paragraph(inline(line[2:]),title));i+=1;continue
        if line.startswith('## '):
            story.append(Paragraph(inline(line[3:]),h2));i+=1;continue
        if line.startswith('### '):
            story.append(Paragraph(inline(line[4:]),h3));i+=1;continue
        if line.startswith('!['):
            m=re.match(r'!\[([^\]]*)\]\(([^)]+)\)',line)
            path=(a.source.parent/m[2]).resolve()
            with PILImage.open(path) as im:iw,ih=im.size
            w=WIDTH;h=w*ih/iw
            if h>480:w*=480/h;h=480
            story.append(KeepTogether([Image(str(path),width=w,height=h),Spacer(1,5),Paragraph(inline(m[1]),caption)]))
            i+=1;figure_count+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[v.strip() for v in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',v.replace(' ','')) for v in cells):
                    rows.append(cells)
                i+=1
            n=len(rows[0]);assert all(len(r)==n for r in rows)
            if rows[0][0]=='人员' and '95%区间' in rows[0]:
                weights=[.70,.52,1.22,.77,.75,1.60,.73,1.15]
            elif rows[0][0]=='人员' and '较宽可判n' in rows[0]:
                weights=[.65,1.2,1.15,.85,1.20,1.0,1.0]
            elif rows[0][0]=='人员' and '初始I' in rows[0]:
                weights=[.7,.7,.7,.9,.9,.9,.9,1.0]
            elif n==4 and rows[0][0]=='维度':
                weights=[.9,2.0,2.0,1.3]
            elif n==7:weights=[1.5,1,1.1,1,1,1,1]
            elif n==5:weights=[1.8,1,1,1,1]
            elif n==3:weights=[1.1,2,3]
            elif n==2:weights=[1.4,4.0]
            else:weights=[1]*n
            widths=[WIDTH*w/sum(weights) for w in weights]
            data=[[Paragraph(inline(c),head if j==0 else cell) for c in row] for j,row in enumerate(rows)]
            t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
            commands=[('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
                      ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                      ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
                      ('LINEBELOW',(0,0),(-1,0),.6,NAVY),
                      ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#CAD5DB'))]
            for j in range(1,len(rows)):
                if j%2==0:commands.append(('BACKGROUND',(0,j),(-1,j),colors.HexColor('#F1F6F8')))
            t.setStyle(TableStyle(commands));story.extend([t,Spacer(1,11)]);table_count+=1;continue
        if line.startswith('- '):
            story.append(Paragraph(inline(line[2:]),bullet,bulletText='•'));i+=1;continue
        paras=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#','|','![','- ')):
            paras.append(lines[i].strip());i+=1
        story.append(Paragraph(inline(' '.join(paras)),body))

    def decorate(canvas,doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#C1D0D8'));canvas.setLineWidth(.4)
        canvas.line(MARGIN,PAGE_H-30,PAGE_W-MARGIN,PAGE_H-30)
        canvas.setFont('NotoSC',8);canvas.setFillColor(GRAY)
        canvas.drawString(MARGIN,PAGE_H-23,'人员标注质量与可靠性  /  数据 v1')
        canvas.drawRightString(PAGE_W-MARGIN,PAGE_H-23,'B8L2 主线 · D10 敏感性')
        canvas.line(MARGIN,31,PAGE_W-MARGIN,31)
        canvas.drawString(MARGIN,19,'2026-10-17  ·  source commit c4dd8266c42a')
        canvas.drawRightString(PAGE_W-MARGIN,19,f'第 {doc.page} 页')
        canvas.restoreState()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(a.out),pagesize=A4,leftMargin=MARGIN,rightMargin=MARGIN,
        topMargin=45,bottomMargin=43,title='人员标注质量与可靠性：数据v1独立研究与实算',
        author='Independent analysis for 3D_Manhattan_label',subject='B8L2/D10 personnel quality, correction, scope, reviewed errors and real fusion trajectories')
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    receipt={'status':'rendered','pdf':a.out.name,'source':a.source.name,'tables':table_count,'figures':figure_count,
             'embedded_fonts':['NotoSansSC Regular','NotoSansSC Bold'],'data_release':'v1'}
    (a.out.parent/'PDF_RENDER_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__': main()
