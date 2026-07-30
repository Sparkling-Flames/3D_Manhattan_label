"""Render and semantically check the human references to the Paper A contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, PROJECT_ROOT, sha256_file

NORMATIVE_REFERENCES = (
    PROJECT_ROOT / "docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md",
    PROJECT_ROOT / "docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md",
    PROJECT_ROOT / "docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md",
)

FORBIDDEN_NORMATIVE_PATTERNS = (
    "Paper_A_新版完整论文提纲_vFinal_Draft.md` 为设计真源",
    "S_Global(u) = LCB(Q_u_GT_task_adjusted)",
    "global_lcb",
    "global_rank_LCB",
    "normalized_cluster_margin",
    "R_u_LOO_compatible",
    "R_LOO_FREEZE_STATUS",
)


def render(contract_path: Path = METHOD_CONTRACT) -> str:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    digest = sha256_file(contract_path)
    peer = data["peer"]
    measurement = data["measurement_status"]
    launch = data["c2b_launch"]
    return f"""# Paper A 当前方法合同（自动生成）

> 本文档由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 自动生成，不得手工定义规范性方法字段。

- 合同版本：`{data['contract_version']}`
- JSON SHA-256：`{digest}`
- Formal launch 默认：`{str(data['formal_launch_default']).lower()}`

## 冻结方法

- C2 候选：`D8, D10, D12`；C2-A-RP 每人最多 `4` 张。
- 基础工人轴：`Q_GT, R_peer, F_struct`；LOO 只作可用时的 tie-break/sensitivity。
- R_peer：少于 `{peer['weak_descriptive_min']}` 个 task 为不足，`3-4` 为描述性，至少 `{peer['formal_estimated_min']}` 个 task 才是正式 estimated。
- Q_GT/F_struct：support 为 `1-2` 时仅 `weak_descriptive`，至少 `3` 且 estimator status 为 `estimated` 才是正式 estimated。
- C2-B roster 只消费 `worker_profile_v2.c2_risk_model_eligible`。
- Strong Global：`S_G=z(Q_GT_EB)`；peer/LOO 仅在当前并列组全员可评价时使用，否则整层跳过，最后使用 frozen random。
- 非唯一 complete-link partition 的主分析状态为 `not_evaluable`，并保存全部候选 partition。
- rolling enrollment 必须绑定 `calibration_enrollment_registry.csv`；主画像为 pooled，同时必须生成 original-only sensitivity。
- 规划入口：`{launch['planning_entrypoint']}`；最终构建入口：`{launch['final_build_entrypoint']}`。规划入口不自动构建启动包。
- 本轮只允许生成 C2-B 启动包；不自动导入 Label Studio，Stage 3/T1/V1 保持关闭。

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
    stale: list[str] = []
    conflicts: list[str] = []
    for path in NORMATIVE_REFERENCES:
        if not path.is_file():
            stale.append(f"missing:{path}")
            continue
        content = path.read_text(encoding="utf-8")
        if version not in content or digest not in content:
            stale.append(str(path))
        conflicts.extend(f"{path}:{pattern}" for pattern in FORBIDDEN_NORMATIVE_PATTERNS if pattern in content)
    if stale:
        raise ValueError("Paper A normative references are stale: " + ";".join(stale))
    if conflicts:
        raise ValueError("Paper A normative references contain superseded semantics: " + ";".join(conflicts))


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
