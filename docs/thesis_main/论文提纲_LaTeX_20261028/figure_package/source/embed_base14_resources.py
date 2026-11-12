"""Embed legacy Base-14 CFF font programs, including clipped resource entries."""
from pathlib import Path
import fitz,json
import numpy as np
PKG=Path(__file__).resolve().parents[1]
records=[]
for path in sorted((PKG/'panels').glob('*/*.pdf')):
 d=fitz.open(path);p=d[0];targets={f[0]:f[3] for f in p.get_fonts(full=True) if f[2]=='Type1' and f[3] in ('Helvetica','Helvetica-Bold') and d.xref_get_key(f[0],'FontDescriptor')[0]=='null'}
 if not targets:continue
 before=p.get_pixmap(dpi=144,alpha=False);a=np.frombuffer(before.samples,np.uint8)
 for xref,name in targets.items():
  font=fitz.Font('hebo' if name.endswith('Bold') else 'helv');assert font.buffer[:1]==b'\x01'
  data=d.get_new_xref();d.update_object(data,'<< /Subtype /Type1C >>');d.update_stream(data,font.buffer)
  fd=d.get_new_xref();bb=font.bbox;bbox=' '.join(str(round(x*1000)) for x in [bb.x0,bb.y0,bb.x1,bb.y1])
  desc=f'<< /Type /FontDescriptor /FontName /{name} /Flags 32 /FontBBox [{bbox}] /ItalicAngle 0 /Ascent {round(font.ascender*1000)} /Descent {round(font.descender*1000)} /CapHeight 729 /StemV 80 /FontFile3 {data} 0 R >>'
  d.update_object(fd,desc);d.xref_set_key(xref,'FontDescriptor',f'{fd} 0 R')
 after=p.get_pixmap(dpi=144,alpha=False);b=np.frombuffer(after.samples,np.uint8)
 assert np.array_equal(a,b),(str(path),'Font resource embedding changed visible rendering')
 tmp=path.with_suffix('.embedded.pdf');d.save(tmp,garbage=4,deflate=True);d.close();tmp.replace(path)
 records.append({'file':str(path.relative_to(PKG)),'font_resources_embedded':len(targets),'render_pixels_changed':0,'text_and_graphic_operators_changed':False})
(PKG/'qa/base14_resource_embedding.json').write_text(json.dumps(records,indent=2))
print(json.dumps({'panels_updated':len(records),'font_resources_embedded':sum(r['font_resources_embedded'] for r in records),'visible_pixel_changes':0}))
