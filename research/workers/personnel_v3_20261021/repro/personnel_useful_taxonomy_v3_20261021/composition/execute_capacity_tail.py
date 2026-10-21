"""One sequential four-worker tail: F01 census, large blocks, pure blocks.

Start only after the complete main request universe has been exported. A wait
mode allows the queue to be registered early without competing for CPU.
"""
import argparse,json,time
from execute_registered_batches import package
from run_multin_batches import HERE,gs,run,pd,sha

def run_plan(filename,receipt_name):
    plan=pd.read_csv(HERE/filename)
    for bid in plan.batch_id:
        folder=HERE/'batches'/bid
        if not (folder/'COMPLETION.json').exists():run(bid,4)
        if not (folder/'PACKAGE.json').exists():package(bid)
        gs.save(HERE/'CAPACITY_TAIL_PROGRESS.json',dict(current_plan=filename,last_completed_batch=bid,status='running'))
    gs.save(HERE/receipt_name,dict(status='complete',batches=len(plan),requested=int(plan.requested.sum()),new_required=int(plan.required.sum()),frozen_plan_sha256=sha(HERE/filename),all_batches=[gs.read(HERE/'batches'/bid/'COMPLETION.json') for bid in plan.batch_id]))

def main(wait):
    while not (HERE/'ALL_BATCHES_COMPLETE.json').exists():
        if not wait:raise RuntimeError('Complete the registered main member census first')
        time.sleep(10)
    # Complete the tiny exact F01 census first, so policy analysis can proceed
    # while larger independent fusion batches continue in this same queue.
    for filename,receipt in [('F01_BATCH_PLAN.csv','F01_CAPACITY_BATCHES_COMPLETE.json'),('LARGE_BLOCK_BATCH_PLAN.csv','LARGE_BLOCK_BATCHES_COMPLETE.json'),('PURE_BATCH_PLAN.csv','PURE_BLOCK_BATCHES_COMPLETE.json')]:
        run_plan(filename,receipt)
    gs.save(HERE/'CAPACITY_TAIL_PROGRESS.json',dict(status='complete',plans=['F01_BATCH_PLAN.csv','LARGE_BLOCK_BATCH_PLAN.csv','PURE_BATCH_PLAN.csv']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wait-main',action='store_true');a=p.parse_args();main(a.wait_main)
