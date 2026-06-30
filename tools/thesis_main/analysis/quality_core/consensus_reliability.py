"""Consensus and reliability-input boundary.

Owns the future split for scope vote aggregation, mixed/unknown-scope exclusion,
consensus medoids, leave-one-out consensus, and per-worker reliability inputs.

This module does not freeze formal C1/C2 worker statistics.
"""

BOUNDARY = "consensus_reliability"
