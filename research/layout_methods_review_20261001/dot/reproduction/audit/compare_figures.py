#!/usr/bin/env python3
import pathlib,json,re,argparse,hashlib
from PIL import Image
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--source',type=pathlib.Path,required=True);parser.add_argument('--work',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);args=parser.parse_args();source=args.source;root=args.work;rows=[]
def canonical_svg(text):
 text=re.sub(r'<dc:date>.*?</dc:date>','<dc:date>GENERATED_TIMESTAMP</dc:date>',text)
 identifiers=re.findall(r'\bid="([^"]+)"',text);mapping={old:'id_'+str(i) for i,old in enumerate(identifiers)}
 text=re.sub(r'\bid="([^"]+)"',lambda m:'id="'+mapping[m[1]]+'"',text)
 text=re.sub(r'(?<=href=")#([^"]+)',lambda m:'#'+mapping.get(m[1],m[1]),text)
 text=re.sub(r'url\(#([^)]+)\)',lambda m:'url(#'+mapping.get(m[1],m[1])+')',text)
 return text
for f in sorted((source/'figures').glob('*')):
 g=root/'returned_copy/figures'/f.name;row=dict(file=f.name,byte_identical=f.read_bytes()==g.read_bytes())
 if f.suffix=='.png':
  a,b=Image.open(f).convert('RGBA'),Image.open(g).convert('RGBA');row.update(original_dimensions=a.size,reproduced_dimensions=b.size,pixels_identical=a.size==b.size and np.array_equal(np.asarray(a),np.asarray(b)))
  if a.size==b.size:
   aa,bb=np.asarray(a,dtype=np.int16),np.asarray(b,dtype=np.int16);row.update(different_pixels=int(np.any(aa!=bb,axis=2).sum()),max_channel_difference=int(abs(aa-bb).max()),mean_absolute_channel_difference=float(abs(aa-bb).mean()))
 elif f.suffix=='.svg':row.update(normalized_equal=canonical_svg(f.read_text())==canonical_svg(g.read_text()),normalization='Replace dc:date; consistently rename all declared IDs and their href/url references by document order. Numeric paths, labels, styles and coordinates remain compared exactly.')
 rows.append(row)
(root/'audit/figure_comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
if (root/'audit/summary.json').exists():
 s=json.loads((root/'audit/summary.json').read_text());s['figure_png_all_bytes_equal']=all(r['byte_identical'] for r in rows if r['file'].endswith('.png'));s['figure_svg_all_normalized_equal']=all(r['normalized_equal'] for r in rows if r['file'].endswith('.svg'));(root/'audit/summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(rows,indent=2))
if not all(r.get('pixels_identical',r.get('normalized_equal',False)) for r in rows):raise SystemExit(1)
