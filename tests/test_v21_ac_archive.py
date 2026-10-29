import csv
import zipfile
import pytest
from tools.thesis_main.analysis.import_v21_ac_20261030 import import_packages


def test_archive_retains_versions_and_reuses_identical_files(tmp_path):
    paths=[]
    for stage, text in [('01','old'),('07','new')]:
        path=tmp_path/f'stage{stage}.zip';paths.append(path)
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('code/main.py',text);z.writestr('data.csv','same')
    out=tmp_path/'out';r=import_packages(paths,out)
    assert r['archive_entries']==4 and r['unique_files']==3
    assert (out/'code/main.py').read_text()=='new'
    assert (out/'source_variants/stage01/code/main.py').read_text()=='old'
    assert import_packages(paths,out)==r
    (out/'data.csv').write_text('user change')
    with pytest.raises(ValueError,match='已有文件不同'):
        import_packages(paths,out)


def test_archive_rejects_path_escape(tmp_path):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('../outside.txt','bad')
    with pytest.raises(ValueError):import_packages([path],tmp_path/'out')
    assert not (tmp_path/'outside.txt').exists()
