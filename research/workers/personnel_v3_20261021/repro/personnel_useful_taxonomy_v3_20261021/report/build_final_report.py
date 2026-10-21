#!/usr/bin/env python3
"""Publish the final scientific report with exact figures and durable file links.

This script only renders and packages completed results. It makes no scientific
model, scoring, image-generation, or fusion calls. The source Markdown remains
repository-relative; the independent Markdown and HTML resolve every data link
against successful file-save receipts or an exported download directory.
"""
from pathlib import Path
import argparse
import base64
import csv
import hashlib
import html
import io
import json
import mimetypes
import os
import re
import sys
import zipfile
from html.parser import HTMLParser

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
SOURCE = HERE / '人员分类与整体构成_整合报告_20261021.md'
STANDALONE = HERE / '人员分类与整体构成_整合报告_独立版_20261021.md'
HTML = HERE / '人员分类与整体构成_整合报告_20261021.html'
PACK = HERE / 'HOHONET_人员分类与整体构成_报告与关键表_20261021.zip'
LINK_RE = re.compile(r'(!?)\[([^\]]+)\]\(([^)]+)\)')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_atomic(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.partial')
    with tmp.open('wb') as f:
        f.write(data.encode('utf-8') if isinstance(data, str) else data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def saved_map(receipts, download_index=None):
    saved = {}
    if download_index and Path(download_index).is_file():
        with Path(download_index).open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                saved[r['local_path']] = dict(url=r['direct_download_url'],
                    library_file_id=r['library_file_id'], version=r['saved_version'])
    for p in sorted(Path(receipts).glob('receipt_*.json')):
        try:
            rows = json.loads(p.read_text())['results']
        except (ValueError, KeyError, OSError):
            continue
        for r in rows:
            if r.get('status') == 'succeeded':
                saved[r['local_path']] = dict(
                    url='https://chatgpt.com/api/library/files/' + r['library_file_id'] + '/download',
                    library_file_id=r['library_file_id'], version=r.get('current_version_number'))
    return saved


def resolve_saved(p, saved):
    if str(p) in saved:
        return p, saved[str(p)]
    # The scientific source may cite the readable CSV; the independent saved
    # artifact is sometimes its lossless gzip encoding.
    alt = Path(str(p) + '.gz')
    if p.suffix == '.csv' and str(alt) in saved:
        return alt, saved[str(alt)]
    return p, None


def inventory(source, saved):
    rows = []
    for image, label, target in LINK_RE.findall(source):
        if target.startswith(('http://', 'https://', 'sandbox:', '#', 'data:')):
            continue
        p = (SOURCE.parent / target).resolve()
        assert p.is_file(), f'Missing referenced file: {p}'
        delivered, r = resolve_saved(p, saved)
        rows.append(dict(label=label, kind='image' if image else 'file',
            repository_target=target, source_path=str(p), source_bytes=p.stat().st_size,
            source_sha256=sha(p), delivered_path=str(delivered),
            direct_download_url=r['url'] if r else '',
            library_file_id=r['library_file_id'] if r else '',
            saved_version=r['version'] if r else ''))
    return rows


class CheckHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.hrefs = []
        self.tables = 0
        self.h1 = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'img': self.images.append(a.get('src', ''))
        if tag == 'a': self.hrefs.append(a.get('href', ''))
        if tag == 'table': self.tables += 1
        if tag == 'h1': self.h1 += 1


CSS = '''
:root{--ink:#162f3d;--muted:#536c78;--line:#d6e2e8;--accent:#087f84;--paper:#fff;--bg:#edf3f5}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:var(--ink);background:var(--bg);
font:16px/1.82 -apple-system,BlinkMacSystemFont,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}
a{color:#087b85;text-decoration:none}a:hover{text-decoration:underline}a:focus{outline:2px solid #087f84;outline-offset:3px}
.masthead{background:#123441;color:white;padding:30px 5vw 27px}.masthead .eyebrow{color:#9ce1d9;font-size:13px;letter-spacing:.12em}
.masthead .title{font-size:28px;font-weight:700;margin:8px 0}.masthead p{margin:5px 0;color:#d0e1e8}
.downloads{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.downloads a{color:white;border:1px solid #56818e;border-radius:6px;padding:6px 13px;font-size:14px}
.layout{display:grid;grid-template-columns:265px minmax(0,1180px);max-width:1530px;margin:24px auto;gap:28px;padding:0 24px}
nav{align-self:start;position:sticky;top:18px;max-height:calc(100vh - 36px);overflow:auto;font-size:13px;line-height:1.55;padding:12px}
nav .toc-label{font-weight:700;margin-bottom:10px}nav ul{list-style:none;padding-left:0}nav ul ul{padding-left:13px}nav li{margin:7px 0}
main{min-width:0;background:var(--paper);padding:36px 45px 55px;border:1px solid #dfe8ec;border-radius:8px;box-shadow:0 3px 12px #15303a08}
h1{font-size:29px;line-height:1.45;margin:0 0 22px}h2{font-size:24px;line-height:1.5;margin:46px 0 18px;padding-top:10px;border-top:2px solid #cfe3e7;scroll-margin-top:18px}
h3{font-size:19px;margin:28px 0 14px;scroll-margin-top:18px}p{margin:13px 0}strong{font-weight:700}
table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65;margin:20px 0;display:block;overflow:auto}
th,td{border:1px solid var(--line);padding:10px 12px;vertical-align:top}th{background:#e8f2f3;font-weight:700;text-align:left}tr:nth-child(even) td{background:#f9fbfc}
img{display:block;max-width:100%;height:auto;margin:24px auto;border:1px solid #d7e3e7;background:white}
code{background:#eef3f5;border-radius:3px;padding:2px 5px;font-size:.9em;word-break:break-word}
pre{overflow:auto;background:#eef3f5;padding:16px;line-height:1.5}pre code{padding:0}
blockquote{border-left:4px solid #65aaa8;margin:20px 0;padding:8px 20px;background:#f0f8f7}
li{margin:6px 0}.headerlink{font-size:12px;color:#7c9aa4;margin-left:8px;opacity:0}h2:hover .headerlink,h3:hover .headerlink{opacity:1}
footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:20px;margin-top:42px}
@media(max-width:1000px){.layout{display:block;padding:0 12px;margin:12px auto}nav{position:static;max-height:260px;margin-bottom:12px}main{padding:24px 22px}.masthead .title{font-size:24px}}
@media print{body{background:white;font-size:10pt}.masthead{background:white;color:var(--ink);padding:0}.masthead p,.masthead .eyebrow{color:var(--muted)}.downloads,nav{display:none}.layout{display:block;margin:0;padding:0}main{border:0;box-shadow:none;padding:15px 0}h1{font-size:22pt}h2{font-size:16pt;break-after:avoid}h3{font-size:13pt;break-after:avoid}table{font-size:9pt;display:table}tr,img{break-inside:avoid}a{color:inherit}.headerlink{display:none}}
'''


def package_report(rows):
    # A readable report plus compact labels and decision tables; complete event
    # and endpoint caches are linked, never duplicated into this package.
    rels = [
        'taxonomy/MANUAL_LABELS_EXPLAINED.csv', 'taxonomy/SEMI_LABELS_EXPLAINED.csv',
        'taxonomy/CLASS_DEFINITIONS.csv', 'taxonomy/OLD_NEW_MANUAL_CLASS_CROSSWALK.csv',
        'integration/PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv',
        'integration/PHASE3_METHOD_EXPERIMENT_COVERAGE.csv',
        'integration/taxonomy_adoption_synthesis/ADOPTION_MATRIX.csv',
        'integration/taxonomy_adoption_synthesis/PRACTICAL_COMPOSITION_RULES.csv',
        'integration/taxonomy_adoption_synthesis/PRACTICAL_CONCLUSIONS_ZH.md',
        'integration/RESEARCH_DESK_FIELD_GUIDE_ZH.md',
        'integration/REPRODUCE_AND_RECOVER_ZH.md',
        'integration/HOHONET_全部已保存文件_独立下载目录.csv',
        'integration/HOHONET_全部已保存文件_独立下载目录.md',
        'composition/final_summary/STRICT_MATCHED_COMPARISONS_WIDE.csv',
        'composition/final_summary/MANUAL_BEHAVIOR_PURE_DIRECTION_SUPPORT.csv',
        'composition/final_summary/FINAL_COMPLETION.json',
        'utility/UTILITY_ACTUAL_USE_DIGEST.csv',
        'utility/MANUAL_POLICY_COMPONENT_DIGEST.csv',
        'response/COMPLETED_RESPONSE_PRIMARY_RESULTS.csv',
        'response/COMPLETED_RESPONSE_DECOMPOSITION.csv',
    ]
    files = {V3 / r for r in rels}
    files.update([SOURCE, STANDALONE, HTML, HERE/'REPORT_LINK_MANIFEST.csv', HERE/'REPORT_RENDER_CHECK.json'])
    # Include original exact rendered figures as separate reusable artifacts.
    files.update(Path(r['source_path']) for r in rows if r['kind'] == 'image')
    for p in files: assert p.is_file(), p
    manifest = [dict(path=str(p.relative_to(V3)), bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(files)]
    tmp = PACK.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(files): z.write(p, str(p.relative_to(V3)))
        z.writestr('REPORT_PACKAGE_CONTENTS.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        assert not any('.partial' in n or '.tmp' in n for n in z.namelist())
    with tmp.open('rb') as f: os.fsync(f.fileno())
    os.replace(tmp, PACK)
    receipt = dict(status='complete', file=str(PACK), bytes=PACK.stat().st_size,
        sha256=sha(PACK), files=len(files)+1, native_calls=0,
        full_event_endpoint_tables='independent downloads; not copied into report package')
    write_atomic(HERE/'REPORT_PACKAGE_RECEIPT.json', json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--receipts', default='/tmp/hohonet_v3_library_20261021')
    ap.add_argument('--download-index', default=str(V3/'integration/HOHONET_全部已保存文件_独立下载目录.csv'))
    ap.add_argument('--inventory-only', action='store_true')
    ap.add_argument('--package', action='store_true')
    args = ap.parse_args()
    source = SOURCE.read_text()
    assert not any(t in source for t in ['TODO', 'TBD', '{{FINAL', '[[FINAL']), 'Unfilled report placeholder'
    saved = saved_map(args.receipts, args.download_index)
    rows = inventory(source, saved)
    with (HERE/'REPORT_LINK_MANIFEST.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    missing = sorted({r['source_path'] for r in rows if not r['direct_download_url']})
    if args.inventory_only:
        print(json.dumps(dict(references=len(rows), missing_saved_files=missing), ensure_ascii=False, indent=2))
        return
    assert not missing, 'Report links not yet saved: ' + repr(missing)
    by_target = {r['repository_target']: r for r in rows}
    image_count = 0
    def replace_link(m, embed=False):
        nonlocal image_count
        is_image, label, target = m.groups()
        if target not in by_target: return m.group(0)
        r = by_target[target]
        if is_image and embed:
            p = Path(r['source_path'])
            mime = mimetypes.guess_type(p.name)[0] or 'image/png'
            uri = 'data:' + mime + ';base64,' + base64.b64encode(p.read_bytes()).decode('ascii')
            image_count += 1
            return '![' + label + '](' + uri + ')'
        return is_image + '[' + label + '](' + r['direct_download_url'] + ')'
    standalone = LINK_RE.sub(lambda m: replace_link(m, False), source)
    write_atomic(STANDALONE, standalone)
    embedded = LINK_RE.sub(lambda m: replace_link(m, True), source)
    sys.path.insert(0, '/tmp/hohonet_report_deps')
    import markdown
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc', 'sane_lists'],
        extension_configs={'toc': {'toc_depth': '2-3', 'permalink': '#'}})
    body = md.convert(embedded)
    buttons = []
    for label, p in [
        ('独立下载目录', V3/'integration/HOHONET_全部已保存文件_独立下载目录.md'),
        ('Manual逐人标签', V3/'taxonomy/MANUAL_LABELS_EXPLAINED.csv'),
        ('Semi逐人标签', V3/'taxonomy/SEMI_LABELS_EXPLAINED.csv'),
        ('复现代码与必要小输入', V3/'integration/HOHONET_v3_复现代码与必要小输入_20261021.zip')]:
        _, r = resolve_saved(p, saved)
        assert r, p
        buttons.append('<a href="' + html.escape(r['url'], quote=True) + '">' + label + '</a>')
    document = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>HOHONET 人员分类与整体构成 · 整合报告</title><style>' + CSS + '</style></head><body>'
        '<header class="masthead"><div class="eyebrow">HOHONET · 人员分类与整体构成 · 2026-10-21</div>'
        '<div class="title">发现真实标法差异，判断分类的实际用途</div>'
        '<p>历史完整事件修复 · 新分类与楼外评价 · 多人数整体构成 · 原图机制证据</p>'
        '<div class="downloads">' + ''.join(buttons) + '</div></header>'
        '<div class="layout"><nav aria-label="报告目录"><div class="toc-label">报告目录</div>' + md.toc + '</nav><main>'
        + body + '<footer>所有图像为实际数据、原图与原生标注的确定性绘制。'
        '完整事件、端点、标签和代码均有独立文件入口。基准 main：324dba44d0a82d9d64a62965f2e549ee05165417。'
        '</footer></main></div></body></html>')
    check = CheckHTML(); check.feed(document)
    assert len(check.images) == image_count and check.h1 == 1
    assert all(s.startswith('data:image/') for s in check.images)
    assert not any(h.startswith(('../', './', 'file:', '/workspace/')) for h in check.hrefs)
    from PIL import Image
    for src in check.images:
        with Image.open(io.BytesIO(base64.b64decode(src.split(',', 1)[1]))) as im: im.verify()
    write_atomic(HTML, document)
    receipt = dict(status='complete', source_sha256=sha(SOURCE),
        standalone_markdown_sha256=sha(STANDALONE), html_sha256=sha(HTML),
        references=len(rows), missing_local_files=0, missing_saved_links=0,
        embedded_exact_images=image_count, tables=check.tables, source_h1=check.h1,
        relative_or_unavailable_html_file_links=0, bytes=HTML.stat().st_size,
        native_calls=0, image_generation_calls=0)
    write_atomic(HERE/'REPORT_RENDER_CHECK.json', json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.package: receipt['package'] = package_report(rows)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
