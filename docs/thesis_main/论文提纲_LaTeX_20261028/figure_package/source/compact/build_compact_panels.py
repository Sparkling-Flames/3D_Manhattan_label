"""Reflow existing vector data graphics into one-row panels; no data recomputation.

All old PDF text is removed as text objects, with images and graphics untouched.
Data-graphics crops are copied with explicit affine transforms. Axis labels are
re-typeset at final physical size. This is not a white overlay or raster redraw.
"""
from pathlib import Path
import json, math, shutil
import fitz

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[1]
SRC=PACKAGE/'source/input_figures'
OUT=PACKAGE/'panels'
QA=HERE/'_build'
QA.mkdir(exist_ok=True)
TICKS=json.loads((HERE/'source_axis_ticks.json').read_text())
from matplotlib import font_manager
FONT=Path(font_manager.findfont('DejaVu Sans'))
BOLD=Path(font_manager.findfont(font_manager.FontProperties(family='DejaVu Sans',weight='bold')))
BLUE=(0,0.4470588,0.6980392);ORANGE=(.8352941,.3686275,0);GRAY=(.48,.52,.55)

def graphics_only(path):
 d=fitz.open(path);p=d[0];before=len(p.get_drawings())
 p.add_redact_annot(p.rect,fill=None,cross_out=False)
 p.apply_redactions(images=0,graphics=0,text=0)
 assert not p.get_text().strip()
 assert len(p.get_drawings())==before
 return d

def page(w,h):
 d=fitz.open();p=d.new_page(width=w,height=h)
 p.insert_font(fontname='DV',fontfile=str(FONT));p.insert_font(fontname='DVB',fontfile=str(BOLD))
 return d,p

def text(p,x,y,s,size=8.0,align='left',color=(.08,.10,.12),bold=False,rotate=0):
 f=fitz.Font(fontfile=str(BOLD if bold else FONT));width=f.text_length(s,fontsize=size)
 if rotate==0:
  if align=='center':x-=width/2
  if align=='right':x-=width
 elif align=='center':y+=width/2
 p.insert_text((x,y),s,fontname='DVB' if bold else 'DV',fontsize=size,color=color,rotate=rotate)

def save(d,folder,name):
 folder.mkdir(parents=True,exist_ok=True);path=folder/(name+'.pdf')
 d.subset_fonts();d.save(path,garbage=4,deflate=True);d.close()
 with fitz.open(path) as c:
  p=c[0];p.get_pixmap(dpi=600,alpha=False).save(folder/(name+'.png'))
  (folder/(name+'.svg')).write_text(p.get_svg_image(text_as_path=True))
  p.get_pixmap(dpi=150,alpha=False).save(QA/(folder.name+'_'+name+'.png'))
 return str(path)

records=[]
g=graphics_only(SRC/'group_size_171_trimmed.pdf')
group=[
 ('a',(33.52,54.9,225.6,157.85),(40,100),[40,60,80,100],'Mean Q',['3–6: +4.739','20–30: +0.500']),
 ('b',(289.19,54.9,481.3,157.85),(20,100),[20,40,60,80,100],'P10 of Q',['20–30: +2.848']),
 ('c',(33.52,224.16,225.6,327.11),(0,16),[0,4,8,12,16],'SD of Q',['20–30: −2.031']),
 ('d',(289.19,224.16,481.3,327.11),(75,101),[75,80,85,90,95,100],'Complete (%)',['3–6: −1.857 pp','20–30: +0.420 pp'])]
# 126 pt per panel; total artwork width 4*126+3*6 = 522 pt.
for name,clip,yr,ticks,ylab,notes in group:
 d,p=page(126,122);dest=fitz.Rect(29,8,123,94)
 p.show_pdf_page(dest,g,0,clip=fitz.Rect(clip),keep_proportion=False)
 def fx(x):return dest.x0+(x-clip[0])/(clip[2]-clip[0])*dest.width
 def fy(y):return dest.y0+(y-clip[1])/(clip[3]-clip[1])*dest.height
 for value,coordinate in TICKS['fig10'][name]['x']:
  if value in [3,6,10,20,30]:text(p,fx(coordinate),105,str(int(value)),7.5,align='center')
 for value,coordinate in TICKS['fig10'][name]['y']:text(p,26,fy(coordinate)+2.5,str(int(value)),7.5,align='right')
 text(p,76,119,'Annotators',8.0,align='center')
 text(p,7.5,51,ylab,8.0,align='center',rotate=90)
 # Data callouts kept, set in a legible block free of the plotted trajectory.
 yy=79 if name!='c' else 19
 for k,s in enumerate(notes):text(p,121,yy+k*9,s,7.1,align='right')
 path=save(d,OUT/'fig10',name)
 records.append({'figure':10,'panel':name,'file':path,'source':str(SRC/'group_size_171_trimmed.pdf'),'source_crop':clip,'destination_crop':list(dest),'width_pt':126,'height_pt':122,'subcaption':{'a':'Mean quality','b':'Lower-tail quality','c':'Between-team variation','d':'Complete outputs'}[name]})

