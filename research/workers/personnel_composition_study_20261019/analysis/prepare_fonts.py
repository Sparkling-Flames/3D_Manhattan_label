"""Prepare reproducible Noto Sans SC static fonts, optionally a report-only subset.

The delivered subset is sufficient for this study's code, cases and report.  Use
the full static font for newly supplied labels containing additional characters.
No network operation occurs unless --download is explicitly supplied.
"""
import argparse, gzip, hashlib, json
from pathlib import Path
from urllib.request import urlopen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools import subset

ROOT=Path(__file__).resolve().parents[1]
SOURCE_URL='https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/Variable/TTF/Subset/NotoSansSC-VF.ttf'
LICENSE_URL='https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=ROOT/'analysis/fonts/NotoSansSC-VF.ttf')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/fonts')
    ap.add_argument('--download',action='store_true')
    ap.add_argument('--subset',action='store_true')
    ap.add_argument('--characters',type=Path)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.download:
        a.source.parent.mkdir(parents=True,exist_ok=True)
        with urlopen(SOURCE_URL) as r:a.source.write_bytes(r.read())
        with urlopen(LICENSE_URL) as r:(a.out/'OFL.txt').write_bytes(r.read())
    if not a.source.exists():raise SystemExit('Missing source font; pass --source or --download.')
    chars=set(chr(i) for i in range(32,127));sources=[]
    if a.characters:
        chars.update(a.characters.read_text())
    elif a.subset:
        patterns=['analysis/*.py','analysis/*.md','analysis/composition/*.py',
          'analysis/forward/*.py','analysis/reverse/*.py','analysis/figures_summary/*.py',
          'analysis/figures_summary/*.csv','analysis/figures_summary/*.json',
          'analysis/representative_cases/cases/*.json','analysis/independent/POOL_IMAGE_CONDITIONS.csv',
          'analysis/report_tables/*.csv','analysis/composition/scene_analysis/*.csv.gz']
        for pattern in patterns:
            for p in sorted(ROOT.glob(pattern)):
                with (gzip.open(p,'rt',encoding='utf8') if p.suffix=='.gz' else p.open(encoding='utf8')) as f:chars.update(f.read())
                sources.append(str(p.relative_to(ROOT)))
    chars.discard('\x00')
    corpus=''.join(sorted(chars));(a.out/'CHARACTERS.txt').write_text(corpus)
    produced=[]
    for weight,name in [(400,'Regular'),(700,'Bold')]:
        font=TTFont(a.source,recalcTimestamp=False)
        instantiateVariableFont(font,{'wght':weight},inplace=True)
        if a.subset:
            opt=subset.Options();opt.recalc_timestamp=False
            opt.name_IDs=['*'];opt.name_legacy=True;opt.name_languages=['*']
            sub=subset.Subsetter(options=opt);sub.populate(text=corpus);sub.subset(font)
        p=a.out/('NotoSansSC-'+name+'.ttf');font.save(p)
        produced.append(dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    receipt=dict(source_url=SOURCE_URL,license_url=LICENSE_URL,license='SIL Open Font License 1.1',
      source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),subset=a.subset,
      characters=len(chars),character_file='CHARACTERS.txt',character_sha256=hashlib.sha256(corpus.encode()).hexdigest(),
      corpus_sources=sources,files=produced,fonttools_version=__import__('fontTools').__version__)
    (a.out/'FONT_PROVENANCE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(subset=a.subset,characters=len(chars),files=produced)))

if __name__=='__main__':main()
