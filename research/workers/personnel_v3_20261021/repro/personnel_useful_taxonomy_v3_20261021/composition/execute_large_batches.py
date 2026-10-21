"""Evaluate registered m>=8 supplements after the main member census."""
from execute_registered_batches import package
from run_multin_batches import HERE,gs,run,pd,sha

def main():
    if not (HERE/'ALL_BATCHES_COMPLETE.json').exists():
        raise RuntimeError('Complete frozen main panels first; one shared endpoint is reused.')
    plan=pd.read_csv(HERE/'LARGE_BLOCK_BATCH_PLAN.csv')
    for bid in plan.batch_id:
        folder=HERE/'batches'/bid
        if not (folder/'COMPLETION.json').exists():run(bid,4)
        if not (folder/'PACKAGE.json').exists():package(bid)
    gs.save(HERE/'LARGE_BLOCK_BATCHES_COMPLETE.json',dict(status='complete',batches=len(plan),requested=int(plan.requested.sum()),new_required=int(plan.required.sum()),frozen_plan_sha256=sha(HERE/'LARGE_BLOCK_BATCH_PLAN.csv'),all_batches=[gs.read(HERE/'batches'/bid/'COMPLETION.json') for bid in plan.batch_id]))

if __name__=='__main__':main()
