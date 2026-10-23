"""Export self-contained final HTML using Pandoc; all figures are existing files."""
from pathlib import Path
import argparse, subprocess, hashlib, json, re

def main(root):
    root=Path(root).resolve()
    cmd=['pandoc','REPORT_ZH.md','--from=gfm','--to=html5','--standalone','--embed-resources',
         '--toc','--toc-depth=2','--metadata=lang:zh-CN',
         '--metadata=title:HOHONET 同房大块严格匹配重建终稿',
         '--css=delivery/report_style.css','--output=REPORT_ZH.html']
    subprocess.run(cmd,cwd=root,check=True)
    data=(root/'REPORT_ZH.html').read_bytes();text=data.decode()
    count=len(re.findall('src="data:image/',text))
    assert count==5, f'Expected five embedded figures, got {count}'
    assert '<table>' in text and '</html>' in text
    (root/'delivery/REPORT_HTML_RECEIPT.json').write_text(json.dumps({
        'source':'REPORT_ZH.md','output':'REPORT_ZH.html','embedded_figures':count,
        'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
        'images_fetched_from_web':0,'source_report_sha256':hashlib.sha256((root/'REPORT_ZH.md').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
    print('Self-contained report exported',len(data),'bytes',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    a=p.parse_args();main(a.root)
