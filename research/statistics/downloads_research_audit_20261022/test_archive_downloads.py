from pathlib import PurePosixPath
import gzip
import pytest
from research.statistics.downloads_research_audit_20261022.archive_downloads import safe_member, historical_candidate, privacy_flags

def test_zip_paths_cannot_escape():
    for name in ('../outside.py','/absolute.py','C:/outside.py','a/../../outside'):
        with pytest.raises(ValueError):
            safe_member(name)
    assert safe_member('研究/code.py') == PurePosixPath('研究/code.py')

def test_source_selection_excludes_repo_and_raw_assets():
    assert historical_candidate('source/model_config.json',100)
    assert historical_candidate('study/reproduce.py',300)
    assert not historical_candidate('repo_main_20261019/tool.py',300)
    assert not historical_candidate('raw/export.json',100)
    assert not historical_candidate('model_config.json',200000)

def test_compressed_private_fields_stay_local():
    raw=b'{"source_account_id":"person"}\n'
    assert 'direct_identity_field' in privacy_flags(gzip.compress(raw),'.gz')
    assert not privacy_flags(b'{"worker_id":"W100","B8L2":80}', '.json')

def test_numpy_matrix_operator_is_not_an_email():
    assert not privacy_flags(b'import numpy as np\nx = a@np.array([1])\n', '.py')
def test_missing_core_source_stops_before_ledger_writes():
    from pathlib import Path
    from research.statistics.downloads_research_audit_20261022.archive_downloads import main
    with pytest.raises(FileNotFoundError, match='ledgers preserved'):
        main(Path.cwd(), Path.cwd()/'source_not_present_for_boundary_test')