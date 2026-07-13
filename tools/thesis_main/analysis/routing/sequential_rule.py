from __future__ import annotations

from typing import Any


RULE_VERSION = "sequential_routing_candidate_v1"

CONFIGS = {
    "low_risk": {"k_dispatch_initial": 2, "k_min_for_stop": 2, "standard_cap": 5, "escalation_cap": 7},
    "high_risk": {"k_dispatch_initial": 3, "k_min_for_stop": 3, "standard_cap": 5, "escalation_cap": 7},
    "stress": {"k_dispatch_initial": 3, "k_min_for_stop": 3, "standard_cap": 5, "escalation_cap": 7},
}


def candidate_rule_config(risk_bucket: str = "low_risk", *, k0: int | None = None, k_max: int | None = None) -> dict[str, Any]:
    config = dict(CONFIGS.get(str(risk_bucket), CONFIGS["low_risk"]))
    if k0 is not None or k_max is not None:
        if k0 is not None:
            config["k_dispatch_initial"] = int(k0)
            config["k_min_for_stop"] = int(k0)
        if k_max is not None:
            config["standard_cap"] = int(k_max)
            config["escalation_cap"] = int(k_max)
        config["legacy_compatibility_mode"] = "legacy_fixed_cap"
    else:
        config["legacy_compatibility_mode"] = "none"
    config["rule_version"] = RULE_VERSION
    config["candidate_only"] = True
    return config


def decide_candidate_action(evidence: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or candidate_rule_config()
    try:
        k = int(evidence.get("n_independent_workers") or evidence.get("k") or 0)
    except (TypeError, ValueError):
        k = 0
    min_stop = int(config["k_min_for_stop"])
    standard_cap = int(config["standard_cap"])
    escalation_cap = int(config["escalation_cap"])
    high_risk = str(evidence.get("risk_bucket", "")).lower() in {"high", "high_risk", "stress"} or str(evidence.get("support_gap_candidate", "")).lower() == "true"
    if k < min_stop:
        action = "continue_initial"
    elif high_risk and k < escalation_cap:
        action = "escalate_candidate"
    elif k < standard_cap:
        action = "stop_candidate"
    elif k < escalation_cap and high_risk:
        action = "escalate_candidate"
    else:
        action = "stop_at_cap_candidate"
    return {
        "action": action,
        "observed_k": k,
        "k_dispatch_initial": int(config["k_dispatch_initial"]),
        "k_min_for_stop": min_stop,
        "standard_cap": standard_cap,
        "escalation_cap": escalation_cap,
        "candidate_only": True,
        "routing_eligible": False,
        "interpretation_allowed": False,
    }
