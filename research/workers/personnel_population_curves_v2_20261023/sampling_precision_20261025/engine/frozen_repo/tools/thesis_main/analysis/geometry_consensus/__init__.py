"""Candidate-only, seam-aware geometry consensus helpers for Paper A vFinal."""

from .representation import normalize_geometry
from .pairwise import pairwise_similarity

__all__ = ["normalize_geometry", "pairwise_similarity"]
