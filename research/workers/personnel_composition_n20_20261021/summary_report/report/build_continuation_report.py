#!/usr/bin/env python3
"""Finalize a small, self-contained continuation report; never run experiments."""
from pathlib import Path
import base64
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
CONT = HERE.parent
STUDY = CONT.parent
TITLE = "HOHONET_人员分类与整体构成_续研报告_20261021"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""): h.update(block)
    return h.hexdigest()

def atomic_text(path, text):
    tmp = path.with_suffix(path.suffix+".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)

def write_csv(path, rows):
    tmp = path.with_suffix(path.suffix+".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        f.flush();os.fsync(f.fileno())
    with tmp.open(encoding="utf-8-sig",newline="") as f: assert len(list(csv.DictReader(f)))==len(rows)
    tmp.replace(path)

def adoption_table():
    labels=list(csv.DictReader((STUDY/"integration/CLASS_MEMBERS.csv").open(encoding="utf-8-sig")))
    definitions=[
      ("manual","M_structure","coarse","主要结构解释层","同图常规/简化与较多短转折表达；困难机会差异更明显","n20总体无同构成稳定优势；局部补票与共同端点弱质量响应仍有用途","E0,E2,E4,E8"),
      ("manual","M_structure","fine","条件性保留","局部短转折机制；当前n20、m4—5的质量波动区分","全部样本含跨父变化；父内679事件区间跨零；D10和成员条件敏感","E2,E4,E8"),
      ("manual","MV_QTD_manual_new","coarse","效率层的质量父分区","同新来源QH/QL构成的基准","仅保持Q父构成不足以稳定团队时间","E0,E2,E4"),
      ("manual","MV_QTD_manual_new","fine","采用为效率辅助分类","Q父构成固定的1319事件有时间增量；875方向事件给节时与低尾","连续QT二阶矩更强；质量无粗细增益；不是结构保留类","E2,E4,E5"),
      ("semi","SP_scale","coarse","采用为尺度解释层","终稿推导高度及位置尺度倾向；坐标中位数机制","仅2楼的匹配总体稳定差约零；来源未全部独立识别","E0,E3,E9"),
      ("semi","SP_scale","fine","仅条件性尺度细分","较大底面积/常规尺度与较低推导高度的区别","n20细匹配28例全部跨父；宽域细分质量误差增加","E0,E3,E4"),
      ("semi","MV_QTScopeSemi_semi_new","coarse","探索性报告行为父层","自身Semi历史Q分区","n20人员21—22，m≥4无容量机会","E0,E3,E4"),
      ("semi","MV_QTScopeSemi_semi_new","fine","保留探索","自身终稿Q/T/scope与编辑报告行为；最终4叶","缺精确初始化；时间增量弱且权重敏感；不复制Manual结论","E0,E4,E5"),
      ("manual","A2_relation","single","独立原答关系对照","跨图共簇/几何关系的人员分区，同点数与来源匹配后仍较相似","n20困难图同构成稳定差−11.90pp；不等于团队可互换","E0,E2,E4"),
      ("semi","A2_relation","single","独立原答关系对照","Semi自身原答关系分区","n20同构成稳定差−3.22pp，时间可比机会很少","E0,E3,E4"),
      ("manual","Rnew2","coarse","保留历史反向基线","原历史标签与合法12楼外支持","n20相同支持域未超过连续QT；没有重跑m2学习","E0,E4,E5"),
      ("manual","F01","coarse","保留历史效率基线","旧高Q人员域的快慢分型","本阶段n20原标签人员不足或无合法外楼映射，不计负效果","E0,E4,E5"),
      ("manual","MV_QTD_manual","coarse","保留前阶段探索身份","混来源QTD父层；前阶段实际构成与机制结果","本阶段未新增其专门网格，不与同新来源QTD合并","E0,E8"),
      ("manual","MV_QTD_manual","fine","保留前阶段探索身份","混来源QTD细层；前阶段jtc正反机制案例","本阶段未新增其专门网格；有来源关联","E0,E8"),
      ("manual","MV_TDScopeSemi_manual_new","coarse","保留前阶段探索身份","T/难度/scope/Semi四域无Q对照父层","本阶段未追加深研，不能记为新效果失败","E0,E10"),
      ("manual","MV_TDScopeSemi_manual_new","fine","保留前阶段探索身份","前阶段无Q四域细分及448个实际事件","本阶段未追加深研，不冒充推荐统一层级","E0,E10")]
    rows=[]
    for cond,method,tier,decision,use,bound,evidence in definitions:
        selected=[r for r in labels if r["condition"]==cond and r["method_id"]==method and r["tier"]==tier]
        assert selected,(cond,method,tier)
        rows.append(dict(stage="continuation_20261021",condition=cond,method_id=method,tier=tier,
                         adoption_zh=decision,use_zh=use,conditions_and_limits_zh=bound,
                         descriptive_classes="|".join(r["class_id"] for r in selected),
                         descriptive_K=len(selected),known_people=sum(int(r["people"]) for r in selected),
                         label_snapshot_id="|".join(sorted({r["label_snapshot_id"] for r in selected})),
                         fit_scope="|".join(sorted({r["fit_scope"] for r in selected})),
                         class_members_source="../../integration/CLASS_MEMBERS.csv",
                         validation_source="../../integration/VALIDATION_LABEL_INDEX.csv",
                         label_changed_in_continuation=False,universal_K_cap="none",evidence_sections=evidence))
    write_csv(HERE/"分类采用判断_续研_20261021.csv",rows)

def prepare_font(text):
    from fontTools.ttLib import TTFont
    from fontTools import subset
    from fontTools.varLib.instancer import instantiateVariableFont
    assets=HERE/"assets";assets.mkdir(exist_ok=True)
    target=assets/"HOHONET_Continuation_Regular.ttf"
    source=Path("/tmp/HOHONET_NotoSansCJKsc-VF.ttf")
    licence=Path("/tmp/HOHONET_NotoSansCJK_LICENSE.txt")
    chars=set(text)|set(chr(i) for i in range(32,127))|set("−×±°Δ≥≤≈→")
    if source.exists():
        font=TTFont(source);cmap=font.getBestCmap()
        missing=sorted(ord(c) for c in chars if ord(c)>31 and ord(c) not in cmap)
        assert not missing,missing
        opts=subset.Options();opts.name_IDs=["*"];opts.name_legacy=True;opts.name_languages=["*"];opts.recalc_timestamp=False
        sub=subset.Subsetter(options=opts);sub.populate(unicodes=[ord(c) for c in chars]);sub.subset(font)
        if "fvar" in font:font=instantiateVariableFont(font,{"wght":400},inplace=True)
        font.save(target);shutil.copyfile(licence,assets/"NotoSansCJK_LICENSE.txt")
        atomic_text(assets/"FONT_RECEIPT.json",json.dumps({"source_url":"https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/Variable/TTF/NotoSansCJKsc-VF.ttf",
          "source_sha256":sha(source),"weight":400,"codepoints":len(chars),"missing_codepoints":missing,"output_sha256":sha(target)},indent=2)+"\n")
    assert target.is_file(), "Recover the report assets, or provide the licensed font at the receipt's source."
    cmap=TTFont(target).getBestCmap()
    assert all(ord(c)<32 or ord(c) in cmap for c in chars)
    return target

def render_html():
    source=HERE/(TITLE+".md"); text=source.read_text()
    renderer_path=STUDY/"report/render_report.py"
    spec=importlib.util.spec_from_file_location("original_report_renderer",renderer_path)
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    renderer.HERE=HERE
    doc=renderer.blocks(text)
    target=HERE/(TITLE+".html");tmp=target.with_suffix(".html.tmp")
    renderer.render_html(doc,tmp)
    font=prepare_font(text)
    body=tmp.read_text()
    body=body.replace("<title>HOHONET 人员分类与整体构成研究 · 2026-10-21</title>","<title>HOHONET 人员分类与整体构成：第二阶段续研 · 2026-10-21</title>")
    css="<style>@font-face{font-family:HOHONETContinuation;src:url(data:font/ttf;base64,"+base64.b64encode(font.read_bytes()).decode()+") format('truetype');font-weight:400;font-style:normal}body{font-family:HOHONETContinuation,system-ui,sans-serif}code{font-family:HOHONETContinuation,monospace}</style>"
    body=body.replace("</head>",css+"</head>")
    atomic_text(target,body);tmp.unlink(missing_ok=True)
    images=[(v[0],(HERE/v[1]).resolve()) for k,v in doc if k=="image"]
    assert body.count('<img src="data:image/')==len(images)==5
    receipt={"source_sha256":sha(source),"html_sha256":sha(target),"blocks":len(doc),
      "tables":sum(k=="table" for k,v in doc),"embedded_images":len(images),"self_contained_html":True,
      "font_sha256":sha(font),"images":[{"caption":a,"path":str(p.relative_to(CONT)),"sha256":sha(p)} for a,p in images],
      "render_source":str(renderer_path.relative_to(STUDY)),"render_source_sha256":sha(renderer_path)}
    atomic_text(HERE/"CONTINUATION_RENDER_RECEIPT.json",json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")

def package():
    names=[TITLE+".md",TITLE+".html","研究台接入_续研字段说明.md","分类采用判断_续研_20261021.csv",
      "N20_MATCHED_INTEGRATED_KEY_RESULTS.csv","N20_TIME_RESPONSE_KEY_RESULTS.csv",
      "N20_同构成与改构成_质量和形状.png","N20_效率细类与连续特征.png",
      "render_continuation_summary.py","build_continuation_report.py","build_continuation_file_index.py",
      "SUMMARY_FIGURES_RECEIPT.json","CONTINUATION_RENDER_RECEIPT.json",
      "assets/HOHONET_Continuation_Regular.ttf","assets/NotoSansCJK_LICENSE.txt","assets/FONT_RECEIPT.json"]
    files=[HERE/n for n in names];assert all(p.is_file() for p in files)
    rows=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    write_csv(HERE/"CONTINUATION_REPORT_PACKAGE_MANIFEST.csv",rows)
    files.append(HERE/"CONTINUATION_REPORT_PACKAGE_MANIFEST.csv")
    target=HERE/"HOHONET_续研总报告与关键图表_20261021.zip";tmp=target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,"report/"+str(p.relative_to(HERE)))
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        for row in rows:assert hashlib.sha256(z.read("report/"+row["path"])).hexdigest()==row["sha256"]
    tmp.replace(target)
    atomic_text(HERE/"CONTINUATION_REPORT_PACKAGE_RECEIPT.json",json.dumps({"path":target.name,"bytes":target.stat().st_size,"files":len(files),"sha256":sha(target),
      "excluded":"raw photos, raw annotations, event shards, native caches, repeated analysis packages, virtual environments",
      "recovery":"Unpack beside the other continuation packages. Old shared renderer, font sources and native inputs remain referenced by stage."},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"package":target.name,"bytes":target.stat().st_size,"files":len(files),"sha256":sha(target)},ensure_ascii=False))

if __name__=="__main__":
    adoption_table();render_html();package()
