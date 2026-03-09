# tools/benchmark_cost.py
import os
import sys
import argparse
import importlib
import time
import torch
import numpy as np
from thop import profile

# 将项目根目录添加到 sys.path，以便能找到 lib 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.config import config, update_config

def benchmark():
    # 1. 模拟参数 (直接硬编码你常用的配置，方便运行)
    # 注意：这里假设你用的是 mp3d_layout 的配置，如果不是请修改
    args_cfg = "config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml"
    
    # 更新配置
    # opts 必须是一个列表，即使是空的，不能是 None
    update_config(config, argparse.Namespace(cfg=args_cfg, opts=[]))
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🚀 Running benchmark on device: {device}")
    if device == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")

    # 2. 初始化模型
    print("📦 Loading model...")
    model_file = importlib.import_module(config.model.file)
    model_class = getattr(model_file, config.model.modelclass)
    net = model_class(**config.model.kwargs).to(device)
    net.eval()

    # 3. 准备假数据 (1张 512x1024 的图片)
    dummy_input = torch.randn(1, 3, 512, 1024).to(device)

    # --- 指标 1: 理论计算量 (FLOPs) & 参数量 (Params) ---
    print("\n📊 Calculating FLOPs & Params...")
    try:
        flops, params = profile(net, inputs=(dummy_input, ), verbose=False)
        print(f"   ► Params (参数量): {params / 1e6:.2f} M (百万)")
        print(f"   ► FLOPs (计算量):  {flops / 1e9:.2f} G (十亿次浮点运算)")
    except Exception as e:
        print(f"   Skipping FLOPs calculation: {e}")

    # --- 指标 2: 实际推理耗时 (Latency) ---
    print("\n⏱️  Measuring Inference Speed (Latency)...")
    
    # 预热 (Warmup) - 让 GPU 进入状态
    print("   Warming up GPU...")
    with torch.no_grad():
        for _ in range(10):
            _ = net(dummy_input)
    
    # 正式测试
    iterations = 50
    times = []
    print(f"   Running {iterations} iterations...")
    
    with torch.no_grad():
        for _ in range(iterations):
            # 同步 GPU 时间，确保测得准
            if device == 'cuda': torch.cuda.synchronize()
            start = time.time()
            
            # 执行推理
            _ = net(dummy_input)
            
            if device == 'cuda': torch.cuda.synchronize()
            end = time.time()
            times.append((end - start) * 1000) # 毫秒

    avg_time = np.mean(times)
    fps = 1000 / avg_time
    print(f"   ► Average Latency: {avg_time:.2f} ms/image")
    print(f"   ► Throughput:      {fps:.2f} FPS (images/second)")

    # --- 指标 3: 显存占用 (VRAM) ---
    if device == 'cuda':
        max_mem = torch.cuda.max_memory_allocated() / 1024 / 1024
        print(f"\n💾 Peak GPU Memory Usage: {max_mem:.2f} MB")

if __name__ == '__main__':
    benchmark()