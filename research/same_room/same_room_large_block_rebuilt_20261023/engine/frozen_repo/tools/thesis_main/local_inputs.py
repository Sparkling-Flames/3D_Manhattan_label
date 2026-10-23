"""Explicit local inputs and pinned repository receipts; never search user folders."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = Path(__file__).with_name('local_input_archives.json')


def require_file(path):
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise FileNotFoundError(
            f'Required input missing: {path}. Place the verified original here or configure '
            'HOHONET_SOURCE_ZIP / HOHONET_REVIEW_INPUT_DIR explicitly. '
            'No Downloads fallback is attempted; no files have been migrated.')
    return path


def source_zip(explicit=None):
    """Explicit argument > environment > repository data/external/label_data.zip."""
    selected = explicit if explicit is not None else os.environ.get('HOHONET_SOURCE_ZIP')
    return require_file(selected if selected is not None else 'data/external/label_data.zip')


def review_input(name, explicit=None):
    """Use the pinned original receipt; explicit inputs never fall back to it."""
    if Path(name).name != name:
        raise ValueError('Expected an input filename, not a directory')
    if explicit is not None:
        return require_file(explicit)
    directory = os.environ.get('HOHONET_REVIEW_INPUT_DIR')
    if directory is not None:
        return require_file(Path(directory) / name)
    archives = json.loads(ARCHIVES.read_text(encoding='utf-8'))
    if name not in archives:
        return require_file(Path('inputs/local_reviews') / name)
    record = archives[name]
    path = require_file(record['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError(f'Archived input SHA256 mismatch: {path}; refusing a different version')
    return path
