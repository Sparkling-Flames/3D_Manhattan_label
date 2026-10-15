"""Render the research-material index from research/catalog/CATALOG.json."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "research" / "catalog" / "CATALOG.json"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def validate_catalog(catalog: dict) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for item in catalog.get("materials", []):
        item_id = item.get("id")
        if not item_id or item_id in seen:
            errors.append(f"missing or duplicate material id: {item_id}")
        seen.add(item_id)
        for field in ("theme", "type", "source_path", "current_path", "adoption_status", "verification_status", "availability", "relationships"):
            if field not in item:
                errors.append(f"{item_id}: missing {field}")
        current = item.get("current_path")
        if current and not (ROOT / current).exists():
            errors.append(f"{item_id}: current path missing: {current}")
    for model in catalog.get("algorithms", []):
        if not model.get("id") or not model.get("formula"):
            errors.append(f"algorithm missing id/formula: {model}")
        for field in ("purpose", "parameters", "adoption_status", "verification_status"):
            if not model.get(field):
                errors.append(f"{model.get('id')}: missing {field}")
        for source in model.get("evidence_paths", []) + model.get("implementation_paths", []):
            if not (ROOT / source).exists():
                errors.append(f"{model.get('id')}: evidence path missing: {source}")
    for component in catalog.get("quality_components", []):
        if not all(component.get(key) for key in ("symbol", "unit", "meaning")):
            errors.append(f"quality component incomplete: {component}")
    snapshot_ids: set[str] = set()
    for snapshot in catalog.get("result_snapshots", []):
        snapshot_id = snapshot.get("id")
        if not snapshot_id or snapshot_id in snapshot_ids:
            errors.append(f"missing or duplicate snapshot id: {snapshot_id}")
        snapshot_ids.add(snapshot_id)
        for field in ("batch", "input_version", "reference_version", "eligibility_rule", "auxiliary_tags", "method_version"):
            if not snapshot.get(field):
                errors.append(f"{snapshot_id}: missing {field}")
    for snapshot in catalog.get("result_snapshots", []):
        path = snapshot.get("result_path")
        if path and not (ROOT / path).exists():
            errors.append(f"{snapshot.get('id')}: result path missing: {path}")
        for field in ("member_list_path", "source_paths", "reproduction_paths"):
            values = snapshot.get(field, [])
            if field == "member_list_path":
                values = [values] if values else []
            if not isinstance(values, list):
                errors.append(f"{snapshot.get('id')}: {field} must be a path list")
                continue
            for value in values:
                if not (ROOT / value).exists():
                    errors.append(f"{snapshot.get('id')}: {field} path missing: {value}")
        if not snapshot.get("reproduction_status"):
            errors.append(f"{snapshot.get('id')}: missing reproduction_status")
    for item in catalog.get("count_definitions", []):
        if not (ROOT / item.get("evidence", "")).exists():
            errors.append(f"{item.get('count')}: count evidence missing: {item.get('evidence')}")
    migration_sources: set[str] = set()
    migration_targets: set[str] = set()
    for item in catalog.get("migrations", []):
        source, target = item.get("source_path"), item.get("current_path")
        if not source or source in migration_sources:
            errors.append(f"missing or duplicate migration source: {source}")
        if not target or target in migration_targets:
            errors.append(f"missing or duplicate migration target: {target}")
        migration_sources.add(source)
        migration_targets.add(target)
        if target and not (ROOT / target).exists():
            errors.append(f"migration target missing: {target}")
    thread_ids: set[str] = set()
    for thread in catalog.get("threads", []):
        thread_id = thread.get("id")
        if not thread_id or thread_id in thread_ids:
            errors.append(f"missing or duplicate thread id: {thread_id}")
        thread_ids.add(thread_id)
        for evidence in thread.get("saved_evidence_paths", []):
            if not (ROOT / evidence).exists():
                errors.append(f"{thread_id}: thread evidence missing: {evidence}")
    return errors


def _link(from_path: Path, target: str, label: str | None = None) -> str:
    path = ROOT / target
    if path.is_dir() and (path / "README.md").exists():
        path = path / "README.md"
        target = path.relative_to(ROOT).as_posix()
    relative = os.path.relpath(ROOT / target, from_path.parent).replace("\\", "/")
    return f"[{label or target}]({relative})"


def _material_table(page: Path, materials: list[dict]) -> list[str]:
    lines = ["|资料|日期|采用状态|核验状态|关联|原路径（迁移前）|", "|---|---|---|---|---|---|"]
    for item in sorted(materials, key=lambda x: (x.get("date") or "", x.get("title", "")), reverse=True):
        title = item.get("title", item["id"])
        link = _link(page, item["current_path"], title) if item.get("current_path") else title
        source = item.get("source_path", "")
        if source == item.get("current_path"):
            source = "原位"
        relationships = "；".join(item.get("relationships", []))
        lines.append(
            f"|{link}|{item.get('date') or '—'}|{item.get('adoption_status', '待判断')}|"
            f"{item.get('verification_status', '未审阅')}|{relationships}|`{source}`|"
        )
    return lines


def render_topic(catalog: dict, topic: dict) -> str:
    page = ROOT / topic["page_path"]
    materials = [x for x in catalog["materials"] if x.get("theme") == topic["id"]]
    lines = [
        f"# {topic['title']}",
        "",
        topic["description"],
        "",
        "此页是导航，不替代合同、原始来源或实验包内的字段定义。采用状态与核验状态分开记录；未复验不表示无效，历史材料也不因未采用而删除。",
        "",
    ]
    for key, heading in (("current_basis", "当前依据"), ("history", "历史版本与对照"), ("source_evidence", "原始证据与来源"), ("open_questions", "未决问题"), ("reproduction", "复现入口")):
        values = topic.get(key, [])
        lines.extend([f"## {heading}", ""])
        if not values:
            lines.append("本目录未登记独立条目；请从总目录按主题检索。")
        else:
            for entry in values:
                text = entry["text"]
                if entry.get("path"):
                    text = f"{text}：{_link(page, entry['path'])}"
                lines.append(f"- {text}")
        lines.append("")
    lines.extend(["## 已登记资料", ""])
    lines.extend(_material_table(page, materials))
    lines.extend(["", f"机器目录与完整主题索引：{_link(page, 'research/catalog/INDEX.md')}。", ""])
    return "\n".join(lines)


def render_index(catalog: dict) -> str:
    page = ROOT / "research" / "catalog" / "INDEX.md"
    lines = [
        "# HOHONET 研究资料总目录",
        "",
        f"目录版本：{catalog['catalog_version']}；盘点日期：{catalog['inventory_date']}。",
        "",
        catalog["coverage_note"],
        "",
        "机器可读真源为 [CATALOG.json](CATALOG.json)。本目录只定位资料，不改变其方法、数据资格或采用状态。原路径保留在迁移映射中；原始标注、审核回执、规范合同与统一输入未迁移。",
        "",
        "## 按主题查找",
        "",
        "|主题|入口|资料数|说明|",
        "|---|---|---:|---|",
    ]
    for topic in catalog["topics"]:
        count = sum(x.get("theme") == topic["id"] for x in catalog["materials"])
        lines.append(f"|{topic['title']}|{_link(page, topic['page_path'], '打开主题入口')}|{count}|{topic['description']}|")
    lines.extend(["", "## 质量分项与单位", "", "|分项|单位|测量含义|", "|---|---|---|"])
    for component in catalog.get("quality_components", []):
        lines.append(f"|`{component['symbol']}`|{component['unit']}|{component['meaning']}|")
    lines.extend(["", "## 质量算法身份与采用地位", "", "|版本|定义|关键参数|测量目的|采用状态|版本关系|实现/证据入口|", "|---|---|---|---|---|---|---|"])
    for model in catalog["algorithms"]:
        evidence_paths = model.get("implementation_paths", []) + model.get("evidence_paths", [])
        evidence = ", ".join(_link(page, p) for p in dict.fromkeys(evidence_paths)) or "—"
        formula = model["formula"].replace("|", "\\|")
        relation = "；".join(model.get("relationships", []))
        lines.append(f"|{model['name']} (`{model['id']}`)|`{formula}`|{model.get('parameters', '—')}|{model.get('purpose', '—')}|{model['adoption_status']}|{relation}|{evidence}|")
    lines.extend(["", "## 有代表性的结果快照", "", "|快照|实际分母及用途|批次与输入|目标/参考|纳入规则与标签|方法版本|结果与成员名单|来源证据|复现入口/状态|", "|---|---|---|---|---|---|---|---|---|"])
    for snapshot in catalog["result_snapshots"]:
        sources = ", ".join(_link(page, p) for p in snapshot.get("source_paths", [])) or "—"
        reproduction = ", ".join(_link(page, p) for p in snapshot.get("reproduction_paths", [])) or "—"
        lines.append(
            f"|{snapshot['title']} (`{snapshot['id']}`)|{snapshot['population']}|{snapshot['batch']}；{snapshot['input_version']}|"
            f"{snapshot['reference_version']}|{snapshot['eligibility_rule']}；{snapshot['auxiliary_tags']}|"
            f"{snapshot['method_version']}|{_link(page, snapshot['result_path'], '结果')} / {_link(page, snapshot['member_list_path'], '成员名单')}|"
            f"{sources}|{reproduction}；{snapshot['reproduction_status']}|"
        )
    lines.extend(["", "## 结果分母的身份", "", "|计数|含义|证据|", "|---:|---|---|"])
    for item in catalog.get("count_definitions", []):
        lines.append(f"|{item['count']}|{item['meaning']}|{_link(page, item['evidence'])}|")
    lines.extend(["", "## 版本比较约定", ""])
    for note in catalog["comparison_rules"]:
        lines.append(f"- {note}")
    lines.extend(["", "## 迁移映射", "", "按原路径检索的可读表见 [MIGRATION.md](MIGRATION.md)；机器映射见 [MIGRATION_MAP.json](MIGRATION_MAP.json)。迁移只改变组织路径，不将旧结果改称新版本；未迁移的历史资料仍在原位。", ""])
    lines.extend(["## 原线程与外部来源", "", "线程摘要与可保存证据的对应关系见 [THREADS.md](THREADS.md)；摘要不冒充完整对话。", ""])
    lines.extend(["完整材料登记按主题分列于各主题入口；本页保留算法、代表结果与分母定义，避免重复生成长清单。", ""])
    return "\n".join(lines)


def render_migrations(catalog: dict) -> str:
    page = ROOT / "research" / "catalog" / "MIGRATION.md"
    lines = [
        "# 资料迁移与历史沿革索引",
        "",
        "迁移映射只说明位置变化；日期来自资料名/来源登记，不能据此判断方法优劣。源包内内容保持原样。",
        "",
        "|资料日期|迁移前|当前路径|处理|说明|",
        "|---|---|---|---|---|",
    ]
    for item in sorted(catalog.get("migrations", []), key=lambda x: (re.search(r"20\d{6}", x["source_path"]).group(0) if re.search(r"20\d{6}", x["source_path"]) else "99999999", x["source_path"])):
        current = _link(page, item["current_path"], item["current_path"])
        date = re.search(r"20\d{6}", item["source_path"])
        lines.append(f"|{date.group(0) if date else '—'}|`{item['source_path']}`|{current}|{item['action']}|{item.get('reason', '')}|")
    lines.append("")
    return "\n".join(lines)


def render_threads(catalog: dict) -> str:
    page = ROOT / "research" / "catalog" / "THREADS.md"
    lines = [
        "# 原线程与来源摘要",
        "",
        "此表只保存可核对的线程身份、最近返回摘要和仓库证据位置。它不代表导出了线程全文；未归档的对话仍需在对应应用中查看。",
        "",
        "|线程标题|线程ID/入口|检查时状态|最近返回或任务状态|仓库证据|对话归档状态|",
        "|---|---|---|---|---|---|",
    ]
    for thread in catalog.get("threads", []):
        title = thread["title"]
        link = f"[{title}]({thread['link']})" if thread.get("link") else title
        evidence = ", ".join(_link(page, p) for p in thread.get("saved_evidence_paths", [])) or "—"
        lines.append(
            f"|{link}|`{thread['id']}`|{thread.get('observed_at', '未记录日期')}：{thread['observed_status']}|"
            f"{thread['latest_return_summary']}|{evidence}|{thread['archive_status']}|"
        )
    lines.extend(["", "## 外部来源和本地独有材料", "", "|来源|登记位置|可访问性|说明|", "|---|---|---|---|"])
    for source in catalog.get("external_sources", []):
        path = source.get("source_path", "")
        link = f"[{path}]({path})" if path.startswith("https://") else f"`{path}`"
        note = source.get("distinction", source.get("repository_copy", ""))
        lines.append(f"|{source['title']}|{link}|{source['availability']}|{note}|")
    lines.append("")
    return "\n".join(lines)


def render_outputs(catalog: dict) -> dict[Path, str]:
    outputs = {
        ROOT / "research" / "catalog" / "INDEX.md": render_index(catalog),
        ROOT / "research" / "catalog" / "THREADS.md": render_threads(catalog),
        ROOT / "research" / "catalog" / "MIGRATION.md": render_migrations(catalog),
        ROOT / "research" / "catalog" / "MIGRATION_MAP.json": json.dumps({"migrations": catalog["migrations"]}, ensure_ascii=False, indent=2),
    }
    for topic in catalog["topics"]:
        outputs[ROOT / topic["page_path"]] = render_topic(catalog, topic)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write generated indexes")
    action.add_argument("--check", action="store_true", help="validate paths and generated indexes")
    args = parser.parse_args()
    catalog = load_catalog()
    errors = validate_catalog(catalog)
    if errors:
        raise SystemExit("\n".join(errors))
    outputs = render_outputs(catalog)
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content + "\n", encoding="utf-8", newline="\r\n")
    else:
        stale = [str(path.relative_to(ROOT)) for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content + "\n"]
        if stale:
            raise SystemExit("generated catalog pages are stale: " + ", ".join(stale))
    print(f"catalog valid: {len(catalog['materials'])} materials, {len(catalog['algorithms'])} algorithms, {len(catalog['result_snapshots'])} result snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
