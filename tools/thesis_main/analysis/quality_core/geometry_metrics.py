"""Geometry metric boundary.

Owns the future split for diagnostic IoU, RMSE, boundary RMSE, pointwise RMSE,
layout 2D/3D IoU, depth metrics, and pairing/coverage gates.

These metrics are analysis diagnostics, not admission or routing decisions.
"""

BOUNDARY = "geometry_metrics"
