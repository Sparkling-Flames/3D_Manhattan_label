"""Reject unrecorded scoring-code drift; never edit the frozen configuration."""
import hashlib
from pathlib import Path

def verify_scoring_identity(frozen,root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    actual=hashlib.sha256((root/'scripts/scoring.py').read_bytes()).hexdigest()
    expected=frozen['scoring_sha256']
    if actual!=expected:
        raise RuntimeError('Scoring source differs from the frozen study. Create a new research version instead of relabelling new scores with the old freeze.')
    return actual
