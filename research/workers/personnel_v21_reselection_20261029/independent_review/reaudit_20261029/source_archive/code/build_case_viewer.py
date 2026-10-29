#!/usr/bin/env python3
"""Build one offline HTML viewer from the already frozen case deliveries.

Presentation only: no fitting, fusion, scoring, team generation, or reference
changes. Original six_cases and vfua_case files are read without modification.
PNG/PDF figures and data downloads are embedded byte-for-byte as base64 assets.
"""
from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import html
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

OUT = Path(__file__).resolve().parents[1]
CASE_ROOT = OUT / "stage04_cases"
DEST = CASE_ROOT / "HOHONET_v21_seven_cases_viewer_ZH.html"
ASSETS: dict[str, dict] = {}
PATH_ASSET: dict[str, str] = {}
DISPLAYED_IMAGE_IDS: set[str] = set()
LINK_AUDIT: list[dict] = []
SOURCE_FILES: list[dict] = []

CASES = [
    ("six_cases", "2978172ce6fe180ffe50e2dc", "case-7y3s", "7y3sRwLe3Va-04", "高分集中，位置仍响应"),
    ("six_cases", "8ffd905ec3a4770f8606cd93", "case-b6", "B6ByNegPMKs-48", "满票结构下的共同定位偏差"),
    ("six_cases", "7881ea8d8b010028bc505a47", "case-unb", "uNb9QFRL6hY-40", "同类成员使关键角跨过票线"),
    ("six_cases", "ce5e6ff5c300c3022395c8d6", "case-x8", "x8F5xyUWy9e-08", "互斥八票组与连接失败"),
    ("six_cases", "0836672f35ad7742021ab716", "case-jtc", "jtcxE69GiFV-13", "短折补票与对应重分组"),
    ("six_cases", "bd186f9502bc8688246f76d7", "case-s9", "S9hNv5qa7GM-09", "既定范围下的分支冲突"),
    ("vfua_case", "f48b5b2dcce86d87b6ce5ece", "case-vfua-scored", "VFuaQ6m2Qom-04", "C比B好，仍比原队A差"),
    ("vfua_case", "cee80eb52074a9b2d594a037", "case-vfua-failed", "VFuaQ6m2Qom-04", "同一Z、另一背景、三臂失败"),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    with (gzip.open(path, "rt", encoding="utf-8-sig") if path.suffix == ".gz"
          else path.open(encoding="utf-8-sig")) as handle:
        return json.load(handle)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def asset(path: Path) -> str:
    path = path.resolve()
    relative = path.relative_to(CASE_ROOT.resolve()).as_posix()
    if relative in PATH_ASSET:
        return PATH_ASSET[relative]
    assert path.is_file(), relative
    data = path.read_bytes()
    if path.suffix == ".gz":
        gzip.decompress(data)
    key = "a" + sha(relative.encode())[:15]
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix == ".gz":
        mime = "application/gzip"
    if path.suffix == ".md":
        mime = "text/markdown;charset=utf-8"
    if path.suffix in {".csv", ".json", ".txt", ".py"}:
        mime += ";charset=utf-8"
    filename = path.name
    if path.parent.name in {c[1] for c in CASES}:
        filename = path.parent.name[:8] + "_" + filename
    ASSETS[key] = dict(path=relative, filename=filename, mime=mime,
                       bytes=len(data), sha256=sha(data),
                       base64=base64.b64encode(data).decode("ascii"))
    PATH_ASSET[relative] = key
    return key


def file_link(path: Path, label: str, css: str = "download") -> str:
    key = asset(path)
    return (f'<a class="{esc(css)}" href="#embedded-downloads" '
            f'data-download="{key}" download="{esc(ASSETS[key]["filename"])}">'
            f'{esc(label)}</a>')


def image_figure(path: Path, caption: str, expanded: bool, label: str) -> str:
    key = asset(path)
    anchor = "image-" + key
    if key in DISPLAYED_IMAGE_IDS:
        anchor += "-repeat"
    DISPLAYED_IMAGE_IDS.add(key)
    img = (f'<figure id="{anchor}" class="case-figure">'
           f'<div class="figure-actions"><span>{esc(caption)}</span>'
           f'<button type="button" data-enlarge="{key}">放大查看</button>'
           f'{file_link(path, "下载 PNG", "small-link")}</div>'
           f'<img data-image="{key}" alt="{esc(caption)}" decoding="async">'
           f'<figcaption>{esc(caption)}</figcaption></figure>')
    if expanded and label == "ERP / BEV":
        return img
    return (f'<details class="figure-details"{" open" if expanded else ""}>'
            f'<summary>{esc(label)}</summary>{img}</details>')


def case_gallery(case) -> str:
    folder, event_id, anchor, image_code, purpose = case
    base = CASE_ROOT / folder
    figure = base / "figures" / event_id
    trace = read_json(base / "traces" / (event_id + ".json.gz"))
    e = trace["event"]
    meta = (f'<div class="identity"><span>{esc(e["method"])}</span>'
            f'<span>留楼外：{esc(e["building"])}</span>'
            f'<span>当前折 {esc(e["source_class"])} → {esc(e["target_class"])}</span>'
            f'<span>n={e["n"]} / m={e["m"]}</span></div>')
    scorecards = []
    for arm, block in zip("ABC", "XYZ"):
        row = trace["arms"][arm]
        q = "不可评" if row["B8L2"] is None else f'{row["B8L2"]:.4f}'
        failure = row["B8L2"] is None
        scorecards.append(f'<div class="arm-card {"failed" if failure else ""}">'
                          f'<span>{arm} = D + {block}</span><strong>Q {q}</strong>'
                          f'<small>入选节点 {row["nodes"]} · {esc(row["score_status"])}</small></div>')
    intro = (meta + '<div class="arm-cards">' + ''.join(scorecards) + '</div>'
             '<p class="caption-note">节点数是当前入选对应组数。不可连接时没有完整环或完整质量值；'
             '成功端点仍保留 source_suggestion / complete_conditional 状态，不冒充已人工认证的真值环。</p>')
    buttons = [file_link(figure / "RAW_ANSWERS.csv", "完整原答 / 人员 / 坐标"),
               file_link(figure / "VOTE_GROUPS_WITH_BLOCKS.csv", "各臂分块票账"),
               file_link(figure / "COMMON_D_GROUP_LINKS.csv", "共同 D 对应关系"),
               file_link(figure / "ABC_COMPONENTS.csv", "Q 分项与失败状态"),
               file_link(base / "traces" / (event_id + ".json.gz"), "完整 full_state（gzip）"),
               file_link(figure / "ERP_BEV.pdf", "ERP / BEV PDF")]
    if folder == "vfua_case":
        intro += '<p class="identity-note">TARGET 与 RAW3 对应事件使用相同 D/X/Y/Z、相同三臂团队和参考；本卡只计一套实际 ABC。</p>'
    body = intro + '<div class="button-row">' + ''.join(buttons) + '</div>'
    body += image_figure(figure / "ERP_BEV.png", image_code + "：实际三臂 ERP 与底面几何", True, "ERP / BEV")
    local = figure / "LOCAL_CRITICAL_VOTES.png"
    if local.exists():
        body += image_figure(local, image_code + "：关键局部、对应组位置和独立人员支持票", True, "局部图与关键票线")
    body += image_figure(figure / "3D_VOTES.png", image_code + "：三维代理与全部候选组票数", False, "三维与完整支持票")
    body += image_figure(base / "originals" / (image_code + ".png"), image_code + "：未经改写的原始全景图", False, "查看原始全景图")
    return '<div class="case-gallery">' + body + '</div>'


def marked(markdown: str) -> str:
    node = os.environ.get("CODEX_PRIMARY_RUNTIME_NODE", "node")
    modules = os.environ.get("CODEX_PRIMARY_RUNTIME_NODE_MODULES")
    if modules:
        entry = (Path(modules) / "marked/lib/marked.esm.js").as_uri()
    else:
        entry = "marked"
    script = ("import {marked} from " + json.dumps(entry) + ";"
              "import fs from 'node:fs';"
              "process.stdout.write(marked.parse(fs.readFileSync(0,'utf8')));")
    return subprocess.run([node, "--input-type=module", "-e", script], input=markdown,
                          text=True, check=True, capture_output=True).stdout


class RewriteHTML(HTMLParser):
    """Keep source prose; resolve every source-document link into this file."""
    ALLOWED = {"h1", "h2", "h3", "h4", "h5", "p", "strong", "em", "del", "code", "pre",
               "a", "table", "thead", "tbody", "tr", "th", "td", "ul", "ol", "li", "blockquote", "hr", "br"}

    def __init__(self, base: Path):
        super().__init__(convert_charrefs=False)
        self.base, self.out = base, []

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED:
            raise ValueError("Unexpected source HTML element: " + tag)
        original_tag = tag
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            tag = "h" + str(min(int(tag[1]) + 1, 6))
        if original_tag == "table":
            self.out.append('<div class="tablewrap">')
        if tag == "a":
            values = dict(attrs)
            target = values.get("href", "")
            assert target and not re.match(r"[a-zA-Z]+:", target), target
            assert not target.startswith(("/", "#")), target
            path = (self.base / unquote(target)).resolve()
            key = asset(path)
            LINK_AUDIT.append(dict(source=self.base.relative_to(CASE_ROOT).as_posix(),
                                   original_link=target, embedded_asset=key))
            if path.suffix.lower() == ".png":
                self.out.append(f'<a href="#image-{key}" data-image-jump="{key}">')
            else:
                self.out.append(f'<a href="#embedded-downloads" data-download="{key}" '
                                f'download="{esc(ASSETS[key]["filename"])}">')
        else:
            kept = [(k, v) for k, v in attrs if k in {"class", "start", "align"}]
            self.out.append('<' + tag + ''.join(f' {esc(k)}="{esc(v)}"' for k, v in kept) + '>')

    def handle_endtag(self, tag):
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            tag = "h" + str(min(int(tag[1]) + 1, 6))
        self.out.append('</' + tag + '>')
        if tag == "table":
            self.out.append('</div>')

    def handle_data(self, data):
        self.out.append(esc(data))

    def handle_entityref(self, name):
        self.out.append('&' + name + ';')

    def handle_charref(self, name):
        self.out.append('&#' + name + ';')


def source_section(markdown: str, base: Path) -> str:
    parser = RewriteHTML(base)
    parser.feed(marked(markdown))
    return ''.join(parser.out)


def source_report(folder: str, report: str, prefix: str) -> str:
    path = CASE_ROOT / folder / report
    data = path.read_bytes()
    SOURCE_FILES.append(dict(path=path.relative_to(CASE_ROOT).as_posix(), bytes=len(data), sha256=sha(data)))
    text = data.decode("utf-8")
    chunks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    out = []
    for i, chunk in enumerate(chunks):
        heading = chunk.splitlines()[0].lstrip('# ').strip()
        case = None
        if folder == "six_cases":
            for number in range(1, 7):
                if heading.startswith(str(number) + '. '):
                    case = CASES[number - 1]
                    break
        else:
            if heading.startswith('第一套 ABC'):
                case = CASES[6]
            elif heading.startswith('第二套 ABC'):
                case = CASES[7]
        anchor = case[2] if case else prefix + '-section-' + str(i)
        out.append(f'<section class="report-section {"event-section" if case else ""}" id="{anchor}">')
        rendered = source_section(chunk, path.parent)
        if case:
            # Keep the complete source text and insert exact figures below its heading.
            end = rendered.find('</h3>')
            assert end >= 0
            rendered = rendered[:end + 5] + case_gallery(case) + rendered[end + 5:]
        out.append(rendered + '</section>')
    return ''.join(out)


CSS = r"""
:root{color-scheme:light;--ink:#183743;--muted:#536c75;--line:#d5e0e3;--accent:#176b71;--wash:#eef4f4;--fail:#9b3e32;--paper:#fff}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:86px}body{margin:0;background:#f3f6f6;color:var(--ink);font-family:system-ui,-apple-system,'Noto Sans CJK SC','Microsoft YaHei',sans-serif;font-size:16px;line-height:1.78}a{color:#126d78;text-decoration-thickness:1px;text-underline-offset:3px}button{font:inherit;cursor:pointer}main,.top-inner{max-width:1280px;margin:auto;padding:0 26px}.topbar{position:sticky;top:0;z-index:30;border-bottom:1px solid var(--line);background:#f9fbfbeb;backdrop-filter:blur(12px)}.top-inner{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:58px}.brand{font-weight:750;letter-spacing:.02em;font-size:15px}.top-actions{display:flex;gap:8px;flex-wrap:wrap}.top-actions a,.top-actions button{background:transparent;border:1px solid #b8cccf;border-radius:5px;padding:5px 11px;font-size:13px;text-decoration:none;color:var(--ink)}header{padding:46px 0 24px}.eyebrow{color:var(--accent);font-size:13px;letter-spacing:.13em;font-weight:750}h1{font-size:clamp(28px,4vw,46px);line-height:1.25;margin:10px 0 15px;letter-spacing:-.02em}h2{font-size:26px;line-height:1.4;margin:8px 0 18px}h3{font-size:22px;line-height:1.5;margin:8px 0 16px}h4{font-size:19px;line-height:1.5;margin:26px 0 12px}p{margin:12px 0}code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.88em;overflow-wrap:anywhere}pre{overflow:auto;background:#f0f4f5;border:1px solid var(--line);padding:16px;border-radius:6px;font-size:13px;line-height:1.6}pre code{overflow-wrap:normal}.lead{max-width:1000px;font-size:18px;color:var(--muted)}.contract{padding:15px 19px;border-left:4px solid var(--accent);background:#e6f0ef;border-radius:0 6px 6px 0;margin:24px 0}.contract strong{font-weight:750}.facts{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0}.fact{background:white;border:1px solid var(--line);border-radius:7px;padding:14px 16px}.fact strong{display:block;font-size:27px;line-height:1.35}.fact span{font-size:13px;color:var(--muted)}.jump-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:24px 0}.jump-grid a{display:block;text-decoration:none;border:1px solid #c5d8db;background:#fafdfe;padding:12px;border-radius:6px;font-size:13px;line-height:1.5}.jump-grid b{display:block;color:var(--ink);font-size:14px;margin-bottom:3px}.summary-panel,.report-section,.data-panel{background:white;border:1px solid var(--line);border-radius:8px;margin:22px 0;padding:25px}.report-section.event-section{border-top:4px solid var(--accent)}.part-title{margin-top:46px;padding:12px 0;border-bottom:2px solid #a9c5c9}.tablewrap{overflow-x:auto;margin:16px 0;border:1px solid var(--line);border-radius:5px}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}th,td{padding:10px 12px;text-align:left;vertical-align:top;border-right:1px solid var(--line);border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:#edf3f4;font-weight:700}tr:last-child td{border-bottom:0}th:last-child,td:last-child{border-right:0}.summary-table{min-width:860px}.summary-table td:nth-child(n+3){font-variant-numeric:tabular-nums}.negative{color:#9b3e32}.positive{color:#166557}.muted,.caption-note{font-size:13px;color:var(--muted)}.identity{display:flex;gap:7px;flex-wrap:wrap;margin:15px 0}.identity span{font-size:12px;border:1px solid #cddde0;background:#f4f8f8;border-radius:4px;padding:4px 8px}.identity-note{font-size:13px;padding:10px 12px;background:#eaf2ed;border-left:3px solid #6a9784}.arm-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}.arm-card{border:1px solid var(--line);border-radius:5px;padding:12px 15px;background:#f9fbfb}.arm-card span{display:block;font-size:13px;font-weight:700}.arm-card strong{display:block;font-size:23px;font-variant-numeric:tabular-nums}.arm-card small{display:block;font-size:11px;overflow-wrap:anywhere;color:var(--muted)}.arm-card.failed{background:#fff3ef;border-color:#e1c1b8}.arm-card.failed strong{color:var(--fail)}.button-row{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}.download{display:inline-block;text-decoration:none;border:1px solid #b8cfd2;border-radius:4px;background:#f5f9f9;padding:7px 10px;font-size:12px;line-height:1.5}.case-gallery{margin-bottom:24px}.case-figure{margin:14px 0;border:1px solid #d4dfe3;background:white;border-radius:5px;overflow:hidden;scroll-margin-top:80px}.case-figure img{display:block;width:100%;height:auto;min-height:100px;background:#f6f9f9}.case-figure img:not([src]){min-height:220px}.case-figure figcaption{padding:10px 14px;font-size:12px;color:var(--muted);border-top:1px solid #e4ebed}.figure-actions{display:flex;align-items:center;gap:12px;padding:10px 13px;background:#f3f7f8;border-bottom:1px solid #e4ebed;font-size:12px}.figure-actions span{flex:1}.figure-actions button{font-size:12px;border:1px solid #bbd0d4;background:white;border-radius:4px;padding:3px 8px;color:var(--ink)}.small-link{white-space:nowrap}.figure-details{margin:12px 0;border:1px solid var(--line);border-radius:5px;padding:0 12px;background:#fbfdfd}.figure-details summary{cursor:pointer;font-size:14px;font-weight:650;padding:12px 0}.figure-details[open] summary{border-bottom:1px solid var(--line)}.data-panel details{margin:12px 0;border-top:1px solid var(--line);padding:9px 0}.data-panel summary{cursor:pointer;font-weight:650}.file-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:12px}.file-grid a{font-size:11px;overflow-wrap:anywhere}.notice{padding:12px 16px;background:#fff3df;border:1px solid #e7cc9e;border-radius:5px}.asset-status{font-size:12px;color:var(--muted);margin:8px 0}.footer{margin:30px 0 60px;font-size:13px;color:var(--muted)}dialog{width:96vw;max-width:1700px;max-height:96vh;border:1px solid #a7bec5;border-radius:8px;padding:12px;background:white;color:var(--ink)}dialog::backdrop{background:#0a1d2caa}dialog .dialog-toolbar{display:flex;align-items:center;gap:10px;position:sticky;top:0;background:white;padding:4px 0 10px}dialog .dialog-toolbar span{flex:1;font-size:13px}dialog img{display:block;width:100%;height:auto}dialog .close{border:1px solid #bccfd4;background:#f2f7f8;padding:5px 12px;border-radius:4px}ul,ol{padding-left:26px}blockquote{margin:16px 0;padding:2px 18px;border-left:3px solid #9dbac2;color:#49616b}.loading-indicator{padding:9px 0;font-size:12px;color:var(--muted)}
@media(max-width:800px){main,.top-inner{padding:0 13px}.top-inner{min-height:65px}.brand{max-width:200px;font-size:13px}.facts{grid-template-columns:repeat(3,1fr)}.fact strong{font-size:22px}.jump-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.summary-panel,.report-section,.data-panel{padding:16px}.arm-cards{gap:6px}.arm-card{padding:8px}.arm-card strong{font-size:18px}.figure-actions span{display:none}.file-grid{grid-template-columns:1fr}h3{font-size:20px}.lead{font-size:16px}}
@media print{body{background:white;font-size:10pt}.topbar,.jump-grid,.top-actions,.download,.figure-actions,.data-panel,dialog,.loading-indicator{display:none!important}main{max-width:none;padding:0}.report-section,.summary-panel{border:0;padding:0;break-inside:auto}.case-figure{break-inside:avoid}.case-figure img{max-height:240mm;object-fit:contain}.facts{margin:10px 0}.part-title{break-before:page}.figure-details{border:0}a{color:inherit;text-decoration:none}}
"""

SCRIPT = r"""
(() => {
  'use strict';
  const assets = JSON.parse(document.getElementById('embedded-assets').textContent);
  const urls = new Map();
  const errors = [];
  function objectURL(id) {
    if (urls.has(id)) return urls.get(id);
    const a = assets[id];
    if (!a) throw new Error('Missing embedded asset: ' + id);
    const decoded = atob(a.base64);
    const bytes = new Uint8Array(decoded.length);
    for (let i = 0; i < decoded.length; i++) bytes[i] = decoded.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([bytes], {type: a.mime}));
    urls.set(id, url);
    return url;
  }
  function loadImage(img) {
    if (!img.src) img.src = objectURL(img.dataset.image);
    return img.decode().catch(error => { errors.push(String(error)); });
  }
  async function loadAllImages() {
    await Promise.all([...document.querySelectorAll('img[data-image]')].map(loadImage));
    document.getElementById('asset-status').textContent = '全部嵌入图像已载入，可离线浏览或打印。';
    return [...document.querySelectorAll('img[data-image]')].map(img => ({id:img.dataset.image,complete:img.complete,width:img.naturalWidth,height:img.naturalHeight}));
  }
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      loadImage(entry.target); observer.unobserve(entry.target);
    }
  }, {rootMargin: '600px'});
  document.querySelectorAll('img[data-image]').forEach(img => observer.observe(img));
  function reveal(target) {
    for (let node = target; node; node = node.parentElement) if (node.tagName === 'DETAILS') node.open = true;
    target.querySelectorAll('img[data-image]').forEach(loadImage);
    target.scrollIntoView({behavior:'smooth',block:'start'});
  }
  document.addEventListener('click', event => {
    const download = event.target.closest('[data-download]');
    if (download) {
      event.preventDefault();
      const id = download.dataset.download, a = assets[id];
      const link = document.createElement('a'); link.href = objectURL(id); link.download = a.filename;
      document.body.append(link); link.click(); link.remove(); return;
    }
    const enlarge = event.target.closest('[data-enlarge]');
    if (enlarge) {
      const id = enlarge.dataset.enlarge;
      document.getElementById('dialog-image').src = objectURL(id);
      document.getElementById('dialog-label').textContent = assets[id].path;
      document.getElementById('image-dialog').showModal(); return;
    }
    const jump = event.target.closest('a[href^="#"]');
    if (jump) {
      const target = document.getElementById(jump.getAttribute('href').slice(1));
      if (target) { event.preventDefault(); history.replaceState(null, '', jump.getAttribute('href')); reveal(target); }
    }
  });
  document.getElementById('dialog-close').addEventListener('click', () => document.getElementById('image-dialog').close());
  document.getElementById('load-all').addEventListener('click', async () => {
    document.getElementById('asset-status').textContent = '正在从本文件载入全部图像……'; await loadAllImages();
  });
  document.getElementById('print-all').addEventListener('click', async () => {
    document.querySelectorAll('details.figure-details').forEach(d => d.open = true);
    await loadAllImages(); window.print();
  });
  window.__hohonetViewer = {
    ready: true, errors, loadAllImages,
    assetCount: Object.keys(assets).length,
    assetMetadata: Object.fromEntries(Object.entries(assets).map(([id,a]) => [id,{path:a.path,bytes:a.bytes,sha256:a.sha256,mime:a.mime}])),
    showAsset: objectURL,
  };
  if (location.hash) {
    const target = document.getElementById(location.hash.slice(1));
    if (target) setTimeout(() => reveal(target), 30);
  }
})();
"""


class StaticAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.downloads, self.images = [], [], [], []
        self.external, self.text = [], []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'href' in attrs:
            self.links.append(attrs['href'])
        if 'data-download' in attrs:
            self.downloads.append(attrs['data-download'])
        if 'data-image' in attrs:
            self.images.append(attrs['data-image'])
        for name in ['href', 'src']:
            if attrs.get(name) and not attrs[name].startswith(('#', 'data:', 'blob:')):
                self.external.append(attrs[name])
        if tag in ['script', 'style']:
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.ignored -= 1

    def handle_data(self, data):
        if not self.ignored:
            self.text.append(data)


def verify_static(page: str, case_values: list[dict]):
    audit = StaticAudit()
    audit.feed(page)
    duplicate_ids = sorted({x for x in audit.ids if audit.ids.count(x) > 1})
    broken_anchors = sorted({x for x in audit.links if x.startswith('#') and x[1:] not in audit.ids})
    assert not duplicate_ids and not broken_anchors and not audit.external
    assert set(audit.downloads) <= set(ASSETS) and set(audit.images) <= set(ASSETS)
    for key, record in ASSETS.items():
        data = base64.b64decode(record['base64'], validate=True)
        assert len(data) == record['bytes'] and sha(data) == record['sha256']
        assert data == (CASE_ROOT / record['path']).read_bytes()
        if record['path'].endswith('.gz'):
            gzip.decompress(data)
    visible = ''.join(audit.text)
    checks = ["95.5160", "95.6950", "95.4887", "51.3339", "63.0342", "54.6487",
              "48.4411", "97.3068", "48.4319", "97.6518", "99.0946", "74.4297",
              "75.2693", "92.8731", "80.6945", "79.1831", "79.7922", "26.1511",
              "44.8821", "53.6411", "34.9101", "18.7310", "26.8205", "20.5758",
              "4+3=7", "4+6=10", "4+2=6", "W106", "10、9、11",
              "当前 scope 与参考保持", "缺失 Q 不填 0"]
    assert all(x in visible for x in checks), [x for x in checks if x not in visible]
    assert len(case_values) == 8
    assert sum(v['Q'][a] is None for v in case_values for a in 'ABC') == 5
    assert all(v['n'] == 16 and v['m'] == 8 for v in case_values)
    receipt = dict(viewer=DEST.name, static_validation_passed=True,
                   all_embedded_assets_byte_identical=True, embedded_assets_checked=len(ASSETS),
                   all_nested_gzip_readable=True, no_duplicate_ids=True,
                   anchor_links_checked=len(audit.links), broken_anchors=[],
                   external_network_or_file_links=[], download_links_checked=len(audit.downloads),
                   image_elements=len(audit.images), unique_embedded_images=len(set(audit.images)),
                   mechanism_number_checks=checks, all_mechanism_numbers_present=True,
                   missing_Q_endpoints=5, missing_Q_not_imputed=True,
                   cases=case_values, browser_validation_pending=True)
    (CASE_ROOT / 'VIEWER_VALIDATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return receipt


def main():
    assert (CASE_ROOT / 'six_cases').is_dir() and (CASE_ROOT / 'vfua_case').is_dir()
    traces = []
    for folder, eid, anchor, image, purpose in CASES:
        t = read_json(CASE_ROOT / folder / 'traces' / (eid + '.json.gz'))
        e = t['event']
        assert e['image'] == image and int(e['n']) == 16 and int(e['m']) == 8
        assert e['condition'] == 'manual' and e['layer'] == 'ordinary_manual'
        traces.append(t)
    team_keys = {t['arms'][a]['team_key'] for t in traces for a in 'ABC'}
    group_count = sum(len(t['arms'][a]['full_state']['identity_groups']) for t in traces for a in 'ABC')
    votes = sum(len(g['members']) for t in traces for a in 'ABC' for g in t['arms'][a]['full_state']['identity_groups'])
    assert len(team_keys) == 24 and group_count == 219 and votes == 2066
    case_values = [dict(event_id=t['event']['event_id'], image=t['event']['image'],
                        n=int(t['event']['n']), m=int(t['event']['m']),
                        Q={a:t['arms'][a]['B8L2'] for a in 'ABC'},
                        nodes={a:t['arms'][a]['nodes'] for a in 'ABC'},
                        score_status={a:t['arms'][a]['score_status'] for a in 'ABC'}) for t in traces]
    body = ['<div class="topbar"><div class="top-inner"><a class="brand" href="#top">HOHONET v2.1 · 案例浏览</a>'
            '<div class="top-actions"><a href="#overview">总览</a><a href="#embedded-downloads">数据下载</a>'
            '<button id="load-all" type="button">载入全部图</button><button id="print-all" type="button">打印</button></div></div></div><main id="top">',
            '<header><div class="eyebrow">普通 MANUAL · 冻结参考 · 严格 ABC</div>'
            '<h1>人员类别如何改变共识</h1><p class="lead">七张真实全景、八套实际 ABC。'
            '把 Q、几何、支持票、具体成员和失败状态放在同一个可回查页面。</p>'
            '<div class="contract"><strong>当前 scope 与参考保持，不在本页重新裁定。缺失 Q 不填 0。</strong><br>'
            'A=D+X，B=D+Y，C=D+Z；D/X/Y/Z 真实互斥，X/Y 同类、Z 异类，全部 n16/m8。'
            '这些案例按完整结果后选择，不代表总体胜率。本页整理既有结果，没有新增物理团队。</div>'
            '<div class="facts"><div class="fact"><strong>7</strong><span>独立全景图</span></div>'
            '<div class="fact"><strong>8</strong><span>不同实际 ABC</span></div>'
            '<div class="fact"><strong>24</strong><span>唯一端点诊断重放</span></div>'
            '<div class="fact"><strong>219</strong><span>完整对应组</span></div>'
            '<div class="fact"><strong>2,066</strong><span>原答观测票</span></div></div>'
            '<p class="muted">本文件内嵌全部正文、图像与数据下载；打开后不需要联网或旁边的文件夹。'
            '原始 six_cases/、vfua_case/ 网页及文件另行原样保留。下载的是源文件原始字节。</p>'
            '<p id="asset-status" class="asset-status">图像在进入视野时从本文件载入；可点击“载入全部图”。</p>'
            '<noscript><p class="notice">正文可直接阅读；嵌入图像和下载功能需要浏览器启用本地 JavaScript。不会访问网络。</p></noscript>',
            '<nav class="jump-grid" aria-label="案例跳转">']
    for folder, eid, anchor, image, purpose in CASES:
        suffix = ' · 可评组' if anchor.endswith('scored') else ' · 失败组' if anchor.endswith('failed') else ''
        body.append(f'<a href="#{anchor}"><b>{esc(image + suffix)}</b>{esc(purpose)}</a>')
    body.append('</nav></header><section id="overview" class="summary-panel"><h2>同类、跨类与失败：先看实际端点</h2>'
                '<p>Q 为已保存的 B8L2；节点数指入选对应组。VFua 的两套 ABC 在 TARGET 与 RAW3 下成员及结果相同，分别只计一次。</p>'
                '<div class="tablewrap"><table class="summary-table"><thead><tr><th>图片 / 事件</th><th>分类 / 当前折方向</th><th>Q A</th><th>Q B</th><th>Q C</th><th>入选节点 A/B/C</th><th>机制</th></tr></thead><tbody>')
    for case, t in zip(CASES, traces):
        folder, eid, anchor, image, purpose = case
        e = t['event']
        qs = ['<span class="negative">不可评</span>' if t['arms'][a]['B8L2'] is None else f"{t['arms'][a]['B8L2']:.4f}" for a in 'ABC']
        method = 'TARGET / RAW3（同实体）' if folder == 'vfua_case' else e['method'].replace('V21_DSTRUCT_', '').replace('TARGET_DSTRUCT_', 'TARGET ')
        body.append(f'<tr><td><a href="#{anchor}">{image}</a><br><code>{eid}</code></td>'
                    f'<td>{esc(method)}<br>{e["source_class"]} → {e["target_class"]}</td>'
                    + ''.join('<td>' + q + '</td>' for q in qs)
                    + '<td>' + '/'.join(str(t['arms'][a]['nodes']) for a in 'ABC') + '</td><td>' + esc(purpose) + '</td></tr>')
    body.append('</tbody></table></div><p class="muted">类别号仅对相应方法、留楼外折有定义。'
                '同一类别不保证成员可互换；几何变化不自动等于质量改善；失败端点不补造完整环。</p></section>')

    body.append('<div class="part-title"><h2>第一部分 · 六个冻结机制案例</h2><p>以下保留原完整说明，并把实际图、原答与票账嵌入对应章节。</p></div>')
    body.append(source_report('six_cases', 'CASE_MECHANISM_REVIEW_ZH.md', 'six'))
    body.append('<div class="part-title"><h2>第二部分 · VFua 共同池负尾与背景响应</h2><p>同一图中的两套实际 ABC，解释均值与多数比例、C−A 与 C−B，以及固定 Z 的背景依赖。</p></div>')
    body.append(source_report('vfua_case', 'VFUA_COMMON_POOL_NEGATIVE_TAIL_ZH.md', 'vfua'))

    # Embed all portable data/code/PDF files, while leaving original directories intact.
    wanted = {'.csv', '.gz', '.json', '.md', '.txt', '.py', '.pdf'}
    for folder in ['six_cases', 'vfua_case']:
        for path in sorted((CASE_ROOT / folder).rglob('*')):
            if path.is_file() and path.suffix in wanted and '__pycache__' not in path.parts:
                asset(path)
    body.append('<section id="embedded-downloads" class="data-panel"><h2>内嵌下载：完整数据与复现资料</h2>'
                '<p>所有以下文件直接从本 HTML 的内嵌字节导出；CSV、JSON、gzip、Markdown、代码与 PDF 不依赖外部路径。'
                'gzip 保留压缩源格式，解压后可读取完整表或 full_state。字体文件和原来的两个网页保留在原子目录，浏览本页不依赖它们。</p>')
    for folder, title in [('six_cases', '六例原交付'), ('vfua_case', 'VFua 补充交付')]:
        body.append(f'<details><summary>{title}：逐文件下载</summary><div class="file-grid">')
        for key, record in sorted(ASSETS.items(), key=lambda item: item[1]['path']):
            if record['path'].startswith(folder + '/'):
                body.append(f'<a class="download" href="#embedded-downloads" data-download="{key}" '
                            f'download="{esc(record["filename"])}">{esc(record["path"])} '
                            f'<small>（{record["bytes"]:,} B）</small></a>')
        body.append('</div></details>')
    body.append('</section><div class="footer"><p>图像全部来自冻结原答与实际端点。ERP 采用原坐标，BEV/三维按相机高归一。'
                '范围不重判、缺 Q 不填 0、节点组跨臂使用原答观测签名追踪。</p>'
                '<p><a href="#top">返回顶部</a> · 2026-10-29 · 本页只整理与验证交付，没有重新研究或计算团队。</p></div></main>'
                '<dialog id="image-dialog"><div class="dialog-toolbar"><span id="dialog-label"></span>'
                '<button id="dialog-close" type="button" class="close">关闭</button></div><img id="dialog-image" alt="放大图"></dialog>')
    content = ''.join(body)
    assert '/workspace/' not in content and 'sandbox:' not in content
    embedded = json.dumps(ASSETS, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            'script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src blob: data:; '
            'connect-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            '<title>HOHONET v2.1 · 七图八套 ABC 离线案例浏览</title><style>' + CSS + '</style></head><body>'
            + content + '<script id="embedded-assets" type="application/json">' + embedded + '</script>'
            '<script id="case-values" type="application/json">' + json.dumps(case_values, ensure_ascii=False) + '</script>'
            '<script>' + SCRIPT + '</script></body></html>')
    DEST.write_text(page, encoding='utf-8')
    verify_static(page, case_values)
    metadata = {key: {k: v for k, v in record.items() if k != 'base64'} for key, record in ASSETS.items()}
    receipt = dict(viewer=DEST.name, bytes=DEST.stat().st_size, sha256=sha(DEST.read_bytes()),
                   independent_images=7, distinct_ABC=8, distinct_endpoints=24,
                   identity_groups=219, vote_observations=2066, embedded_assets=len(ASSETS),
                   embedded_png_count=sum(v['mime'].startswith('image/png') for v in ASSETS.values()),
                   embedded_asset_bytes=sum(v['bytes'] for v in ASSETS.values()),
                   external_network_dependencies=0, external_file_dependencies=0,
                   source_reports=SOURCE_FILES, source_links_rewritten=LINK_AUDIT,
                   new_research_or_team_computation=False, assets=metadata)
    (CASE_ROOT / 'VIEWER_ASSET_MANIFEST.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: receipt[k] for k in ['viewer', 'bytes', 'embedded_assets', 'embedded_png_count', 'embedded_asset_bytes', 'external_file_dependencies']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
