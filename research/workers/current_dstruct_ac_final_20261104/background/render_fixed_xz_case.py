"""Render exactly the two already selected fixed-XZ background examples.

No team selection, fusion, scoring, point change or new ring is performed.
The photograph is copied unchanged from its indexed GitHub Release ZIP member.
ERP drawing follows the retained great-circle/seam convention in the original
stage06_cases/code/geometry_draw.py. BEV uses the saved endpoint footprints.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import urllib.request
import zlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, patheffects
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from PIL import Image

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = TASK.parents[2]
CODE = "q9vSo1VnCiC-30"
EVENTS = ["ACG_c49c5c8dde3e059485cb0a82", "ACG_f16945ce9cbf4d52b667f651"]
BLOCK = "ACG_BLOCK_3f29e4cd489ab2fb5894"
SELECTION_FILE = "ILLUSTRATIVE_FIXED_XZ_CASE.json"
SELECTION_KIND = "same_D_class_vector_member_case"
OUTPUT_STEM = "FIXED_XZ_SAME_D_COMPOSITION"
RECEIPT_STEM = "FIXED_XZ"
RELEASE = "https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/"
ARCHIVE_BYTES = {"quality_original_images_20261015_01_of_03.zip": 165604756, "quality_original_images_20261015_02_of_03.zip": 165701699, "quality_original_images_20261015_03_of_03.zip": 164293015}
COLORS = {"A": "#2177a6", "C": "#d36b2c", "R": "#202a34"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding="utf-8")


def fetch_original(code=CODE):
    selected = HERE / "source" / ("ORIGINAL_IMAGE_INDEX.csv" if code == "q9vSo1VnCiC-30" else code + "_ORIGINAL_IMAGE_INDEX.csv")
    if selected.exists():
        index = pd.read_csv(selected, dtype=str)
    else:
        source = REPO / "research/workers/personnel_ac_v21_20261030/stage06_cases/source"
        original = pd.read_csv(source / "release_IMAGE_INDEX.csv", dtype=str)
        members = pd.read_csv(source / "ZIP_MEMBER_INDEX.csv", dtype=str)
        index = original.loc[original.image_code.eq(code)].merge(members, on=["archive", "archive_path"], validate="one_to_one")
        selected.parent.mkdir(parents=True, exist_ok=True)
        index.to_csv(selected, index=False)
    assert len(index) == 1 and index.iloc[0].image_code == code
    row = index.iloc[0].to_dict()
    dest = HERE / "originals" / (code + ".png")
    crc = int(row["zip_crc32"], 16)
    length = int(row["uncompressed_bytes"])
    url = RELEASE + row["archive"]
    transferred = 0
    data = dest.read_bytes() if dest.exists() else None
    if data is not None:
        assert len(data) == length and zlib.crc32(data) == crc, "Existing original differs from frozen ZIP member"
        retrieval = "existing_original_exact_bytes_size_and_ZIP_CRC"
    else:
        def ranged(lo, hi):
            req = urllib.request.Request(url, headers={"Range": f"bytes={lo}-{hi}", "User-Agent": "HOHONET-fixed-XZ-background-case"})
            with urllib.request.urlopen(req, timeout=60) as response:
                assert response.status == 206 and response.headers.get("Content-Range") == f"bytes {lo}-{hi}/{ARCHIVE_BYTES[row['archive']]}", "Exact range not honored"
                payload = response.read()
            assert len(payload) == hi - lo + 1
            return payload
        offset = int(row["header_offset"])
        header = ranged(offset, offset + 29)
        sig, _, flags, compression, _, _, _, _, _, namelen, extralen = struct.unpack("<IHHHHHIIIHH", header)
        assert sig == 0x04034b50 and not flags & 1 and compression in [0, 8]
        lo = offset + 30
        payload = ranged(lo, lo + namelen + extralen + int(row["compressed_bytes"]) - 1)
        filename = payload[:namelen].decode("utf-8" if flags & 0x800 else "cp437")
        assert filename == row["archive_path"]
        compressed = payload[namelen + extralen:]
        data = zlib.decompress(compressed, -15) if compression == 8 else compressed
        transferred = len(header) + len(payload)
        retrieval = "release_exact_member_byte_ranges"
    assert len(data) == length == int(row["bytes"]) and zlib.crc32(data) == crc
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".png.writing")
    temp.write_bytes(data)
    temp.replace(dest)
    with Image.open(dest) as photo:
        assert photo.size == (int(row["width"]), int(row["height"]))
        photo.verify()
    receipt = dict(row, source_release_url=url, path=str(dest.relative_to(HERE)), sha256=sha(dest),
                   retrieval=retrieval, transferred_bytes=transferred, original_bytes_unchanged=True,
                   photo_edits=0, source_selected_index_sha256=sha(selected))
    write_json(HERE / ("FIXED_XZ_ORIGINAL_IMAGE_RECEIPT.json" if code == "q9vSo1VnCiC-30" else code + "_ORIGINAL_IMAGE_RECEIPT.json"), receipt)
    return dest, receipt


def arc(p, q, n=60):
    def ray(v):
        u, t = v[0] * 2 * np.pi / 1024, (.5 - v[1] / 512) * np.pi
        return np.array([-np.sin(u) * np.cos(t), np.cos(u) * np.cos(t), np.sin(t)])
    a, b = ray(p), ray(q)
    theta = np.arccos(np.clip(a @ b, -1, 1))
    t = np.linspace(0, 1, n)
    if theta < 1e-8:
        r = (1 - t[:, None]) * a + t[:, None] * b
    elif abs(np.sin(theta)) < 1e-8:
        return [np.asarray([p, q])]
    else:
        r = np.sin((1 - t) * theta)[:, None] * a / np.sin(theta) + np.sin(t * theta)[:, None] * b / np.sin(theta)
    r /= np.linalg.norm(r, axis=1)[:, None]
    x = np.mod(np.arctan2(-r[:, 0], r[:, 1]), 2 * np.pi) * 1024 / (2 * np.pi)
    y = (.5 - np.arcsin(np.clip(r[:, 2], -1, 1)) / np.pi) * 512
    cuts = np.where(np.abs(np.diff(x)) > 512)[0] + 1
    return [segment for segment in np.split(np.column_stack([x, y]), cuts) if len(segment) > 1]


def erp(ax, points, color, ls="-", lw=1.7):
    p = np.asarray(points, float)
    assert len(p) % 2 == 0 and len(p) >= 6
    segments = []
    for k in [0, 1]:
        ring = p[k::2]
        for j in range(len(ring)):
            segments.extend(arc(ring[j], ring[(j + 1) % len(ring)]))
    for top, bottom in zip(p[::2], p[1::2]):
        segments.extend(arc(top, bottom, 15))
    artist = LineCollection(segments, colors=color, linewidths=lw, linestyles=ls)
    artist.set_path_effects([patheffects.Stroke(linewidth=lw + 1.1, foreground="white", alpha=.7), patheffects.Normal()])
    ax.add_collection(artist)


def set_font(path):
    if path:
        font_manager.fontManager.addfont(path)
        family = font_manager.FontProperties(fname=path).get_name()
    else:
        names = set(font_manager.get_font_names())
        family = next((n for n in ["Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", "SimHei"] if n in names), None)
        if not family:
            raise RuntimeError("Provide --font /path/to/CJK-font.otf")
    plt.rcParams.update({"font.family": family, "axes.unicode_minus": False, "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    return family


def load_evidence():
    selection = json.loads((HERE / SELECTION_FILE).read_text(encoding="utf-8"))
    frozen = [selection["low_delta"], selection["high_delta"]]
    assert [r["event_id"] for r in frozen] == EVENTS and selection["fixed_block_id"] == BLOCK
    src = pd.read_csv(HERE / "BACKGROUND_EXPLANATORY_CASES.csv.gz", low_memory=False)
    src = src.loc[src.case_selection.eq(SELECTION_KIND)].set_index("event_id", verify_integrity=True).loc[EVENTS]
    assert set(src.block_id) == {BLOCK} and set(src.image) == {CODE}
    assert src.X_workers.nunique() == src.Z_workers.nunique() == 1
    assert src.D_class_signature.nunique() == 1
    assert src.D_workers.nunique() == 2 and src.n.nunique() == src.m.nunique() == 1
    for fixed in frozen:
        row = src.loc[fixed["event_id"]]
        for field in ["A_team_key", "C_team_key", "D_workers", "X_workers", "Z_workers", "background_id", "reference_id", "reference_version"]:
            assert fixed[field] == row[field], "Frozen illustrative identity changed: " + field
        for field in ["Q_A", "Q_C", "dQ"]:
            assert abs(fixed[field] - row[field]) < 1e-10
    pools = json.loads(gzip.decompress((TASK / "supplement/inputs/SELECTED_POOLS.json.gz").read_bytes()))["images"]
    pool = next(p for p in pools if p["pool_id"] == src.pool_id.iloc[0])
    scalars = pd.read_csv(TASK / "supplement/endpoints/ENDPOINT_SCALARS.csv.gz", low_memory=False).set_index("team_key", verify_integrity=True)
    geometry = pd.read_csv(TASK / "supplement/endpoints/ENDPOINT_GEOMETRY.csv.gz", low_memory=False).set_index("team_key", verify_integrity=True)
    figures, checks = [], []
    for event, row in src.iterrows():
        arms = {}
        D, X, Z = [set(row[c + "_workers"].split("|")) for c in ["D", "X", "Z"]]
        assert not (D & X or D & Z or X & Z)
        for arm, members in [("A", D | X), ("C", D | Z)]:
            key = row[arm + "_team_key"]
            end, geo = scalars.loc[key], geometry.loc[key]
            assert set(end.member_workers.split("|")) == set(geo.member_workers.split("|")) == members
            assert end.reference_id == geo.reference_id == row.reference_id == pool["reference"]["target_id"]
            assert end.reference_version == geo.reference_version == row.reference_version
            assert abs(end.B8L2 - row[arm + "_B8L2"]) < 1e-10
            g = json.loads(geo.geometry_json)
            assert g["geometry_status"] == "ok" and len(g["points"]) // 2 == int(end.nodes)
            arms[arm] = dict(team_key=key, workers=sorted(members), geometry=g, metrics=end.to_dict())
            checks.append(dict(event_id=event, arm=arm, team_key=key, member_reference_score_geometry_binding="passed"))
        figures.append(dict(event_id=event, row=row.to_dict(), arms=arms))
    return figures, pool, checks


def plot(photo_path, receipt, cases, pool, family):
    photo = Image.open(photo_path)
    ref = pool["reference"]["points_1024x512"]
    floor_ref = np.asarray(pool["reference"]["floor_xz_h"])
    floors = [floor_ref] + [np.asarray(c["arms"][arm]["geometry"]["footprint"]) for c in cases for arm in ["A", "C"]]
    pts = np.concatenate(floors)
    xlim = [pts[:, 0].min() - .35, pts[:, 0].max() + .35]
    ylim = [pts[:, 1].min() - .35, pts[:, 1].max() + .35]
    fig = plt.figure(figsize=(16, 18.4))
    grid = fig.add_gridspec(4, 2, height_ratios=[.88, 1, 1, 1.12], hspace=.28, wspace=.12)
    first = cases[0]["row"]
    stable = SELECTION_KIND == "smallest_observed_background_range"
    title = "同一换人块、同一背景类别配额，也存在几乎不变的背景对照" if stable else "同一换人块、同一背景类别配额，具体背景成员可改变结果"
    fig.suptitle(title, x=.035, y=.987, ha="left", fontsize=19, weight="bold")
    fig.text(.035, .958, f"{CODE} · 当前DSTRUCT {first['direction'].replace('_to_', '→')} · n={int(first['n'])}，m={int(first['m'])}（{100*first['m']/first['n']:.0f}%） · 原目标／同一参考 · 自动版保存结果", fontsize=12, color="#45556a")
    ax = fig.add_subplot(grid[0, 0])
    ax.imshow(photo, extent=[0, 1024, 512, 0])
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("原图（Release原PNG字节保留）", loc="left", fontsize=12)
    ax = fig.add_subplot(grid[0, 1]); ax.axis("off")
    dcomposition = "＋".join(f"{int(first['D_current_' + c])}名{c}" for c in ['C1','C2','C3'] if first['D_current_' + c] > 0)
    source_class, target_class = first['direction'].split('_to_')
    lines = [
        (f"完全相同的换出块 X：{int(first['m'])}名{source_class}", "#2177a6", 12),
        (first["X_workers"].replace("|", "  "), "#263749", 10),
        (f"完全相同的换入块 Z：{int(first['m'])}名{target_class}", "#d36b2c", 12),
        (first["Z_workers"].replace("|", "  "), "#263749", 10),
        (f"两组D均为{dcomposition}；未知标签{int(first['D_current_unknown'])}", "#263749", 12),
        ("D1：" + cases[0]["row"]["D_workers"].replace("|", "  "), "#263749", 10),
        ("D2：" + cases[1]["row"]["D_workers"].replace("|", "  "), "#263749", 10),
        ("每个AC对内部D完全相同；两对之间只改变D成员。", "#263749", 10),
        ("四端均可评、自然连接；不新增融合、不修点、不强制连接。", "#45556a", 10),
        ("本例记录劳动跨来源，不报告合法ΔT。", "#45556a", 10),
    ]
    y = 1.
    for txt, color, size in lines:
        ax.text(0, y, txt, va="top", color=color, fontsize=size)
        y -= .095
    handles = [Line2D([0], [0], color=COLORS["R"], ls="--", lw=1.8, label="GT参考"),
               Line2D([0], [0], color=COLORS["A"], lw=2.2, label="A=D∪X"),
               Line2D([0], [0], color=COLORS["C"], lw=2.2, label="C=D∪Z")]
    for i, case in enumerate(cases):
        row = case["row"]
        for j, arm in enumerate(["A", "C"]):
            end = case["arms"][arm]
            m = end["metrics"]
            ax = fig.add_subplot(grid[i + 1, j])
            ax.imshow(photo, extent=[0, 1024, 512, 0])
            erp(ax, ref, COLORS["R"], "--", 1.25)
            erp(ax, end["geometry"]["points"], COLORS[arm], lw=1.8)
            p = np.asarray(end["geometry"]["points"])
            ax.scatter(p[:, 0], p[:, 1], s=13, color=COLORS[arm], edgecolors="white", linewidths=.6, zorder=4)
            ax.set_xlim(0, 1024); ax.set_ylim(512, 0)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"背景D{i+1} · {arm}  |  Q={m['B8L2']:.3f}  ·  {int(m['nodes'])}节点", loc="left", fontsize=12, color=COLORS[arm], weight="bold", pad=8)
            ax.text(0, -.055, f"3D IoU {m['IoU3D100']:.3f}%  ·  底面IoU {m['iou_2d']:.4f}  ·  方向误差 {m['dir']:.3f}°  ·  底边误差 {m['S_bottom_deg']:.3f}°", transform=ax.transAxes, va="top", fontsize=9.4, color="#263749")
        ax = fig.add_subplot(grid[3, i])
        for floor, color, label, ls in [(floor_ref, COLORS["R"], "GT参考", "--")] + [(np.asarray(case["arms"][arm]["geometry"]["footprint"]), COLORS[arm], arm, "-") for arm in ["A", "C"]]:
            closed = np.vstack([floor, floor[0]])
            ax.plot(closed[:, 0], closed[:, 1], color=color, lw=2.0, ls=ls, label=label)
            ax.scatter(floor[:, 0], floor[:, 1], color=color, s=22)
        ax.scatter([0], [0], marker="^", s=35, color="#556575")
        ax.annotate("相机", (0, 0), xytext=(6, 5), textcoords="offset points", fontsize=9)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(xlim); ax.set_ylim(ylim)
        ax.grid(alpha=.2); ax.set_axisbelow(True)
        ax.set_xlabel("x / 相机高度h"); ax.set_ylabel("z / 相机高度h")
        ax.set_title(f"D{i+1} 底面对照：ΔQ={row['dQ']:+.3f}；节点 {int(row['A_nodes'])}→{int(row['C_nodes'])}", loc="left", fontsize=12, weight="bold")
        ax.legend(handles=handles, loc="lower left", ncol=3, fontsize=9, frameon=True, framealpha=.9)
        ax.text(0, -.20, f"Δ3D IoU {row['delta_IoU3D100']:+.3f}个百分点  ·  Δ方向误差 {row['delta_dir']:+.3f}°\nΔ底边误差 {row['delta_S_bottom_deg']:+.3f}°  ·  参考节点召回 {row['A_ref_node_recall_9']:.3f}→{row['C_ref_node_recall_9']:.3f}", transform=ax.transAxes, fontsize=9.6, va="top", color="#263749", linespacing=1.5)
    if stable:
        note = f"说明：这是已有可比较块中ΔQ背景跨度最小的解释实例，不代表所有背景均稳定。D1、D2的ΔQ分别为{cases[0]['row']['dQ']:+.6f}、{cases[1]['row']['dQ']:+.6f}；\n两者仅相差{cases[1]['row']['dQ']-cases[0]['row']['dQ']:.6f}Q。该例与大幅变化例并列，说明背景敏感性取决于具体图片、成员和融合状态。"
    else:
        note = "说明：这是已计算结果中按最大背景跨度选出的解释实例，不代表典型效应大小。同类配额相同仍不足以确定具体团队的输出；\nD1的6节点几何变化较小但方向误差增大；D2的A缺少一个参考结构转折，换入后恢复6节点，范围和方向同时改善。"
    fig.text(.035, .045, note, fontsize=10.5, color="#3b4e63", linespacing=1.5)
    fig.text(.035, .014, f"原图：quality-original-images-20261015 / {receipt['archive']} / {receipt['bytes']}字节 / CRC32 {receipt['zip_crc32']}\n完整URL、SHA256、四端身份与指标见同目录receipt/JSON；仅绘制冻结点与连线，原图文件保持2048×1024且字节未改。", fontsize=9, color="#536577")
    fig.subplots_adjust(left=.04, right=.97, top=.927, bottom=.125)
    for ext in ["png", "svg"]:
        path = HERE / (OUTPUT_STEM + "." + ext)
        buffer = io.BytesIO()
        fig.savefig(buffer, format=ext, dpi=170, bbox_inches="tight", facecolor="white")
        path.write_bytes(buffer.getvalue())
    plt.close(fig)


def main():
    global CODE, EVENTS, BLOCK, SELECTION_FILE, SELECTION_KIND, OUTPUT_STEM, RECEIPT_STEM
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=os.environ.get("HOHONET_CJK_FONT"))
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--fetch-image", choices=["q9vSo1VnCiC-30", "e9zR4mvMWw7-15", "yqstnuAEVhm-27"])
    parser.add_argument("--case", choices=["large_range", "stable"], default="large_range")
    args = parser.parse_args()
    if args.case == "stable":
        CODE = "e9zR4mvMWw7-15"
        EVENTS = ["ACG_62799995a93d15315a52700f", "ACG_12ee3f7179528ccbbf7d9539"]
        BLOCK = "ACG_BLOCK_ee94b668f26aeeb8580c"
        SELECTION_FILE = "ILLUSTRATIVE_STABLE_FIXED_XZ_CASE.json"
        SELECTION_KIND = "smallest_observed_background_range"
        OUTPUT_STEM = "FIXED_XZ_STABLE_BACKGROUND"
        RECEIPT_STEM = "STABLE_FIXED_XZ"
    photo, receipt = fetch_original(args.fetch_image or CODE)
    if args.fetch_only or args.fetch_image:
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
        return
    font = set_font(args.font)
    cases, pool, checks = load_evidence()
    plot(photo, receipt, cases, pool, font)
    values = []
    metrics = ["B8L2", "D10", "IoU3D100", "iou_2d", "nodes", "fusion_turn_n", "fusion_short_turn_edges", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension", "ref_node_recall_9", "ref_edge_recall_9"]
    for i, case in enumerate(cases):
        for arm in ["A", "C"]:
            end = case["arms"][arm]
            values.append(dict(background="D" + str(i + 1), event_id=case["event_id"], arm=arm, team_key=end["team_key"],
                               D_workers=case["row"]["D_workers"], X_workers=case["row"]["X_workers"], Z_workers=case["row"]["Z_workers"],
                               members="|".join(end["workers"]), **{m: end["metrics"].get(m) for m in metrics}))
    pd.DataFrame(values).to_csv(HERE / (RECEIPT_STEM + "_FOUR_ENDPOINT_METRICS.csv"), index=False)
    evidence = dict(image=CODE, block_id=BLOCK, reference=pool["reference"], cases=cases, original=receipt,
                    selection=SELECTION_KIND + "; not representative effect size",
                    new_fusions=0, new_team_selections=0, new_scores=0)
    (HERE / (RECEIPT_STEM + "_RENDER_EVIDENCE.json.gz")).write_bytes(gzip.compress(json.dumps(evidence, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)).encode(), mtime=0))
    original_index = "ORIGINAL_IMAGE_INDEX.csv" if CODE == "q9vSo1VnCiC-30" else CODE + "_ORIGINAL_IMAGE_INDEX.csv"
    inputs = [HERE / SELECTION_FILE, HERE / "BACKGROUND_EXPLANATORY_CASES.csv.gz", TASK / "supplement/inputs/SELECTED_POOLS.json.gz", TASK / "supplement/endpoints/ENDPOINT_SCALARS.csv.gz", TASK / "supplement/endpoints/ENDPOINT_GEOMETRY.csv.gz", HERE / "source" / original_index]
    write_json(HERE / (RECEIPT_STEM + "_FIGURE_RECEIPT.json"), dict(status="generated", event_ids=EVENTS, block_id=BLOCK, endpoint_bindings=checks,
               input_sources=[dict(path=str(p.relative_to(REPO)), sha256=sha(p)) for p in inputs], original_sha256=receipt["sha256"], original_crc32=receipt["zip_crc32"],
               font_family=font, figure=OUTPUT_STEM + ".png", new_fusions=0, new_scores=0, new_team_selections=0,
               frozen_analysis_or_mechanism_files_modified=False))
    print("fixed-XZ four-endpoint figure rendered", flush=True)


if __name__ == "__main__":
    main()
