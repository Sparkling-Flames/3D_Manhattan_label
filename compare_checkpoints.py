import argparse
import os
from collections import OrderedDict

import torch


def load_state_dict(path):
    raw = torch.load(path, map_location='cpu')
    if isinstance(raw, dict):
        if 'state_dict' in raw and isinstance(raw['state_dict'], dict):
            return raw['state_dict']
        if 'net' in raw and isinstance(raw['net'], dict):
            return raw['net']
    if isinstance(raw, OrderedDict):
        return raw
    raise ValueError(f'无法从 {path} 提取 state_dict，内容结构未知。')


def tensor_stats(t):
    return dict(
        numel=t.numel(),
        mean=float(t.float().mean()),
        std=float(t.float().std()),
    )


def main():
    parser = argparse.ArgumentParser(description='比较两个 HoHoNet checkpoint 的参数差异')
    parser.add_argument('--ref', required=True, help='参考模型路径，例如官方 ep300.pth')
    parser.add_argument('--cmp', required=True, help='待比较模型路径，例如自训练 ep350_eval.pth')
    parser.add_argument('--topk', type=int, default=10, help='列出差异最大的参数个数')
    args = parser.parse_args()

    if not os.path.isfile(args.ref):
        raise FileNotFoundError(args.ref)
    if not os.path.isfile(args.cmp):
        raise FileNotFoundError(args.cmp)

    ref_sd = load_state_dict(args.ref)
    cmp_sd = load_state_dict(args.cmp)

    ref_keys = set(ref_sd.keys())
    cmp_keys = set(cmp_sd.keys())

    shared = sorted(ref_keys & cmp_keys)
    only_ref = sorted(ref_keys - cmp_keys)
    only_cmp = sorted(cmp_keys - ref_keys)

    diffs = []
    total_l2 = 0.0
    total_params = 0
    for k in shared:
        ref_t = ref_sd[k].float()
        cmp_t = cmp_sd[k].float()
        if ref_t.shape != cmp_t.shape:
            diffs.append((k, float('inf'), ref_t.shape, cmp_t.shape))
            continue
        delta = cmp_t - ref_t
        l2 = delta.pow(2).sum().item()
        mae = delta.abs().mean().item()
        diffs.append((k, mae, ref_t.shape, cmp_t.shape))
        total_l2 += l2
        total_params += ref_t.numel()

    diffs.sort(key=lambda x: x[1], reverse=True)

    print('=== 基本信息 ===')
    print(f'Shared params: {len(shared)}')
    print(f'Only in ref: {len(only_ref)}')
    print(f'Only in cmp: {len(only_cmp)}')
    print(f'Total comparable params: {total_params}')
    print(f'Total L2 distance: {total_l2:.6f}')
    if total_params > 0:
        print(f'Avg per-parameter L2: {total_l2 / total_params:.6e}')

    if only_ref:
        print('\n[Warning] 以下参数仅存在于参考模型:')
        for k in only_ref[:20]:
            print('  ', k)
        if len(only_ref) > 20:
            print('  ...')
    if only_cmp:
        print('\n[Warning] 以下参数仅存在于比较模型:')
        for k in only_cmp[:20]:
            print('  ', k)
        if len(only_cmp) > 20:
            print('  ...')

    print(f'\n=== MAE 差异前 {min(args.topk, len(diffs))} 名 ===')
    for name, mae, shape_ref, shape_cmp in diffs[:args.topk]:
        shape_info = f'{shape_ref} vs {shape_cmp}' if shape_ref != shape_cmp else str(shape_ref)
        print(f'{name}: MAE={mae:.6f}, shape={shape_info}')


if __name__ == '__main__':
    main()
