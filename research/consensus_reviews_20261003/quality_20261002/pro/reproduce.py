"""Re-run this independent excerpt audit. Does not run the full source repository."""
from pathlib import Path
import os,subprocess,sys
B=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(B/'matplotlib_cache'))
for script in ['run_audit.py','check_results.py','compare_saved_summary.py','make_figures.py']:
    subprocess.run([sys.executable,str(B/'src'/script)],check=True,cwd=B)
