import gzip
import pandas as pd
from tools.thesis_main.analysis.reaggregate_v21_policy_frozen_20261028 import TARGET, load_module


def test_binary_atomic_save_preserves_compressed_data(tmp_path):
    module=load_module(); payload=gzip.compress(b'first\nsecond\n'*1000,mtime=0)
    path=tmp_path/'values.gz';module.atomic_bytes(path,payload)
    assert gzip.decompress(path.read_bytes())==b'first\nsecond\n'*1000


def test_sample_policy_keeps_registered_path_coverage():
    path=TARGET/'analysis_policy26/parts/B6ByNegPMKs-10__manual__2a73346a88/EXACT_PAIRED_EVENTS.csv.gz'
    events=pd.read_csv(path)
    for (_, _),group in events.groupby(['version','policy']):
        assert group.base_path_id.nunique()==16
        assert not group.duplicated(['base_path_id','k']).any()
