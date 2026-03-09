import os
import argparse
import torch


def summarize_state_dict(sd):
    total_params = 0
    for k, v in sd.items():
        if hasattr(v, 'numel'):
            total_params += v.numel()
    return total_params


def main():
    parser = argparse.ArgumentParser(description='Convert training checkpoint (with optimizer/scheduler) to pure model state_dict.')
    parser.add_argument('--src', required=True, help='源 checkpoint 路径，如 ckpt/.../ep350.pth')
    parser.add_argument('--dst', help='输出路径，默认自动生成 *_eval.pth')
    args = parser.parse_args()

    if not os.path.isfile(args.src):
        raise FileNotFoundError(f'src not found: {args.src}')

    raw = torch.load(args.src, map_location='cpu')

    if 'net' in raw and isinstance(raw['net'], dict):
        sd = raw['net']
        reason = '提取 raw["net"]'
    elif 'state_dict' in raw and isinstance(raw['state_dict'], dict):
        sd = raw['state_dict']
        reason = '提取 raw["state_dict"]'
    elif isinstance(raw, dict):
        # 可能已经是纯 state_dict (键名形如 backbone.conv1.weight 等)
        # 做一个简单启发式判断：若有至少一个含 .weight 的键
        if any(k.endswith('.weight') for k in raw.keys()):
            sd = raw
            reason = '原文件已是纯 state_dict'
        else:
            raise ValueError('无法识别的 checkpoint 格式，需要手动检查其键。')
    else:
        raise ValueError('未知 checkpoint 内容类型。')

    dst = args.dst
    if dst is None:
        root, ext = os.path.splitext(args.src)
        dst = root + '_eval' + ext

    torch.save(sd, dst)
    print(f'转换完成: {dst}\n来源: {args.src}\n方式: {reason}\n参数总数: {summarize_state_dict(sd)}')


if __name__ == '__main__':
    main()
