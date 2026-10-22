"""Assemble downloadable research artifacts without duplicate large caches.

The package overlays the pinned main checkout. Files already tracked in main
are referenced by the reproducibility manifest, not copied into this package.
Historical missing small dependencies are included at their original paths.
No remote upload or scientific computation is performed here.
"""
from pathlib import Path
import csv
import hashlib
import json
import os
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
DELIVERY = ROOT / "delivery"
PACKAGE = DELIVERY / "packages"
MAIN_REPORT = "人员分类主线_有效换类条件与采用判断.md"
HTML_REPORT = "人员分类主线_有效换类条件与采用判断.html"
LARGE = [
    "manual_joint/EVENTS_COMPLETE.csv.gz",
    "manual_joint/phase_b_highq_slower/EVENTS_COMPLETE.csv.gz",
    "structure/EVENTS_COMPLETE.csv.gz", "semi/EVENTS_COMPLETE.csv.gz",
    "manual_joint/POLICIES_COMPLETE.csv.gz", "manual_joint/NESTED_N_PATHS_COMPLETE.csv.gz",
    "semi/CONTINUOUS_QT_COMPLETE.csv.gz",
    "delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz",
    "delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz",
    "delivery/endpoints/ENDPOINT_SOURCE_INDEX.csv.gz",
    "integration/coverage/PHYSICAL_REGISTRATION_MAP.csv.gz",
]
CHECKPOINT_DIRS = {"runtime", "results", "completed_pools", "registered_pools", "__pycache__", "event_parts", "packages"}
MECHANISM_DIRS = [ROOT/"mechanisms", ROOT/"semi/mechanism_cases", ROOT/"manual_joint/mechanism_case"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def save_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+".publishing")
    with open(tmp,"wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    assert tmp.stat().st_size==len(data)
    os.replace(tmp,path)


def link(p, text=None):
    return f"[{text or p.name}](sandbox:{p.resolve()})"


def make_html():
    css = """body{font-family:system-ui,'Noto Sans CJK SC','Microsoft YaHei',sans-serif;max-width:1120px;margin:42px auto;padding:0 28px;color:#182c39;line-height:1.8;font-size:16px}h1{font-size:32px;line-height:1.35}h2{margin-top:2em;border-bottom:2px solid #6d9bad;padding-bottom:8px}h3{margin-top:1.5em}a{color:#156c8b}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.6;display:block;overflow:auto;margin:20px 0}th{background:#e7f0f3}td,th{padding:9px 12px;border:1px solid #ccdce2;text-align:left}tr:nth-child(even){background:#f7fafb}img{max-width:100%;height:auto;border:1px solid #e0e8eb}code{background:#eef3f6;font-size:.9em;padding:2px 4px;overflow-wrap:anywhere}pre{padding:14px;background:#eef3f6;overflow:auto}blockquote{border-left:4px solid #5a8b9d;margin:20px 0;padding-left:18px}#TOC{background:#f1f6f8;padding:20px 28px;border-radius:8px;font-size:14px}#TOC li{margin:3px 0}@media print{body{max-width:none;margin:0;font-size:11pt}h2{page-break-before:auto}tr,img{break-inside:avoid}a{color:inherit}#TOC{display:none}}"""
    style=DELIVERY/"report_style.css"
    save_bytes(style,css.encode())
    # Relative figure locations stay portable in Markdown; the HTML embeds them.
    subprocess.run(["pandoc",str(ROOT/MAIN_REPORT),"-f","gfm","-t","html5","--standalone",
                    "--embed-resources","--toc","--toc-depth=2","--metadata","lang=zh-CN",
                    "--metadata","title=HOHONET 人员分类主线：有效换类条件与采用判断",
                    "--css",str(style),"--resource-path",str(ROOT),"-o",str(ROOT/HTML_REPORT)],check=True)
    text=(ROOT/HTML_REPORT).read_text()
    def replace(m):
        url=m.group(1)
        if url.startswith(("#","http:","https:","data:","sandbox:")):
            return m.group(0)
        p=(ROOT/url).resolve()
        return f'href="sandbox:{p}"' if p.exists() else m.group(0)
    text=re.sub(r'href="([^"]+)"',replace,text)
    save_bytes(ROOT/HTML_REPORT,text.encode())


def core_files():
    result=[]
    for p in ROOT.rglob("*"):
        if not p.is_file():continue
        rel=p.relative_to(ROOT)
        if any(part in CHECKPOINT_DIRS for part in rel.parts):continue
        if any(p.is_relative_to(d) for d in MECHANISM_DIRS):continue
        if str(rel) in LARGE or p.name in {"FILE_INDEX.md","FILE_INDEX.csv","FINAL_DELIVERY_RECEIPT.json"}:continue
        if p.name.endswith((".tmp",".writing.gz",".publishing",".log",".txt")):continue
        if rel.parts[0]=="delivery" and (len(rel.parts)<2 or rel.parts[1]!="endpoints"):continue
        if "native" in rel.parts:
            if p.name not in {"REQUESTS.csv.gz","COMPLETION.json"} and not p.name.endswith("BATCH_PLAN.csv"):continue
        if p.suffix in {".py",".md",".json",".html"}:result.append(p)
        elif p.name.endswith(".csv.gz"):
            if p.stat().st_size<=3_000_000 or p.name in {"EVENTS_REGISTERED.csv.gz","ALL_EVENTS_REGISTERED.csv.gz"}:result.append(p)
        elif p.suffix==".csv" and p.stat().st_size<=4_000_000:result.append(p)
        elif p.suffix==".png" and "figures" in rel.parts:result.append(p)
    # Include only necessary small dependencies missing from tracked main.
    tracked=set(subprocess.check_output(["git","ls-files","-z"],cwd=REPO).decode().split("\0"))
    with open(ROOT/"integration/reproduce/INPUT_CODE_MANIFEST.csv",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            p=Path(r["absolute_local_path"])
            if not p.is_relative_to(REPO) or p.is_relative_to(ROOT):continue
            if str(p.relative_to(REPO)) in tracked:continue
            if any(x in r["role"] for x in ["prior_endpoint_cache","historical_code_or_small_input_package"]):continue
            assert p.exists() and p.stat().st_size<2_000_000,p
            result.append(p)
    return sorted(set(result))


def mechanism_files():
    result=[]
    for d in MECHANISM_DIRS:
        for p in d.rglob("*"):
            if not p.is_file() or "__pycache__" in p.parts:continue
            if p.suffix not in {".py",".md",".json",".csv",".gz",".png"}:continue
            if p.name.endswith((".writing.gz",".tmp")):continue
            result.append(p)
    return sorted(set(result))


def write_zip(name, files):
    p=PACKAGE/name
    tmp=p.with_name(p.name+".publishing")
    with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for f in files:z.write(f,str(f.relative_to(REPO)))
        import io
        inventory=io.StringIO(newline="")
        w=csv.writer(inventory);w.writerow(["path","bytes","sha256"])
        for f in files:w.writerow([str(f.relative_to(REPO)),f.stat().st_size,sha(f)])
        z.writestr("PACKAGE_CONTENTS.csv",inventory.getvalue())
        z.writestr("HOHONET_DELIVERY_README.txt",
                   "解压覆盖在固定 main 8bfd3e4 的仓库根目录。底层真实数据 v2。\n"
                   "完整事件、端点为独立下载；此包不含原图全集、环境或重复大缓存。\n"
                   "运行与恢复见 research/workers/personnel_exchange_closure_20261022/integration/reproduce/REPRODUCE_ZH.md。\n")
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        assert len(z.infolist())==len(files)+2
    os.replace(tmp,p)
    return p


def main():
    PACKAGE.mkdir(parents=True,exist_ok=True)
    make_html()
    core=core_files(); mechanisms=mechanism_files()
    package1=write_zip("HOHONET_20261022_报告标签关键表与代码.zip",core)
    package2=write_zip("HOHONET_20261022_实际原图叠图与票账案例.zip",mechanisms)
    records=[]
    def add(p,role,bundle="",stage="new_closure"):
        assert p.exists(),p
        records.append(dict(path=str(p.relative_to(REPO)),absolute_local_path=str(p.resolve()),
                            bytes=p.stat().st_size,sha256=sha(p),role=role,bundle=bundle,stage=stage,
                            download_url="sandbox:"+str(p.resolve())))
    add(package1,"compact_core_package")
    add(package2,"actual_case_package")
    for p in core:add(p,"core_file",package1.name,"new_or_inherited_as_named_in_manifest")
    for p in mechanisms:add(p,"mechanism_evidence",package2.name)
    for rel in LARGE:
        p=ROOT/rel
        if p.exists():add(p,"independent_complete_table")
    parts=sorted((DELIVERY/"event_parts").rglob("EVENTS_PART_*.csv.gz"))
    part_receipt=json.loads((DELIVERY/"event_parts/DELIVERY_VERIFICATION.json").read_text())
    assert len(parts)==part_receipt["total_parts"]==18
    assert sum(p.stat().st_size for p in parts)==part_receipt["total_bytes"]
    for p in parts:add(p,"optional_event_shard")
    part_aux=sorted((DELIVERY/"event_parts").rglob("MANIFEST.csv"))+sorted((DELIVERY/"event_parts").rglob("VERIFICATION.json"))+[DELIVERY/"event_parts/README.md",DELIVERY/"event_parts/DELIVERY_VERIFICATION.json"]
    for p in part_aux:add(p,"optional_event_shard_manifest")
    # File contents can change while drafting; the final index is published after
    # all packages and inputs have been written and checked.
    bypath={r['path']:r for r in records}
    records=list(bypath.values())
    fields=list(records[0])
    import io
    s=io.StringIO(newline="");w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(records)
    save_bytes(ROOT/"FILE_INDEX.csv",("\ufeff"+s.getvalue()).encode())
    lines=["# HOHONET 本轮完整下载清单", "", "底层真实数据v2；2026-10-22有效换类续研。完整报告、大表和端点都可以独立取得。", "",
           "## 首先阅读", "", f"- {link(ROOT/HTML_REPORT)}：单文件阅读版，案例图已嵌入。",
           f"- {link(ROOT/MAIN_REPORT)}：仓库Markdown原稿。",
           f"- {link(ROOT/'integration/有效换类条件表.csv')}：43个实际条件，含分母与来源。",
           f"- {link(ROOT/'integration/有效换类条件表_精简.csv')}。",
           f"- {link(ROOT/'classification/CLASSIFICATION_SCHEME_CATALOG.csv')}。",
           f"- {link(ROOT/'integration/coverage/COVERAGE_FINAL_ZH.md')}。", "",
           "## 精简包", "",
           f"- {link(package1)}，{package1.stat().st_size/1e6:.2f} MB：报告、标签、关键表、冻结请求与代码；不含完整大事件和大端点。",
           f"- {link(package2)}，{package2.stat().st_size/1e6:.2f} MB：少量实际原图、ERP/BEV/3D叠图、局部票账、精确案例与绘图代码；不含原图全集。", "",
           "## 完整事件、策略与端点（独立文件）", "", "| 文件 | MB | 作用 |", "|---|---:|---|"]
    for rel in LARGE:
        p=ROOT/rel
        if p.exists():lines.append(f"| {link(p,rel)} | {p.stat().st_size/1e6:.2f} | {'可选身份映射' if 'MAP' in p.name else '完整数据；含失败与精确身份'} |")
    lines += ["", "## 可选分片", "", "大事件表同时提供不超过25 MiB的CSV.gz分片；完整表与分片任选一种，勿把两套拼接当新增记录。", "",
              f"- {link(DELIVERY/'event_parts/README.md')}。", ""]
    for p in part_aux:
        if p.name=="MANIFEST.csv":lines.append(f"- {link(p,str(p.relative_to(DELIVERY/'event_parts')))}：分片行数、顺序、字节和SHA。")
    for p in parts:lines.append(f"- {link(p,str(p.relative_to(DELIVERY/'event_parts')))}（{p.stat().st_size/1e6:.2f} MB）")
    lines += ["", "## 实际机制案例（独立阅读）", ""]
    for p in mechanisms:
        if p.suffix==".md" or p.name=="comparison.png" or p.name in {"STRUCTURE_LOCAL_VOTES.png","THRESHOLD_REVERSAL.png","FAILURE_LOCAL_CONNECTION.png"}:
            lines.append(f"- {link(p,str(p.relative_to(ROOT)))}")
    lines += ["", "## 旧包完整文件", "", f"- {link(ROOT/'integration/historical/HISTORICAL_DOWNLOAD_INDEX_ZH.md')}：114文件，31份完整历史事件、56份历史批次端点等；保留原阶段身份。",
              f"- {link(ROOT/'integration/historical/HISTORICAL_DOWNLOAD_INDEX.csv')}。", "", "## 复现、校验与单独小文件", "",
              f"- {link(ROOT/'integration/reproduce/REPRODUCE_ZH.md')}：默认重聚合已交付结果，不重新融合。",
              f"- {link(ROOT/'FILE_INDEX.csv')}：本轮全部可下载文件的路径、SHA256、字节数、包归属与阶段。", "",
              "下列小文件也可独立下载；大缓存和重复分池结果不在精简包。", ""]
    # Grouped independent links allow use without a ZIP and without a huge table.
    groups={}
    for p in core:
        if not p.is_relative_to(ROOT):continue
        rel=p.relative_to(ROOT);group=rel.parts[0] if len(rel.parts)>1 else "主报告与代码"
        if group=="native":continue
        groups.setdefault(group,[]).append(p)
    for group,files in sorted(groups.items()):
        lines += [f"### {group}", ""]
        lines += [f"- {link(p,str(p.relative_to(ROOT)))}" for p in files]
        lines.append("")
    save_bytes(ROOT/"FILE_INDEX.md","\n".join(lines).encode())
    receipt=dict(status="complete",underlying_data="real_v2",files=len(records),
                 packages=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in [package1,package2]],
                 event_shards=len(parts),new_native_fusion_in_packaging=0,
                 remote_upload_performed=False,
                 excluded=["full original-image collection","virtual environment","runtime and per-pool duplicate caches","historical full caches already separately delivered"],
                 file_index_sha256=sha(ROOT/"FILE_INDEX.csv"))
    save_bytes(ROOT/"FINAL_DELIVERY_RECEIPT.json",json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