l=graphics_only(SRC/'localization_mechanism.pdf')
# Complete floor layout is preserved at equal x/z scale. Remaining panels are
# magnified observations of the same existing corner, not new measurements.
configs=[('a',(39.85,61.8,509.3,152.4),190,fitz.Rect(29,38,184,38+(152.4-61.8)*155/(509.3-39.85))),
 ('b',(39.85,197,166.9,321.4),104,fitz.Rect(29,25,101,25+124.4*72/127.05)),
 ('c',(211.82,197,338.8,321.4),104,fitz.Rect(29,25,101,25+124.4*72/126.98)),
 ('d',(383.79,197,510.2,321.4),104,fitz.Rect(29,25,101,25+124.4*72/126.41))]
for name,clip,w,dest in configs:
 d,p=page(w,126);p.show_pdf_page(dest,l,0,clip=fitz.Rect(clip),keep_proportion=False)
 def pt(x,y):return(dest.x0+(x-clip[0])/(clip[2]-clip[0])*dest.width,dest.y0+(y-clip[1])/(clip[3]-clip[1])*dest.height)
 if name=='a':
  for x,px in TICKS['fig13'][name]['x']:
   xx,yy=pt(px,152.4);text(p,xx,yy+10,str(int(x)),7.3,align='center')
  for y,py in TICKS['fig13'][name]['y']:
   xx,yy=pt(39.85,py);text(p,26,yy+2.4,f'{y:.1f}',7.3,align='right')
  text(p,106,92,'x/h',8.0,align='center');text(p,7.5,53,'z/h',8.0,align='center',rotate=90)
  # Four complete-layout identities remain at their original scientific positions.
  for x,y,s in [(495.98,164.5,'1'),(495.98,71.9,'2'),(65.95,71.9,'3'),(64.8,164.5,'4')]:
   xx,yy=pt(x,y)
   p.draw_circle((xx,yy-2.6),5.1,color=(.2,.23,.26),fill=(1,1,1),width=.45)
   text(p,xx,yy,s,7.0,align='center',bold=True)
  xx,yy=pt(404,123);text(p,xx,yy,'Camera',7.2,align='center')
  text(p,30,108,'Before Q = 77.41',7.4,color=BLUE)
  text(p,108,108,'After Q = 92.58',7.4,color=ORANGE)
  text(p,106,121,'ΔQ = +15.17',7.6,align='center')
 elif name=='b':
  for v,px in TICKS['fig13'][name]['x']:text(p,pt(px,0)[0],109,f'{v:.1f}',7.2,align='center')
  for v,py in TICKS['fig13'][name]['y']:text(p,26,pt(0,py)[1]+2.5,f'{v:.1f}',7.2,align='right')
  text(p,65,123,'x/h',8.0,align='center');text(p,7.5,61,'z/h',8.0,align='center',rotate=90)
  # Before, after and reference already have a native TeX key above the row.
  # Place the displacement outside the plot so no local wall is hidden.
  text(p,65,15,'Shift 0.17 h',7.5,align='center')
 else:
  for v,px in TICKS['fig13'][name]['x']:text(p,pt(px,0)[0],109,str(int(v)),7.2,align='center')
  for v,py in TICKS['fig13'][name]['y']:text(p,26,pt(0,py)[1]+2.5,str(int(v)),7.2,align='right')
  text(p,65,123,'u (px)',8.0,align='center');text(p,7.5,62,'v (px; downward)',7.6,align='center',rotate=90)
  # Exact saved shifts are outside the observation field.
  text(p,65,8,'Δu = −0.423 px',7.1,align='center')
  text(p,65,17,'Δv = +0.021 px' if name=='c' else 'Δv = +0.821 px',7.1,align='center')
 path=save(d,OUT/'fig13',name)
 records.append({'figure':13,'panel':name,'file':path,'source':str(SRC/'localization_mechanism.pdf'),'source_crop':clip,'destination_crop':list(dest),'width_pt':w,'height_pt':126,'subcaption':{'a':'Complete footprints','b':'Corner 4 detail','c':'Upper endpoints','d':'Lower endpoints'}[name]})

(QA/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
print(json.dumps({'panels_written':len(records),'fig10_row_width_pt':4*126+3*6,'fig13_row_width_pt':190+3*104+3*6,'height_pt':{'fig10':122,'fig13':126}},indent=2))
