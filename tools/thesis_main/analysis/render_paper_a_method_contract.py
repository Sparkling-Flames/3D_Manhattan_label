"""Render and semantically check Paper A's single normative method contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, PROJECT_ROOT, sha256_file


NORMATIVE_REFERENCES = (
    PROJECT_ROOT / "docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md",
    PROJECT_ROOT / "docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md",
    PROJECT_ROOT / "docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md",
    PROJECT_ROOT / "docs/thesis_main/ANALYSIS_DATA_FLOW.md",
    PROJECT_ROOT / "docs/README_INDEX.md",
    PROJECT_ROOT / "docs/PROJECT_MAP_CLEAN_20260308.md",
    PROJECT_ROOT / "docs/agent/AGENT_CONTEXT_INDEX.md",
    PROJECT_ROOT / "docs/agent/playbooks/protocol_guard.md",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/main.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/07_C1三轨工人测量.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/10_StrongGlobal与FullIntegrated.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/11_T1条件效应.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/12_V1政策试验.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/15_统计分析与功效.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/16_结果章节结构.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/A3_启用门槛保守估计表.tex",
    PROJECT_ROOT / "docs/thesis_main/manuscript/overleaf_project/sections/A4_测度与统计方法速查.tex",
)
SOURCE_OUTLINE = PROJECT_ROOT / "docs/thesis_main/Paper_A_新版完整论文提纲_vFinal_Draft.md"

NORMATIVE_REFERENCES = tuple(path for path in NORMATIVE_REFERENCES if path.suffix.lower() != ".tex")
FORMAL_DOCUMENT_PATTERN = re.compile(r"(contract|protocol|sop|sap)", re.IGNORECASE)

FORBIDDEN_NORMATIVE_PATTERNS = (
    "S_Global(u) = LCB(Q_u_GT_task_adjusted)",
    "global_lcb",
    "global_rank_LCB",
    "normalized_cluster_margin",
    "normalized margin",
    "R_u_LOO_compatible",
    "R_LOO_FREEZE_STATUS",
    "global_analysis_eligible",
    "loo_analysis_eligible",
    "R_LOO_compatible",
    "Paper A current unique outline source",
    "0-3 blocks",
    "0–3 blocks",
    "maximum 6",
    "pair-level administrative censor",
    "D:/Work/HOHONET",
    "worker isolation passed",
    "CE worker visibility",
    "Label Studio UI visibility passed",
)


def _legacy_render(contract_path: Path = METHOD_CONTRACT) -> str:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    digest = sha256_file(contract_path)
    peer = data["peer"]
    enrollment = data["rolling_enrollment"]
    return f"""<!-- PAPER_A_MACHINE_STATUS: generated -->
# Paper A 当前方法合同（自动生成）

> 本文档只由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 渲染；不得手工定义规范性字段。

- 合同版本：`{data['contract_version']}`
- JSON SHA-256：`{digest}`
- 正式启动默认值：`{str(data['formal_launch_default']).lower()}`

## 画像、质量与同行

- 正式三轴唯一为 `Q_GT`、`R_peer`、`F_struct`；`R_LOO_medoid` 与 `R_LOO_strict` 仅为独立 sensitivity/tie-break 状态。
- C1-only Q_GT：`{data['q_gt_models']['c1_only']['formula']}`；C1+C2 final：`{data['q_gt_models']['c1_c2_final']['formula']}`。没有冻结的跨阶段 anchor 或等价支持结构时，stage effect 为 `{data['q_gt_models']['c1_c2_final']['not_identifiable_status']}`。
- `R_peer_task` 是 worker-task 内 pairwise similarity 中位数；`R_peer_all` 是其 task-equal 中位数；`R_peer_stable` 排除 supported-multimodal task。
- R_peer 的 support 状态：`<= {peer['insufficient_support_max']}` 为 `insufficient_support`，`{peer['weak_descriptive_min']}-{peer['weak_descriptive_max']}` 为 `weak_descriptive`，`>= {peer['formal_estimated_min']}` 才为 `estimated`。C2-B 需要 `estimated`。
- 历史同行字段不构成规范字段，也不能被正式生产者或消费者读取。

## 行级 eligibility

所有 primary estimand 先通过 `formal_assignment_eligible`；outside 永不进入 primary estimand。规范字段为：

| 用途 | 唯一字段 |
|---|---|
| GT quality | `{data['estimand_eligibility']['GT_quality']}` |
| peer | `{data['estimand_eligibility']['peer']}` |
| LOO medoid / strict | `{data['estimand_eligibility']['LOO_medoid']}` / `{data['estimand_eligibility']['LOO_strict']}` |
| structural / time | `{data['estimand_eligibility']['structural']}` / `{data['estimand_eligibility']['time']}` |
| Semi correction / predictive / routing feature | `{data['estimand_eligibility']['Semi_correction']}` |

