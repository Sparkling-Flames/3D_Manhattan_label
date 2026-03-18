# Appendix A Operator Freeze Note v1

This note freezes the XML `model_issue` aliases against the current C-line operator families and the current bundle status.
It is appendix-facing and auditable, but thesis-facing completeness remains partial.

## 1. XML alias to operator family

| XML alias | Operator family | Current bundle status | Thesis-facing role |
| --- | --- | --- | --- |
| `acceptable` | `acceptable` | `appendix_only` | `normal_control` |
| `overextend_adjacent` | `overextend_adjacent` | `realized` | `misleading_trap_default_family` |
| `underextend` | `underextend` | `reject` | `misleading_trap_extension_family_not_required` |
| `over_parsing` | `over_parsing` | `realized` | `misleading_trap_default_family` |
| `corner_drift` | `corner_drift` | `realized` | `misleading_trap_default_family` |
| `corner_duplicate` | `corner_duplicate` | `realized` | `misleading_trap_default_family` |
| `topology_failure` | `topology_failure` | `planned` | `misleading_trap_extension_family_not_required` |
| `fail` | `fail` | `planned` | `misleading_trap_priority_overflow_family` |

## 2. Current bundle status

- Realized families: `overextend_adjacent`, `over_parsing`, `corner_drift`, `corner_duplicate`.
- Reject family: `underextend` remains partial because the `medium + 4-corner + transform_degenerate` subedge is still open for manual resolution.
- Planned families: `topology_failure`, `fail` remain frozen in the operator/appendix layer but are not materialized in the current bundle.
- Appendix-only family: `acceptable` is frozen in the alias/operator chain, but the current bundle does not contain normal-control rows.

## 3. What the paper can and cannot claim now

- Can write: XML `model_issue` alias to C-line operator family mapping is frozen and auditable.
- Can write: the current semi trap system has reproducible operator materialization capability.
- Cannot write: C-line is complete.
- Cannot write: Appendix A is fully closed.
- Cannot write: the current bundle already satisfies the thesis-facing `PreScreen_semi ~= 18` target.

Appendix A alias/operator freeze is auditable, but thesis-facing completeness remains partial.
