from pathlib import Path
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from tools.thesis_main.analysis import worker_cluster_sensitivity_20260921 as m


@pytest.mark.parametrize('preload_common', [False, True])
@pytest.mark.parametrize('fail_reference', [False, True])
def test_import_isolates_frozen_common(preload_common, fail_reference):
    script = textwrap.dedent('''
        import importlib.machinery
        from pathlib import Path
        import sys
        import types

        preload_common, fail_reference = sys.argv[1:]
        unrelated = types.ModuleType('common')
        if preload_common == 'True':
            sys.modules['common'] = unrelated
        before = list(sys.path)

        if fail_reference == 'True':
            original_exec = importlib.machinery.SourceFileLoader.exec_module
            def fail_replay(loader, module):
                if Path(loader.path).name == '02_replay.py':
                    raise RuntimeError('reference load failed')
                return original_exec(loader, module)
            importlib.machinery.SourceFileLoader.exec_module = fail_replay

        try:
            from tools.thesis_main.analysis import worker_cluster_sensitivity_20260921 as m
        except RuntimeError as error:
            assert fail_reference == 'True' and str(error) == 'reference load failed'
        else:
            assert fail_reference == 'False'
            assert Path(m.c.__file__) == m.PACKAGE / 'code/common.py'
            assert Path(m.ref.__file__) == m.PACKAGE / 'code/02_replay.py'
            assert m.c.SOURCE == m.SOURCE.resolve()
            assert m.c is not unrelated and m.ref.c is m.c

        assert sys.path == before
        if preload_common == 'True':
            assert sys.modules['common'] is unrelated
        else:
            assert 'common' not in sys.modules
    ''')
    result = subprocess.run(
        [sys.executable, '-c', script, str(preload_common), str(fail_reference)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('entry_point', ['main', 'joint'])
def test_run_configures_frozen_source_before_loading(monkeypatch, tmp_path, entry_point):
    calls = []

    class StopAtLoad(Exception):
        pass

    def configure(source):
        calls.append(('configure', source))

    def load():
        assert calls == [('configure', m.SOURCE)]
        calls.append(('load',))
        raise StopAtLoad

    monkeypatch.setattr(m.c, 'configure', configure)
    monkeypatch.setattr(m.c, 'load', load)
    monkeypatch.setattr(m, 'OUT', tmp_path)
    with pytest.raises(StopAtLoad):
        getattr(m, entry_point)()
    assert calls == [('configure', m.SOURCE), ('load',)]


def test_subset_and_replay_match_reference(monkeypatch):
    v = dict(image_id='x', code='x', building='b', N=8,
             ids=list('abcdefgh'), workers=list('ABCDEFGH'),
             d=np.array([[0 if i//3 == j//3 else 60 for j in range(8)] for i in range(8)]))
    sub = m.subset(v, [0, 2, 5])
    assert sub['workers'] == ['A', 'C', 'F'] and sub['d'][0, 1] == 0
    orders = [list('ABCDEFGH'), list('HGFEDCBA')]
    actual = m.replay(v, orders)
    monkeypatch.setattr(m.ref, 'EPS', [.1])
    monkeypatch.setattr(m.ref, 'TAILS', [3])
    monkeypatch.setattr(m.ref, 'PROFILES', [('uncapped', None, None), ('cap3_s20', 3, .2)])
    expected = m.ref.run((v, orders))[0]
    for row in actual:
        match = next(r for r in expected if r['method'] == row['method'] and r['profile'] == row['profile'])
        for key in ['status', 'possible_onset', 'conservative_onset', 'final_stable_probability']:
            assert row[key] == match[key]