## Global、Full 与 C2-B

- C2-B roster 只消费 `worker_profile_v2.c2_risk_model_eligible`，并要求 Q_GT、R_peer、F_struct 三轴；LOO 和 timing 不是 roster 硬门。
- Strong Global 的静态顺序是 `S_G -> R_peer_stable -> R_LOO_medoid -> frozen_random`。peer 或 LOO 仅在当前并列组全部可评价时使用，否则整层跳过；availability/capacity 只属于运行时 scheduler。
- Full 中 unsupported、family ambiguity 或 conditional support 不足只使相应局部 component 为零；超出 calibration support、profile version conflict 或 endpoint instability 才整体回退 Strong Global。

## rolling、reference、T1 与 V1

- rolling registry：`{enrollment['registry_filename']}`；主画像为 pooled，必须同时提供 original-only sensitivity。amendment 时只可见 C1 部分执行和 W014/W034 运营状态，不能读取 final profile、C2、T1/V1 outcome、quality、peer、rank、activation 或 policy divergence。
- reference registry 必须在 formal C1 Q_GT 前冻结；任何 submission 不能用其触发的 reference revision 为自身计分；Stage 3 前再冻结 final reference registry。
- T1：一个预冻结 pair 在唯一合法 rerun 后仍不可评价，则整个 image 从主要 paired estimand 行政删失；可用 pair 只作 sensitivity。
- V1：在线引擎只消费当前可见状态并追加 ledger；batch 模块只做 replay/audit。它只消费 `policy_candidate_v2.global_rank_S_G`，并校验 method contract、policy manifest、candidate roster SHA 和 profile version。层级是 severe failure、unresolved+severe、delivery-adjusted quality superiority、count/cost。
"""


def render(contract_path: Path = METHOD_CONTRACT) -> str:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    digest = sha256_file(contract_path)
    return f"""<!-- PAPER_A_MACHINE_STATUS: generated -->
# Paper A current method contract (generated)

This file is generated from `PAPER_A_METHOD_CONTRACT_CURRENT.json`; normative fields are not defined by hand.
- contract_version: `{data['contract_version']}`
- JSON SHA-256: `{digest}`
- formal_launch_default: `{str(data['formal_launch_default']).lower()}`

## Formal measurement and freeze roles

- The three formal axes are `Q_GT`, `R_peer`, and `F_struct`. `R_LOO_medoid` and `R_LOO_strict` are separate sensitivity/tie-break states.
- `C1_EVIDENCE_FROZEN` contains C1 canonical evidence, eligibility, peer evidence, structural EB, W034 sensitivity, and this method binding only.
- `FINAL_POOLED_PROFILE_FROZEN` is an independent artifact binding C1, C2-B, C2-A-RP, the final C1+C2 Q_GT model, pooled worker profile, enrollment, and this method binding.
- Stage 3 validates C1 evidence, final pooled profile, enrollment closure, and terminal-worker closure as separate roles.

## C2-B and runtime

- C2-B consumes `worker_profile_v2.c2_risk_model_eligible` and the selected design manifest.
- Batch B reuses the selected design ID, common anchors, bridge pool, task pool, and method SHA; it never infers bridge count from Batch A rows.
- Runtime mapping is a local planned/runtime audit. It does not claim Label Studio UI visibility.
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
    formal_dir = PROJECT_ROOT / "docs/thesis_main"
    status_documents = [path for path in formal_dir.iterdir() if path.is_file() and FORMAL_DOCUMENT_PATTERN.search(path.name)] + [
        PROJECT_ROOT / "docs/README_INDEX.md", PROJECT_ROOT / "docs/PROJECT_MAP_CLEAN_20260308.md",
        PROJECT_ROOT / "docs/agent/AGENT_CONTEXT_INDEX.md", PROJECT_ROOT / "docs/agent/playbooks/protocol_guard.md",
    ]
    for path in status_documents:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            try:
                status = str(json.loads(content).get("status", ""))
            except json.JSONDecodeError:
                status = ""
            if status not in {"current_normative_source", "normative", "generated", "superseded"}:
                stale.append(f"missing_machine_status:{path}")
        elif not re.search(r"PAPER_A_MACHINE_STATUS:\s*(normative|generated|superseded)\b", content):
            stale.append(f"missing_machine_status:{path}")
        if path.name == "ANALYSIS_DATA_FLOW.md" and "-->" not in "\n".join(content.splitlines()[:2]):
            stale.append(f"unclosed_machine_comment:{path}")
    if not SOURCE_OUTLINE.is_file() or "STATUS: superseded_non_normative_outline" not in SOURCE_OUTLINE.read_text(encoding="utf-8"):
        stale.append(f"source_outline_not_superseded:{SOURCE_OUTLINE}")
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
    args.output.write_bytes(expected.encode("utf-8"))


if __name__ == "__main__":
    main()
