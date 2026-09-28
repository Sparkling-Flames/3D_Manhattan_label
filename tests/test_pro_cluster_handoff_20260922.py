from pathlib import Path
import zipfile

import pytest

from tools.thesis_main.analysis.pro_cluster_handoff_20260922 import prepare, unpack, RECEIVED


def test_prepare_preserves_frozen_source_and_rejects_overwrite_and_escape(tmp_path):
    base, extra = tmp_path / 'base.zip', tmp_path / 'extra.zip'
    for path, content in [(base, 'old'), (extra, 'new')]:
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('version.txt', content)
    target = tmp_path / 'research'
    prepare(target, base, extra)
    assert (target / 'version.txt').read_text() == 'new'
    assert (target / RECEIVED / 'local_recompute/source_work/version.txt').read_text() == 'old'
    with pytest.raises(FileExistsError):
        prepare(target, base, extra)
    with zipfile.ZipFile(extra, 'w') as z:
        z.writestr('../escape.txt', 'bad')
    with pytest.raises(ValueError):
        unpack(extra, tmp_path / 'other')
    assert not (tmp_path / 'escape.txt').exists()
