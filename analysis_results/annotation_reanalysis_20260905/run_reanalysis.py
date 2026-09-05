from pathlib import Path
import subprocess,sys,os
root=Path(__file__).resolve().parent
env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1")
for script in ["inspect_inputs.py","fit_exploratory_profiles.py","extra_diagnostics.py","cross_condition_diagnostic.py","compare_grouping_methods.py"]:
    print("Running",script,flush=True)
    subprocess.run([sys.executable,str(root/script)],check=True,cwd=root,env=env)
print("Done. All analyses are retrospective/exploratory; no new human data were generated.")
