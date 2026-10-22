"""Resume completed-condition response evaluation; never consumes partial batches."""
from pathlib import Path
import argparse,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('condition',choices=['semi','manual']);a=p.parse_args()
    ids=[1,2,3,10,11] if a.condition=='semi' else [4,5,6,7,8,9,12,13,14,15,16,17]
    files=[HERE.parent/'composition/batches'/f'batch_{i:03d}'/'COMPLETION.json' for i in ids]
    print(json.dumps({'condition':a.condition,'requires_batches':ids}),flush=True)
    while not all(f.is_file() and json.loads(f.read_text()).get('status')=='complete' for f in files):time.sleep(5)
    subprocess.run([sys.executable,str(HERE/'analyze_responses.py'),'derive'],check=True)
    for d in ['geometry_common','qt_common']:
        subprocess.run([sys.executable,str(HERE/'analyze_responses.py'),'run','--condition',a.condition,'--domain',d],check=True)
