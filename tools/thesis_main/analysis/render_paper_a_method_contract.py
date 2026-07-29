"""Render/check the human-readable mirror of the normative Paper A JSON contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, PROJECT_ROOT, sha256_file

NORMATIVE_REFERENCES = (
    PROJECT_ROOT / "docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md",
    PROJECT_ROOT / "docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md",
    PROJECT_ROOT / "docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/07_C1三轨工人测量.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/10_StrongGlobal与FullIntegrated.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/11_T1条件效应.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/15_统计分析与功效.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/16_结果章节结构.tex",
)


def render(contract_path: Path = METHOD_CONTRACT) -> str:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    digest = sha256_file(contract_path)
    return f"""# Paper A 当前方法合同（自动生成）

> 本文档由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 自动生成，不得手工定义规范性方法字段。

- 合同版本：`{data['contract_version']}`
- JSON SHA-256：`{digest}`
- Formal launch 默认：`{str(data['formal_launch_default']).lower()}`

## 冻结方法

- C2 候选：`D8, D10, D12`；C2-A-RP 每人最多 `4` 张。
- 基础工人轴：`Q_GT, R_peer, F_struct`；LOO 只作用途级 tie-break/sensitivity。
- Strong Global：`S_G=z(Q_GT_EB)`；静态顺序为 `S_G -> R_peer_stable -> R_LOO_medoid -> frozen random`。
- 非唯一 complete-link partition 的主分析状态为 `not_evaluable`。
- T1 唯一重跑后任一 pair 不可评价时整图行政删失。
- V1 在线引擎只消费当前状态；批处理仅作 deterministic replay/audit。

## Rolling amendment 信息集

- C1 已部分执行，W014/W034 运营状态已知。
- final worker profile、C2 outcome、T1/V1 outcome 尚不可见。
- assignment 不得读取 C1 quality、peer、ranking、component activation 或 policy divergence。

## 机器合同

- `assignment_evidence_v2`
- `peer_worker_task_v2`
- `worker_profile_v2`
- `policy_candidate_v2`
- `geometry_cluster_v2`
"""


def check_references(contract_path: Path = METHOD_CONTRACT) -> None:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    version, digest = data["contract_version"], sha256_file(contract_path)
    stale = []
    for path in NORMATIVE_REFERENCES:
        if not path.is_file():
            stale.append(f"missing:{path}")
            continue
        content = path.read_text(encoding="utf-8")
        if version not in content or digest not in content:
            stale.append(str(path))
    if stale:
        raise ValueError("Paper A normative references are stale: " + ";".join(stale))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=METHOD_CONTRACT)
    parser.add_argument("--output", type=Path, default=METHOD_CONTRACT.with_suffix(".md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(args.contract)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit("Paper A generated method contract is stale")
        try:
            check_references(args.contract)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        return
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
