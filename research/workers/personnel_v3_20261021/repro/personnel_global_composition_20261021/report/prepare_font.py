"""Make a licensed regular-weight CJK subset for this study's artifacts."""
from pathlib import Path
import argparse,hashlib,json,shutil
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.varLib.instancer import instantiateVariableFont

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('/tmp/HOHONET_NotoSansCJKsc-VF.ttf'))
    p.add_argument('--license',type=Path,default=Path('/tmp/HOHONET_NotoSansCJK_LICENSE.txt'));args=p.parse_args()
    files=[q for suffix in ['*.md','*.py'] for q in STUDY.rglob(suffix) if 'runtime' not in q.parts]
    chars=set(''.join(q.read_text(encoding='utf8') for q in files))
    chars.update(chr(i) for i in range(32,127));chars.update('−×±°Δρηαβλ≥≤≈→ⅠⅡⅢ均值结构效率风险质量楼外分项')
    font=TTFont(args.source);cmap=font.getBestCmap();missing=sorted({ord(c) for c in chars if ord(c)>31 and ord(c) not in cmap})
    options=subset.Options();options.name_IDs=['*'];options.name_legacy=True;options.name_languages=['*'];options.recalc_timestamp=False
    sub=subset.Subsetter(options=options);sub.populate(unicodes=[ord(c) for c in chars]);sub.subset(font)
    if 'fvar' in font:font=instantiateVariableFont(font,{'wght':400},inplace=True)
    out=HERE/'assets';out.mkdir(exist_ok=True);target=out/'HOHONET_Report_Regular.ttf';font.save(target)
    shutil.copyfile(args.license,out/'NotoSansCJK_LICENSE.txt')
    receipt={'source_url':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/Variable/TTF/NotoSansCJKsc-VF.ttf',
      'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'weight':400,'subset_codepoints':len(chars),
      'missing_codepoints_in_source':missing,'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
      'license_source':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE'}
    (out/'FONT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
