#!/usr/bin/env python3
"""Build the release download index from actual upload and ZIP validation receipts.

Python standard library only; no network, uploads, ZIP extraction, scientific
recomputation, or edits to stage outputs. The six published scientific archives
are enumerated explicitly. The superseded, unpublished STAGE02_SAME_ROOM archive
is deliberately ignored. Missing receipts remain visibly pending, with no
invented file IDs, sizes, hashes, or successful validation claims.

Usage:
  python scripts/build_delivery_index.py --check-only
  python scripts/build_delivery_index.py
  python scripts/build_delivery_index.py --require-complete
  python scripts/build_delivery_index.py --root /path/to/release

Only DOWNLOAD_INDEX.csv and DOWNLOAD_INDEX.html are written, atomically, to the
delivery directory (or --output-dir). Re-run after the last upload or archive
version replacement so the index reflects the latest local receipts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

FROZEN_COMMIT = "13a7861334749805a86dc19e9ea79fcaa71020c0"
RELEASE_DIR = "HOHONET_v21_full_chain_20261030"
IGNORED_ARCHIVE = "STAGE02_SAME_ROOM.zip"
MAIN_PACKAGES = [
    ("00_CODE_SOURCES_SYNTHESIS_AND_REPOSITORY_UPDATE.zip", "00｜代码、共享输入与综合交付", "全部计算代码、共享最小源输入、综合报告、v2→v2.1对照及缺口表、仓库文档更新与可审阅应用材料。", "各阶段完整复现的共享基础；与所需阶段数据包合用。"),
    ("STAGE01_HALF_TEAM.zip", "01｜最新半队与全部反例", "最新14/7综合事件、全部非正及不可评案例、20/7衔接、原图/完整原答/几何/节点和连接证据及逐事件结果。", "与00包合用；保持最新综合事件及各指标的独立分母。"),
    ("STAGE02A_SAME_ROOM_ABC.zip", "02A｜同房旧ABC与机制", "当前标签下旧同房ABC的实际双视角效果、容量、成员与背景、Q分项/几何/劳动/状态、完整病例原图和票账。", "与02B共同组成完整同房交付；复现另需00共享代码/输入。"),
    ("STAGE02B_SAME_ROOM_PREDICTION.zip", "02B｜同房均值、个人与预测", "同房报告、三套支持情景、均值/个人相似与残差预测、多历史增量、直接边审计、匹配对照、人员×视角构成和最小输入。", "与02A共同组成完整同房交付；复现另需00共享代码/输入。"),
    ("STAGE03_SPEED_DIFFICULTY.zip", "03｜同类近Q快慢×难度", "v2原支持与v2.1扩展的同类、近楼外历史Q、同来源快慢匹配，逐人员/图片/楼结果、原答结构和真实案例。", "与00包合用；区分表达更多与表达更正确。"),
    ("STAGE05_SELECTION_STOP.zip", "05｜选队、停止与历史成本", "当前质量/资格下Q与QT选队、停止规则和历史获取成本，精确团队/端点、几何及分项、既有历史与冷启动分账。", "与00包合用；保留原历史面板和停止规则身份。"),
]
MAIN_NAMES = {p[0] for p in MAIN_PACKAGES}
REPORT_NAMES = {"HOHONET_V21_FULL_CHAIN_REPORT_ZH.html", "HOHONET_V21_FULL_CHAIN_REPORT_ZH.md"}

# These are confirmed renames of real uploaded files, not fallback IDs. A row
# is emitted only if the exact ID appears in an actual successful receipt.
CONFIRMED_RENAMES = {
    "libfile_292ed0b096648191aba33f766860a1cf": "03_SPEED_DIFFICULTY_CASES_VIEWER.html",
    "libfile_9037e8e081f88191805afd582bda9617": "05_SELECTION_STOP_REPORT_ZH.md",
}
FIELDS = [
    "record_type", "title", "file_name", "status", "library_file_id",
    "download_url", "bytes", "sha256", "metadata_source",
    "archive_members", "source_files", "full_read_and_crc_passed",
    "nested_gzip_json_csv_images_validated", "all_source_hashes_match",
    "validation_receipt", "validation_receipt_download_url", "upload_receipt",
    "library_version_number", "uploaded_local_source", "content_description",
    "combine_with", "notes", "frozen_source_commit", "index_complete",
]


def basename(value: Any) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def portable_source(value: Any, root: Path) -> str:
    """Recover a relative path even after moving the receipt cache elsewhere."""
    s = str(value or "").replace("\\", "/")
    for marker in ("/" + root.name + "/", "/" + RELEASE_DIR + "/"):
        if marker in s:
            return s.split(marker, 1)[1]
    try:
        return str(Path(s).resolve().relative_to(root.resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return basename(s)


def walk_upload_results(obj: Any) -> Iterable[dict[str, Any]]:
    """Accept single batches, nested results/content wrappers, and batch lists."""
    if isinstance(obj, dict):
        if "library_file_id" in obj:
            yield obj
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                yield from walk_upload_results(value)
            elif key in {"text", "content", "result"} and isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (ValueError, TypeError):
                    continue
                yield from walk_upload_results(parsed)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_upload_results(value)


def load_receipts(delivery: Path, root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    files = sorted(delivery.glob("UPLOAD_*_RECEIPT.json"), key=lambda p: (p.stat().st_mtime_ns, p.name))
    for sequence, path in enumerate(files):
        try:
            contents = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError) as exc:
            warnings.append(f"上传回执不能解析：{path.name}：{exc}")
            continue
        for position, item in enumerate(walk_upload_results(contents)):
            status = str(item.get("status", "")).lower()
            success = status in {"succeeded", "success", "completed"} or (not status and item.get("success") is True)
            if not success:
                if status not in {"failed", "error", "rejected", "cancelled"}:
                    warnings.append(f"未将缺少成功状态的条目认作已发布：{path.name} / {item.get('file_name', '')}")
                continue
            file_id = str(item.get("library_file_id", ""))
            if not re.fullmatch(r"libfile_[A-Za-z0-9_-]+", file_id):
                warnings.append(f"文件ID格式无效，未生成下载链接：{path.name}")
                continue
            source = portable_source(item.get("local_path", ""), root)
            name = CONFIRMED_RENAMES.get(file_id) or str(item.get("file_name") or basename(item.get("path")) or basename(source))
            if not name or name in {IGNORED_ARCHIVE, IGNORED_ARCHIVE + ".VALIDATION.json", "DOWNLOAD_INDEX.csv", "DOWNLOAD_INDEX.html"} or basename(source) in {IGNORED_ARCHIVE, IGNORED_ARCHIVE + ".VALIDATION.json"}:
                continue
            try:
                version = int(item.get("current_version_number", 0))
            except (ValueError, TypeError):
                version = 0
            candidates.append({**item, "file_name": name, "library_file_id": file_id,
                               "source_relative": source, "upload_receipt": path.name,
                               "version": version, "sequence": sequence, "position": position})
    # Within one native Library identity, the highest confirmed version wins.
    by_id: dict[str, dict[str, Any]] = {}
    for row in candidates:
        old = by_id.get(row["library_file_id"])
        if old is None or (row["version"], row["sequence"], row["position"]) > (old["version"], old["sequence"], old["position"]):
            by_id[row["library_file_id"]] = row
    # A re-upload may create a different identity with the same filename. Use
    # the latest successful receipt and disclose the duplicate, never invent an ID.
    by_name: dict[str, dict[str, Any]] = {}
    for row in sorted(by_id.values(), key=lambda x: (x["sequence"], x["position"])):
        name = row["file_name"]
        if name in by_name and by_name[name]["library_file_id"] != row["library_file_id"]:
            warnings.append(f"同名文件存在多个已发布身份，采用最新成功回执：{name}")
        by_name[name] = row
    return list(by_name.values()), warnings


def native_url(file_id: str) -> str:
    return "https://chatgpt.com/library?" + urlencode({"file_id": file_id, "account_id": "personal"}) if file_id else ""


def common_row(upload: dict[str, Any] | None, name: str, kind: str, title: str) -> dict[str, Any]:
    row: dict[str, Any] = {k: "" for k in FIELDS}
    row.update(record_type=kind, title=title, file_name=name, frozen_source_commit=FROZEN_COMMIT)
    if upload:
        row.update(library_file_id=upload["library_file_id"], download_url=native_url(upload["library_file_id"]),
                   upload_receipt=upload["upload_receipt"], library_version_number=upload["version"],
                   uploaded_local_source=upload["source_relative"])
    return row


def auxiliary_description(name: str, source: str) -> tuple[str, str, str]:
    low = (name + " " + source).lower()
    if name.endswith(".zip.VALIDATION.json"):
        return "validation_receipt", "压缩包完整读取验证回执", "文件大小、SHA256、全部ZIP成员读取/CRC、内层格式及源哈希核对的实际回执。"
    if "crosswalk" in low:
        return "auxiliary", "v2→v2.1全链路对照表", "逐问题保留原结论、当前结果、变化原因、支持范围和论文采用说法。"
    if "gap_register" in low:
        return "auxiliary", "剩余缺口登记", "区分已有数据待整理、必须补算、新设计和人工判断，附具体范围与依据。"
    if source in {"REPORT_ZH.md", "REPORT_ZH.html"} or name in REPORT_NAMES or basename(source) in REPORT_NAMES:
        return "auxiliary", "中文综合研究报告", "本轮完整结论、方法边界、证据衔接、交付说明与采用建议。"
    if "selection_policy_cases" in low or "selection_case_exhibits" in low:
        return "auxiliary", "Q/QT选队原图与完整原答案例", "四个既定政策案例的真实原图、完整原答、两队冻结几何和分项；保持原科学结果及输出状态。"
    if "viewer" in low:
        if "speed" in low or "stage03" in low:
            return "auxiliary", "快慢×难度案例查看器", "原图、完整原答、参考及人员匹配的可直接查看案例。"
        if "same_room" in low or "stage02" in low:
            return "auxiliary", "同房案例独立查看器", "6张真实原图、14个原事件、84端点，参考/原答/融合及局部票账；图像已内嵌。"
        if "half" in low or "all36" in low or "stage01" in low:
            return "auxiliary", "最新半队全部案例查看器", "最新综合事件的全部反例与不可评案例，原图、原答、参考、几何和机制索引。"
        return "auxiliary", "研究案例查看器", "已上传的案例页面；具体覆盖以页面说明为准。"
    if "report" in low:
        if "selection" in low or "stage05" in low:
            return "auxiliary", "选队、停止与历史成本报告", "当前资格下的选队效果、停止规则、尾部和合法劳动，以及历史获取成本。"
        if "same_room" in low or "stage02" in low:
            return "auxiliary", "同房研究报告", "旧ABC双视角作用、容量、公共/个人预测、多历史、构成方差与边界。"
        return "auxiliary", "研究报告或报告核验", "已上传正式文件，保留自身支持与验证范围。"
    return "validation_receipt", "补充核验文件", "已上传的实际核验或交付回执；不代替主研究数据包。"


def build_rows(root: Path, delivery: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    uploads, warnings = load_receipts(delivery, root)
    by_name = {x["file_name"]: x for x in uploads}
    rows: list[dict[str, Any]] = []
    member_metadata: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, title, description, combination in MAIN_PACKAGES:
        upload = by_name.get(name)
        # Real uploaded source basename is accepted if the native name changed;
        # the downloadable identity must still come from a successful receipt.
        if upload is None:
            choices = [u for u in uploads if basename(u["source_relative"]) == name]
            upload = max(choices, key=lambda u: (u["sequence"], u["position"]), default=None)
        row = common_row(upload, name, "main_archive", title)
        row.update(content_description=description, combine_with=combination)
        check_path = delivery / (name + ".VALIDATION.json")
        issues: list[str] = []
        if check_path.exists():
            row["validation_receipt"] = check_path.name
            try:
                val = json.loads(check_path.read_text(encoding="utf-8-sig"))
                if basename(val.get("archive")) != name:
                    issues.append("验证回执的archive名称与目标包不一致")
                size = val.get("bytes")
                digest = str(val.get("sha256", ""))
                if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                    issues.append("验证回执缺少合法字节数")
                else:
                    row["bytes"] = size
                if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                    issues.append("验证回执缺少合法SHA256")
                else:
                    row["sha256"] = digest.lower()
                row.update(metadata_source=check_path.name, archive_members=val.get("archive_members", ""), source_files=val.get("source_files", ""))
                for key in ["full_read_and_crc_passed", "nested_gzip_json_csv_images_validated", "all_source_hashes_match"]:
                    row[key] = val.get(key, "")
                    if val.get(key) is not True:
                        issues.append(key + "未明确通过")
                for member in val.get("verification", []):
                    if isinstance(member, dict) and member.get("member"):
                        member_metadata.setdefault(str(member["member"]), []).append((check_path.name, member))
                temporaries = [m.get("member", "") for m in val.get("verification", []) if isinstance(m, dict) and str(m.get("member", "")).endswith(".tmp")]
                if temporaries:
                    issues.append("验证清单仍有临时文件，应核对并排除：" + " | ".join(temporaries))
                # Stat only; do not reopen or revalidate large archives here.
                if (delivery / name).exists() and row["bytes"] != (delivery / name).stat().st_size:
                    issues.append("本地ZIP大小与验证回执不一致")
            except (OSError, ValueError, TypeError) as exc:
                issues.append("验证回执解析失败：" + str(exc))
        else:
            issues.append("对应完整读取验证回执尚未齐备")
        linked_check = by_name.get(check_path.name)
        if linked_check:
            row["validation_receipt_download_url"] = native_url(linked_check["library_file_id"])
        if not upload:
            row["status"] = "pending_upload"
            issues.insert(0, "尚无成功上传回执；下载ID与链接留空")
        elif issues:
            row["status"] = "published_validation_attention"
        else:
            row["status"] = "published_verified"
        row["notes"] = "；".join(issues) if issues else "已发布；完整内部读取结果引用本包实际验证回执。"
        rows.append(row)

    used_ids = {r["library_file_id"] for r in rows if r["library_file_id"]}
    auxiliaries = [u for u in uploads if u["library_file_id"] not in used_ids and u["file_name"] not in MAIN_NAMES]
    for upload in sorted(auxiliaries, key=lambda u: u["file_name"]):
        name = upload["file_name"]
        kind, title, description = auxiliary_description(name, upload["source_relative"])
        row = common_row(upload, name, kind, title)
        row.update(status="published", content_description=description, notes="下载链接来自实际成功上传回执。")
        local = root / upload["source_relative"]
        member_key = RELEASE_DIR + "/" + upload["source_relative"]
        matches = member_metadata.get(member_key, [])
        if matches:
            unique = {(m.get("bytes"), m.get("sha256")) for _, m in matches}
            if len(unique) == 1:
                check_name, m = matches[-1]
                row.update(bytes=m.get("bytes", ""), sha256=m.get("sha256", ""), metadata_source="包内成员验证：" + check_name)
            else:
                row["notes"] += " 多个当前包内记录的该路径摘要不一致，未猜测辅助文件摘要。"
        if not row["bytes"] and local.is_file():
            row["bytes"] = local.stat().st_size
            if row["bytes"] <= 32 * 1024 * 1024:
                h = hashlib.sha256()
                with local.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        h.update(chunk)
                row["sha256"] = h.hexdigest()
                row["metadata_source"] = "本地上传源；未重下载远端版本"
            else:
                row["metadata_source"] = "本地上传源大小；索引阶段不重读较大辅助文件"
        if upload["library_file_id"] in CONFIRMED_RENAMES:
            row["notes"] += " 已按确认的原生文件改名显示，Library文件ID保持不变。"
        rows.append(row)

    # The report is explicitly still pending until its own upload receipt exists.
    report_available = any(u["source_relative"] in {"REPORT_ZH.md", "REPORT_ZH.html"} or u["file_name"] in REPORT_NAMES or basename(u["source_relative"]) in REPORT_NAMES for u in uploads)
    if not report_available:
        row = common_row(None, "HOHONET_V21_FULL_CHAIN_REPORT_ZH.html / .md", "pending_auxiliary", "中文综合研究报告（独立文件）")
        row.update(status="pending_upload", content_description="主综合报告的独立可下载文件。", notes="报告上传回执尚未齐备；不填猜测ID。")
        rows.append(row)
    main_rows = [r for r in rows if r["record_type"] == "main_archive"]
    main_complete = len(main_rows) == 6 and all(r["status"] == "published_verified" for r in main_rows)
    complete = main_complete and report_available
    for row in rows:
        row["index_complete"] = complete
    state = {"index_complete": complete, "main_archives_ready": sum(r["status"] == "published_verified" for r in main_rows),
             "main_archives_expected": 6, "standalone_report_available": report_available,
             "pending_or_attention": [r["file_name"] for r in rows if r["status"] not in {"published", "published_verified"}],
             "warnings": warnings, "rows": len(rows), "frozen_source_commit": FROZEN_COMMIT}
    return rows, state


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def size_text(value: Any) -> str:
    return f"{int(value):,} 字节（{int(value) / 1024 / 1024:.2f} MiB）" if isinstance(value, int) else "待齐"


def render_html(rows: list[dict[str, Any]], state: dict[str, Any]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status_names = {"published_verified": "已发布 · 内部完整读取通过", "published": "已发布", "pending_upload": "待上传回执", "published_validation_attention": "已发布 · 验证信息待处理"}
    cards = []
    for row in rows:
        if row["record_type"] != "main_archive":
            continue
        link = f'<a class="download" href="{esc(row["download_url"])}">下载 {esc(row["file_name"])}</a>' if row["download_url"] else f'<span class="pending">{esc(row["file_name"])} · 链接待齐</span>'
        verified = row["status"] == "published_verified"
        details = "".join(f"<dt>{esc(label)}</dt><dd>{esc(row[key]) or '待齐'}</dd>" for label, key in [("Library文件ID", "library_file_id"), ("SHA256", "sha256"), ("ZIP成员数", "archive_members"), ("源文件数", "source_files"), ("完整读取与CRC", "full_read_and_crc_passed"), ("内层格式核验", "nested_gzip_json_csv_images_validated"), ("源哈希一致", "all_source_hashes_match"), ("原生版本号", "library_version_number"), ("上传回执", "upload_receipt"), ("验证回执", "validation_receipt")])
        checklink = f'<p><a href="{esc(row["validation_receipt_download_url"])}">下载对应完整验证回执</a></p>' if row["validation_receipt_download_url"] else ""
        cards.append(f'<article><div class="state {"ok" if verified else "pending"}">{esc(status_names[row["status"]])}</div><h3>{esc(row["title"])}</h3><p>{esc(row["content_description"])}</p><p>{esc(row["combine_with"])}</p><p>{link}</p><p class="size">{size_text(row["bytes"])}</p><details><summary>文件ID、SHA256与读取结果</summary><dl>{details}</dl><p>{esc(row["notes"])}</p>{checklink}</details></article>')
    others = []
    for row in rows:
        if row["record_type"] == "main_archive":
            continue
        label = f'<a href="{esc(row["download_url"])}">{esc(row["file_name"])}</a>' if row["download_url"] else esc(row["file_name"])
        others.append(f'<tr><td>{esc(row["title"])}<br>{label}</td><td>{esc(status_names[row["status"]])}</td><td>{esc(row["content_description"])}</td><td class="mono">{esc(row["library_file_id"]) or "待齐"}<br>{size_text(row["bytes"])}</td></tr>')
    heading = "六个科学主包与综合报告已齐备" if state["index_complete"] else "当前索引尚未最终齐备"
    missing = "、".join(state["pending_or_attention"])
    readiness = f'<p>已确认 {state["main_archives_ready"]}/6 个主包具有成功上传身份及完整读取验证。' + (f'待齐或待处理：{esc(missing)}。' if missing else "") + '</p>'
    warn = '<section><h2>回执检查提示</h2><ul>' + ''.join(f'<li>{esc(w)}</li>' for w in state["warnings"]) + '</ul></section>' if state["warnings"] else ''
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET v2.1 完整研究交付下载索引</title>
<style>body{{margin:0;background:#f3f5f8;color:#172331;font:16px/1.65 system-ui,sans-serif}}main{{max-width:1260px;margin:0 auto;padding:32px 24px 60px}}h1{{font-size:30px;line-height:1.35}}h2{{font-size:23px;margin-top:32px}}h3{{font-size:20px;margin:10px 0}}section,.intro{{background:white;border:1px solid #d8e0e8;border-radius:10px;padding:22px;margin:18px 0}}.cards{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}article{{background:white;border:1px solid #cdd8e3;border-radius:10px;padding:22px;overflow-wrap:anywhere}}a{{color:#175f9d;text-decoration:underline}}.download{{font-weight:650}}.state{{font-size:14px;letter-spacing:.02em}}.ok{{color:#146747}}.pending{{color:#8b540e}}.size,.muted{{color:#536272;font-size:14px}}.banner{{border-left:5px solid {"#23865e" if state["index_complete"] else "#b97b22"}}}details{{margin-top:12px}}summary{{cursor:pointer;color:#23557f}}dl{{display:grid;grid-template-columns:140px minmax(0,1fr);gap:8px 14px;font-size:13px}}dt{{font-weight:600}}dd{{margin:0;word-break:break-all}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;vertical-align:top;border-bottom:1px solid #dae2ea;padding:12px 10px}}th{{background:#f0f4f8}}.mono{{font-family:ui-monospace,monospace;font-size:12px;overflow-wrap:anywhere}}code{{overflow-wrap:anywhere}}@media(max-width:780px){{.cards{{grid-template-columns:1fr}}main{{padding:20px 12px}}dl{{grid-template-columns:110px 1fr}}}}</style></head>
<body><main><h1>HOHONET v2.1 完整研究交付</h1><p class="muted">原生下载链接、精确文件身份及压缩包完整读取结果 · 索引生成：{generated}</p>
<section class="banner"><h2>{heading}</h2>{readiness}<p>冻结研究来源提交：<code>{FROZEN_COMMIT}</code>。分类仍是工作分析对象，本次交付不代替用户最终选型。</p></section>
<section><h2>下载与解压</h2><p>六个科学主包按阶段保存。完整复现请下载00共享包及各阶段包，解压到同一个父目录；包内保留共同根目录 <code>{RELEASE_DIR}/</code>，合并后形成完整代码、输入、结果、病例和仓库更新材料。请保留原目录结构。</p><p><strong>02A与02B需要合用：</strong>02A包含同房旧ABC、容量、端点与机制；02B包含同房完整报告、公共/个人预测、多历史、支持分层和复现输入。两包不是彼此的替代版本。原未发布 <code>{IGNORED_ARCHIVE}</code> 不列入此次下载清单。</p><p>本轮在独立工作目录计算并分阶段保存，<strong>未直接修改 D:\\Work\\HOHONET</strong>。00包内的仓库更新材料可审阅后应用；v2冻结身份、原实验身份和并行工作保持分开。</p></section>
<h2>六个科学主包</h2><div class="cards">{''.join(cards)}</div>
<section><h2>独立报告、查看器、对照表与验证回执</h2><p>以下链接均来自实际成功上传回执。已改名文件保持原Library文件ID；不存在的上传记录不生成猜测链接。</p><div class="scroll"><table><thead><tr><th>文件与用途</th><th>发布状态</th><th>内容</th><th>精确文件ID / 大小</th></tr></thead><tbody>{''.join(others)}</tbody></table></div></section>
{warn}<section><h2>可追溯说明</h2><p>主包的字节数、SHA256、成员数与内部完整读取结果均取自运行时对应的 <code>*.zip.VALIDATION.json</code>；上传身份取自实际 <code>UPLOAD_*_RECEIPT.json</code>，支持多个批次及同一原生文件的新版本。索引脚本不重新运行科学计算，不重新读取大ZIP，也不把文件存在本身当作验证通过。</p><p>同目录 <code>DOWNLOAD_INDEX.csv</code> 提供同一清单的机器可读字段，包含原生链接、版本、摘要和回执定位。辅助文件摘要注明是包内验证记录还是本地上传源；未据此声称已重新下载远端文件。</p></section></main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--delivery", type=Path, help="Receipt/validation directory; default ROOT/delivery")
    parser.add_argument("--output-dir", type=Path, help="Output directory; default delivery")
    parser.add_argument("--check-only", action="store_true", help="Read receipts and print readiness; write no files")
    parser.add_argument("--require-complete", action="store_true", help="Exit 2 if six verified main packages and standalone report are not all present")
    args = parser.parse_args()
    root = args.root.resolve(); delivery = (args.delivery or root / "delivery").resolve()
    rows, state = build_rows(root, delivery)
    if not args.check_only:
        output = (args.output_dir or delivery).resolve(); output.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO(newline=""); writer = csv.DictWriter(buffer, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
        outputs = {"DOWNLOAD_INDEX.csv": buffer.getvalue(), "DOWNLOAD_INDEX.html": render_html(rows, state)}
        for name, text in outputs.items():
            temp = output / (name + ".tmp"); temp.write_text(text, encoding="utf-8-sig" if name.endswith(".csv") else "utf-8", newline=""); temp.replace(output / name)
        state["written_files"] = [str(output / name) for name in outputs]
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 2 if args.require_complete and not state["index_complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
