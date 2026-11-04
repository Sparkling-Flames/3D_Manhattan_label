"""Render report equations as exact vector text for fully offline HTML."""
from pathlib import Path
from io import BytesIO
import hashlib,json,re
import matplotlib
matplotlib.use('Agg')
from matplotlib.mathtext import math_to_image
from matplotlib.font_manager import FontProperties

HERE=Path(__file__).resolve().parent
PATTERN=re.compile(r'\\\[([\s\S]*?)\\\]|\\\(([^\n]*?)\\\)')
def main():
    out=HERE/'math_assets';out.mkdir(exist_ok=True)
    manifest={};failures=[]
    for path in sorted(HERE.rglob('*.md')):
        if any(x in path.parts for x in ['source','inputs']):continue
        text=path.read_text(encoding='utf-8');rows=[]
        for m in PATTERN.finditer(text):
            raw=m.group(0);formula=' '.join((m.group(1) if m.group(1) is not None else m.group(2)).split())
            # Mathtext uses the long TeX relation spellings; retain the original
            # Markdown for replacement while rendering an equivalent expression.
            formula=re.sub(r'\\ge(?![A-Za-z])',lambda _:r'\geq ',formula)
            formula=re.sub(r'\\le(?![A-Za-z])',lambda _:r'\leq ',formula)
            display=m.group(1) is not None;tag=hashlib.sha256(raw.encode()).hexdigest()[:18]
            filename=f'equation_{tag}.svg';target=out/filename
            try:
                buf=BytesIO();math_to_image('$'+formula+'$',buf,prop=FontProperties(size=14 if display else 12),format='svg',color='#17333c')
                target.write_bytes(buf.getvalue())
                header=buf.getvalue().decode()
                width=float(re.search(r'<svg[^>]*width="([\d.]+)pt"',header).group(1))*4/3
                height=float(re.search(r'<svg[^>]*height="([\d.]+)pt"',header).group(1))*4/3
                rows.append(dict(raw=raw,file='math_assets/'+filename,display=display,width=width,height=height,alt=formula))
            except Exception as e:failures.append(dict(file=str(path.relative_to(HERE)),formula=formula,reason=str(e)))
        if rows:manifest[str(path.relative_to(HERE))]=rows
    (HERE/'math_assets/MANIFEST.json').write_text(json.dumps(dict(files=manifest,failures=failures),ensure_ascii=False,indent=2))
    print(json.dumps(dict(reports_with_math=len(manifest),equations=sum(map(len,manifest.values())),failures=failures),ensure_ascii=False))

if __name__=='__main__':main()
