"""Run the seven exact source test functions against AST-extracted exact audited functions.
This is not a full repository import/integration test or 137-image reproduction.
"""
import ast, json, pathlib, runpy, pytest
p=pathlib.Path(__file__).parent
x=runpy.run_path(str(p/'check_partition_ties.py'))
ns=x['ns'];ns['pytest']=pytest;ns['json']=json
tree=ast.parse((p/'tests/test_global_pair_consensus_20261004.py').read_text())
tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
exec(compile(tree,str(p/'tests/test_global_pair_consensus_20261004.py'),'exec'),ns)
n=0
for name,fn in list(ns.items()):
    if name.startswith('test_'):
        fn();n+=1;print('PASS',name)
assert n==7
print('PASS: seven source tests; exact function extraction harness, not full repository integration')
