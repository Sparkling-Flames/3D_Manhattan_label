"""Render the complete Chinese Markdown report, keeping evidence paths and figures.

The input is the frozen narrative, not a new scientific analysis. The standalone
PNGs remain the lossless export version; the PDF embeds efficient RGB previews.
"""
from __future__ import annotations
import argparse, hashlib, io, json, re
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate,Frame,PageTemplate,Paragraph,
    Spacer,Table,TableStyle,Image,PageBreak,KeepTogether)
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
W,H=A4;M=38;CW=W-2*M
INK=colors.HexColor('#193547');TEAL=colors.HexColor('#176F86')
MUTED=colors.HexColor('#536979');LIGHT=colors.HexColor('#EDF3F6')

def norm(s):
    return str(s).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2212','-')

def inline(s):
    s=escape(norm(s))
    s=re.sub(r'`([^`]+)`',lambda m:'<font color="#235E77">'+m.group(1)+'</font>',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)',r'\1 (\2)',s)
    return s

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--markdown',type=Path);ap.add_argument('--out',type=Path)
    a=ap.parse_args();root=a.root.resolve();md=a.markdown or root/'REPORT_ZH.md';out=a.out or root/'REPORT_ZH.pdf'
    font=root/'analysis/fonts'
    pdfmetrics.registerFont(TTFont('NSC',str(font/'NotoSansSC-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NSCB',str(font/'NotoSansSC-Bold.ttf')))
    pdfmetrics.registerFontFamily('NSC',normal='NSC',bold='NSCB',italic='NSC',boldItalic='NSCB')
    base=ParagraphStyle('base',fontName='NSC',fontSize=9.0,leading=14.5,textColor=INK,
        wordWrap='CJK',spaceAfter=7,splitLongWords=True,allowWidows=0,allowOrphans=0)
    styles={'body':base,
      'h1':ParagraphStyle('h1',parent=base,fontName='NSCB',fontSize=21,leading=29,spaceAfter=14),
      'h2':ParagraphStyle('h2',parent=base,fontName='NSCB',fontSize=15,leading=22,spaceAfter=12,keepWithNext=True),
      'h3':ParagraphStyle('h3',parent=base,fontName='NSCB',fontSize=11.5,leading=17,spaceBefore=10,spaceAfter=7,keepWithNext=True),
      'subtitle':ParagraphStyle('subtitle',parent=base,fontName='NSCB',fontSize=11.2,leading=17,textColor=TEAL,spaceAfter=13),
      'caption':ParagraphStyle('caption',parent=base,fontSize=8,leading=11.5,textColor=MUTED,spaceAfter=10),
      'code':ParagraphStyle('code',parent=base,fontSize=8,leading=11,backColor=LIGHT,borderPadding=6),
      'bullet':ParagraphStyle('bullet',parent=base,leftIndent=11,firstLineIndent=-9)}
    doc=BaseDocTemplate(str(out),pagesize=A4,rightMargin=M,leftMargin=M,topMargin=48,bottomMargin=43,
      title='HOHONET 人员类别、组合配比与融合不确定性：20261020 接续研究',author='人员组合实算研究')
    def header(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#CCDCE5'));canvas.setLineWidth(.45)
        canvas.line(M,H-33,W-M,H-33);canvas.setFont('NSC',7.5);canvas.setFillColor(MUTED)
        canvas.drawString(M,H-24,'HOHONET  |  人员类别、组合配比与融合不确定性')
        canvas.drawRightString(W-M,H-24,'20261020 接续研究')
        canvas.drawString(M,22,'冻结融合与参考  ·  B8L2 主评价 / D10 敏感性  ·  v2 内部复查')
        canvas.drawRightString(W-M,22,str(doc.page));canvas.restoreState()
    frame=Frame(M,43,CW,H-91,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='main',frames=frame,onPage=header))
    content=md.read_text(encoding='utf8');lines=content.splitlines();flow=[];figs=[];tables=0;i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].strip().startswith('```'):code.append(lines[i]);i+=1
            flow.append(Paragraph('<br/>'.join(escape(norm(x)).replace(' ','&#160;') for x in code),styles['code']));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in cells):rows.append(cells)
                i+=1
            n=len(rows[0]);assert all(len(x)==n for x in rows),rows
            weights=[]
            for col in range(n):
                lens=sorted(len(re.sub(r'[*`]|\[E\d+\]','',r[col])) for r in rows)
                weights.append(max(8,min(43,lens[-1] if len(lens)<4 else lens[-2])))
            total=sum(weights);widths=[CW*x/total for x in weights]
            size=8.2 if n<=4 else 7.4
            sty=ParagraphStyle('table'+str(tables),parent=base,fontSize=size,leading=size*1.43,spaceAfter=0)
            hsty=ParagraphStyle('th'+str(tables),parent=sty,fontName='NSCB',textColor=colors.white)
            table=Table([[Paragraph(inline(v),hsty if j==0 else sty) for v in row] for j,row in enumerate(rows)],
              colWidths=widths,repeatRows=1,hAlign='LEFT')
            commands=[('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),TEAL),
              ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
              ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
              ('LINEBELOW',(0,0),(-1,-1),.35,colors.HexColor('#D5E1E8'))]
            for j in range(1,len(rows)):
                if j%2:commands.append(('BACKGROUND',(0,j),(-1,j),LIGHT))
            table.setStyle(TableStyle(commands));flow.extend([table,Spacer(1,9)]);tables+=1;continue
        m=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if m:
            imagepath=root/m.group(2);assert imagepath.is_file(),imagepath
            photo=PILImage.open(imagepath).convert('RGB');iw,ih=photo.size
            # Original lossless PNG is delivered separately. The PDF preview is
            # sized for A4 at about 230 dpi; no scientific pixels are invented.
            photo.thumbnail((1800,2050));buffer=io.BytesIO();photo.save(buffer,format='JPEG',quality=90,subsampling=0);buffer.seek(0)
            scale=min(CW/iw,565/ih)
            picture=Image(buffer,width=iw*scale,height=ih*scale);picture.hAlign='CENTER'
            flow.append(KeepTogether([picture,Spacer(1,4),Paragraph(inline(m.group(1)),styles['caption'])]))
            figs.append({'path':m.group(2),'sha256':hashlib.sha256(imagepath.read_bytes()).hexdigest()});i+=1;continue
        h=re.match(r'^(#{1,4})\s+(.*)',line)
        if h:
            level=len(h.group(1));text=h.group(2)
            if level==2 and re.match(r'\d+\.',text):flow.append(PageBreak())
            style='h1' if level==1 else ('subtitle' if text.startswith('20261020') else 'h2' if level==2 else 'h3')
            flow.append(Paragraph(inline(text),styles[style]));i+=1;continue
        if line.startswith('- ') or re.match(r'^\d+\. ',line):
            flow.append(Paragraph(inline(line),styles['bullet']));i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||!\[|```|- |\d+\. )',lines[i].strip()):
            para.append(lines[i].strip());i+=1
        flow.append(Paragraph(inline(' '.join(para)),base))
    out.parent.mkdir(parents=True,exist_ok=True);doc.build(flow)
    reader=PdfReader(out);text='\n'.join(p.extract_text() or '' for p in reader.pages)
    receipt={'markdown_sha256':hashlib.sha256(md.read_bytes()).hexdigest(),'pages':len(reader.pages),
      'bytes':out.stat().st_size,'pdf_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
      'figures':figs,'tables':tables,'extracted_characters':len(text),'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'scope':'Complete Markdown narrative and tables rendered; PDF thumbnails plus standalone lossless PNGs. Visual QA is recorded separately.'}
    (out.parent/'REPORT_RENDER_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='figures'},ensure_ascii=False))

if __name__=='__main__':main()
